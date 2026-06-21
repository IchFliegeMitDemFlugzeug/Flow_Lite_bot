# services/bot/tools/bin_lookup.py

"""Безопасное локальное определение карты по BIN/IIN.

Модуль не хранит и не логирует полный номер карты: наружу возвращаются только
bin8/bin6, last4 и маска. Для блока настроек этого достаточно, чтобы показать
пользователю найденный банк и платёжную систему перед сохранением карты.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any
from urllib import request, error

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
BIN_DB_PATH = CONFIG_DIR / "bin_db.json"
BIN_CACHE_PATH = CONFIG_DIR / "bin_cache.json"
HTTP_TIMEOUT_SECONDS = 2.5
CACHE_TTL_DAYS = 30


@dataclass(slots=True)
class CardBinInfo:
    ok: bool
    source: str = "unknown"
    confidence: str = "unknown"
    bin: str = ""
    bin_length: int = 0
    payment_system: str = "unknown"
    bank_name: str = ""
    bank_id: str = ""
    country: str = ""
    card_type: str = "unknown"
    card_level: str = ""
    masked: str = ""
    last4: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.ok:
            data.pop("error", None)
        return data


def _digits_only(value: str) -> str:
    """Оставляем только цифры, чтобы пробелы и дефисы не мешали проверке."""
    return re.sub(r"\D+", "", str(value or ""))


def is_luhn_valid(card_number: str) -> bool:
    """Проверяем номер карты по алгоритму Луна без внешних сервисов."""
    digits = _digits_only(card_number)
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    should_double = False
    for char in reversed(digits):
        number = int(char)
        if should_double:
            number *= 2
            if number > 9:
                number -= 9
        checksum += number
        should_double = not should_double
    return checksum % 10 == 0


def normalize_card_number(card_number: str) -> dict[str, str] | None:
    """Возвращаем безопасные части карты: bin8, bin6, last4 и маску."""
    digits = _digits_only(card_number)
    if not is_luhn_valid(digits):
        return None
    bin8 = digits[:8] if len(digits) >= 8 else ""
    bin6 = digits[:6]
    last4 = digits[-4:]
    middle_stars = "*" * max(0, len(digits) - len(bin6) - len(last4))
    return {"bin8": bin8, "bin6": bin6, "last4": last4, "masked": f"{bin6}{middle_stars}{last4}"}


def detect_payment_system(card_number_or_bin: str) -> str:
    """Определяем платёжную систему по открытым диапазонам BIN."""
    digits = _digits_only(card_number_or_bin)
    if len(digits) >= 4 and 2200 <= int(digits[:4]) <= 2204:
        return "mir"
    if digits.startswith("4"):
        return "visa"
    if len(digits) >= 2 and 51 <= int(digits[:2]) <= 55:
        return "mastercard"
    if len(digits) >= 4 and 2221 <= int(digits[:4]) <= 2720:
        return "mastercard"
    if digits.startswith("62"):
        return "unionpay"
    if digits.startswith(("34", "37")):
        return "amex"
    if digits.startswith("35"):
        return "jcb"
    return "unknown"


def map_bank_name_to_project_bank_id(bank_name: str) -> str:
    """Приводим разные написания банка к bank_id, который использует проект."""
    normalized = re.sub(r"[\s\-_.]+", " ", str(bank_name or "").lower()).strip()
    compact = normalized.replace(" ", "")
    aliases = {
        "sber": {"сбер", "sber", "sberbank", "сбербанк", "паосбербанк", "пaoсбербанк"},
        "vtb": {"втб", "vtb", "bankvtb", "банквтб"},
        "tbank": {"тинькофф", "tinkoff", "tbank", "tбанк", "тбанк"},
        "alfabank": {"альфа", "alfabank", "alfaбанк", "альфабанк"},
        "gazprombank": {"газпромбанк", "gazprombank", "gpb"},
        "psb": {"псб", "psb", "promsvyazbank", "промсвязьбанк"},
        "mkb": {"мкб", "mkb", "creditbankofmoscow", "московскийкредитныйбанк"},
        "mtsbank": {"мтс", "mts", "mtsbank", "мтсбанк"},
        "pochtabank": {"почтабанк", "pochtabank"},
        "sovcombank": {"совкомбанк", "sovcombank", "halva"},
        "rshb": {"россельхозбанк", "rshb", "russianagriculturalbank"},
    }
    for bank_id, names in aliases.items():
        if compact in names or normalized in names:
            return bank_id
    return ""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _build_info(parts: dict[str, str], bin_value: str, source: str, confidence: str, row: dict[str, Any]) -> CardBinInfo:
    bank_name = str(row.get("bank_name") or row.get("bank") or row.get("issuer") or "")
    bank_id = str(row.get("bank_id") or map_bank_name_to_project_bank_id(bank_name) or "")
    return CardBinInfo(
        ok=True,
        source=source,
        confidence=confidence,
        bin=bin_value,
        bin_length=len(bin_value),
        payment_system=str(row.get("payment_system") or row.get("scheme") or detect_payment_system(bin_value)),
        bank_name=bank_name,
        bank_id=bank_id,
        country=str(row.get("country") or row.get("alpha_2") or ""),
        card_type=str(row.get("card_type") or row.get("type") or "unknown"),
        card_level=str(row.get("card_level") or row.get("category") or ""),
        masked=parts["masked"],
        last4=parts["last4"],
    )


def _lookup_local(parts: dict[str, str]) -> CardBinInfo | None:
    db = _read_json(BIN_DB_PATH)
    for bin_value, confidence in ((parts["bin8"], "local_8"), (parts["bin6"], "local_6")):
        if bin_value and bin_value in db:
            return _build_info(parts, bin_value, "local", confidence, db[bin_value])
    return None


def _utc_now_iso() -> str:
    """Возвращаем текущее UTC-время для служебных полей кэша."""
    return datetime.now(timezone.utc).isoformat()


def _lookup_cache(parts: dict[str, str]) -> CardBinInfo | None:
    """Ищем внешний результат в кэше только по bin8/bin6, без полного PAN."""
    cache = _read_json(BIN_CACHE_PATH)
    now = datetime.now(timezone.utc)
    for bin_value, confidence in ((parts["bin8"], "external_8"), (parts["bin6"], "external_6")):
        item = cache.get(bin_value)
        if not item:
            continue
        updated_at = str(item.get("updated_at") or item.get("created_at") or "")
        try:
            updated_dt = datetime.fromisoformat(updated_at)
        except ValueError:
            continue
        if now - updated_dt > timedelta(days=CACHE_TTL_DAYS):
            continue
        result = item.get("result") or {}
        return _build_info(parts, bin_value, str(item.get("source") or result.get("source") or "cache"), confidence, result)
    return None


def _save_cache(bin_value: str, source: str, info: CardBinInfo) -> None:
    """Сохраняем внешний ответ в JSON-кэш без полного номера карты."""
    if not bin_value:
        return
    BIN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache = _read_json(BIN_CACHE_PATH)
    now = _utc_now_iso()
    existing = cache.get(bin_value) or {}
    result = info.to_dict()
    result.pop("masked", None)
    result.pop("last4", None)
    cache[bin_value] = {
        "bin": bin_value,
        "result": result,
        "source": source,
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
    }
    BIN_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _request_json(url: str, api_key: str) -> dict[str, Any] | None:
    req = request.Request(url, headers={"x-api-key": api_key, "Authorization": f"Bearer {api_key}"})
    try:
        with request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _external_lookup(parts: dict[str, str]) -> CardBinInfo | None:
    if os.getenv("BIN_LOOKUP_EXTERNAL_ENABLED", "true").lower() == "false":
        return None
    providers = (
        ("handyapi", "HANDYAPI_KEY", "HANDYAPI_BASE_URL", "https://data.handyapi.com/bin"),
        ("binsearchlookup", "BINSEARCHLOOKUP_KEY", "BINSEARCHLOOKUP_BASE_URL", "https://api.binsearchlookup.com"),
    )
    for source, key_env, base_env, default_base in providers:
        api_key = os.getenv(key_env, "")
        if not api_key:
            continue
        base_url = os.getenv(base_env, default_base).rstrip("/")
        for bin_value, confidence in ((parts["bin8"], "external_8"), (parts["bin6"], "external_6")):
            payload = _request_json(f"{base_url}/{bin_value}", api_key)
            if payload:
                return _build_info(parts, bin_value, source, confidence, payload)
    return None


def detect_card_bin(card_number: str) -> dict[str, Any]:
    """Главная функция: валидирует карту и возвращает безопасную BIN-подсказку."""
    parts = normalize_card_number(card_number)
    if parts is None:
        return CardBinInfo(ok=False, error="invalid_card_number").to_dict()
    local_info = _lookup_local(parts)
    if local_info is not None:
        return local_info.to_dict()
    cached_info = _lookup_cache(parts)
    if cached_info is not None:
        return cached_info.to_dict()
    external_info = _external_lookup(parts)
    if external_info is not None:
        _save_cache(external_info.bin, external_info.source, external_info)
        return external_info.to_dict()
    scheme = detect_payment_system(parts["bin8"] or parts["bin6"])
    return CardBinInfo(
        ok=True,
        source="local_scheme_only" if scheme != "unknown" else "unknown",
        confidence="scheme_only" if scheme != "unknown" else "unknown",
        bin=parts["bin8"] or parts["bin6"],
        bin_length=len(parts["bin8"] or parts["bin6"]),
        payment_system=scheme,
        masked=parts["masked"],
        last4=parts["last4"],
    ).to_dict()
