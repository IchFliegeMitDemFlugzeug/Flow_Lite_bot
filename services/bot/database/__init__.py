# services/bot/database/__init__.py
"""\
Public database interface for the bot (async).

All functions in this module are async and must be awaited.

External API (used by handlers):
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

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    BotLastStep,
    CardData,
    ChatLastMessage,
    DBUser,
    DBUserPaymentMethod,
    PaymentMethodType,
    PhoneData,
    User,
)
from .storage import get_session


# ============================================================
# Helpers
# ============================================================


async def _get_or_create_db_user(
    session: AsyncSession,
    tg_user_id: int,
    *,
    mark_authorised: bool = False,
) -> DBUser:
    """Find user by Telegram user_id in 'users' table or create a new row.

    If mark_authorised=True:
    - on create: sets authorised_at
    - on existing row: sets authorised_at only if it is NULL
    """
    tg_user_id = int(tg_user_id)

    res = await session.execute(select(DBUser).where(DBUser.tg_user_id == tg_user_id))
    db_user = res.scalar_one_or_none()

    if db_user is None:
        db_user = DBUser(tg_user_id=tg_user_id)
        if mark_authorised:
            db_user.authorised_at = datetime.utcnow()
        session.add(db_user)
        await session.flush()  # ensure db_user.id is populated
        return db_user

    if mark_authorised and db_user.authorised_at is None:
        db_user.authorised_at = datetime.utcnow()

    return db_user


# ============================================================
# Public functions
# ============================================================


async def get_user(user_id: int) -> User:
    """Get (or create) a user by Telegram user_id.

    Returns a domain User instance assembled from MySQL:
    - basic fields from 'users';
    - phones and cards from 'user_payment_methods';
    - registration_step and current_phone/card from 'bot_last_step';
    - last_bot_message_id from 'chat_last_message'.
    """
    tg_user_id = int(user_id)

    async with get_session() as session:
        db_user = await _get_or_create_db_user(session, tg_user_id, mark_authorised=True)

        # ----- phones and cards from user_payment_methods -----
        phones: Dict[str, PhoneData] = {}
        cards: Dict[str, CardData] = {}

        pm_res = await session.execute(
            select(DBUserPaymentMethod).where(
                and_(
                    DBUserPaymentMethod.user_id == db_user.id,
                    DBUserPaymentMethod.is_active.is_(True),
                )
            )
        )
        for pm in pm_res.scalars().all():
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

        # ----- registration progress from bot_last_step -----
        bot_step_res = await session.execute(
            select(BotLastStep).where(
                and_(
                    BotLastStep.user_id == db_user.id,
                    BotLastStep.chat_id == tg_user_id,
                )
            )
        )
        bot_step = bot_step_res.scalar_one_or_none()

        registration_step: Optional[str] = None
        current_phone: Optional[str] = None
        if bot_step is not None:
            registration_step = bot_step.last_step
            current_phone = bot_step.pay_method_number

        # ----- last bot message from chat_last_message -----
        last_bot_message_id: Optional[int] = None

        last_msg_res = await session.execute(
            select(ChatLastMessage).where(
                and_(
                    ChatLastMessage.user_id == db_user.id,
                    ChatLastMessage.chat_id == tg_user_id,
                )
            )
        )
        last_msg = last_msg_res.scalar_one_or_none()

        if last_msg is not None and last_msg.last_message_id is not None:
            try:
                last_bot_message_id = int(last_msg.last_message_id)
            except (TypeError, ValueError):
                last_bot_message_id = None

        return User(
            id=tg_user_id,
            first_name=db_user.first_name,
            last_name=db_user.last_name,
            username=db_user.tg_username,
            registration_step=registration_step,
            current_phone=current_phone,
            last_bot_message_id=last_bot_message_id,
            phones=phones,
            cards=cards,
        )


async def update_basic_user_info(
    user_id: int,
    first_name: Optional[str],
    last_name: Optional[str],
    username: Optional[str],
) -> None:
    """Update basic user info (first_name, last_name, username) in MySQL."""
    tg_user_id = int(user_id)

    async with get_session() as session:
        db_user = await _get_or_create_db_user(session, tg_user_id)
        db_user.first_name = first_name
        db_user.last_name = last_name
        db_user.tg_username = username


async def add_or_update_phone(
    user_id: int,
    phone: str,
    banks: List[str],
    main_bank: Optional[str],
) -> None:
    """Add or update a user's phone number.

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

    async with get_session() as session:
        db_user = await _get_or_create_db_user(session, tg_user_id)

        existing_res = await session.execute(
            select(DBUserPaymentMethod).where(
                and_(
                    DBUserPaymentMethod.user_id == db_user.id,
                    DBUserPaymentMethod.method_type == PaymentMethodType.phone,
                    DBUserPaymentMethod.pay_method_number == phone_str,
                )
            )
        )
        existing_pms = existing_res.scalars().all()

        # If no banks are provided, deactivate all phone records for this number.
        if not norm_banks:
            for pm in existing_pms:
                pm.is_active = False
                pm.is_primary = False
            return

        existing_by_provider: Dict[str, DBUserPaymentMethod] = {}
        for pm in existing_pms:
            existing_by_provider[pm.provider or ""] = pm

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


