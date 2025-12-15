# services/bot/tools/inline_mode/query_parser.py

# -*- coding: utf-8 -*-                          # Указываем кодировку файла

"""
Парсер текстового запроса для INLINE-режима бота.

Теперь учитываем, что в запросе может быть НЕСКОЛЬКО банков.
Примеры raw_query (то, что после @bot_bot):

    "500 Сбер и Т-Банк"
    "500р ПСБ, потом на Т-Банк"
    "Сбер ПСБ Т-Банк"
    "500, сначала МКБ, потом ПСБ"
    "привет, как обычно Сбер или Т-Банк"

Задача парсера:
1) Найти сумму (если есть) — первую последовательность цифр.
2) Найти ВСЕ банки, которые упоминаются в сообщении и есть в словаре BANKS.
3) Сохранить:
   - raw_query       — исходный текст;
   - amount          — сумма (int | None);
   - bank_codes      — список кодов банков (["sber", "tbank", ...]);
   - bank_code       — первый из bank_codes (для совместимости);
   - bank_candidate  — текст-кандидат на банк (если bank_codes пустой).
"""

from __future__ import annotations                      # Разрешаем отложенные аннотации типов

import re                                               # Регулярные выражения — для поиска чисел/чистки текста
from dataclasses import dataclass                       # dataclass — удобные "структуры данных"
from typing import Optional, List                       # Optional[T] и List[T] — для аннотаций типов

from ..banks_wordbook import BANKS                      # Словарь банков (code, button_title, message_title, ...)


# ------------------------- #
#   МОДЕЛЬ РЕЗУЛЬТАТА ПАРСЕРА
# ------------------------- #


@dataclass
class ParsedInlineQuery:
    """
    Результат разбора inline-запроса.

    Поля:
        raw_query      — исходный текст (как пришёл от Telegram).
        amount         — сумма перевода (int) или None.
        bank_codes     — список всех найденных кодов банков (в порядке обнаружения).
        bank_code      — первый банк из bank_codes (для совместимости со старым кодом).
        bank_candidate — текст-кандидат на банк, если банки по словарю не найдены.
    """

    raw_query: str                                      # Оригинальный текст запроса
    amount: Optional[int]                               # Найденная сумма или None
    bank_codes: List[str]                               # Список всех кодов банков (может быть пустым)
    bank_code: Optional[str]                            # Первый код из bank_codes или None
    bank_candidate: Optional[str]                       # Текст-кандидат (для неизвестных банков) или None


# ------------------------- #
#   ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ------------------------- #


def _normalize_bank_text(text: str) -> str:
    """
    Нормализуем строку для сравнения с названиями банков.

    Делаем:
    - приводим к нижнему регистру;
    - заменяем 'ё' на 'е';
    - убираем пробелы, дефисы, точки, запятые, кавычки, скобки.

    Примеры:
        "Т-Банк"                     -> "тбанк"
        "   Т Банк "                 -> "тбанк"
        "Московский Кредитный Банк"  -> "московскийкредитныйбанк"
        "ПСБ"                        -> "псб"
    """
    text = (text or "").lower()                       # Приводим к нижнему регистру, защищаемся от None
    text = text.replace("ё", "е")                     # Убираем различие между "е" и "ё"
    text = re.sub(r"[\s\-\.,\"'«»()]+", "", text)     # Удаляем пробелы и знаки препинания
    return text                                       # Возвращаем нормализованный текст


def _strip_amount_tokens(raw: str) -> str:
    """
    Удаляем из строки фрагменты, похожие на "сумму с валютой".

    Ищем паттерны:
        "500"
        "500р"
        "500 р"
        "500руб"
        "500 rub"
        "500₽"
        "500 руб."
    и заменяем их на пробел, чтобы при поиске банков они не мешали.

    Примеры:
        "500 Сбер"                 -> " Сбер"
        "500р  ПСБ зарплата"      -> "  ПСБ зарплата"
        "Сбер 700р как обычно"    -> "Сбер  как обычно"
    """
    return re.sub(
        r"\d+\s*(?:р|p|руб|rub|₽)?\.?",               # Число + необязательное обозначение валюты
        " ",                                         # Заменяем найденное на пробел
        raw,
        flags=re.IGNORECASE,                         # Игнорируем регистр при поиске "руб"/"rub"
    )


def _extract_amount(raw: str) -> Optional[int]:
    """
    Ищем сумму перевода в строке.

    Логика:
    - находим ПЕРВУЮ последовательность цифр;
    - считаем её суммой;
    - всё остальное игнорируем.

    Примеры:
        "500"                      -> 500
        "500р"                     -> 500
        "500 ₽ Сбер"              -> 500
        "Сбер 700р как обычно"    -> 700
        "Сбер"                    -> None
    """
    if not raw:                                      # Если строка пустая — суммы нет
        return None

    match = re.search(r"\d+", raw)                   # Ищем первую группу цифр
    if not match:                                    # Если цифр не нашли
        return None                                  # Считаем, что суммы нет

    digits = match.group(0)                          # Берём найденные цифры как строку

    try:
        return int(digits)                           # Пробуем превратить строку в int
    except ValueError:                               # На всякий случай ловим ошибку
        return None                                  # В случае ошибки возвращаем None


