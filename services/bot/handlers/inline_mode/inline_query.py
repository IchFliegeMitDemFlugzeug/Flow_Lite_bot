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
import hmac  # hmac нужен для подписи пакета, чтобы WebApp мог проверить целостность
import hashlib  # hashlib нужен для алгоритма SHA-256 при подписи
import json  # json нужен, чтобы сериализовать контекст операции в строку и сохранить в БД
import os  # os нужен, чтобы читать секрет из переменных окружения (не хардкодить)
import logging  # logging нужен, чтобы писать предупреждения/диагностику, если match не найден
import time  # time нужен для организации простого кэша с временем жизни

from dataclasses import asdict  # asdict нужен, чтобы превращать dataclass в dict перед json.dumps
from typing import Dict, List, Optional, Tuple  # Dict/Tuple — для хранения кэша, List/Optional — аннотации типов

from aiogram import Router  # Router — отдельный роутер для inline-логики
from aiogram.types import (  # Импортируем нужные типы из aiogram.types
    InlineQuery,  # InlineQuery — входящий inline-запрос (когда юзер набирает @бот)
    InlineQueryResultArticle,  # InlineQueryResultArticle — элемент списка результатов
    InputTextMessageContent,  # InputTextMessageContent — контент сообщения, который отправится в чат
    ChosenInlineResult,  # ChosenInlineResult — апдейт, когда юзер реально выбрал вариант и отправил его в чат
)

from bot.database import get_user  # Получение доменной модели пользователя из БД

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

# ------------------------------  # Визуальный разделитель блока кэша/вспомогательных настроек
# Простой кэш для ускорения inline_query
# ------------------------------  # Конец заголовка блока

_USER_CACHE_TTL_SECONDS: int = 30  # TTL кэша пользователя (секунды): достаточно коротко, чтобы не держать устаревшие данные
_OPTIONS_CACHE_TTL_SECONDS: int = 30  # TTL кэша списка вариантов (секунды): синхронизирован с кэшем пользователя

_USER_CACHE: Dict[int, Tuple[float, object]] = {}  # Кэш пользователей: user_id -> (момент истечения, объект пользователя)
_OPTIONS_CACHE: Dict[Tuple[int, str], Tuple[float, List[InlinePaymentOption]]] = {}  # Кэш вариантов: (user_id, ключ запроса) -> (момент истечения, список вариантов)


def _now() -> float:  # Функция, возвращающая текущее время в монотонных секундах
    return time.monotonic()  # monotonic защищает от изменений системных часов


def _build_query_cache_key(*, raw_query: str, parsed: ParsedInlineQuery) -> str:  # Генерируем ключ кэша для вариантов по тексту запроса
    serialized_query: str = json.dumps(  # Преобразуем распарсенный запрос в детерминированную строку
        asdict(parsed),  # Конвертируем ParsedInlineQuery в словарь
        ensure_ascii=False,  # Сохраняем русские символы как есть
        sort_keys=True,  # Сортируем ключи, чтобы одинаковые запросы давали одинаковую строку
    )  # Получаем готовую строку

    normalized_raw_query: str = raw_query.strip()  # Убираем лишние пробелы слева/справа, чтобы не плодить ключи

    return f"{normalized_raw_query}|{serialized_query}"  # Склеиваем сырой текст и распарсенный вид в один ключ


def _get_cached_user(*, user_id: int) -> Optional[object]:  # Пытаемся взять пользователя из кэша
    cache_entry = _USER_CACHE.get(user_id)  # Читаем запись по user_id

    if not cache_entry:  # Если записи нет — сразу возвращаем None
        return None  # Кэш пуст

    expires_at, cached_user = cache_entry  # Распаковываем срок жизни и объект

    if expires_at < _now():  # Если срок жизни истёк
        _USER_CACHE.pop(user_id, None)  # Удаляем устаревшую запись, чтобы не держать мусор
        return None  # Сообщаем, что кэш недействителен

    return cached_user  # Возвращаем свежий объект пользователя


