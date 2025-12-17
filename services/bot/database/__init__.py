# services/bot/database/__init__.py
"""
Public database interface for the bot.

External API (used by handlers) stays the same:
- get_user
- update_basic_user_info
- add_or_update_phone
- set_registration_progress
- get_registration_progress
- add_or_update_card
- remove_card
- remove_phone
- set_last_bot_message_id
- get_last_bot_message_id

Internally data is stored in MySQL via SQLAlchemy ORM models.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Iterable, NamedTuple

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .models import (
    User,                   # domain dataclass
    PhoneData,
    CardData,
    DBUser,                 # ORM models
    DBUserPaymentMethod,
    BotLastStep,
    ChatLastMessage,
    PaymentMethodType,
)
from .storage import get_session

import time

from threading import RLock

from datetime import datetime



# ============================================================
# Helpers
# ============================================================


def _get_or_create_db_user(
    session: Session,
    tg_user_id: int,
    *,
    mark_authorised: bool = False,
) -> DBUser:
    """
    Find user by Telegram user_id in 'users' table or create a new row.

    If mark_authorised=True:
    - on create: sets authorised_at
    - on existing row: sets authorised_at only if it is NULL
    """
    tg_user_id = int(tg_user_id)

    db_user = session.execute(
        select(DBUser).where(DBUser.tg_user_id == tg_user_id)
    ).scalar_one_or_none()

    if db_user is None:
        db_user = DBUser(tg_user_id=tg_user_id)
        if mark_authorised:
            db_user.authorised_at = datetime.utcnow()
        session.add(db_user)
        session.flush()  # ensure db_user.id is populated
        return db_user

    if mark_authorised and db_user.authorised_at is None:
        db_user.authorised_at = datetime.utcnow()

    return db_user



# ============================================================
# TTL cache: DBUser core + active DBUserPaymentMethod
# ============================================================

_USER_CORE_TTL_SEC = 120.0
_PM_TTL_SEC = 120.0

_USER_CORE_LOCK = RLock()
_PM_LOCK = RLock()


class _UserCore(NamedTuple):
    db_user_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]


class _PMSnapshot(NamedTuple):
    method_type: PaymentMethodType
    pay_method_number: Optional[str]
    provider: Optional[str]
    is_primary: bool
    card_brand: Optional[str]


# tg_user_id -> (expires_at, _UserCore)
_USER_CORE_CACHE: Dict[int, Tuple[float, _UserCore]] = {}

# users.id -> (expires_at, tuple[_PMSnapshot, ...])  (ТОЛЬКО active)
_PM_CACHE: Dict[int, Tuple[float, Tuple[_PMSnapshot, ...]]] = {}


def _user_core_cache_get(tg_user_id: int) -> Optional[_UserCore]:
    now = time.monotonic()
    key = int(tg_user_id)
    with _USER_CORE_LOCK:
        item = _USER_CORE_CACHE.get(key)
        if not item:
            return None
        expires_at, val = item
        if expires_at <= now:
            _USER_CORE_CACHE.pop(key, None)
            return None
        return val


def _user_core_cache_set(tg_user_id: int, core: _UserCore) -> None:
    key = int(tg_user_id)
    expires_at = time.monotonic() + _USER_CORE_TTL_SEC
    with _USER_CORE_LOCK:
        _USER_CORE_CACHE[key] = (expires_at, core)


def _pm_cache_get(db_user_id: int) -> Optional[Tuple[_PMSnapshot, ...]]:
    now = time.monotonic()
    key = int(db_user_id)
    with _PM_LOCK:
        item = _PM_CACHE.get(key)
        if not item:
            return None
        expires_at, val = item
        if expires_at <= now:
            _PM_CACHE.pop(key, None)
            return None
        return val


def _pm_cache_set(db_user_id: int, pms: Tuple[_PMSnapshot, ...]) -> None:
    key = int(db_user_id)
    expires_at = time.monotonic() + _PM_TTL_SEC
    with _PM_LOCK:
        _PM_CACHE[key] = (expires_at, pms)


def invalidate_user_core_cache(tg_user_id: int) -> None:
    with _USER_CORE_LOCK:
        _USER_CORE_CACHE.pop(int(tg_user_id), None)


def invalidate_payment_methods_cache(db_user_id: int) -> None:
    with _PM_LOCK:
        _PM_CACHE.pop(int(db_user_id), None)


# ============================================================
# Public functions
# ============================================================


def get_user(user_id: int) -> User:
    """
    Get (or create) a user by Telegram user_id.

    Cached:
    - DBUser core fields (id, first_name, last_name, tg_username)
    - active user_payment_methods

    NOT cached (always read directly from DB):
    - bot_last_step
    - chat_last_message
    """
    tg_user_id = int(user_id)

    with get_session() as session:
        # ----- DBUser core (cached) -----
        core = _user_core_cache_get(tg_user_id)
        if core is None:
            db_user = _get_or_create_db_user(session, tg_user_id, mark_authorised=True)
            core = _UserCore(
                db_user_id=int(db_user.id),
                first_name=db_user.first_name,
                last_name=db_user.last_name,
                username=db_user.tg_username,
            )
            _user_core_cache_set(tg_user_id, core)

        db_user_id = core.db_user_id

        # ----- payment methods (cached, active only) -----
        pm_snapshots = _pm_cache_get(db_user_id)
        if pm_snapshots is None:
            rows = session.execute(
                select(DBUserPaymentMethod).where(DBUserPaymentMethod.user_id == db_user_id)
            ).scalars().all()

            pm_snapshots = tuple(
                _PMSnapshot(
                    method_type=pm.method_type,
                    pay_method_number=pm.pay_method_number,
                    provider=pm.provider,
                    is_primary=bool(pm.is_primary),
                    card_brand=pm.card_brand,
                )
                for pm in rows
                if pm.is_active
            )
            _pm_cache_set(db_user_id, pm_snapshots)

        phones: Dict[str, PhoneData] = {}
        cards: Dict[str, CardData] = {}

        for pm in pm_snapshots:
            if pm.method_type == PaymentMethodType.phone:
                phone_number = pm.pay_method_number
                if not phone_number:
                    continue

                phone_data = phones.get(phone_number)
                if phone_data is None:
                    phone_data = PhoneData()
                    phones[phone_number] = phone_data

                if pm.provider:
                    if pm.provider not in phone_data.banks:
                        phone_data.banks.append(pm.provider)
                    if pm.is_primary:
                        phone_data.main_bank = pm.provider

            elif pm.method_type == PaymentMethodType.card:
                card_number = pm.pay_method_number
                if not card_number:
                    continue

                cards[card_number] = CardData(
                    number=card_number,
                    bank=pm.provider,
                    payment_system=pm.card_brand,
                )

        # ----- registration progress from bot_last_step (NOT cached) -----
        bot_step = session.execute(
            select(BotLastStep).where(
                and_(
                    BotLastStep.user_id == db_user_id,
                    BotLastStep.chat_id == tg_user_id,
                )
            )
        ).scalar_one_or_none()

        registration_step: Optional[str] = None
        current_phone: Optional[str] = None
        if bot_step is not None:
            registration_step = bot_step.last_step
            current_phone = bot_step.pay_method_number

        # ----- last bot message from chat_last_message (NOT cached) -----
        last_bot_message_id: Optional[int] = None

        last_msg = session.execute(
            select(ChatLastMessage).where(
                and_(
                    ChatLastMessage.user_id == db_user_id,
                    ChatLastMessage.chat_id == tg_user_id,
                )
            )
        ).scalar_one_or_none()

        if last_msg is not None and last_msg.last_message_id is not None:
            try:
                last_bot_message_id = int(last_msg.last_message_id)
            except (TypeError, ValueError):
                last_bot_message_id = None

        return User(
            id=tg_user_id,
            first_name=core.first_name,
            last_name=core.last_name,
            username=core.username,
            registration_step=registration_step,
            current_phone=current_phone,
            last_bot_message_id=last_bot_message_id,
            phones=phones,
            cards=cards,
        )


# Добавление клиентов в таблицу users (нажали на кнопку в inline-сообщении)
def ensure_inline_user(
    user_id: int,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    username: Optional[str] = None,
) -> None:
    """
    Create user row if missing for a user who clicked an inline button in a private chat.
    Does NOT set authorised_at.
    """
    tg_user_id = int(user_id)

    with get_session() as session:
        db_user = _get_or_create_db_user(session, tg_user_id, mark_authorised=False)
        if db_user.first_name is None:
            # обновляем базовые поля только если переданы (не затираем None)
            if first_name is not None:
                db_user.first_name = first_name
            if last_name is not None:
                db_user.last_name = last_name
            if username is not None:
                db_user.tg_username = username


def update_basic_user_info(
    user_id: int,
    first_name: Optional[str],
    last_name: Optional[str],
    username: Optional[str],
) -> None:
    """Update basic user info (first_name, last_name, username) in MySQL."""
    tg_user_id = int(user_id)

    with get_session() as session:
        db_user = _get_or_create_db_user(session, tg_user_id)

        db_user.first_name = first_name
        db_user.last_name = last_name
        db_user.tg_username = username
        # commit is done by get_session()
        invalidate_user_core_cache(tg_user_id)


def add_or_update_phone(
    user_id: int,
    phone: str,
    banks: List[str],
    main_bank: Optional[str],
) -> None:
    """
    Add or update a user's phone number.

    Representation in user_payment_methods:
    - method_type = 'phone';
    - pay_method_number = phone;
    - one row per selected bank (provider);
    - row corresponding to main_bank has is_primary = 1, others have 0;
    - rows for banks that are no longer selected are marked is_active = 0.
    """
    tg_user_id = int(user_id)
    phone_str = str(phone).strip()
    if not phone_str:
        return

    # Normalise bank list (unique, non-empty strings).
    norm_banks: List[str] = []
    for b in banks or []:
        b_str = str(b).strip()
        if b_str and b_str not in norm_banks:
            norm_banks.append(b_str)

    if main_bank is not None:
        main_bank = str(main_bank).strip() or None

    if main_bank and main_bank not in norm_banks:
        norm_banks.insert(0, main_bank)

    with get_session() as session:
        db_user = _get_or_create_db_user(session, tg_user_id)

        existing_pms = session.execute(
            select(DBUserPaymentMethod).where(
                and_(
                    DBUserPaymentMethod.user_id == db_user.id,
                    DBUserPaymentMethod.method_type == PaymentMethodType.phone,
                    DBUserPaymentMethod.pay_method_number == phone_str,
                )
            )
        ).scalars().all()

        # If no banks are provided, deactivate all phone records for this number.
        if not norm_banks:
            for pm in existing_pms:
                pm.is_active = False
                pm.is_primary = False
            return

        existing_by_provider: Dict[str, DBUserPaymentMethod] = {}
        for pm in existing_pms:
            key = pm.provider or ""
            existing_by_provider[key] = pm

        selected_set = set(norm_banks)

        # Deactivate providers that are no longer selected.
        for pm in existing_pms:
            prov = pm.provider or ""
            if prov not in selected_set:
                pm.is_active = False
                pm.is_primary = False

        # Upsert rows for each selected bank.
        for bank_code in norm_banks:
            prov = bank_code
            is_primary = bool(main_bank) and (bank_code == main_bank)

            pm = existing_by_provider.get(prov)
            if pm is None:
                pm = DBUserPaymentMethod(
                    user_id=db_user.id,
                    method_type=PaymentMethodType.phone,
                    pay_method_number=phone_str,
                    provider=prov,
                    is_primary=is_primary,
                    is_active=True,
                )
                session.add(pm)
            else:
                pm.provider = prov
                pm.is_primary = is_primary
                pm.is_active = True

        invalidate_user_payment_methods_cache(tg_user_id)


def set_registration_progress(
    user_id: int,
    step: Optional[str],
    current_phone: Optional[str],
) -> None:
    """
    Save user's registration progress.

    - step is stored in bot_last_step.last_step;
    - current_phone is stored in bot_last_step.pay_method_number (can be phone or card);
    - if step is None, the row is removed (progress cleared).
    """
    tg_user_id = int(user_id)

    with get_session() as session:
        db_user = _get_or_create_db_user(session, tg_user_id)

        existing: Optional[BotLastStep] = session.execute(
            select(BotLastStep).where(
                and_(
                    BotLastStep.user_id == db_user.id,
                    BotLastStep.chat_id == tg_user_id,
                )
            )
        ).scalar_one_or_none()

        if step is None:
            if existing is not None:
                session.delete(existing)
            return

        if existing is None:
            existing = BotLastStep(
                user_id=db_user.id,
                chat_id=tg_user_id,
                last_step=step,
                pay_method_number=current_phone,
            )
            session.add(existing)
        else:
            existing.last_step = step
            existing.pay_method_number = current_phone


def get_registration_progress(user_id: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Read user's registration progress.

    Returns (registration_step, pay_method_number).

    pay_method_number in this context is used as current_phone/current_card
    depending on what is being processed.
    """
    tg_user_id = int(user_id)

    with get_session() as session:
        db_user: Optional[DBUser] = session.execute(
            select(DBUser).where(DBUser.tg_user_id == tg_user_id)
        ).scalar_one_or_none()

        if db_user is None:
            return None, None

        bot_step: Optional[BotLastStep] = session.execute(
            select(BotLastStep).where(
                and_(
                    BotLastStep.user_id == db_user.id,
                    BotLastStep.chat_id == tg_user_id,
                )
            )
        ).scalar_one_or_none()

        if bot_step is None:
            return None, None

        return bot_step.last_step, bot_step.pay_method_number


