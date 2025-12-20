# services/bot/keyboards/inline_mode/transfer_actions.py

"""
Инлайн-клавиатура под сообщением с реквизитами перевода.

Требование из твоего сценария:
- В инлайн-сообщении нужна ОДНА обычная URL-кнопка.
- Кнопка должна открывать DIRECT LINK Mini App вида:
    https://t.me/<botusername>/<appname>?startapp=<token>

Что это даёт:
- Mini App запускается по ссылке в ЛЮБОМ чате.
- Mini App получает initData (контекст/данные) и tgWebAppStartParam (startapp-токен).

Важно понимать ограничение:
- По нажатию URL-кнопки бот НЕ получает CallbackQuery.
  Если нужно узнавать «кто нажал» именно на стороне бота —
  тогда нельзя использовать URL-кнопку, нужен callback_data.
"""

from __future__ import annotations                                      # Разрешаем отложенные аннотации типов (удобно для type hints)

from urllib.parse import quote                                          # quote — безопасно кодируем startapp параметр для URL

from aiogram.types import (                                             # Импортируем нужные типы из aiogram
    InlineKeyboardMarkup,                                               # Класс инлайн-клавиатуры (то, что вернём наружу)
    InlineKeyboardButton,                                               # Класс кнопки инлайн-клавиатуры (внутри клавиатуры)
)

from ...texts.inline_mode.inline_results import InlinePaymentOption     # Структура варианта (телефон/карта, банк, сумма)
from ...tools.inline_mode.query_parser import ParsedInlineQuery         # Результат парсинга inline-запроса (сумма, банки и т.п.)


# ---------------------------------------------------------------------
# НАСТРОЙКИ DIRECT LINK Mini App (зашиваем ссылки в код)
# ---------------------------------------------------------------------

# 1) Username твоего бота БЕЗ @.
#    Пример: если бот @my_payflow_bot, то тут должно быть "my_payflow_bot".
BOT_USERNAME: str = "flow_lite_robot"                    # TODO: замени на реальный username бота

# 2) Короткое имя Mini App (appname / short name), которое ты задаёшь в BotFather при создании Mini App.
#    Оно участвует в URL как второй сегмент пути: https://t.me/<botusername>/<appname>
MINI_APP_SHORT_NAME: str = "choose_banks"          # TODO: замени на реальный short name Mini App

# 3) Шаблон прямой ссылки на Mini App.
#    Telegram ожидает именно такой формат для direct link Mini App.
MINI_APP_DIRECT_LINK_TEMPLATE: str = "https://t.me/{bot}/{app}?startapp={startapp}"  # Строка-шаблон для финального URL


def _build_mini_app_direct_link(*, startapp_token: str) -> str:
    """ 
    Собираем прямую ссылку на Mini App (direct link).

    Параметры:
        startapp_token — тот самый токен, который ты хочешь передать в Mini App.
                        Он попадёт в tgWebAppStartParam внутри Mini App.

    Возвращаем:
        Готовую строку URL вида:
            https://t.me/<botusername>/<appname>?startapp=<token>
    """

    # Кодируем токен для URL.
    # Даже если token уже url-safe (например, secrets.token_urlsafe),
    # quote — дополнительная защита от пробелов/символов (на всякий случай).
    encoded_token: str = quote(startapp_token or "", safe="")           # safe="" означает: кодируем всё потенциально опасное

    # Подставляем bot/app/token в шаблон и возвращаем финальную ссылку.
    return MINI_APP_DIRECT_LINK_TEMPLATE.format(                         # Формируем строку по шаблону
        bot=BOT_USERNAME,                                                # Подставляем username бота
        app=MINI_APP_SHORT_NAME,                                         # Подставляем short name Mini App
        startapp=encoded_token,                                          # Подставляем закодированный startapp токен
    )


def build_transfer_actions_keyboard(
    *,                                                                   # Обязываем передавать аргументы только по имени (keyword-only)
    transfer_id: str,                                                    # Уникальный токен операции (он же startapp параметр)
    option: InlinePaymentOption,                                         # Вариант реквизита (пока не используем, но оставляем для расширения)
    parsed_query: ParsedInlineQuery,                                     # Результат разбора inline-запроса (пока не используем, но оставляем)
) -> InlineKeyboardMarkup:
    """
    Строим инлайн-клавиатуру под сообщением с реквизитами.

    Реализация для твоего сценария:
    - Кнопка — обычная URL-кнопка.
    - URL — direct link Mini App с параметром startapp=<transfer_id>.

    Возвращаем:
        InlineKeyboardMarkup — готовая инлайн-клавиатура.
    """

    # Собираем ссылку на Mini App, в которую передаём наш transfer_id.
    # В Mini App это будет доступно как tgWebAppStartParam.
    mini_app_url: str = _build_mini_app_direct_link(                     # Вызываем нашу сборку ссылки
        startapp_token=transfer_id,                                      # Передаём токен операции
    )

    # Создаём кнопку.
    # ВАЖНО: у кнопки должен быть ровно ОДИН тип действия.
    # Здесь это URL-кнопка, поэтому используем поле url=...
    transfer_button: InlineKeyboardButton = InlineKeyboardButton(        # Создаём объект кнопки
        text="☑ Перейти к оплате",                                      # Текст на кнопке (можешь переименовать)
        url=mini_app_url,                                                # Ссылка на Mini App (direct link)
    )

    # Собираем клавиатуру из одной строки с одной кнопкой.
    keyboard: InlineKeyboardMarkup = InlineKeyboardMarkup(               # Создаём объект клавиатуры
        inline_keyboard=[                                                # inline_keyboard — список строк
            [transfer_button],                                           # Одна строка, в ней одна кнопка
        ],
    )

    return keyboard                                                      # Возвращаем готовую клавиатуру
