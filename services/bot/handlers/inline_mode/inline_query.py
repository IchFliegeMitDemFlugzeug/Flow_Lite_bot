# services/bot/handlers/inline_mode/inline_query.py  # Путь файла в проекте (чтобы сразу было понятно, куда вставлять)

"""  # Начало многострочного комментария (docstring) — описание файла
Хэндлер обработки INLINE-запросов (то, что юзер вводит после @botusername).

Цель обновления (под твой запрос):
1) INLINE-результаты остаются списком (как сейчас), НО рядом с текстом показываем мини-картинки (thumbnail) — логотипы банков.
2) ВАЖНО: НЕ пишем transfer_id/контекст в БД на этапе inline_query (когда юзер просто набирает @ и смотрит список).
   Пишем в БД ТОЛЬКО тогда, когда юзер реально выбрал вариант и отправил сообщение в чат (ChosenInlineResult).
3) Для этого transfer_id должен быть воспроизводимым (детерминированным), чтобы мы могли:
   - в inline_query показать варианты с id=transfer_id,
   - в chosen_inline_result по result_id восстановить, какой именно option выбрали,
   - и уже тогда сохранить transfer_id + контекст в БД.

Ограничения Telegram:
- В inline-сообщениях Telegram запрещает кнопки типа web_app (BUTTON_TYPE_INVALID), но обычные url-кнопки разрешены.
- По нажатию url-кнопки бот НЕ получает CallbackQuery, поэтому "кто открыл webapp" узнаётся ТОЛЬКО на стороне WebApp (через initData).
"""  # Конец docstring

from __future__ import annotations  # Разрешаем отложенные аннотации типов (удобно для type hints)

import base64  # base64 нужен, чтобы красиво кодировать байты хэша в URL-safe строку
import hashlib  # hashlib нужен для SHA-256 (как криптопримитив внутри HMAC)
import hmac  # hmac нужен, чтобы делать детерминированный "подписанный" хэш от параметров
import json  # json нужен, чтобы сериализовать контекст операции в строку и сохранить в БД
import os  # os нужен, чтобы читать секрет из переменных окружения (не хардкодить)
import logging  # logging нужен, чтобы писать предупреждения/диагностику, если match не найден

from dataclasses import asdict  # asdict нужен, чтобы превращать dataclass в dict перед json.dumps
from typing import List, Optional  # List — тип списка, Optional — тип "может быть None"

from aiogram import Router  # Router — отдельный роутер для inline-логики
from aiogram.types import (  # Импортируем нужные типы из aiogram.types
    InlineQuery,  # InlineQuery — входящий inline-запрос (когда юзер набирает @бот)
    InlineQueryResultArticle,  # InlineQueryResultArticle — элемент списка результатов
    InputTextMessageContent,  # InputTextMessageContent — контент сообщения, который отправится в чат
    ChosenInlineResult,  # ChosenInlineResult — апдейт, когда юзер реально выбрал вариант и отправил его в чат
)

from bot.database import (  # Публичные функции БД, которые разрешено вызывать из хэндлеров
    get_user,  # Получение доменной модели пользователя из БД
    inline_mode_upsert_webapp_session,  # Запись transfer_id + контекста (и позже — opener_* из backend WebApp)
)

from bot.tools.inline_mode.query_parser import (  # Парсер текста inline-запроса
    parse_inline_query,  # Функция парсинга
    ParsedInlineQuery,  # Структура результата парсинга
)

from bot.texts.inline_mode.inline_results import (  # Генерация вариантов в списке подсказок
    build_inline_payment_options,  # Собирает варианты (телефоны/карты) под запрос
    build_bank_not_client_error_text,  # Строит "Вы не клиент этого банка"
    InlinePaymentOption,  # Структура одного варианта
)

from bot.texts.inline_mode.transfer_message import (  # Текст сообщения с реквизитами
    build_transfer_message_text,  # Сборка текста сообщения
)

from ...keyboards.inline_mode.transfer_actions import (  # Клавиатура под сообщением
    build_transfer_actions_keyboard,  # Сборщик клавиатуры (URL -> t.me/<bot>/<app>?startapp=<token>)
)

from ...tools.inline_mode.bank_logos import (  # Утилита для подстановки URL логотипа банка
    build_bank_logo_url,  # Возвращает HTTPS-URL логотипа по bank_code
)