def _cache_user(*, user_id: int, user: object) -> object:  # Кладём пользователя в кэш и возвращаем его же
    _USER_CACHE[user_id] = (_now() + _USER_CACHE_TTL_SECONDS, user)  # Записываем срок истечения и объект
    return user  # Возвращаем записанный объект для удобства цепочки вызовов


def _get_user_fast(*, user_id: int) -> object:  # Быстро получаем пользователя: сначала из кэша, потом из БД
    cached_user = _get_cached_user(user_id=user_id)  # Пробуем взять из кэша

    if cached_user is not None:  # Если нашли свежую запись
        return cached_user  # Возвращаем кэш сразу (ускоряем обработку)

    fetched_user = get_user(user_id=user_id)  # Если кэша нет — обращаемся к БД
    return _cache_user(user_id=user_id, user=fetched_user)  # Кладём в кэш и возвращаем


def _get_cached_options(*, user_id: int, cache_key: str) -> Optional[List[InlinePaymentOption]]:  # Пытаемся взять варианты из кэша
    cache_entry = _OPTIONS_CACHE.get((user_id, cache_key))  # Читаем запись по ключу (user_id + запрос)

    if not cache_entry:  # Если записи нет — возвращаем None
        return None  # Кэш пуст

    expires_at, cached_options = cache_entry  # Распаковываем срок жизни и список вариантов

    if expires_at < _now():  # Проверяем, не истёк ли TTL
        _OPTIONS_CACHE.pop((user_id, cache_key), None)  # Удаляем устаревшую запись
        return None  # Сообщаем, что кэш недействителен

    return cached_options  # Возвращаем свежие варианты


def _cache_options(*, user_id: int, cache_key: str, options: List[InlinePaymentOption]) -> List[InlinePaymentOption]:  # Кладём варианты в кэш
    _OPTIONS_CACHE[(user_id, cache_key)] = (  # Сохраняем под составным ключом
        _now() + _OPTIONS_CACHE_TTL_SECONDS,  # Вычисляем момент истечения
        options,  # Сохраняем список вариантов
    )  # Конец записи в кэш
    return options  # Возвращаем для удобства цепочки вызовов


def _get_options_fast(*, user: object, parsed_query: ParsedInlineQuery, raw_query: str) -> List[InlinePaymentOption]:  # Быстро получаем список вариантов
    cache_key: str = _build_query_cache_key(raw_query=raw_query, parsed=parsed_query)  # Строим ключ кэша для запроса

    cached_options = _get_cached_options(  # Пытаемся достать варианты из кэша
        user_id=user.id,  # Используем id пользователя как часть ключа
        cache_key=cache_key,  # Передаём ключ запроса
    )  # Получаем либо список, либо None

    if cached_options is not None:  # Если в кэше есть свежие данные
        return cached_options  # Возвращаем их, экономя время на запросах

    built_options = build_inline_payment_options(  # Если кэша нет — собираем варианты как раньше
        user=user,  # Данные пользователя
        parsed_query=parsed_query,  # Распарсенный запрос
    )  # Получаем список вариантов

    return _cache_options(  # Кладём результат в кэш и возвращаем
        user_id=user.id,  # Привязываем к пользователю
        cache_key=cache_key,  # Привязываем к конкретному тексту запроса
        options=built_options,  # Сохраняем построенные варианты
    )  # Возвращаем список вариантов


