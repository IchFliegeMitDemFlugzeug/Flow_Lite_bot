# services/bot/keyboards/inline_mode/transfer_actions.py

"""
Инлайн-клавиатура под сообщением с реквизитами перевода.

Сейчас:
- одна кнопка "Перевести";
- кнопка ведёт по временной заглушке на поиск "котики" в Google.

Дальше вместо этой заглушки мы подставим реальную ссылку на страницу
с выбором банка / диплинк в приложение и т.п.
"""

from __future__ import annotations                                      # Разрешаем отложенные аннотации типов (удобно для type hints)

from aiogram.types import (                                            # Импортируем нужные типы из aiogram
    InlineKeyboardMarkup,                                              # Класс инлайн-клавиатуры
    InlineKeyboardButton,                                              # Класс кнопки инлайн-клавиатуры
)

from ...texts.inline_mode.inline_results import InlinePaymentOption    # Структура варианта (телефон/карта, банк, сумма)
from ...tools.inline_mode.query_parser import ParsedInlineQuery        # Результат парсинга inline-запроса (сумма, банки и т.п.)


def build_transfer_actions_keyboard(
    *,                                                                  # Обязываем передавать аргументы только по имени (keyword-only)
    option: InlinePaymentOption,                                        # Вариант реквизита, который выбрал пользователь (телефон/карта)
    parsed_query: ParsedInlineQuery,                                    # Результат разбора inline-запроса (сумма, список банков, raw-текст)
) -> InlineKeyboardMarkup:
    """
    Строим инлайн-клавиатуру под сообщением с реквизитами.

    Пока делаем простую заглушку:
    - одна кнопка "Перевести";
    - ведёт на поисковый запрос "котики" в Google.

    Параметры:
        option       — выбранный вариант реквизита (на будущее, когда будем делать реальные диплинки);
        parsed_query — разобранный запрос (также пригодится для реальных ссылок).

    Возвращаем:
        InlineKeyboardMarkup — готовую инлайн-клавиатуру, которую можно передать в reply_markup.
    """

    # ВРЕМЕННАЯ ЗАГЛУШКА: ссылка на поиск "котики" в Google
    placeholder_url: str = "https://www.google.com/search?q=%D0%BA%D0%BE%D1%82%D0%B8%D0%BA%D0%B8"  # URL с запросом "котики" в адресной строке

    # Создаём одну кнопку инлайн-клавиатуры
    transfer_button: InlineKeyboardButton = InlineKeyboardButton(      # Описываем кнопку
        text="✅ Перевести",                                              # Надпись на кнопке, которую увидит пользователь
        url=placeholder_url,                                           # Куда перейдёт пользователь при нажатии (пока заглушка)
        # В будущем вместо url мы можем использовать callback_data или диплинк,
        # в зависимости от того, как будет реализован сценарий.
    )

    # Формируем разметку клавиатуры из ОДНОЙ строки с ОДНОЙ кнопкой
    keyboard: InlineKeyboardMarkup = InlineKeyboardMarkup(             # Создаём объект инлайн-клавиатуры
        inline_keyboard=[                                              # Параметр inline_keyboard принимает список строк (row), каждая строка — список кнопок
            [transfer_button],                                         # Одна строка, в ней одна кнопка "Перевести"
        ]
    )

    return keyboard                                                    # Возвращаем готовую клавиатуру, чтобы прикрепить её к сообщению