# ------------------------------  # Визуальный разделитель блока констант/настроек
# Роутер inline-режима
# ------------------------------  # Конец заголовка блока

inline_mode_router: Router = Router(  # Создаём роутер, в который будем регистрировать inline-хэндлеры
    name="inline_mode",  # Даём имя роутеру — удобно видеть в логах/отладке
)  # Этот роутер потом подключается в main.py

logger = logging.getLogger(__name__)  # Создаём логгер для этого модуля (чтобы писать предупреждения)


def _serialize_context_for_db(  # Функция сериализует контекст операции в JSON-строку (для сохранения в БД)
    *,  # Делаем параметры только именованными, чтобы не перепутать порядок
    option: InlinePaymentOption,  # Выбранный вариант (телефон/карта/сценарий)
    parsed: ParsedInlineQuery,  # Распарсенный запрос (сумма/банк/кандидат)
    raw_query: str,  # Сырой текст inline-запроса
) -> str:  # Возвращаем строку JSON
    """  # Докстринг функции — пояснение, что и зачем мы делаем
    Сериализуем контекст операции в JSON-строку для записи в БД.

    Почему JSON:
    - удобно хранить как TEXT/JSON в MySQL;
    - удобно дебажить;
    - можно расширять без миграций структуры поля.
    """  # Конец докстринга

    payload: dict = {  # Собираем единый словарь контекста
        "raw_query": raw_query,  # Оригинальный текст, который пользователь ввёл после @бот
        "parsed": asdict(parsed),  # ParsedInlineQuery (dataclass) превращаем в dict
        "option": asdict(option),  # InlinePaymentOption (dataclass) превращаем в dict
    }  # Закрываем словарь

    return json.dumps(payload, ensure_ascii=False)  # Делаем JSON строку без экранирования кириллицы


def _compute_transfer_id(  # Функция детерминированно вычисляет transfer_id для конкретного option
    *,  # Только именованные аргументы — меньше шансов перепутать входные данные
    creator_user_id: int,  # TG id пользователя, который выбирает вариант (он же "создатель" inline-сообщения)
    raw_query: str,  # Сырой inline-запрос (влияет на итоговый набор вариантов)
    option: InlinePaymentOption,  # Конкретный вариант реквизитов
) -> str:  # Возвращаем URL-safe токен
    """  # Докстринг функции
    Детерминированно строим transfer_id, чтобы мы могли:
    - показать результат с id=transfer_id в inline_query,
    - потом поймать chosen_inline_result.result_id и восстановить, какой option был выбран,
      НЕ сохраняя ничего в БД на этапе ввода @.

    Реализация:
    - используем HMAC-SHA256 по "секрету" (чтобы токены нельзя было подбирать/коллизии были крайне маловероятны),
    - берём первые 16 байт результата (достаточно для компактного токена),
    - кодируем в base64 urlsafe без '='.

    ВАЖНО:
    - секрет нужно задать в переменной окружения INLINE_TRANSFER_SECRET,
      иначе в dev будет использован дефолт (и на проде так оставлять нельзя).
    """  # Конец докстринга

    secret: str = os.getenv("INLINE_TRANSFER_SECRET", "dev-change-me")  # Берём секрет из env (или dev-дефолт)

    # Собираем "сообщение" для HMAC: ровно те поля, которые идентифицируют конкретный вариант.  # Комментарий-пояснение
    msg: str = (  # Формируем одну строку, чтобы стабильно хэшировалось
        f"{creator_user_id}|"  # Включаем id пользователя (чтобы разные юзеры не пересекались)
        f"{raw_query}|"  # Включаем текст запроса (чтобы разные запросы давали разные токены)
        f"{option.payment_type}|"  # Включаем тип (телефон/карта и т.д.)
        f"{option.identifier}|"  # Включаем сам идентификатор (номер телефона/карта)
        f"{option.bank_code or ''}"  # Включаем код банка (или пустую строку)
    )  # Конец формирования строки

    digest: bytes = hmac.new(  # Строим HMAC
        key=secret.encode("utf-8"),  # Секрет в байтах
        msg=msg.encode("utf-8"),  # Сообщение в байтах
        digestmod=hashlib.sha256,  # Алгоритм хэширования SHA-256
    ).digest()  # Получаем "сырые" байты хэша

    short_digest: bytes = digest[:16]  # Берём первые 16 байт — это компактно и достаточно надёжно

    token: str = base64.urlsafe_b64encode(short_digest).decode("ascii").rstrip("=")  # Кодируем в URL-safe base64 и убираем '='

    return token  # Возвращаем итоговый transfer_id (короткий, URL-safe, воспроизводимый)


