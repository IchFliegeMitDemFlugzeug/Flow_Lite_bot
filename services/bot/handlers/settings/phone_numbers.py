# services/bot/handlers/settings/settings_phone_numbers.py

"""
Хэндлеры экрана «Настройки номеров телефонов».

В этом файле ТОЛЬКО обработка коллбэков кнопок ЭТОГО экрана:
    - PHONE_SETTINGS_ADD_CALLBACK_DATA       — «Добавить номер»;
    - PHONE_SETTINGS_DELETE_CALLBACK_DATA    — «Удалить номер»;
    - PHONE_SETTINGS_BANKS_CALLBACK_DATA     — «Удалить/добавить банк к номеру»;
    - PHONE_SETTINGS_MAIN_BANK_CALLBACK_DATA — «Выбрать основной банк для номера»;
    - PHONE_SETTINGS_BACK_CALLBACK_DATA      — «Назад» (возврат на основной экран «Настройки»).

Сам показ экрана «Настройки номеров телефонов» выполняется функцией
send_phone_numbers_settings_screen из файла settings_common.py.
"""

from __future__ import annotations                                   # Разрешаем отложенные аннотации типов

from typing import Optional                                          # Optional — тип "может быть None"

from aiogram import F, Router                                                # F — фильтры по полям апдейта
from aiogram.types import (                                          # Типы Telegram-объектов
    CallbackQuery,                                                   # CallbackQuery — ответ на нажатие инлайн-кнопки
    Message,                                                         # Message — обычное сообщение (используем только в back)
)
from aiogram.fsm.context import FSMContext                           # Контекст FSM

from .settings import (                                      # Импортируем общий роутер и функцию основного экрана                                                 # Единый роутер для всех настроек
    send_settings_screen,                                            # Функция показа основного экрана «Настройки»
)
from ...keyboards.settings.phone_numbers import (                    # Импортируем callback_data для экрана телефонов
    PHONE_SETTINGS_ADD_CALLBACK_DATA,                                # callback_data «Добавить номер»
    PHONE_SETTINGS_DELETE_CALLBACK_DATA,                             # callback_data «Удалить номер»
    PHONE_SETTINGS_BANKS_CALLBACK_DATA,  # (если у тебя другое имя — поправь)
    PHONE_SETTINGS_MAIN_BANK_CALLBACK_DATA,                          # callback_data «Выбрать основной банк для номера»
    PHONE_SETTINGS_BACK_CALLBACK_DATA,                               # callback_data «Назад»
)

# ВНИМАНИЕ: если в твоём коде константа называется не PHONE_SETTINGS_BANK_CALLBACK_DATA,
# а, как мы писали раньше, PHONE_SETTINGS_BANKS_CALLBACK_DATA — просто приведи имя к одному варианту.
# Здесь я использую PHONE_SETTINGS_BANKS_CALLBACK_DATA. Если у тебя уже есть другая константа —
# замени import на правильный (чтобы совпадало с keys-файлом).

settings_phone_numbers_router: Router = Router(                                    # Создаём экземпляр роутера
    name="settings_phone_numbers",                                                 # Имя роутера (удобно для логирования/отладки)
)

@settings_phone_numbers_router.callback_query(                                     # Хэндлер кнопки «Добавить номер»
    F.data == PHONE_SETTINGS_ADD_CALLBACK_DATA,                      # Срабатывает, если callback_data == "phone_settings:add"
)
async def on_phone_settings_add_number_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # Контекст FSM (пока не используем, но оставляем)
) -> None:
    """
    Кнопка «Добавить номер» на экране «Настройки номеров телефонов».

    Пока реализована как заглушка — просто показываем пользователю короткое сообщение.
    В будущем сюда можно подвязать FSM для ввода нового номера телефона.
    """

    await callback.answer("Функция добавления номера пока в разработке.")  # Уведомляем пользователя и закрываем "часики"


@settings_phone_numbers_router.callback_query(                                     # Хэндлер кнопки «Удалить номер»
    F.data == PHONE_SETTINGS_DELETE_CALLBACK_DATA,                   # Срабатывает, если callback_data == "phone_settings:delete"
)
async def on_phone_settings_delete_number_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # Контекст FSM (на будущее)
) -> None:
    """
    Кнопка «Удалить номер» на экране «Настройки номеров телефонов».

    Пока это заглушка. В дальнейшем можно реализовать:
    - выбор номера из списка;
    - подтверждение удаления;
    - обновление БД.
    """

    await callback.answer("Функция удаления номера пока в разработке.")    # Короткий ответ-заглушка


@settings_phone_numbers_router.callback_query(                                     # Хэндлер кнопки «Удалить/добавить банк к номеру»
    F.data == PHONE_SETTINGS_BANKS_CALLBACK_DATA,                    # Срабатывает, если callback_data == "phone_settings:banks"
)
async def on_phone_settings_manage_banks_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # Контекст FSM (на будущее)
) -> None:
    """
    Кнопка «Удалить/добавить банк к номеру» на экране «Настройки номеров телефонов».

    Пока заглушка. Потом можно будет:
    - выбрать номер телефона;
    - показать список его банков;
    - дать удалить/добавить банки.
    """

    await callback.answer("Управление банками номера пока в разработке.")  # Сообщаем, что функционал пока не готов


@settings_phone_numbers_router.callback_query(                                     # Хэндлер кнопки «Выбрать основной банк для номера»
    F.data == PHONE_SETTINGS_MAIN_BANK_CALLBACK_DATA,                # Фильтр по callback_data == "phone_settings:main_bank"
)
async def on_phone_settings_choose_main_bank_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # Контекст FSM (на будущее)
) -> None:
    """
    Кнопка «Выбрать основной банк для номера» на экране «Настройки номеров телефонов».

    Пока заглушка. В дальнейшем можно реализовать:
    - выбор номера телефона;
    - выбор банка из списка привязанных к этому номеру;
    - запись выбранного банка как "основного".
    """

    await callback.answer("Выбор основного банка пока в разработке.")      # Короткий ответ-заглушка


@settings_phone_numbers_router.callback_query(                                     # Хэндлер кнопки «Назад»
    F.data == PHONE_SETTINGS_BACK_CALLBACK_DATA,                     # Фильтр по callback_data == "phone_settings:back"
)
async def on_phone_settings_back_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # Контекст FSM пользователя
) -> None:
    """
    Кнопка «Назад» на экране «Настройки номеров телефонов».

    Должна вернуть пользователя на ОСНОВНОЙ экран «Настройки».
    """

    await callback.answer()                                          # Закрываем "часики" на кнопке

    message: Optional[Message] = callback.message                    # Берём текущее сообщение (где сейчас экран телефонов)
    if message is None:                                              # Если сообщения нет — нечего редактировать
        return                                                       # Тихо выходим

    # Показываем основной экран «Настройки» (функция из settings_common.py)
    await send_settings_screen(
        message=message,                                             # То же сообщение
        state=state,                                                 # Контекст FSM
    )
