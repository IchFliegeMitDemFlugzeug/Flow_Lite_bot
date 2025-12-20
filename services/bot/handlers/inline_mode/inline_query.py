# services/bot/handlers/inline_mode/inline_query.py

""" 
Хэндлер обработки INLINE-запросов (то, что юзер вводит после @botusername).

Текущая реализация под ТВОЙ сценарий:
- В инлайн-сообщение мы ставим ОДНУ обычную URL-кнопку.
- URL ведёт не на внешний сайт, а на DIRECT LINK Mini App:
    https://t.me/<botusername>/<appname>?startapp=<token>

Почему так:
- В inline-сообщениях Telegram запрещает кнопки типа web_app (BUTTON_TYPE_INVALID),
  но обычные url-кнопки разрешены.
- По нажатию url-кнопки бот НЕ получает CallbackQuery (то есть бот не узнаёт, кто нажал).
  Зато сама Mini App получает initData (контекст/данные) + tgWebAppStartParam,
  который равен значению startapp (token) из ссылки.

Важное следствие:
- Если тебе нужно "узнать, кто нажал" именно на стороне бота — это ДРУГОЙ сценарий
  (там нужен callback_data). В этом файле мы делаем именно то, что ты описал: url -> Mini App.
"""

from __future__ import annotations                           # Разрешаем отложенные аннотации типов (удобно для type hints)

from typing import Dict, List, Tuple                          # Dict/List/Tuple — для типизации кэша и списков результатов

import secrets                                                # secrets — безопасная генерация токенов startapp/transfer_id
import time                                                   # time — таймстемпы для TTL и очистки кэша

from aiogram import Router                                    # Router — роутер для inline-логики
from aiogram.types import (                                   # Нужные типы aiogram
    InlineQuery,                                              # InlineQuery — входящий inline-запрос
    InlineQueryResultArticle,                                 # Результат-статья для списка подсказок
    InputTextMessageContent,                                  # Контент сообщения, который улетит в чат
)

from bot.database import get_user                             # Получение доменной модели пользователя из БД

from bot.tools.inline_mode.query_parser import (              # Парсер текста inline-запроса
    parse_inline_query,                                       # Функция парсинга
    ParsedInlineQuery,                                        # Структура результата парсинга
)
from bot.texts.inline_mode.inline_results import (            # Генерация вариантов в списке подсказок
    build_inline_payment_options,                             # Собирает варианты (телефоны/карты) под запрос
    build_bank_not_client_error_text,                         # Строит "Вы не клиент этого банка"
    InlinePaymentOption,                                      # Структура одного варианта
)
from bot.texts.inline_mode.transfer_message import (          # Текст сообщения с реквизитами
    build_transfer_message_text,                              # Сборка текста сообщения
)

from ...keyboards.inline_mode.transfer_actions import (       # Клавиатура под сообщением
    build_transfer_actions_keyboard,                          # Сборщик клавиатуры (URL -> t.me/<bot>/<app>?startapp=<token>)
)


# ------------------------------
# In-memory кэш контекста переводов (MVP)
# ------------------------------

# TTL записи в кэше: 6 часов.
# Зачем кэш нужен теперь, если мы убрали callback?
# - Он всё равно полезен: token (startapp) в Mini App можно отправить на твой backend,
#   а backend сможет сопоставить token -> (option/parsed/raw_query/creator_user_id) по этому кэшу.
_TRANSFER_TTL_SECONDS: int = 60 * 60 * 6

# Формат кэша:
# transfer_id -> (created_at_ts, option, parsed, raw_query, creator_user_id)
_TRANSFER_CACHE: Dict[str, Tuple[float, InlinePaymentOption, ParsedInlineQuery, str, int]] = {}


def _cleanup_transfer_cache(*, now_ts: float) -> None:
    """Очищаем кэш от протухших записей, чтобы память не росла бесконечно."""

    to_delete: List[str] = []                                   # Собираем ключи на удаление отдельным списком

    for transfer_id, (created_at, _, _, _, _) in _TRANSFER_CACHE.items():  # Перебираем все записи кэша
        if now_ts - created_at > _TRANSFER_TTL_SECONDS:          # Если запись старше TTL
            to_delete.append(transfer_id)                        # Помечаем на удаление

    for transfer_id in to_delete:                                # Проходим по ключам на удаление
        _TRANSFER_CACHE.pop(transfer_id, None)                   # Удаляем безопасно (если уже удалено — ок)


def _register_transfer_context(
    *,
    option: InlinePaymentOption,
    parsed: ParsedInlineQuery,
    raw_query: str,
    creator_user_id: int,
) -> str:
    """ 
    Регистрируем контекст "операции" и возвращаем одноразовый token,
    который будет вшит в direct link как startapp=<token>.

    Примечание:
    - token должен быть коротким и URL-safe.
    - Все детали держим на сервере (в этом кэше / в БД), а в ссылку кладём только token.
    """

    now_ts: float = time.time()                                  # Берём текущее время (UNIX timestamp)

    _cleanup_transfer_cache(now_ts=now_ts)                       # Чистим старые записи

    transfer_id: str = secrets.token_urlsafe(16)                 # Генерируем URL-safe токен (~22 символа)

    _TRANSFER_CACHE[transfer_id] = (                             # Сохраняем в кэш все нужные данные
        now_ts,                                                  # 1) время создания
        option,                                                  # 2) выбранные реквизиты
        parsed,                                                  # 3) распознанный контекст (сумма/банк)
        raw_query,                                               # 4) исходный текст inline-запроса
        creator_user_id,                                         # 5) кто формировал inline-результат (кто вводил @bot)
    )

    return transfer_id                                           # Возвращаем token (его и кладём в startapp)