def _make_inline_article(  # Функция делает один элемент "зелёного списка"
    *,  # Только именованные аргументы
    option: InlinePaymentOption,  # Вариант реквизита
    parsed: ParsedInlineQuery,  # Результат разбора inline-запроса
    raw_query: str,  # Сырой текст inline-запроса
    creator_user_id: int,  # TG id того, кто формирует inline (кто вводил @bot)
) -> InlineQueryResultArticle:  # Возвращаем InlineQueryResultArticle
    """  # Докстринг функции
    Собираем InlineQueryResultArticle:
    - вычисляем transfer_id (детерминированно, чтобы потом сопоставить в chosen_inline_result),
    - НЕ пишем в БД здесь (по твоему требованию),
    - формируем превью (title/description + thumbnail),
    - формируем контент сообщения + клавиатуру.

    ВАЖНО:
    - запись в БД будет происходить в handle_chosen_inline_result(), когда пользователь реально выбрал вариант.
    """  # Конец докстринга

    transfer_id: str = _compute_transfer_id(  # Вычисляем детерминированный token
        creator_user_id=creator_user_id,  # Передаём TG id пользователя
        raw_query=raw_query,  # Передаём исходный текст запроса
        option=option,  # Передаём вариант (телефон/карта и т.д.)
    )  # Получаем transfer_id

    message_text: str = build_transfer_message_text(  # Собираем текст сообщения, которое улетит в чат
        option=option,  # Выбранные реквизиты (телефон/карта)
        parsed_query=parsed,  # Сумма/банк
    )  # Получаем готовый Markdown-текст

    input_content: InputTextMessageContent = InputTextMessageContent(  # Оборачиваем текст в “контент сообщения”
        message_text=message_text,  # Сам текст, который появится в чате
        parse_mode="Markdown",  # Разрешаем Markdown-разметку
    )  # Готовый объект контента

    reply_markup = build_transfer_actions_keyboard(  # Строим клавиатуру под сообщением
        transfer_id=transfer_id,  # ВАЖНО: это будет startapp=<token> в URL-кнопке
        option=option,  # Передаём option (может пригодиться для расширений/логики)
        parsed_query=parsed,  # Передаём parsed (может пригодиться для расширений/логики)
    )  # На выходе InlineKeyboardMarkup

    logo_url: Optional[str] = build_bank_logo_url(  # Определяем URL логотипа (если банк распознан/задан)
        bank_code=option.bank_code,  # Код банка (например "sber", "tbank")
    )  # Может вернуть None, если логотип не настроен или банк не указан

    article_kwargs: dict = {  # Собираем параметры результата в словарь (так удобнее добавлять thumbnail)
        "id": transfer_id,  # id результата — это наш transfer_id (потом он придёт в chosen_inline_result.result_id)
        "title": option.title,  # Заголовок строки списка
        "description": option.description,  # Подпись серым
        "input_message_content": input_content,  # Контент сообщения, который отправится в чат при выборе
        "reply_markup": reply_markup,  # Клавиатура (URL-кнопка на Mini App)
    }  # Конец словаря

    if not logo_url:  # Если логотипа нет — просто возвращаем результат без превью
        return InlineQueryResultArticle(**article_kwargs)  # Результат без картинки

    # Ниже — "защита от версий": в некоторых версиях может быть thumbnail_url или thumb_url  # Пояснение
    try:  # Пробуем современное имя поля (Bot API: thumbnail_url)
        return InlineQueryResultArticle(  # Собираем результат
            **article_kwargs,  # Передаём основные поля
            thumbnail_url=logo_url,  # Добавляем превью-картинку слева
        )  # Если поле поддерживается — вернёмся отсюда
    except Exception:  # Если pydantic/aiogram ругнулся на неизвестное поле
        return InlineQueryResultArticle(  # Пробуем альтернативное имя
            **article_kwargs,  # Передаём основные поля
            thumb_url=logo_url,  # Запасное имя поля (встречается в некоторых реализациях)
        )  # Возвращаем результат с превью


