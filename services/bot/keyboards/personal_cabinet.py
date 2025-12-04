# services/bot/keyboards/personal_cabinet.py

"""
Клавиатуры для экрана «Личный кабинет».
"""

from aiogram.types import (                # Импортируем нужные типы из aiogram.types
    InlineKeyboardMarkup,                  # InlineKeyboardMarkup — объект инлайн-клавиатуры
    InlineKeyboardButton,                  # InlineKeyboardButton — отдельная инлайн-кнопка
)


def build_personal_cabinet_keyboard(show_details: bool) -> InlineKeyboardMarkup:
    """
    Строим инлайн-клавиатуру для экрана личного кабинета.

    Требования:
    - по одной кнопке в строке;
    - добавлена кнопка «Показать реквизиты» / «Скрыть реквизиты»
      (текст зависит от текущего состояния show_details).

    Структура клавиатуры:

    [ Показать реквизиты / Скрыть реквизиты ]
    [ Настройки ]
    [ Квитанции ]
    [ Информация ]
    """

    # В зависимости от текущего состояния выбираем текст кнопки
    toggle_text: str = "Скрыть реквизиты" if show_details else "Показать реквизиты"

    # Кнопка переключения видимости реквизитов
    toggle_button: InlineKeyboardButton = InlineKeyboardButton(
        text=toggle_text,                  # Текст кнопки (Показать/Скрыть реквизиты)
        callback_data="lk:toggle_details", # Служебная строка, по которой хэндлер поймёт, что нажали именно эту кнопку
    )

    # Кнопка «Настройки»
    settings_button: InlineKeyboardButton = InlineKeyboardButton(
        text="Настройки",                  # Текст на кнопке "Настройки"
        callback_data="lk:settings",       # callback_data для обработки нажатия
    )

    # Кнопка «Квитанции»
    # receipts_button: InlineKeyboardButton = InlineKeyboardButton(
    #     text="Квитанции",                  # Текст на кнопке "Квитанции"
    #     callback_data="lk:receipts",       # callback_data для обработки нажатия
    # )

    # Кнопка «Информация»
    info_button: InlineKeyboardButton = InlineKeyboardButton(
        text="Информация",                 # Текст на кнопке "Информация"
        callback_data="lk:info",           # callback_data для обработки нажатия
    )

    # Формируем клавиатуру: по одной кнопке в строке.
    keyboard: InlineKeyboardMarkup = InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle_button],               # Первая строка: кнопка "Показать/Скрыть реквизиты"
            [settings_button],             # Вторая строка: "Настройки"
            # [receipts_button],             # Третья строка: "Квитанции"
            [info_button],                 # Четвёртая строка: "Информация"
        ]
    )

    return keyboard                       # Возвращаем готовую инлайн-клавиатуру
