# services/bot/handlers/settings/settings_cards.py

"""Хэндлеры экрана «Настройки банковских карт»."""

from __future__ import annotations

from typing import Optional

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from .settings import send_cards_settings_screen, send_settings_screen
from ...database import add_or_update_card
from ...headlines.add_headline import edit_message_with_headline, HEADLINE_SETTINGS_CARDS
from ...keyboards.settings.cards import (
    CARD_SETTINGS_ADD_CALLBACK_DATA,
    CARD_SETTINGS_BACK_CALLBACK_DATA,
    CARD_SETTINGS_DELETE_CALLBACK_DATA,
    CARD_SETTINGS_RETRY_CALLBACK_DATA,
    CARD_SETTINGS_SAVE_CALLBACK_DATA,
    build_add_card_confirm_keyboard,
)
from ...states.settings.settings import SettingsStates
from ...texts.settings.cards import (
    build_add_card_enter_number_text,
    build_add_card_invalid_number_text,
    build_add_card_saved_text,
    build_add_card_verification_text,
)
from ...tools.bin_lookup import detect_card_bin

settings_cards_router: Router = Router(name="settings_cards")


def _card_title(card_info: dict) -> str:
    """Берём человекочитаемое название банка из результата BIN-проверки."""
    return str(card_info.get("bank_name") or card_info.get("bank_id") or "банк не определён")


def _payment_system_title(card_info: dict) -> str:
    """Красиво подписываем платёжную систему для сообщений пользователю."""
    titles = {"mir": "МИР", "visa": "Visa", "mastercard": "Mastercard", "unionpay": "UnionPay", "amex": "AmEx", "jcb": "JCB"}
    return titles.get(str(card_info.get("payment_system") or "").lower(), "не определена")


@settings_cards_router.callback_query(F.data == CARD_SETTINGS_ADD_CALLBACK_DATA)
async def on_card_settings_add_card_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Запускаем сценарий добавления карты вместо прежней заглушки."""
    await callback.answer()
    message: Optional[Message] = callback.message
    if message is None:
        return
    await edit_message_with_headline(
        message=message,
        text=build_add_card_enter_number_text(),
        headline_type=HEADLINE_SETTINGS_CARDS,
        reply_markup=None,
        parse_mode="Markdown",
    )
    await state.set_state(SettingsStates.waiting_for_card_number)


@settings_cards_router.message(SettingsStates.waiting_for_card_number)
async def on_card_number_entered(message: Message, state: FSMContext) -> None:
    """Принимаем номер карты, проверяем Луна/BIN и показываем безопасное подтверждение."""
    raw_card_number = message.text or ""
    card_info = detect_card_bin(raw_card_number)
    if not card_info.get("ok"):
        await message.answer(build_add_card_invalid_number_text(), parse_mode="Markdown")
        return
    await state.update_data(pending_card_number=raw_card_number, pending_card_info=card_info)
    await message.answer(
        build_add_card_verification_text(
            bank_title=_card_title(card_info),
            payment_system=_payment_system_title(card_info),
            masked_card=str(card_info.get("masked") or "****"),
        ),
        reply_markup=build_add_card_confirm_keyboard(),
        parse_mode="Markdown",
    )


@settings_cards_router.callback_query(F.data == CARD_SETTINGS_RETRY_CALLBACK_DATA)
async def on_card_settings_retry_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Возвращаем пользователя к повторному вводу номера карты."""
    await callback.answer()
    await state.update_data(pending_card_number=None, pending_card_info=None)
    message: Optional[Message] = callback.message
    if message is None:
        return
    await edit_message_with_headline(
        message=message,
        text=build_add_card_enter_number_text(),
        headline_type=HEADLINE_SETTINGS_CARDS,
        reply_markup=None,
        parse_mode="Markdown",
    )
    await state.set_state(SettingsStates.waiting_for_card_number)


@settings_cards_router.callback_query(F.data == CARD_SETTINGS_SAVE_CALLBACK_DATA)
async def on_card_settings_save_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняем подтверждённую карту в БД проекта."""
    await callback.answer()
    data = await state.get_data()
    card_number = str(data.get("pending_card_number") or "").strip()
    card_info = data.get("pending_card_info") or {}
    if not card_number or not card_info.get("ok"):
        await callback.answer("Сначала отправьте корректный номер карты.", show_alert=True)
        return
    await add_or_update_card(
        user_id=callback.from_user.id,
        card_number=card_number,
        bank=str(card_info.get("bank_id") or "") or None,
        payment_system=_payment_system_title(card_info),
    )
    await state.update_data(pending_card_number=None, pending_card_info=None)
    await state.set_state(SettingsStates.setting_state)
    message: Optional[Message] = callback.message
    if message is None:
        return
    await edit_message_with_headline(
        message=message,
        text=build_add_card_saved_text(
            bank_title=_card_title(card_info),
            payment_system=_payment_system_title(card_info),
            masked_card=str(card_info.get("masked") or "****"),
        ),
        headline_type=HEADLINE_SETTINGS_CARDS,
        reply_markup=None,
        parse_mode="Markdown",
    )


@settings_cards_router.callback_query(F.data == CARD_SETTINGS_DELETE_CALLBACK_DATA)
async def on_card_settings_delete_card_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Заглушка удаления карты пока оставлена без изменений."""
    await callback.answer("Функция удаления карты пока в разработке.")


@settings_cards_router.callback_query(F.data == CARD_SETTINGS_BACK_CALLBACK_DATA)
async def on_card_settings_back_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка «Назад» возвращает пользователя на экран настроек карт или общих настроек."""
    await callback.answer()
    message: Optional[Message] = callback.message
    if message is None:
        return
    current_state = await state.get_state()
    if current_state == SettingsStates.waiting_for_card_number.state:
        await send_cards_settings_screen(message=message, state=state)
        return
    await send_settings_screen(message=message, state=state)