@inline_mode_router.inline_query()  # Регистрируем хэндлер: реагируем на любые InlineQuery
async def handle_inline_query(inline_query: InlineQuery) -> None:  # Асинхронная функция-обработчик
    """  # Докстринг хэндлера
    Главный хэндлер INLINE-режима (показывает список вариантов).

    ВАЖНО:
    - Здесь мы НИЧЕГО не пишем в БД по transfer_id, потому что пользователь может передумать.
    - Мы только показываем варианты, вычисляя детерминированные id.
    - Запись в БД будет в chosen_inline_result.
    """  # Конец докстринга

    raw_query: str = inline_query.query or ""  # Берём текст после @bot (или пустую строку)

    parsed: ParsedInlineQuery = parse_inline_query(  # Парсим сумму/банк и т.п.
        raw_query=raw_query,  # Передаём сырой текст запроса
    )  # Получаем ParsedInlineQuery

    user = get_user(  # Получаем пользователя из БД (в твоём проекте функция синхронная)
        user_id=inline_query.from_user.id,  # Передаём Telegram ID пользователя, который набирает @бот
    )  # На выходе доменная модель User

    options: List[InlinePaymentOption] = build_inline_payment_options(  # Строим список вариантов оплаты
        user=user,  # Данные пользователя (телефоны/карты/банки)
        parsed_query=parsed,  # Распарсенный запрос (сумма/банк)
    )  # Получаем список InlinePaymentOption

    results: List[InlineQueryResultArticle] = []  # Готовим список результатов, который отдаём Telegram

    if options:  # Если варианты есть — строим статьи
        for option in options:  # Перебираем все варианты (телефоны/карты)
            article: InlineQueryResultArticle = _make_inline_article(  # Создаём InlineQueryResultArticle
                option=option,  # Передаём конкретный вариант
                parsed=parsed,  # Передаём результат парсинга
                raw_query=raw_query,  # Передаём сырой запрос
                creator_user_id=inline_query.from_user.id,  # Передаём id пользователя (создателя)
            )  # Получаем готовую "статью" для списка

            results.append(article)  # Добавляем статью в общий список

    else:  # Если вариантов нет — показываем ошибку/подсказку
        if parsed.bank_code or parsed.bank_candidate:  # Если банк указан, но пользователь не клиент — выводим специальную ошибку
            from ...tools.banks_wordbook import BANKS  # Импортируем словарь банков локально (чтобы не грузить всегда)

            bank_title: str  # Объявляем переменную под красивое имя банка

            if parsed.bank_code and parsed.bank_code in BANKS:  # Если банк распознан по коду и есть в словаре
                bank_title = BANKS[parsed.bank_code]["message_title"]  # Берём человекочитаемое название
            else:  # Если распознали только "кандидата" (сырой текст)
                bank_title = parsed.bank_candidate or "этого банка"  # Подставляем то, что ввёл пользователь

            err = build_bank_not_client_error_text(  # Строим тексты ошибки для inline-результата
                bank_title=bank_title,  # Передаём название банка
            )  # Получаем InlineBankErrorText

            input_content = InputTextMessageContent(  # Сообщение, которое отправится в чат при выборе этого результата
                message_text=err.message_text,  # Текст ошибки
                parse_mode="Markdown",  # Markdown-разметка
            )  # Контент сообщения

            results.append(  # Добавляем один результат-ошибку в список
                InlineQueryResultArticle(  # Создаём InlineQueryResultArticle без клавиатуры
                    id="bank_not_client",  # Статический id (для ошибок детерминизм не нужен)
                    title=err.title,  # Заголовок
                    description=err.description,  # Описание
                    input_message_content=input_content,  # Контент сообщения
                )  # Конец создания статьи
            )  # Конец добавления

        else:  # Если банк не задан и вариантов нет — показываем “нет реквизитов”
            input_content = InputTextMessageContent(  # Сообщение-заглушка
                message_text="У вас пока нет сохранённых реквизитов. Откройте «Личный кабинет» и добавьте телефон или карту.",  # Текст подсказки
            )  # Конец контента

            results.append(  # Добавляем единственный результат “нет реквизитов”
                InlineQueryResultArticle(  # Создаём статью
                    id="no_payment_methods",  # Статический id
                    title="Нет реквизитов",  # Заголовок
                    description="Добавьте телефон/карту в личном кабинете, чтобы бот мог сформировать оплату.",  # Описание
                    input_message_content=input_content,  # Контент сообщения
                )  # Конец создания статьи
            )  # Конец добавления

    await inline_query.answer(  # Отвечаем Telegram списком результатов
        results=results,  # Передаём список InlineQueryResultArticle
        cache_time=1,  # Небольшой кэш на стороне Telegram (уменьшает нагрузку при наборе)
        is_personal=True,  # Результаты персональные (зависят от данных пользователя)
    )  # Telegram покажет пользователю список вариантов


