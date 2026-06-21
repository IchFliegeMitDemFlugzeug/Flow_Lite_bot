# services/bot/keyboards/settings/cards.py

"""
Инлайн-клавиатура для экрана «Настройки банковских карт».

Кнопки (по одной в строке):
- «Добавить карту»
- «Удалить карту»
- «Назад» (возврат на общий экран «Настройки»).
"""

from __future__ import annotations                                   # Разрешаем отложенные аннотации типов

from aiogram.types import InlineKeyboardMarkup                       # Тип итоговой инлайн-клавиатуры
from aiogram.utils.keyboard import InlineKeyboardBuilder             # "Строитель" для последовательного добавления кнопок


# --- Константы callback_data для кнопок экрана «Настройки карт» --- #

CARD_SETTINGS_ADD_CALLBACK_DATA: str = "card_settings:add"           # Callback для кнопки «Добавить карту»
CARD_SETTINGS_DELETE_CALLBACK_DATA: str = "card_settings:delete"     # Callback для кнопки «Удалить карту»
CARD_SETTINGS_BACK_CALLBACK_DATA: str = "card_settings:back"         # Callback для кнопки «Назад» (в общие настройки)
CARD_SETTINGS_SAVE_CALLBACK_DATA: str = "card_settings:save"         # Callback для сохранения введённой карты
CARD_SETTINGS_RETRY_CALLBACK_DATA: str = "card_settings:retry"       # Callback для повторного ввода карты


def build_cards_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Построить инлайн-клавиатуру для экрана «Настройки банковских карт».

    Раскладка:
    [Добавить карту]
    [Удалить карту]
    [Назад]
    """

    builder: InlineKeyboardBuilder = InlineKeyboardBuilder()         # Создаём объект-строитель инлайн-клавиатуры

    # --- Кнопка «Добавить карту» --- #
    builder.button(                                                  # Добавляем первую кнопку
        text="➕ Добавить карту",                                       # Текст на кнопке
        callback_data=CARD_SETTINGS_ADD_CALLBACK_DATA,               # callback_data, прилетит в callback_query.data
    )

    # --- Кнопка «Удалить карту» --- #
    builder.button(                                                  # Добавляем вторую кнопку
        text="✖ Удалить карту",                                        # Текст на кнопке
        callback_data=CARD_SETTINGS_DELETE_CALLBACK_DATA,            # callback_data для удаления карты
    )

    # --- Кнопка «Назад» --- #
    builder.button(                                                  # Добавляем третью кнопку
        text="🔙 Назад",                                                # Текст на кнопке
        callback_data=CARD_SETTINGS_BACK_CALLBACK_DATA,              # callback_data для возврата на общий экран настроек
    )

    builder.adjust(1)                                                # Все кнопки идут по одной в каждой строке

    keyboard: InlineKeyboardMarkup = builder.as_markup()             # Преобразуем билдер в объект InlineKeyboardMarkup

    return keyboard                                                  # Возвращаем готовую инлайн-клавиатуру


def build_add_card_confirm_keyboard() -> InlineKeyboardMarkup:
    """Построить клавиатуру подтверждения добавления карты."""

    builder: InlineKeyboardBuilder = InlineKeyboardBuilder()         # Создаём билдер для кнопок подтверждения
    builder.button(                                                  # Кнопка сохраняет карту после проверки пользователем
        text="✅ Добавить карту",                                   # Текст кнопки сохранения
        callback_data=CARD_SETTINGS_SAVE_CALLBACK_DATA,              # Callback сохранения карты
    )
    builder.button(                                                  # Кнопка позволяет заново ввести номер
        text="✏️ Ввести заново",                                    # Текст кнопки повтора
        callback_data=CARD_SETTINGS_RETRY_CALLBACK_DATA,             # Callback повторного ввода
    )
    builder.button(                                                  # Кнопка возвращает пользователя к списку карт
        text="🔙 Назад",                                            # Текст кнопки назад
        callback_data=CARD_SETTINGS_BACK_CALLBACK_DATA,              # Callback назад
    )
    builder.adjust(1)                                                # Раскладываем по одной кнопке в строке
    return builder.as_markup()                                      # Возвращаем готовую клавиатуру