def add_or_update_card(
    user_id: int,
    card_number: str,
    bank: Optional[str],
    payment_system: Optional[str],
) -> None:
    """
    Add or update a user's bank card.

    Representation in user_payment_methods:
    - method_type = 'card';
    - pay_method_number = card_number;
    - provider = bank;
    - card_brand = payment_system;
    - is_active = 1.
    """
    tg_user_id = int(user_id)
    card_number_str = str(card_number).strip()
    if not card_number_str:
        return

    with get_session() as session:
        db_user = _get_or_create_db_user(session, tg_user_id)

        pm: Optional[DBUserPaymentMethod] = session.execute(
            select(DBUserPaymentMethod).where(
                and_(
                    DBUserPaymentMethod.user_id == db_user.id,
                    DBUserPaymentMethod.method_type == PaymentMethodType.card,
                    DBUserPaymentMethod.pay_method_number == card_number_str,
                )
            )
        ).scalar_one_or_none()

        if pm is None:
            pm = DBUserPaymentMethod(
                user_id=db_user.id,
                method_type=PaymentMethodType.card,
                pay_method_number=card_number_str,
                provider=bank,
                card_brand=payment_system,
                is_primary=False,
                is_active=True,
            )
            session.add(pm)
        else:
            pm.provider = bank
            pm.card_brand = payment_system
            pm.is_active = True

        invalidate_user_payment_methods_cache(tg_user_id)