@inline_mode_router.chosen_inline_result()  # Регистрируем хэндлер: срабатывает, когда юзер выбрал вариант и отправил сообщение в чат
async def handle_chosen_inline_result(chosen: ChosenInlineResult) -> None:  # Асинхронный обработчик выбранного inline-результата
    """  # Докстринг обработчика
    Хэндлер события "ChosenInlineResult" — это момент, когда пользователь:
    - выбрал конкретный пункт из inline-списка,
    - и Telegram реально отправил сообщение в чат.

    ВАЖНО:
    - Именно здесь мы вызываем inline_mode_upsert_webapp_session(...),
      потому что здесь пользователь уже не "передумал" — сообщение отправлено.
    """  # Конец докстринга

    result_id: str = chosen.result_id  # result_id — это id результата, который мы задавали в InlineQueryResultArticle.id

    raw_query: str = chosen.query or ""  # chosen.query — это строка, которую пользователь вводил после @бот

    parsed: ParsedInlineQuery = parse_inline_query(  # Парсим запрос точно так же, как в inline_query
        raw_query=raw_query,  # Передаём сырой запрос
    )  # Получаем ParsedInlineQuery

    user = get_user(  # Получаем пользователя из БД (по тому, кто выбрал результат)
        user_id=chosen.from_user.id,  # TG id пользователя, который отправил inline-сообщение
    )  # Доменная модель User

    options: List[InlinePaymentOption] = build_inline_payment_options(  # Строим варианты заново (как в inline_query)
        user=user,  # Данные пользователя
        parsed_query=parsed,  # Распарсенный запрос
    )  # Список вариантов

    matched_option: Optional[InlinePaymentOption] = None  # Переменная под найденный вариант (пока None)

    for option in options:  # Перебираем варианты и ищем тот, чей transfer_id совпал с result_id
        transfer_id: str = _compute_transfer_id(  # Вычисляем transfer_id для текущего option
            creator_user_id=chosen.from_user.id,  # id пользователя (создателя)
            raw_query=raw_query,  # исходный запрос
            option=option,  # текущий вариант
        )  # Получаем детерминированный токен

        if transfer_id == result_id:  # Сравниваем с тем, что реально выбрали
            matched_option = option  # Если совпало — сохраняем найденный option
            break  # Выходим из цикла, потому что вариант найден

    if matched_option is None:  # Если не нашли соответствие (например, словарь вариантов изменился)
        logger.warning(  # Логируем предупреждение, но не падаем
            "ChosenInlineResult: не удалось сопоставить result_id=%s с текущими options (user_id=%s, query=%r)",  # Шаблон сообщения
            result_id,  # Подставляем result_id
            chosen.from_user.id,  # Подставляем user_id
            raw_query,  # Подставляем raw_query
        )  # Конец логирования
        return  # Выходим — ничего не пишем в БД

    context_json: str = _serialize_context_for_db(  # Сериализуем контекст для БД
        option=matched_option,  # Тот вариант, который реально выбрали
        parsed=parsed,  # Распарсенный запрос
        raw_query=raw_query,  # Сырой запрос
    )  # Получаем JSON строку

    logger.warning(  # warning — чтобы точно печаталось
        "INLINE MODE: chosen_inline_result. user_id=%s result_id=%s query=%r matched_option=%r",
        chosen.from_user.id,
        result_id,
        raw_query,
        asdict(matched_option),
    )

    inline_mode_upsert_webapp_session(  # Пишем в БД (мягко — у тебя функция уже обёрнута try/except)
        transfer_id=result_id,  # transfer_id — это выбранный result_id
        creator_tg_user_id=chosen.from_user.id,  # Кто отправил inline-сообщение (создатель операции)
        context_json=context_json,  # Контекст операции (что выбрали/что ввели)
    )  # opener_* сюда не передаём — их заполнит backend WebApp при открытии страницы
