# services/bot/handlers/settings/settings_cards.py

"""
Хэндлеры экрана «Настройки банковских карт».

В этом файле ТОЛЬКО обработка коллбэков кнопок ЭТОГО экрана:
    - CARD_SETTINGS_ADD_CALLBACK_DATA    — «Добавить карту»;
    - CARD_SETTINGS_DELETE_CALLBACK_DATA — «Удалить карту»;
    - CARD_SETTINGS_BACK_CALLBACK_DATA   — «Назад» (возврат на основной экран «Настройки»).

Сам показ экрана «Настройки банковских карт» выполняется функцией
send_cards_settings_screen из файла settings_common.py.
"""

from __future__ import annotations                                   # Разрешаем отложенные аннотации типов

from typing import Optional                                          # Optional — тип "может быть None"

from aiogram import F, Router                                                # F — фильтры по полям callback_query
from aiogram.types import (                                          # Типы Telegram-объектов
    CallbackQuery,                                                   # CallbackQuery — ответ на нажатие инлайн-кнопки
    Message,                                                         # Message — обычное сообщение (используем в back)
)
from aiogram.fsm.context import FSMContext                           # Контекст FSM

from .settings import (                                      # Импортируем общий роутер и функцию основного экрана                                                 # Единый роутер для всех экранов настроек
    send_settings_screen,                                            # Функция показа основного экрана «Настройки»
)
from ...keyboards.settings.cards import (                            # Импортируем callback_data экрана карт
    CARD_SETTINGS_ADD_CALLBACK_DATA,                                 # callback_data «Добавить карту»
    CARD_SETTINGS_DELETE_CALLBACK_DATA,                              # callback_data «Удалить карту»
    CARD_SETTINGS_BACK_CALLBACK_DATA,                                # callback_data «Назад»
)

settings_cards_router: Router = Router (
    name="settings_cards"
)


@settings_cards_router.callback_query(                                     # Хэндлер кнопки «Добавить карту»
    F.data == CARD_SETTINGS_ADD_CALLBACK_DATA,                       # Срабатывает, если callback_data == "card_settings:add"
)
async def on_card_settings_add_card_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # Контекст FSM (на будущее — для шага ввода карты)
) -> None:
    """
    Кнопка «Добавить карту» на экране «Настройки банковских карт».

    Пока реализована как заглушка — просто уведомляем пользователя.
    В дальнейшем можно будет:
    - запросить номер карты;
    - привязать банк/платёжную систему;
    - сохранить в JSON.
    """

    await callback.answer("Функция добавления карты пока в разработке.")   # Короткий ответ-заглушка


@settings_cards_router.callback_query(                                     # Хэндлер кнопки «Удалить карту»
    F.data == CARD_SETTINGS_DELETE_CALLBACK_DATA,                    # Срабатывает, если callback_data == "card_settings:delete"
)
async def on_card_settings_delete_card_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # Контекст FSM (на будущее — список карт и выбор)
) -> None:
    """
    Кнопка «Удалить карту» на экране «Настройки банковских карт».

    Пока заглушка. В дальнейшем:
    - показать список карт пользователя;
    - дать выбрать одну;
    - удалить её из БД.
    """

    await callback.answer("Функция удаления карты пока в разработке.")     # Короткое уведомление-заглушка


@settings_cards_router.callback_query(                                     # Хэндлер кнопки «Назад»
    F.data == CARD_SETTINGS_BACK_CALLBACK_DATA,                      # Срабатывает, если callback_data == "card_settings:back"
)
async def on_card_settings_back_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # Контекст FSM пользователя
) -> None:
    """
    Кнопка «Назад» на экране «Настройки банковских карт».

    Возвращает пользователя на ОСНОВНОЙ экран «Настройки».
    """

    await callback.answer()                                          # Закрываем "часики" на кнопке

    message: Optional[Message] = callback.message                    # Сообщение, в котором сейчас экран карт
    if message is None:                                              # Если сообщения нет — нечего редактировать
        return                                                       # Выходим

    # Показываем основной экран «Настройки» (функция из settings_common.py)
    await send_settings_screen(
        message=message,                                             # То же сообщение
        state=state,                                                 # Контекст FSM
    )
