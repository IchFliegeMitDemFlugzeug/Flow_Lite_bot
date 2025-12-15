# services/bot/handlers/inline_mode/inline_query.py

"""
Хэндлер обработки INLINE-запросов (то, что юзер вводит после @bot_bot).

Именно этот файл:
- принимает InlineQuery от Telegram;
- разбирает текст запроса (сумма + банк) через tools/inline_mode/query_parser.py;
- достаёт из БД данные юзера (телефоны, карты, банки);
- собирает список вариантов через texts/inline_mode/inline_results.py;
- упаковывает их в InlineQueryResultArticle и отправляет Telegram.

Результат — тот самый зелёный список подсказок, который ты рисовал в схеме.
"""

from __future__ import annotations                           # Разрешаем отложенные аннотации типов (удобно для type hints)

from typing import List                                      # List — для аннотации списков

from aiogram import Router                                  # Router — отдельный роутер для inline-логики
from aiogram.types import (                                 # Импортируем нужные типы из aiogram.types
    InlineQuery,                                            # InlineQuery — объект входящего inline-запроса
    InlineQueryResultArticle,                               # InlineQueryResultArticle — один элемент списка подсказок
    InputTextMessageContent,                                # InputTextMessageContent — что в итоге отправится в чат
)

from bot.database import get_user                           # Функция получения доменной модели User по Telegram user_id

from bot.tools.inline_mode.query_parser import (            # Парсер текста inline-запроса
    parse_inline_query,                                     # Основная функция parse_inline_query(...)
    ParsedInlineQuery,                                      # Структура результата парсинга (amount, bank_code, ...)
)
from bot.texts.inline_mode.inline_results import (          # Логика формирования вариантов для списка
    build_inline_payment_options,                           # Собирает список InlinePaymentOption по юзеру и парсингу
    build_bank_not_client_error_text,                       # Строит текст ошибки "Вы не клиент этого банка"
    InlinePaymentOption,                                    # Структура одного варианта (тип, номер, заголовок и т.д.)
)
#from bot.texts.inline_mode.transfer_message import (        # Текст итогового сообщения, которое уйдёт в чат
    #build_transfer_message_text,                            # Функция, формирующая текст "переведите по номеру..."
#)


# Создаём отдельный роутер для inline-режима.
# Его нужно будет подключить в main.py через dp.include_router(inline_mode_router)
# (ЖЕЛАТЕЛЬНО до global_guard_router, чтобы глобальный фильтр не мешал).
inline_mode_router: Router = Router(
    name="inline_mode",                                     # Дадим осмысленное имя для удобной отладки
)


def _build_inline_article(                                  # Вспомогательная функция — собирает одну подсказку
    option: InlinePaymentOption,                            # Описание варианта (телефон/карта + сумма + банк)
    parsed: ParsedInlineQuery,                              # Результат парсинга запроса (raw_query, amount, bank_code,...)
    result_id: str,                                         # Уникальный ID результата (обязательно по требованиям Telegram)
) -> InlineQueryResultArticle:
    """
    Превращаем наш внутренний InlinePaymentOption в InlineQueryResultArticle.

    Здесь:
    - title/description — это то, что видно в ЗЕЛЁНОМ списке;
    - input_message_content — это текст, который в итоге попадёт в чат,
      когда юзер выберет этот вариант.
    """

    # Строим итоговый текст сообщения, которое окажется в чате,
    # используя отдельный модуль texts/inline_mode/transfer_message.py.
    # Туда передаём:
    #   option  — чтобы знать, телефон это или карта, какой номер, банк, сумма;
    #   parsed  — на всякий случай, если там потом понадобится raw_query и т.п.
    # message_text: str = build_transfer_message_text(
    #     option=option,                                      # Конкретный вариант из списка
    #     parsed_query=parsed,                                # Весь контекст парсинга
    # )

    # Оборачиваем текст в InputTextMessageContent — это "тело" сообщения,
    # которое Telegram отправит в ЧАТ после выбора варианта.
    input_content: InputTextMessageContent = InputTextMessageContent(
        message_text="hjk", #message_text,                          # Тот текст, который увидит юзер в чате
        parse_mode="Markdown",                              # Можно включить Markdown, если будешь оформлять жирный/курсив
    )

    # Собираем объект InlineQueryResultArticle — один элемент списка подсказок.
    article: InlineQueryResultArticle = InlineQueryResultArticle(
        id=result_id,                                       # Уникальный ID результата (строка до 64 байт)
        title=option.title,                                 # Заголовок в списке подсказок (жирный текст)
        description=option.description,                     # Подзаголовок (серый текст под заголовком)
        input_message_content=input_content,                # То, что попадёт в чат по выбору этого варианта
        # Здесь позже можно добавить thumb_url / thumb_width / thumb_height,
        # когда прикрутим превью-картинки из headlines/inline_mode.
    )

    return article                                          # Возвращаем готовый InlineQueryResultArticle