def _extract_bank_candidate_without_dict(raw: str) -> Optional[str]:
    """
    Выделяем текст-кандидат на банк БЕЗ использования словаря BANKS.

    Нужен для сценариев, когда:
    - ни один банк по словарю не расшифровался,
    - но пользователь явно что-то написал (например, "ХуйБанк").

    Логика:
    - убираем сумму/валюту из строки;
    - сжимаем пробелы;
    - если что-то осталось — возвращаем как candidate.

    Важно: если пользователь написал целое предложение,
    candidate может содержать не только банк — это нормально для первых версий.
    """
    if not raw:                                      # Пустой ввод — кандидата нет
        return None

    without_amount = _strip_amount_tokens(raw)       # Выкидываем числа + валюту
    candidate = re.sub(r"\s+", " ", without_amount).strip()  # Сжимаем пробелы и обрезаем края

    return candidate or None                         # Пустую строку превращаем в None


def _detect_all_bank_codes_from_full_text(raw: str) -> List[str]:
    """
    Находим ВСЕ банки в ПОЛНОМ тексте сообщения, используя словарь BANKS.

    Алгоритм:
    1) Удаляем из текста сумму/валюту (чтобы не мешали).
    2) Нормализуем весь текст (_normalize_bank_text).
    3) Для каждого банка из BANKS:
        - берём code, button_title, message_title;
        - нормализуем каждое поле;
        - если norm_variant содержится в norm_text — считаем, что банк есть в сообщении.

    Возвращаем:
        Список КОДОВ банков (["sber", "tbank", "mkb", ...]) без повторов,
        в порядке обхода BANKS (обычно стабилен, т.к. dict insertion-ordered).
    """
    if not raw:                                      # Пустой ввод — ничего не найдём
        return []

    text_without_amount = _strip_amount_tokens(raw)  # Убираем суммы и валюту
    norm_text = _normalize_bank_text(text_without_amount)  # Нормализуем текст

    if not norm_text:                                # Если всё "съели"
        return []                                    # Банков не нашли

    found_codes: List[str] = []                     # Сюда сложим коды найденных банков

    for bank_data in BANKS.values():                # Перебираем ВСЕ банки из словаря
        code = bank_data.get("code") or ""          # Код банка (например, "sber", "tbank")
        if not code:                                # Если кода нет — такой банк пропускаем
            continue

        # Собираем варианты строк, по которым будем искать совпадения
        variants = [
            code,                                   # Сам code тоже может встречаться в тексте
            bank_data.get("button_title") or "",
            bank_data.get("message_title") or "",
        ]

        for variant in variants:                    # Перебираем варианты одной записи банка
            norm_variant = _normalize_bank_text(variant)  # Нормализуем

            if not norm_variant:                   # Пустые строки пропускаем
                continue

            # Если нормализованное название банка встречается в нормализованном тексте —
            # считаем, что банк присутствует в сообщении.
            if norm_variant in norm_text:
                if code not in found_codes:        # Не даём повторяться кодам
                    found_codes.append(code)       # Добавляем код в список найденных
                break                              # Выходим из цикла по variants для этого банка

    return found_codes                             # Возвращаем список кодов (может быть пустой)


# ------------------------- #
#   ОСНОВНАЯ ФУНКЦИЯ ПАРСИНГА
# ------------------------- #


def parse_inline_query(raw_query: Optional[str]) -> ParsedInlineQuery:
    """
    Главная функция, которую будут вызывать inline-хэндлеры.

    Вход:
        raw_query — строка из InlineQuery.query (может быть None или пустой).

    Выход:
        ParsedInlineQuery:
            raw_query      — исходный текст;
            amount         — сумма или None;
            bank_codes     — список всех найденных кодов банков;
            bank_code      — первый из bank_codes или None;
            bank_candidate — текст-кандидат, если банки по словарю не найдены.
    """
    safe_raw = (raw_query or "").strip()           # Гарантируем строку и убираем пробелы по краям

    # --- Шаг 1. Ищем сумму перевода --- #
    amount = _extract_amount(safe_raw)             # Находим первую группу цифр

    # --- Шаг 2. Ищем ВСЕ банки в тексте по словарю BANKS --- #
    bank_codes = _detect_all_bank_codes_from_full_text(safe_raw)  # Список кодов или []

    # --- Шаг 3. Определяем "главный" банк (первый найденный) --- #
    bank_code = bank_codes[0] if bank_codes else None             # Для совместимости с кодом, который ждёт один банк

    # --- Шаг 4. Если ни одного банка не нашли — пробуем выделить текст-кандидат --- #
    if not bank_codes:
        bank_candidate = _extract_bank_candidate_without_dict(safe_raw)  # Текст без суммы/валюты
    else:
        bank_candidate = None                                   # Если банки есть, candidate не нужен

    # Собираем dataclass с результатом и возвращаем его хэндлеру
    return ParsedInlineQuery(
        raw_query=safe_raw,                                     # Исходный текст
        amount=amount,                                          # Найденная сумма (или None)
        bank_codes=bank_codes,                                  # Все коды банков
        bank_code=bank_code,                                    # Первый код (или None)
        bank_candidate=bank_candidate,                          # Текст-кандидат для неизвестного банка
    )