async def set_registration_progress(
    user_id: int,
    step: Optional[str],
    current_phone: Optional[str],
) -> None:
    """Save user's registration progress.

    - step is stored in bot_last_step.last_step;
    - current_phone is stored in bot_last_step.pay_method_number (can be phone or card);
    - if step is None, the row is removed (progress cleared).
    """
    tg_user_id = int(user_id)

    async with get_session() as session:
        db_user = await _get_or_create_db_user(session, tg_user_id)

        existing_res = await session.execute(
            select(BotLastStep).where(
                and_(
                    BotLastStep.user_id == db_user.id,
                    BotLastStep.chat_id == tg_user_id,
                )
            )
        )
        existing = existing_res.scalar_one_or_none()

        if step is None:
            if existing is not None:
                session.delete(existing)
            return

        if existing is None:
            session.add(
                BotLastStep(
                    user_id=db_user.id,
                    chat_id=tg_user_id,
                    last_step=step,
                    pay_method_number=current_phone,
                )
            )
        else:
            existing.last_step = step
            existing.pay_method_number = current_phone


async def get_registration_progress(user_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Read user's registration progress.

    Returns (registration_step, pay_method_number).

    pay_method_number in this context is used as current_phone/current_card
    depending on what is being processed.
    """
    tg_user_id = int(user_id)

    async with get_session() as session:
        db_user_res = await session.execute(select(DBUser).where(DBUser.tg_user_id == tg_user_id))
        db_user = db_user_res.scalar_one_or_none()

        if db_user is None:
            return None, None

        bot_step_res = await session.execute(
            select(BotLastStep).where(
                and_(
                    BotLastStep.user_id == db_user.id,
                    BotLastStep.chat_id == tg_user_id,
                )
            )
        )
        bot_step = bot_step_res.scalar_one_or_none()

        if bot_step is None:
            return None, None

        return bot_step.last_step, bot_step.pay_method_number


async def add_or_update_card(
    user_id: int,
    card_number: str,
    bank: Optional[str],
    payment_system: Optional[str],
) -> None:
    """Add or update a user's bank card.

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

    async with get_session() as session:
        db_user = await _get_or_create_db_user(session, tg_user_id)

        pm_res = await session.execute(
            select(DBUserPaymentMethod).where(
                and_(
                    DBUserPaymentMethod.user_id == db_user.id,
                    DBUserPaymentMethod.method_type == PaymentMethodType.card,
                    DBUserPaymentMethod.pay_method_number == card_number_str,
                )
            )
        )
        pm = pm_res.scalar_one_or_none()

        if pm is None:
            session.add(
                DBUserPaymentMethod(
                    user_id=db_user.id,
                    method_type=PaymentMethodType.card,
                    pay_method_number=card_number_str,
                    provider=bank,
                    card_brand=payment_system,
                    is_primary=False,
                    is_active=True,
                )
            )
        else:
            pm.provider = bank
            pm.card_brand = payment_system
            pm.is_active = True


async def remove_card(user_id: int, card_number: str) -> None:
    """Deactivate a user's bank card by its number (is_active = 0)."""
    tg_user_id = int(user_id)
    card_number_str = str(card_number).strip()
    if not card_number_str:
        return

    async with get_session() as session:
        db_user_res = await session.execute(select(DBUser).where(DBUser.tg_user_id == tg_user_id))
        db_user = db_user_res.scalar_one_or_none()
        if db_user is None:
            return

        pm_res = await session.execute(
            select(DBUserPaymentMethod).where(
                and_(
                    DBUserPaymentMethod.user_id == db_user.id,
                    DBUserPaymentMethod.method_type == PaymentMethodType.card,
                    DBUserPaymentMethod.pay_method_number == card_number_str,
                )
            )
        )
        pm = pm_res.scalar_one_or_none()
        if pm is None:
            return

        pm.is_active = False
        pm.is_primary = False


async def remove_phone(user_id: int, phone: str) -> None:
    """Deactivate a user's phone number (all banks linked to this phone)."""
    tg_user_id = int(user_id)
    phone_str = str(phone).strip()
    if not phone_str:
        return

    async with get_session() as session:
        db_user_res = await session.execute(select(DBUser).where(DBUser.tg_user_id == tg_user_id))
        db_user = db_user_res.scalar_one_or_none()
        if db_user is None:
            return

        pms_res = await session.execute(
            select(DBUserPaymentMethod).where(
                and_(
                    DBUserPaymentMethod.user_id == db_user.id,
                    DBUserPaymentMethod.method_type == PaymentMethodType.phone,
                    DBUserPaymentMethod.pay_method_number == phone_str,
                )
            )
        )
        pms = pms_res.scalars().all()
        if not pms:
            return

        for pm in pms:
            pm.is_active = False
            pm.is_primary = False


# ============================================================
# Storing last bot message_id per chat in DB
# ============================================================


async def set_last_bot_message_id(chat_id: int, message_id: Optional[int]) -> None:
    """Store the last bot message ID for a given chat."""
    chat_id_int = int(chat_id)

    async with get_session() as session:
        db_user = await _get_or_create_db_user(session, chat_id_int)

        existing_res = await session.execute(
            select(ChatLastMessage).where(
                and_(
                    ChatLastMessage.user_id == db_user.id,
                    ChatLastMessage.chat_id == chat_id_int,
                )
            )
        )
        existing = existing_res.scalar_one_or_none()

        if message_id is None:
            if existing is not None:
                session.delete(existing)
            return

        last_message_str = str(int(message_id))

        if existing is None:
            session.add(
                ChatLastMessage(
                    user_id=db_user.id,
                    chat_id=chat_id_int,
                    last_message_id=last_message_str,
                )
            )
        else:
            existing.last_message_id = last_message_str


async def get_last_bot_message_id(chat_id: int) -> Optional[int]:
    """Get the last bot message ID for a given chat_id."""
    chat_id_int = int(chat_id)

    async with get_session() as session:
        db_user_res = await session.execute(select(DBUser).where(DBUser.tg_user_id == chat_id_int))
        db_user = db_user_res.scalar_one_or_none()
        if db_user is None:
            return None

        last_msg_res = await session.execute(
            select(ChatLastMessage).where(
                and_(
                    ChatLastMessage.user_id == db_user.id,
                    ChatLastMessage.chat_id == chat_id_int,
                )
            )
        )
        last_msg = last_msg_res.scalar_one_or_none()

        if last_msg is None or last_msg.last_message_id is None:
            return None

        try:
            return int(last_msg.last_message_id)
        except (TypeError, ValueError):
            return None


__all__ = [
    "get_user",
    "update_basic_user_info",
    "add_or_update_phone",
    "set_registration_progress",
    "get_registration_progress",
    "add_or_update_card",
    "remove_card",
    "remove_phone",
    "set_last_bot_message_id",
    "get_last_bot_message_id",
]