def remove_card(
    user_id: int,
    card_number: str,
) -> None:
    """
    Deactivate a user's bank card by its number.

    Implemented as is_active = 0 in user_payment_methods.
    """
    tg_user_id = int(user_id)
    card_number_str = str(card_number).strip()
    if not card_number_str:
        return

    with get_session() as session:
        db_user: Optional[DBUser] = session.execute(
            select(DBUser).where(DBUser.tg_user_id == tg_user_id)
        ).scalar_one_or_none()

        if db_user is None:
            return

        pm: Optional[DBUserPaymentMethod] = session.execute(
            select(DBUserPaymentMethod).where(
                and_(
                    DBUserPaymentMethod.user_id == db_user.id,
                    DBUserPaymentMethod.method_type == PaymentMethodType.card,
                    DBUserPaymentMethod.pay_method_number == card_number_str,
                )
            )
        ).scalar_one_or_none()

        if pm is None:
            return

        pm.is_active = False
        pm.is_primary = False

        invalidate_user_payment_methods_cache(tg_user_id)


def remove_phone(
    user_id: int,
    phone: str,
) -> None:
    """
    Deactivate a user's phone number (all banks linked to this phone).

    Implemented as is_active = 0 in user_payment_methods for:
    - method_type = 'phone'
    - pay_method_number = phone
    """
    tg_user_id = int(user_id)
    phone_str = str(phone).strip()
    if not phone_str:
        return

    with get_session() as session:
        db_user: Optional[DBUser] = session.execute(
            select(DBUser).where(DBUser.tg_user_id == tg_user_id)
        ).scalar_one_or_none()

        if db_user is None:
            return

        pms = session.execute(
            select(DBUserPaymentMethod).where(
                and_(
                    DBUserPaymentMethod.user_id == db_user.id,
                    DBUserPaymentMethod.method_type == PaymentMethodType.phone,
                    DBUserPaymentMethod.pay_method_number == phone_str,
                    DBUserPaymentMethod.is_active.is_(True),
                )
            )
        ).scalars().all()

        if not pms:
            return

        for pm in pms:
            pm.is_active = False
            pm.is_primary = False
    
        invalidate_payment_methods_cache(tg_user_id)


