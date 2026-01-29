# services/WebApp/backend.py
"""
Асинхронный backend для Mini App на aiohttp + async SQLAlchemy.

Поддерживает:
- POST /api/webapp                    -> сохранить событие Mini App в БД (+ прогреть TTL-кэш)
- GET  /api/webapp?transfer_id=...    -> получить событие по transfer_id (TTL -> DB -> TTL)
- GET  /api/links?transfer_id=...     -> как раньше
- GET  /api/links/{token}            -> как раньше

ВАЖНО:
- Код рассчитан на вашу DDL inline_webapp_events (id PK + UNIQUE transfer_id + TEXT поля).
- Для асинхронной работы с БД нужен get_async_session() в services.bot.database.storage.
  (Ниже отдельно даю пример, как должен выглядеть этот модуль.)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aiohttp import web
from sqlalchemy import text

from services.WebApp.link_builders import get_builder
from services.WebApp.schemas.link_payload import LinkBuilderRequest

# Асинхронная сессия проекта
from services.bot.database.storage import get_session  # должен быть asynccontextmanager, см. пример ниже

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -----------------------------
# TTL-хранилище токенов deeplink
# -----------------------------
class LinkTokenStore:
    """Остаётся in-memory. Если нужно переживать рестарты/мультиинстанс — аналогично событиям переносится в БД."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._storage: Dict[str, Tuple[float, dict]] = {}
        self._lock = asyncio.Lock()  # на случай конкурентных обращений в одном event loop

    async def issue_token(self, payload: dict) -> str:
        token = uuid.uuid4().hex
        expires_at = time.time() + self.ttl_seconds
        async with self._lock:
            self._storage[token] = (expires_at, payload)
        return token

    async def get_payload(self, token: str) -> dict | None:
        async with self._lock:
            record = self._storage.get(token)
            if not record:
                return None
            expires_at, payload = record
            if time.time() > expires_at:
                self._storage.pop(token, None)
                return None
            return payload


token_store = LinkTokenStore()


# -------------------------------------------------
# TTL-кэш событий Mini App + чтение из inline_webapp_events
# -------------------------------------------------
@dataclass
class WebAppEvent:
    """
    Нормализованный формат события, который возвращаем интеграции.
    Поля в БД (DDL):
      id (PK), transfer_id (UNIQUE), inline_payload_json (TEXT), inline_context_json (TEXT),
      opener_tg_user_id (BIGINT), opener_json (TEXT), raw_init_data (TEXT), created_at (DATETIME)
    """
    db_id: int
    transfer_id: str
    transfer_payload: dict
    inline_context: dict
    opener_tg_user_id: Optional[int]
    opener: dict
    raw_init_data: str
    created_at: Optional[str]  # ISO


class WebAppEventStore:
    """Read-through TTL-cache: cache -> DB -> cache."""

    def __init__(self, ttl_seconds: int = 30) -> None:
        self.ttl_seconds = ttl_seconds
        self._storage: Dict[str, Tuple[float, WebAppEvent]] = {}
        self._lock = asyncio.Lock()

    async def put(self, transfer_id: str, event: WebAppEvent) -> None:
        expires_at = time.time() + self.ttl_seconds
        async with self._lock:
            self._storage[transfer_id] = (expires_at, event)

    async def get(self, transfer_id: str) -> Optional[WebAppEvent]:
        async with self._lock:
            record = self._storage.get(transfer_id)
            if not record:
                return None
            expires_at, event = record
            if time.time() > expires_at:
                self._storage.pop(transfer_id, None)
                return None
            return event

    async def invalidate(self, transfer_id: str) -> None:
        async with self._lock:
            self._storage.pop(transfer_id, None)


event_store = WebAppEventStore(ttl_seconds=30)