def _compute_transfer_id(  # Функция кодирует полный пакет данных для WebApp внутрь transfer_id
    *,  # Только именованные аргументы — меньше шансов перепутать входные данные
    creator_user_id: int,  # TG id пользователя, который выбирает вариант (он же "создатель" inline-сообщения)
    raw_query: str,  # Сырой inline-запрос (влияет на итоговый набор вариантов)
    option: InlinePaymentOption,  # Конкретный вариант реквизитов
    parsed_query: ParsedInlineQuery,  # Уже распарсенный inline-запрос (экономим на повторном парсинге)
) -> str:  # Возвращаем URL-safe токен
    """  # Докстринг функции
    Формируем transfer_id как base64-строку с JSON-пакетом.

    Что кладём внутрь пакета:
    - creator_tg_user_id — кто отправил инлайн-сообщение;
    - raw_query/parsed/option — что именно было в сообщении (банк, сумма, реквизит);
    - без timestamp — специально убрали, чтобы transfer_id всегда совпадал между inline_query
      (список) и chosen_inline_result (выбор).

    Почему так:
    - WebApp теперь сам получает все исходные данные через startapp-параметр,
      без предварительной записи в БД на стороне бота.
    - Данные подписываем секретом HMAC и кладём рядом, чтобы WebApp мог проверить целостность.
    """  # Конец докстринга

    payload = {  # Собираем словарь с данными для WebApp
        "creator_tg_user_id": int(creator_user_id),  # Кто сформировал сообщение
        "raw_query": raw_query,  # Исходный текст запроса
        "parsed": asdict(parsed_query),  # Распарсенная структура запроса
        "option": asdict(option),  # Детали выбранного реквизита
        # СОВСЕМ ВАЖНО: timestamp убрали, чтобы transfer_id был строго детерминированным
        # и совпадал между этапами inline_query (показ списка) и chosen_inline_result (выбор).
    }  # Конец словаря

    secret: str = os.getenv("INLINE_TRANSFER_SECRET", "dev-change-me")  # Секрет для подписи

    signature_bytes = hmac.new(  # Строим HMAC для проверки целостности
        key=secret.encode("utf-8"),  # Ключ подписи
        msg=json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),  # Детерминированный JSON
        digestmod=hashlib.sha256,  # SHA-256 как алгоритм
    ).digest()  # Получаем байты подписи

    short_signature = base64.urlsafe_b64encode(signature_bytes[:12]).decode("ascii").rstrip("=")  # Компактная подпись

    transfer_package = {  # Финальный объект, который положим в startapp
        "payload": payload,  # Исходные данные о переводе
        "sig": short_signature,  # Подпись для быстрой проверки
    }  # Конец объекта

    encoded: str = base64.urlsafe_b64encode(  # Кодируем в URL-safe base64
        json.dumps(transfer_package, ensure_ascii=False).encode("utf-8")  # Сериализуем объект в байты
    ).decode("ascii").rstrip("=")  # Превращаем в строку и убираем '=' для компактности

    return encoded  # Возвращаем готовый transfer_id