# ============================================================
# Storing last bot message_id per chat in DB
# ============================================================


def set_last_bot_message_id(
    chat_id: int,
    message_id: Optional[int],
) -> None:
    """
    Store the last bot message ID for a given chat.

    Data is stored in tg_lite_bot.chat_last_message:
    - user_id references users.id (resolved by tg_user_id == chat_id);
    - chat_id is the Telegram chat_id;
    - last_message_id is stored as a string.
    """
    chat_id_int = int(chat_id)

    with get_session() as session:
        db_user = _get_or_create_db_user(session, chat_id_int)

        existing: Optional[ChatLastMessage] = session.execute(
            select(ChatLastMessage).where(
                and_(
                    ChatLastMessage.user_id == db_user.id,
                    ChatLastMessage.chat_id == chat_id_int,
                )
            )
        ).scalar_one_or_none()

        if message_id is None:
            if existing is not None:
                session.delete(existing)
            return

        last_message_str = str(int(message_id))

        if existing is None:
            existing = ChatLastMessage(
                user_id=db_user.id,
                chat_id=chat_id_int,
                last_message_id=last_message_str,
            )
            session.add(existing)
        else:
            existing.last_message_id = last_message_str


def get_last_bot_message_id(chat_id: int) -> Optional[int]:
    """
    Get the last bot message ID for a given chat_id.

    If there is no user/chat record, returns None.
    """
    chat_id_int = int(chat_id)

    with get_session() as session:
        db_user: Optional[DBUser] = session.execute(
            select(DBUser).where(DBUser.tg_user_id == chat_id_int)
        ).scalar_one_or_none()

        if db_user is None:
            return None

        last_msg: Optional[ChatLastMessage] = session.execute(
            select(ChatLastMessage).where(
                and_(
                    ChatLastMessage.user_id == db_user.id,
                    ChatLastMessage.chat_id == chat_id_int,
                )
            )
        ).scalar_one_or_none()

        if last_msg is None or last_msg.last_message_id is None:
            return None

        try:
            return int(last_msg.last_message_id)
        except (TypeError, ValueError):
            return None