def _json_loads_safe(value: Any) -> dict:
    """В DDL поля TEXT, поэтому обычно придёт str; но на всякий случай поддержим и dict."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        obj = json.loads(value)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _dt_to_iso(dt: Any) -> Optional[str]:
    if isinstance(dt, datetime):
        # created_at в MySQL без TZ. Возвращаем как UTC-like строку для интеграции.
        return dt.isoformat() + "Z"
    return None


async def save_event_to_db(payload: dict) -> None:
    """
    UPSERT в inline_webapp_events по UNIQUE(transfer_id).
    Поля opener_json/raw_init_data делаем NULL, если они пустые — это сохраняет смысл COALESCE.
    """
    transfer_id = str(payload.get("transfer_id") or "").strip()
    if not transfer_id:
        return

    inline_payload_json = json.dumps(payload.get("transfer_payload") or {}, ensure_ascii=False)
    inline_context_json = json.dumps(
        {
            "creator_tg_user_id": payload.get("inline_creator_tg_user_id"),
            "generated_at": payload.get("inline_generated_at"),
            "parsed": payload.get("inline_parsed") or {},
            "option": payload.get("inline_option") or {},
        },
        ensure_ascii=False,
    )

    opener = (payload.get("initDataUnsafe") or {}).get("user") or {}
    opener_tg_user_id = opener.get("id") if opener else None
    opener_json = json.dumps(opener, ensure_ascii=False) if opener else None

    raw_init_data = (payload.get("initData") or "").strip()
    raw_init_data = raw_init_data if raw_init_data else None

    sql = text(
        """
        INSERT INTO inline_webapp_events
            (transfer_id, inline_payload_json, inline_context_json,
             opener_tg_user_id, opener_json, raw_init_data, created_at)
        VALUES
            (:transfer_id, :inline_payload_json, :inline_context_json,
             :opener_tg_user_id, :opener_json, :raw_init_data, CURRENT_TIMESTAMP)
        ON DUPLICATE KEY UPDATE
            inline_payload_json = VALUES(inline_payload_json),
            inline_context_json = VALUES(inline_context_json),
            opener_tg_user_id  = COALESCE(VALUES(opener_tg_user_id), opener_tg_user_id),
            opener_json        = COALESCE(VALUES(opener_json), opener_json),
            raw_init_data      = COALESCE(VALUES(raw_init_data), raw_init_data),
            created_at         = created_at;
        """
    )

    params = {
        "transfer_id": transfer_id,
        "inline_payload_json": inline_payload_json,
        "inline_context_json": inline_context_json,
        "opener_tg_user_id": opener_tg_user_id,
        "opener_json": opener_json,
        "raw_init_data": raw_init_data,
    }

    try:
        async with get_session() as session:
            print('Данные записаны')
            await session.execute(sql, params)
        logger.info("WebApp API: event upsert ok transfer_id=%s", transfer_id)
    except Exception as exc:
        # Важно: ошибки БД не должны ломать фронт/миниапп
        logger.warning("WebApp API: DB write error transfer_id=%s: %s", transfer_id, exc)


async def fetch_event_from_db(transfer_id: str) -> Optional[WebAppEvent]:
    """SELECT по transfer_id (UNIQUE) из inline_webapp_events."""
    transfer_id = str(transfer_id or "").strip()
    if not transfer_id:
        return None

    sql = text(
        """
        SELECT
            id,
            transfer_id,
            inline_payload_json,
            inline_context_json,
            opener_tg_user_id,
            opener_json,
            raw_init_data,
            created_at
        FROM inline_webapp_events
        WHERE transfer_id = :transfer_id
        LIMIT 1
        """
    )

    try:
        async with get_session() as session:
            row = (await session.execute(sql, {"transfer_id": transfer_id})).mappings().first()
    except Exception as exc:
        logger.warning("WebApp API: DB read error transfer_id=%s: %s", transfer_id, exc)
        return None

    if not row:
        return None

    transfer_payload = _json_loads_safe(row.get("inline_payload_json"))
    inline_context = _json_loads_safe(row.get("inline_context_json"))
    opener = _json_loads_safe(row.get("opener_json"))

    return WebAppEvent(
        db_id=int(row["id"]),
        transfer_id=str(row["transfer_id"]),
        transfer_payload=transfer_payload,
        inline_context=inline_context,
        opener_tg_user_id=int(row["opener_tg_user_id"]) if row.get("opener_tg_user_id") is not None else None,
        opener=opener,
        raw_init_data=str(row.get("raw_init_data") or ""),
        created_at=_dt_to_iso(row.get("created_at")),
    )


def _build_event_from_post(payload: dict) -> Optional[WebAppEvent]:
    """
    Нормализуем входящее POST-событие в формат WebAppEvent.
    db_id неизвестен (событие может ещё не быть записано), поэтому ставим 0.
    """
    transfer_id = str(payload.get("transfer_id") or "").strip()
    if not transfer_id:
        return None

    transfer_payload = payload.get("transfer_payload") or {}
    inline_context = {
        "creator_tg_user_id": payload.get("inline_creator_tg_user_id"),
        "generated_at": payload.get("inline_generated_at"),
        "parsed": payload.get("inline_parsed") or {},
        "option": payload.get("inline_option") or {},
    }

    opener = (payload.get("initDataUnsafe") or {}).get("user") or {}
    opener_tg_user_id = opener.get("id") if opener else None

    return WebAppEvent(
        db_id=0,
        transfer_id=transfer_id,
        transfer_payload=transfer_payload if isinstance(transfer_payload, dict) else {},
        inline_context=inline_context,
        opener_tg_user_id=opener_tg_user_id,
        opener=opener if isinstance(opener, dict) else {},
        raw_init_data=str(payload.get("initData") or ""),
        created_at=datetime.utcnow().isoformat() + "Z",
    )


# ---------------------------------------------
# Логика генерации банковских ссылок (как раньше)
# ---------------------------------------------
def base64_decode(value: str) -> str:
    import base64
    return base64.b64decode(value.encode("utf-8")).decode("utf-8")


def decode_transfer_payload(start_param: str) -> dict:
    if not start_param:
        return {}
    try:
        normalized = start_param.replace("-", "+").replace("_", "/")
        padding = "=" * ((4 - len(normalized) % 4) % 4)
        decoded = json.loads(base64_decode(normalized + padding))
        return decoded if isinstance(decoded, dict) else {}
    except Exception:
        return {}


def detect_identifier(transfer_id: str, payload: dict) -> Tuple[str, str]:
    option = payload.get("option") or {}
    if "phone" in option:
        return "phone", str(option.get("phone"))
    if "card" in option:
        return "card", str(option.get("card"))

    digits_only = "".join(ch for ch in transfer_id if ch.isdigit() or ch == "+")
    if 10 <= len(digits_only) <= 15:
        return "phone", digits_only
    if len(digits_only) >= 16:
        return "card", digits_only
    raise ValueError("Невозможно определить тип идентификатора")


def load_banks_config() -> List[dict]:
    config_path = Path(__file__).parent / "config" / "banks.json"
    with config_path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


async def build_links_for_transfer(transfer_id: str) -> Tuple[List[dict], List[str]]:
    payload = decode_transfer_payload(transfer_id)
    identifier_type, identifier_value = detect_identifier(transfer_id, payload)

    banks = load_banks_config()
    results: List[dict] = []
    errors: List[str] = []

    for bank in banks:
        bank_id = bank.get("id") or "unknown"
        close_only = bool(bank.get("close_only"))
        supported = bank.get("supported_identifiers") or []

        if close_only:
            results.append(
                {
                    "bank_id": bank_id,
                    "title": bank.get("title", "Банк"),
                    "logo": bank.get("logo", ""),
                    "notes": bank.get("notes", ""),
                    "close_only": True,
                    "link_id": bank.get("id", bank_id),
                    "link_token": "",
                    "deeplink": "",
                    "fallback_url": "",
                }
            )
            continue

        if identifier_type not in supported:
            continue

        builder = get_builder(bank.get("builder", ""))
        if not builder:
            errors.append(f"builder not found for {bank_id}")
            continue

        request_payload: LinkBuilderRequest = {
            "identifier_type": identifier_type,
            "identifier_value": identifier_value,
            "amount": str((payload.get("option") or {}).get("amount") or ""),
            "comment": str((payload.get("option") or {}).get("comment") or ""),
            "extra": payload,
        }

        try:
            built = builder(request_payload)
        except Exception as exc:
            logger.warning("WebApp API: builder error for %s: %s", bank_id, exc)
            errors.append(f"builder failed for {bank_id}")
            built = {"deeplink": "", "fallback_url": "https://www.google.com", "link_id": f"fallback:{bank_id}"}

        token_payload = {
            "bank_id": bank_id,
            "deeplink": built.get("deeplink") or "",
            "fallback_url": built.get("fallback_url") or "",
            "transfer_id": transfer_id,
        }
        token = await token_store.issue_token(token_payload)

        results.append(
            {
                "bank_id": bank_id,
                "title": bank.get("title", "Банк"),
                "logo": bank.get("logo", ""),
                "notes": bank.get("notes", ""),
                "link_id": built.get("link_id", bank_id),
                "link_token": token,
                "deeplink": built.get("deeplink", ""),
                "fallback_url": built.get("fallback_url", ""),
            }
        )

    return results, errors


# -----------------------------
# HTTP Handlers (aiohttp)
# -----------------------------
async def handle_post_webapp(request: web.Request) -> web.Response:
    """
    Принимаем событие Mini App:
    - прогреваем TTL-кэш (быстро для polling)
    - пишем в БД (UPSERT)
    """
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)

    # 1) TTL-cache (не блокирует интеграцию, даже если БД недоступна)
    ev = _build_event_from_post(payload)
    if ev:
        await event_store.put(ev.transfer_id, ev)

    # 2) DB write (ошибки подавляем внутри save_event_to_db)
    await save_event_to_db(payload)

    return web.Response(status=202)


async def handle_get_webapp(request: web.Request) -> web.Response:
    """
    Получение события по transfer_id:
    1) TTL-cache
    2) DB
    3) прогрев TTL-cache
    """
    transfer_id = (request.query.get("transfer_id") or "").strip()
    if not transfer_id:
        return web.json_response({"error": "transfer_id is required"}, status=400)

    include_raw = (request.query.get("include_raw") or "0").lower() in ("1", "true", "yes")

    # 1) cache
    cached = await event_store.get(transfer_id)
    if cached:
        out = {
            "id": cached.db_id,
            "transfer_id": cached.transfer_id,
            "transfer_payload": cached.transfer_payload,
            "inline_context": cached.inline_context,
            "opener_tg_user_id": cached.opener_tg_user_id,
            "opener": cached.opener,
            "created_at": cached.created_at,
            "source": "cache",
        }
        if include_raw:
            out["raw_init_data"] = cached.raw_init_data
        return web.json_response(out)

    # 2) db
    db_event = await fetch_event_from_db(transfer_id)
    if not db_event:
        return web.json_response({"error": "event not found"}, status=404)

    # 3) warm cache
    await event_store.put(transfer_id, db_event)

    out = {
        "id": db_event.db_id,
        "transfer_id": db_event.transfer_id,
        "transfer_payload": db_event.transfer_payload,
        "inline_context": db_event.inline_context,
        "opener_tg_user_id": db_event.opener_tg_user_id,
        "opener": db_event.opener,
        "created_at": db_event.created_at,
        "source": "db",
    }
    if include_raw:
        out["raw_init_data"] = db_event.raw_init_data

    return web.json_response(out)


async def handle_get_links(request: web.Request) -> web.Response:
    transfer_id = (request.query.get("transfer_id") or "").strip()
    if not transfer_id:
        return web.json_response({"error": "transfer_id is required"}, status=400)

    try:
        links, errors = await build_links_for_transfer(transfer_id)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    except Exception as exc:
        logger.warning("WebApp API: internal error in links: %s", exc)
        return web.json_response({"error": "internal_error"}, status=500)

    return web.json_response(
        {
            "transfer_id": transfer_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "links": links,
            "errors": errors,
        }
    )


async def handle_get_link_token(request: web.Request) -> web.Response:
    token = request.match_info.get("token", "")
    payload = await token_store.get_payload(token)
    if not payload:
        return web.json_response({"error": "token not found"}, status=404)
    return web.json_response(payload)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/api/webapp", handle_post_webapp)
    app.router.add_get("/api/webapp", handle_get_webapp)

    app.router.add_get("/api/links", handle_get_links)
    app.router.add_get("/api/links/{token}", handle_get_link_token)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8080)