def _compute_result_id(  # Функция строит короткий id для inline-результата (Telegram требует <=64 символов)
    *,  # Используем только именованные аргументы, чтобы не перепутать порядок
    transfer_id: str,  # Полный transfer_id с данными для WebApp (может быть длинным)
) -> str:  # Возвращаем короткий детерминированный идентификатор
    """  # Докстринг функции
    Telegram ограничивает длину InlineQueryResult.id 64 символами, поэтому
    мы делаем отдельный короткий идентификатор на базе полного transfer_id:
    - хэшируем transfer_id через SHA-256;
    - берём первые 16 байт хэша (достаточно уникальности для наших случаев);
    - кодируем в urlsafe base64 без '=';
    - получаем строку около 22 символов, удовлетворяющую лимиту и детерминированную.
    """  # Конец докстринга

    sha_digest: bytes = hashlib.sha256(  # Считаем SHA-256 от полного transfer_id
        transfer_id.encode("utf-8")  # Переводим строку в байты
    ).digest()  # Получаем байтовое представление хэша

    short_digest: bytes = sha_digest[:16]  # Берём первые 16 байт (128 бит) для компактности

    result_id: str = base64.urlsafe_b64encode(short_digest).decode("ascii").rstrip("=")  # Кодируем в base64 и убираем '='

    return result_id  # Возвращаем короткий id, подходящий Telegram


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

    transfer_id: str = _compute_transfer_id(  # Вычисляем детерминированный token (полная версия для WebApp)
        creator_user_id=creator_user_id,  # Передаём TG id пользователя
        raw_query=raw_query,  # Передаём исходный текст запроса
        option=option,  # Передаём вариант (телефон/карта и т.д.)
        parsed_query=parsed,  # Передаём распарсенный запрос (чтобы не парсить повторно)
    )  # Получаем transfer_id

    result_id: str = _compute_result_id(  # Считаем укороченный id для InlineQueryResult (вписывается в лимит Telegram)
        transfer_id=transfer_id,  # Передаём полный transfer_id, чтобы детерминированно получить короткий
    )  # Получаем короткий result_id

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
        "id": result_id,  # id результата — укороченная версия (Telegram принимает <=64 символов)
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

    raw_query: str = (inline_query.query or "").strip()  # Берём текст после @bot (или пустую строку) и сразу убираем лишние пробелы

    parsed: ParsedInlineQuery = parse_inline_query(  # Парсим сумму/банк и т.п.
        raw_query=raw_query,  # Передаём сырой текст запроса
    )  # Получаем ParsedInlineQuery

    user = _get_user_fast(  # Получаем пользователя сначала из кэша, чтобы не ходить в БД без необходимости
        user_id=inline_query.from_user.id,  # Передаём Telegram ID пользователя, который набирает @бот
    )  # На выходе доменная модель User

    options: List[InlinePaymentOption] = _get_options_fast(  # Строим/достаём список вариантов оплаты с кэшированием
        user=user,  # Данные пользователя (телефоны/карты/банки)
        parsed_query=parsed,  # Распарсенный запрос (сумма/банк)
        raw_query=raw_query,  # Сырой текст запроса (нужен для ключа кэша)
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

    raw_query: str = (chosen.query or "").strip()  # chosen.query — это строка, которую пользователь вводил после @бот (убираем лишние пробелы)

    parsed: ParsedInlineQuery = parse_inline_query(  # Парсим запрос точно так же, как в inline_query
        raw_query=raw_query,  # Передаём сырой запрос
    )  # Получаем ParsedInlineQuery

    user = _get_user_fast(  # Получаем пользователя через кэш, чтобы не дергать БД повторно
        user_id=chosen.from_user.id,  # TG id пользователя, который отправил inline-сообщение
    )  # Доменная модель User

    options: List[InlinePaymentOption] = _get_options_fast(  # Строим варианты заново (или достаём из кэша)
        user=user,  # Данные пользователя
        parsed_query=parsed,  # Распарсенный запрос
        raw_query=raw_query,  # Сырой запрос нужен для корректного ключа кэша
    )  # Список вариантов

    matched_option: Optional[InlinePaymentOption] = None  # Переменная под найденный вариант (пока None)

    for option in options:  # Перебираем варианты и ищем тот, чей transfer_id совпал с result_id
        transfer_id: str = _compute_transfer_id(  # Вычисляем полный transfer_id для текущего option
            creator_user_id=chosen.from_user.id,  # id пользователя (создателя)
            raw_query=raw_query,  # исходный запрос
            option=option,  # текущий вариант
            parsed_query=parsed,  # Передаём распарсенный запрос
        )  # Получаем детерминированный токен

        computed_result_id: str = _compute_result_id(  # Строим короткий id так же, как в inline_query
            transfer_id=transfer_id,  # Передаём полный transfer_id
        )  # Получаем детерминированный короткий id

        if computed_result_id == result_id:  # Сравниваем с тем, что реально выбрали
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

    logger.warning(  # warning — чтобы точно печаталось
        "INLINE MODE: chosen_inline_result. user_id=%s result_id=%s query=%r matched_option=%r",
        chosen.from_user.id,
        result_id,
        raw_query,
        asdict(matched_option),
    )  # Контекст теперь уходит внутри transfer_id в WebApp и там дополняется перед записью
