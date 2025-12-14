# services/bot/database/models.py
"""
Database and domain models for the Telegram bot.

This module defines:

1) Dataclass domain models (User, PhoneData, CardData) that are used by handlers.
2) SQLAlchemy ORM models that map to MySQL tables:
   users, user_payment_methods, payments, message_templates, bot_last_step, chat_last_message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import enum

from sqlalchemy import (
    Boolean,
    CHAR,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum as SAEnum,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT as MySQLBigInt
from sqlalchemy.orm import declarative_base, relationship

# ============================================================
# Dataclass domain models
# ============================================================


@dataclass
class PhoneData:
    """Information about a single phone number of the user."""
    banks: List[str] = field(default_factory=list)
    main_bank: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "banks": list(self.banks),
            "main_bank": self.main_bank,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "PhoneData":
        if not isinstance(data, dict):
            return cls()

        banks_raw = data.get("banks", [])
        if not isinstance(banks_raw, list):
            banks: List[str] = []
        else:
            banks = [str(b) for b in banks_raw]

        main_bank_raw = data.get("main_bank")
        main_bank = str(main_bank_raw) if main_bank_raw is not None else None

        return cls(banks=banks, main_bank=main_bank)


@dataclass
class CardData:
    """Information about a single bank card of the user."""
    number: str
    bank: Optional[str] = None
    payment_system: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "bank": self.bank,
            "payment_system": self.payment_system,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "CardData":
        if not isinstance(data, dict):
            return cls(number="")

        number_raw = data.get("number", "")
        number = str(number_raw)

        bank_raw = data.get("bank")
        bank = str(bank_raw) if bank_raw is not None else None

        ps_raw = data.get("payment_system")
        payment_system = str(ps_raw) if ps_raw is not None else None

        return cls(number=number, bank=bank, payment_system=payment_system)


@dataclass
class User:
    """
    Domain user model used by handlers.

    This is NOT an ORM model; it's an aggregate built on top of the DB data:
    - id == Telegram user_id;
    - phones and cards are collected from table user_payment_methods;
    - registration_step and current_phone/card come from bot_last_step;
    - last_bot_message_id is stored in chat_last_message.
    """
    id: int

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None

    registration_step: Optional[str] = None
    current_phone: Optional[str] = None
    last_bot_message_id: Optional[int] = None

    phones: Dict[str, PhoneData] = field(default_factory=dict)
    cards: Dict[str, CardData] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Legacy conversion to dict, kept for compatibility with old JSON storage."""
        return {
            "id": int(self.id),
            "first_name": self.first_name,
            "last_name": self.last_name,
            "username": self.username,
            "registration_step": self.registration_step,
            "current_phone": self.current_phone,
            "last_bot_message_id": (
                int(self.last_bot_message_id)
                if self.last_bot_message_id is not None
                else None
            ),
            "phones": {
                phone: phone_data.to_dict()
                for phone, phone_data in self.phones.items()
            },
            "cards": {
                card_number: card_data.to_dict()
                for card_number, card_data in self.cards.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "User":
        """Legacy method; in the DB-backed implementation users are built from ORM objects."""
        if not isinstance(data, dict):
            raise ValueError("User.from_dict expects a dict with user fields")

        user_id_raw = data.get("id")
        if user_id_raw is None:
            raise ValueError("User JSON is missing 'id'")

        user_id = int(user_id_raw)

        phones_raw = data.get("phones", {})
        if not isinstance(phones_raw, dict):
            phones_raw = {}

        phones: Dict[str, PhoneData] = {}
        for phone, phone_dict in phones_raw.items():
            phone_str = str(phone)
            phones[phone_str] = PhoneData.from_dict(phone_dict)

        cards_raw = data.get("cards", {})
        if not isinstance(cards_raw, dict):
            cards_raw = {}

        cards: Dict[str, CardData] = {}
        for card_number, card_dict in cards_raw.items():
            card_number_str = str(card_number)
            cards[card_number_str] = CardData.from_dict(card_dict)

        last_bot_message_id_raw = data.get("last_bot_message_id")
        if last_bot_message_id_raw is None:
            last_bot_message_id: Optional[int] = None
        else:
            try:
                last_bot_message_id = int(last_bot_message_id_raw)
            except (TypeError, ValueError):
                last_bot_message_id = None

        return cls(
            id=user_id,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            username=data.get("username"),
            registration_step=data.get("registration_step"),
            current_phone=data.get("current_phone"),
            last_bot_message_id=last_bot_message_id,
            phones=phones,
            cards=cards,
        )


# ============================================================
# SQLAlchemy ORM models
# ============================================================



Base = declarative_base()


class PaymentMethodType(str, enum.Enum):
    card = "card"
    transfer = "transfer"
    integration = "integration"
    phone = "phone"


class PaymentMethodStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    disabled = "disabled"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    failed = "failed"
    refunded = "refunded"


class DBUser(Base):
    """
    ORM-отображение таблицы tg_lite_bot.users.
    """
    __tablename__ = "users"

    id = Column(MySQLBigInt(unsigned=True), primary_key=True, autoincrement=True)
    tg_user_id = Column(MySQLBigInt(unsigned=True), nullable=False, index=True)
    tg_username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    full_name = Column(String(255))
    phone = Column(String(64))
    language_code = Column(String(8), nullable=False, default="ru")
    # В DDL raw_tg_json имеет тип JSON, здесь для простоты используем Text.
    raw_tg_json = Column(Text)

    # В DDL: NOT NULL DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
    deleted_at = Column(DateTime)
    authorised_at = Column(DateTime)

    payment_methods = relationship(
        "DBUserPaymentMethod",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    sent_payments = relationship(
        "Payment",
        back_populates="specialist",
        foreign_keys="Payment.specialist_id",
    )

    received_payments = relationship(
        "Payment",
        back_populates="client",
        foreign_keys="Payment.client_id",
    )

    templates = relationship(
        "MessageTemplate",
        back_populates="specialist",
    )

    bot_steps = relationship(
        "BotLastStep",
        back_populates="user",
    )

    last_messages = relationship(
        "ChatLastMessage",
        back_populates="user",
    )


class DBUserPaymentMethod(Base):
    """
    ORM-отображение таблицы tg_lite_bot.user_payment_methods.
    """
    __tablename__ = "user_payment_methods"

    id = Column(MySQLBigInt(unsigned=True), primary_key=True, autoincrement=True)
    user_id = Column(
        MySQLBigInt(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    method_type = Column(SAEnum(PaymentMethodType), nullable=False)
    provider = Column(String(32))
    currency = Column(CHAR(3))
    is_primary = Column(Boolean, nullable=False, default=False)
    psp_token = Column(String(255))
    card_brand = Column(String(32))
    pay_method_number = Column(String(64), nullable=False)
    card_exp_month = Column(Integer)
    card_exp_year = Column(Integer)
    status = Column(
        SAEnum(PaymentMethodStatus),
        nullable=False,
        default=PaymentMethodStatus.pending,
    )
    is_active = Column(Boolean, nullable=False, default=True)

    # В DDL: NOT NULL DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP
    added_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    verified_at = Column(DateTime)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    user = relationship("DBUser", back_populates="payment_methods")
    payments = relationship("Payment", back_populates="method")


class Payment(Base):
    """
    ORM-отображение таблицы tg_lite_bot.payments.
    """
    __tablename__ = "payments"

    id = Column(MySQLBigInt(unsigned=True), primary_key=True, autoincrement=True)
    specialist_id = Column(
        MySQLBigInt(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    client_id = Column(
        MySQLBigInt(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="CASCADE"),
    )
    amount_minor = Column(MySQLBigInt(unsigned=True), nullable=False)
    currency = Column(CHAR(3), nullable=False, default="RUR")
    description = Column(Text)
    method_id = Column(
        MySQLBigInt(unsigned=True),
        ForeignKey("user_payment_methods.id"),
        nullable=False,
        default=0,
    )
    status = Column(
        SAEnum(PaymentStatus),
        nullable=False,
        default=PaymentStatus.pending,
    )
    proof_file_id = Column(MySQLBigInt(unsigned=True))
    paid_at = Column(DateTime)

    # В DDL: NOT NULL DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    specialist = relationship(
        "DBUser",
        foreign_keys=[specialist_id],
        back_populates="sent_payments",
    )
    client = relationship(
        "DBUser",
        foreign_keys=[client_id],
        back_populates="received_payments",
    )
    method = relationship("DBUserPaymentMethod", back_populates="payments")


class MessageTemplate(Base):
    """
    ORM-отображение таблицы tg_lite_bot.message_templates.
    """
    __tablename__ = "message_templates"

    id = Column(MySQLBigInt(unsigned=True), primary_key=True, autoincrement=True)
    method_type = Column(SAEnum(PaymentMethodType), nullable=False)
    specialist_id = Column(
        MySQLBigInt(unsigned=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    content_md = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    # В DDL: NOT NULL DEFAULT CURRENT_TIMESTAMP, ON UPDATE CURRENT_TIMESTAMP
    added_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    specialist = relationship("DBUser", back_populates="templates")


class BotLastStep(Base):
    """
    ORM-отображение таблицы tg_lite_bot.bot_last_step.

    В новой версии таблицы дополнительно хранит pay_method_number
    (номер телефона или карты), с которым идёт работа.
    """
    __tablename__ = "bot_last_step"

    user_id = Column(
        MySQLBigInt(unsigned=True),
        ForeignKey("users.id"),
        primary_key=True,
        nullable=False,
    )
    chat_id = Column(MySQLBigInt(unsigned=True), primary_key=True, nullable=False)
    last_step = Column(String(32))
    # В DDL: NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
    pay_method_number = Column(String(64))  # Номер телефона или карты

    user = relationship("DBUser", back_populates="bot_steps")


class ChatLastMessage(Base):
    """
    ORM-отображение таблицы tg_lite_bot.chat_last_message.

    Хранит last_message_id для каждой пары (user_id, chat_id).
    """
    __tablename__ = "chat_last_message"

    user_id = Column(
        MySQLBigInt(unsigned=True),
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        primary_key=True,
        nullable=False,
    )
    chat_id = Column(MySQLBigInt(unsigned=True), primary_key=True, nullable=False)
    # В DDL: NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
    last_message_id = Column(String(100), nullable=False)

    user = relationship("DBUser", back_populates="last_messages")