@inline_mode_router.inline_query()                          # Регистрируем хэндлер на ВСЕ inline-запросы бота
async def handle_inline_query(                              # Асинхронная функция обработки inline-апдейта
    inline_query: InlineQuery,                              # Объект, содержащий данные о запросе
) -> None:
    """
    Главный хэндлер INLINE-режима.

    Пошаговая логика:
    1) Забираем текст запроса (inline_query.query).
    2) Парсим его через parse_inline_query (находим сумму и банк).
    3) Достаём из БД пользователя (get_user).
    4) Собираем варианты переводов (build_inline_payment_options).
    5) Если варианты есть -> конвертим их в InlineQueryResultArticle и отправляем.
    6) Если вариантов нет, но указан банк -> отдаём один элемент "Вы не клиент этого банка".
    7) Если вообще ничего нет (нет ни реквизитов, ни банка) -> возвращаем пустой список.
    """

    # 1) Забираем "сырой" текст запроса.
    #    Telegram сюда кладёт всё, что юзер набрал ПОСЛЕ @bot_bot.
    raw_query: str = inline_query.query or ""               # Защищаемся от None, превращаем в пустую строку

    # 2) Парсим строку: ищем сумму, банк и т.п.
    parsed: ParsedInlineQuery = parse_inline_query(
        raw_query=raw_query,                                # Передаём текст в наш парсер
    )

    # 3) Достаём пользователя из нашей базы по Telegram user_id.
    #    get_user — синхронная функция, поэтому просто вызываем её (без await).
    user = get_user(
        user_id=inline_query.from_user.id,                  # Берём числовой ID пользователя из апдейта
    )

    # 4) Собираем все подходящие варианты:
    #    телефоны + карты, отфильтрованные по parsed.bank_code (если он есть),
    #    и с учётом суммы parsed.amount.
    payment_options: List[InlinePaymentOption] = build_inline_payment_options(
        user=user,                                          # Доменная модель пользователя
        parsed_query=parsed,                                # Результат парсинга (сумма, банк и т.д.)
    )

    # 5) Если варианты есть — собираем список InlineQueryResultArticle.
    results: List[InlineQueryResultArticle] = []            # Сюда сложим все результаты для ответа Telegram

    if payment_options:                                     # Если список НЕ пустой
        for index, option in enumerate(payment_options):    # Перебираем варианты с индексом
            result_id: str = f"opt_{index}"                 # Формируем простой уникальный ID (например, "opt_0")

            # Конвертируем наш вариант в InlineQueryResultArticle через вспомогательную функцию.
            article: InlineQueryResultArticle = _build_inline_article(
                option=option,                              # Текущий вариант (телефон или карта)
                parsed=parsed,                              # Общий контекст парсинга
                result_id=result_id,                        # Уникальный ID результата
            )

            results.append(article)                         # Добавляем результат в итоговый список
    else:
        # Вариантов перевода нет. Это может значить:
        # - у пользователя ещё нет ни одного телефона/карты;
        # - он указал банк, которого нет среди его реквизитов;
        # - (будущие кейсы).
        #
        # Если при этом в parsed есть информация о банке (bank_code или bank_candidate),
        # показываем специальный элемент "Вы не клиент "<банк>".
        if parsed.bank_code or parsed.bank_candidate:       # Если юзер явно написал какой-то банк
            # Определяем красивое название банка:
            # - если банк известен по коду -> берём человекочитаемое имя из BANKS
            # - иначе используем то, что юзер ввёл (bank_candidate)
            from ...tools.banks_wordbook import BANKS            # Локальный импорт, чтобы не тащить наверх лишнее

            bank_title: str                                 # Здесь будет то, что вставим в кавычки
            if parsed.bank_code and parsed.bank_code in BANKS:
                # Если есть код банка и он есть в словаре, берём короткое название кнопки
                bank = BANKS[parsed.bank_code]              # Достаём словарь по коду
                bank_title = bank.get("button_title") or bank.get("message_title") or parsed.bank_candidate or "этого банка"
            else:
                # Если код неизвестен, но есть текст-кандидат — используем его
                bank_title = parsed.bank_candidate or "этого банка"

            # Строим текст для ошибки через отдельную функцию из inline_results.
            error_text = build_bank_not_client_error_text(
                bank_name=bank_title,                       # То, что покажем в кавычках
            )

            # Формируем содержимое сообщения (что уйдёт в чат, если вдруг юзер выберет этот пункт).
            error_message_content: InputTextMessageContent = InputTextMessageContent(
                message_text=f"{error_text.title}\n\n{error_text.description}",  # Заголовок + пояснение
            )

            # Собираем сам InlineQueryResultArticle для ошибки.
            error_article: InlineQueryResultArticle = InlineQueryResultArticle(
                id="bank_not_client",                       # Фиксированный ID для этого вида результата
                title=error_text.title,                     # Заголовок "Вы не клиент "<банк>""
                description=error_text.description,         # Пояснение под заголовком
                input_message_content=error_message_content,  # Что попадёт в чат
            )

            results.append(error_article)                   # Добавляем единственный элемент-ошибку в список результатов
        else:
            # Если нет ни вариантов, ни банка — просто не отдаём ничего.
            # Telegram покажет стандартное "Ничего не найдено".
            results = []                                    # На всякий случай явно обнуляем список


    # 6) Отправляем сформированный список результатов обратно в Telegram.
    #    cache_time=0 — чтобы изменения логики inline-режима применялись сразу (без кэширования).
    await inline_query.answer(
        results=results,                                    # Набор InlineQueryResultArticle
        cache_time=0,                                       # Отключаем кэш на стороне Telegram
        is_personal=True,                                   # Результаты "персонализированы" под конкретного юзера
    )