# ------------------------------
# Роутер inline-режима
# ------------------------------

inline_mode_router: Router = Router(                             # Создаём роутер
    name="inline_mode",                                          # Имя роутера (удобно в логах)
)


def _build_inline_article(
    *,
    option: InlinePaymentOption,
    parsed: ParsedInlineQuery,
    raw_query: str,
    creator_user_id: int,
) -> InlineQueryResultArticle:
    """Строим InlineQueryResultArticle из нашего варианта реквизитов."""

    transfer_id: str = _register_transfer_context(               # Регистрируем контекст и получаем token
        option=option,                                           # Передаём вариант реквизитов
        parsed=parsed,                                           # Передаём распарсенный запрос
        raw_query=raw_query,                                     # Передаём сырой текст
        creator_user_id=creator_user_id,                         # Передаём ID автора результата (кто вводил @bot)
    )

    message_text: str = build_transfer_message_text(             # Собираем текст сообщения с реквизитами
        option=option,                                           # На основе выбранного варианта
        parsed_query=parsed,                                     # И распознанного контекста (сумма/банк)
    )

    input_content: InputTextMessageContent = InputTextMessageContent(  # Оборачиваем текст в “контент сообщения”
        message_text=message_text,                               # Текст, который отправится в чат
        parse_mode="Markdown",                                   # Разрешаем Markdown
    )

    reply_markup = build_transfer_actions_keyboard(              # Строим клавиатуру под сообщением
        transfer_id=transfer_id,                                 # ВАЖНО: это будет startapp=<token>
        option=option,                                           # Оставляем (может пригодиться позже)
        parsed_query=parsed,                                     # Оставляем (может пригодиться позже)
    )

    article: InlineQueryResultArticle = InlineQueryResultArticle( # Собираем элемент “зелёного списка”
        id=transfer_id,                                          # Делаем id результата = token (уникально)
        title=option.title,                                      # Заголовок (жирный)
        description=option.description,                          # Описание (серым)
        input_message_content=input_content,                     # Контент сообщения в чат
        reply_markup=reply_markup,                               # Клавиатура с URL-кнопкой на Mini App
    )

    return article                                               # Возвращаем готовый результат


@inline_mode_router.inline_query()                               # Ловим все inline-запросы бота
async def handle_inline_query(inline_query: InlineQuery) -> None: # Главный хэндлер INLINE-режима

    raw_query: str = inline_query.query or ""                    # Берём текст после @bot (или "")

    parsed: ParsedInlineQuery = parse_inline_query(              # Парсим сумму/банк и т.п.
        raw_query=raw_query,                                     # Передаём сырой текст
    )

    user = get_user(                                             # Получаем пользователя из БД
        user_id=inline_query.from_user.id,                       # ID пользователя из Telegram
    )

    payment_options: List[InlinePaymentOption] = build_inline_payment_options(  # Генерируем варианты (телефоны/карты)
        user=user,                                               # Доменная модель пользователя
        parsed_query=parsed,                                     # Контекст запроса
    )

    results: List[InlineQueryResultArticle] = []                 # Сюда положим результаты ответа

    if payment_options:                                          # Если варианты есть
        for option in payment_options:                           # Перебираем каждый вариант
            article: InlineQueryResultArticle = _build_inline_article(
                option=option,                                   # Текущий вариант
                parsed=parsed,                                   # Общий контекст парсинга
                raw_query=raw_query,                             # Сырой текст
                creator_user_id=inline_query.from_user.id,       # Кто формировал inline-результат
            )
            results.append(article)                              # Добавляем в список

    else:
        # Если вариантов нет, но пользователь ввёл банк — покажем "Вы не клиент такого банка".
        if parsed.bank_code or parsed.bank_candidate:
            from ...tools.banks_wordbook import BANKS            # Локальный импорт словаря банков

            bank_title: str                                      # Человекочитаемое название банка

            if parsed.bank_code and parsed.bank_code in BANKS:   # Если банк распознан по коду
                bank = BANKS[parsed.bank_code]                   # Достаём запись банка
                bank_title = (                                   # Выбираем лучшее поле для отображения
                    bank.get("button_title")                     # Короткое название
                    or bank.get("message_title")                 # Или длинное
                    or parsed.bank_candidate                     # Или то, что ввёл юзер
                    or "этого банка"                             # Фолбэк
                )
            else:
                bank_title = parsed.bank_candidate or "этого банка"  # Если не распознали — используем ввод юзера

            error_text = build_bank_not_client_error_text(       # Строим текст ошибки
                bank_name=bank_title,                            # Подставляем банк
            )

            error_message_content: InputTextMessageContent = InputTextMessageContent(  # Контент ошибки
                message_text=f"{error_text.title}\n\n{error_text.description}",        # Заголовок + пояснение
            )

            error_article: InlineQueryResultArticle = InlineQueryResultArticle(        # Один результат-ошибка
                id="bank_not_client",                            # Фиксированный id
                title=error_text.title,                          # Заголовок
                description=error_text.description,              # Описание
                input_message_content=error_message_content,     # Контент
            )

            results.append(error_article)                        # Добавляем ошибку в ответ

    await inline_query.answer(                                   # Отвечаем Telegram списком подсказок
        results=results,                                         # Список результатов
        cache_time=0,                                            # Без кэша (удобно для разработки)
        is_personal=True,                                        # Результаты персональные
    )
