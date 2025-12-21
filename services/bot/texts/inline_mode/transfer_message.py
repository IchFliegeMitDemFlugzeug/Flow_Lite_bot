# services/bot/texts/inline_mode/transfer_message.py

"""
Формирование текста СООБЩЕНИЯ, которое уходит в чат
после выбора варианта из inline-списка.

НОВЫЙ формат (3 строки):

1) Сумма (жирным): {amount} ₽
2) {bank_name}, {phone_number}
3) {user_fio}            (ОПЦИОНАЛЬНО)

Правила:
- Если сумма не указана — показываем "Уточните у получателя" (без "₽").
- Если банк не распознали или он не привязан к реквизитам — "Уточните у получателя".
- user_fio (ФИО полностью) — опционален:
  если его нет / пустой — строку НЕ выводим и бот НЕ падает.
"""

from __future__ import annotations  # Разрешаем "отложенные" аннотации типов (удобно для type hints)

from typing import Optional  # Optional[T] = T | None — для читабельной типизации

from .inline_results import InlinePaymentOption  # Структура с данными варианта (тип, номер, сумма, банк)
from ...tools.inline_mode.query_parser import ParsedInlineQuery  # Результат парсинга inline-запроса
from ...tools.banks_wordbook import BANKS  # Словарь банков (code, button_title, message_title и т.д.)

# Заглушка, когда данных нет
PLUG: str = "_Уточните у получателя_"  # Подчёркивания = курсив в Markdown (parse_mode="Markdown")


def _get_bank_title(bank_code: Optional[str]) -> Optional[str]:
    """
    Возвращаем человекочитаемое название банка по его коду.

    Используем:
    - button_title (короткое название — "Сбер", "Т-Банк", "ПСБ");
    - если его нет, message_title (полное название);
    - если банк не найден или кода нет — возвращаем None.
    """
    if not bank_code:  # Если код банка не передан — возвращаем None
        return None  # Нечего искать

    bank_data = BANKS.get(bank_code)  # Пытаемся достать банк из словаря по коду

    if not bank_data:  # Если по коду ничего не нашли
        return None  # Значит банк неизвестен

    # Берём короткое название, если есть, иначе — полное
    return bank_data.get("button_title") or bank_data.get("message_title")


def _format_amount_value(amount: Optional[int]) -> str:
    """
    Форматируем значение суммы для 1-й строки.

    - Если сумма есть: возвращаем строку "{amount} ₽"
    - Если суммы нет: возвращаем "Уточните у получателя"
    """
    if amount is not None:  # Если сумма определена
        return f"`{amount}`* ₽*"  # Возвращаем сумму с символом рубля

    return PLUG  # Если суммы нет — просим уточнить у получателя


def _format_recipient_bank(option: InlinePaymentOption, parsed_query: ParsedInlineQuery) -> str:
    """
    Определяем, что выводить как bank_name во 2-й строке.

    Приоритет:
    1) option.bank_code — если банк привязан к самому реквизиту (телефон/карта)
    2) parsed_query.bank_code — если вариант "любой банк", но в тексте запроса указан банк
    Если банка нигде нет или код не распознан — возвращаем PLUG.
    """
    bank_code = option.bank_code  # Сначала пробуем банк из варианта (привязка к реквизиту)

    if bank_code is None and parsed_query.bank_code is not None:  # Если у варианта нет банка, но в запросе банк был
        bank_code = parsed_query.bank_code  # Берём банк из запроса

    bank_title = _get_bank_title(bank_code)  # Превращаем код банка в читаемое название

    if bank_title:  # Если получилось получить название
        return bank_title  # Возвращаем название

    return PLUG  # Иначе — заглушка "Уточните у получателя"


def build_transfer_message_text(
    *,
    option: InlinePaymentOption,  # Вариант, который пользователь выбрал из inline-списка
    parsed_query: ParsedInlineQuery,  # Результат парсинга inline-запроса (сумма/банки и т.п.)
    user_fio: Optional[str] = None,  # Полное ФИО (Фамилия Имя Отчество). Опционально.
) -> str:
    """
    Собираем итоговый текст сообщения, которое бот отправит в чат
    после выбора inline-результата.

    Формат:
        *Сумма:* {amount} ₽
        {bank_name}, {phone_number}
        {user_fio}               (опционально)

    Важно:
    - Если user_fio не передали или он пустой — третью строку НЕ выводим.
    """
    # --- 1) Определяем "эффективную" сумму (из варианта или из парсера) --- #
    effective_amount: Optional[int] = (  # Объявляем переменную с типом Optional[int]
        option.amount  # Сначала пытаемся взять сумму, уже сохранённую в варианте
        if option.amount is not None  # Если в варианте сумма действительно есть
        else parsed_query.amount  # Иначе подстраховываемся суммой из парсера
    )

    # --- 2) Формируем 1-ю строку (жирная "Сумма") --- #
    amount_value: str = _format_amount_value(effective_amount)  # Получаем "{amount} ₽" или заглушку
    line_1: str = f"*Сумма • * {amount_value}"  # Собираем первую строку (Markdown bold через *)

    # --- 3) Формируем 2-ю строку: "{bank_name}, {phone_number}" --- #
    bank_name: str = _format_recipient_bank(option, parsed_query)  # Определяем, что писать как банк
    phone_or_card: str = str(option.identifier)  # Берём реквизит как строку (телефон или карта)
    line_2: str = f"{bank_name} • {phone_or_card}"  # Склеиваем "банк, номер"

    # --- 4) Опциональная 3-я строка: "{user_fio}" --- #
    # Приводим user_fio к "нормальной" строке: убираем пробелы, превращаем пустоту в None
    fio_clean: Optional[str] = (  # Объявляем переменную, где будет "очищенное" ФИО
        str(user_fio).strip()  # Приводим к строке и убираем пробелы по краям
        if user_fio is not None  # Только если user_fio вообще передан
        else None  # Иначе оставляем None
    )

    # --- 5) Склеиваем строки --- #
    lines: list[str] = [line_1, line_2]  # Базово всегда есть 2 строки

    if fio_clean:  # Если ФИО непустое (не None и не "")
        lines.append(fio_clean)  # Добавляем 3-ю строку

    message_text: str = "\n".join(lines)  # Склеиваем строки через перенос

    return message_text  # Возвращаем итоговый текст для InputTextMessageContent.message_text