# Получение списка всех методов получения платежей специалиста
def list_user_payment_methods(
    user_id: int,
    *,
    only_active: bool = True,
    method_types: Iterable[PaymentMethodType] | None = None,
) -> list[DBUserPaymentMethod]:
    """
    Read user's payment methods from DB.

    user_id here is Telegram user_id (tg_user_id).
    Returns rows from user_payment_methods for this user.
    """
    tg_user_id = int(user_id)

    with get_session() as session:  # контекстный менеджер с commit/rollback :contentReference[oaicite:1]{index=1}
        db_user = session.execute(
            select(DBUser).where(DBUser.tg_user_id == tg_user_id)
        ).scalar_one_or_none()

        if db_user is None:
            return []

        stmt = select(DBUserPaymentMethod).where(DBUserPaymentMethod.user_id == db_user.id)

        if only_active:
            stmt = stmt.where(DBUserPaymentMethod.is_active.is_(True))

        if method_types:
            stmt = stmt.where(DBUserPaymentMethod.method_type.in_(list(method_types)))

        # Удобная сортировка: тип, primary, банк, номер
        stmt = stmt.order_by(
            DBUserPaymentMethod.method_type,
            DBUserPaymentMethod.is_primary.desc(),
            DBUserPaymentMethod.provider,
            DBUserPaymentMethod.pay_method_number,
        )

        return session.execute(stmt).scalars().all()


_PM_CACHE: dict[tuple[int, bool, tuple[str, ...]], tuple[float, list[DBUserPaymentMethod]]] = {}
_PM_CACHE_TTL_SEC = 120.0


def invalidate_user_payment_methods_cache(user_id: int) -> None:
    tg_user_id = int(user_id)
    for k in list(_PM_CACHE.keys()):
        if k[0] == tg_user_id:
            _PM_CACHE.pop(k, None)


def list_user_payment_methods_cached(
    user_id: int,
    *,
    only_active: bool = True,
    method_types: Iterable[PaymentMethodType] | None = None,
) -> list[DBUserPaymentMethod]:
    tg_user_id = int(user_id)
    mt_key = tuple(sorted([(mt.value if isinstance(mt, PaymentMethodType) else str(mt)) for mt in (method_types or [])]))
    key = (tg_user_id, only_active, mt_key)

    now = time.monotonic()
    cached = _PM_CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]

    data = list_user_payment_methods(user_id, only_active=only_active, method_types=method_types)
    _PM_CACHE[key] = (now + _PM_CACHE_TTL_SEC, data)
    return data
