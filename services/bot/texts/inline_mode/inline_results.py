# services/bot/texts/inline_mode/inline_results.py

"""
Формирование СПИСКА вариантов для INLINE-режима.

Что делает этот модуль:
- берёт данные пользователя (телефоны / карты + банки);
- берёт разобранный запрос из парсера (сумма + банк);
- на выход отдаёт удобные структуры с:
    * заголовком (строка в списке результатов),
    * описанием (серый текст под заголовком),
    * служебной информацией (тип реквизита, номер, банк, сумма).

Согласно твоему запросу:
- в заголовке показываем ТОЛЬКО последние 4 цифры номера:
    * для телефонов — в формате "22 44";
    * для карт — "1234".
- в описании показываем:
    * номер (в таком же коротком формате),
    * сумму (если есть),
    * банк (если есть).
"""

from __future__ import annotations                                       # Разрешаем "отложенные" аннотации типов

from dataclasses import dataclass                                       # dataclass — для удобных "структур"
from typing import List, Literal, Optional                              # Типы-аннотации

from ...database.models import User                                     # Модель пользователя с реквизитами
from ...tools.inline_mode.query_parser import ParsedInlineQuery         # Результат парсинга inline-запроса
from ...tools.banks_wordbook import BANKS                               # Словарь банков (коды,short/long имена)


# ---------------------------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ТИПЫ ДЛЯ РЕЗУЛЬТАТОВ
# ---------------------------------------------------------------------------


@dataclass
class InlinePaymentOption:
    """
    Описание ОДНОГО варианта в списке inline-результатов.

    Поля:
        payment_type  — "phone" или "card" (тип реквизита).
        identifier    — сам номер (телефон или карта) в "сырым" виде.
        title         — заголовок варианта (строка в списке).
        description   — описание под заголовком (серый текст).
        amount        — сумма перевода (может быть None, если не указана).
        bank_code     — внутренний код банка (например, "sber", "tbank") или None.
    """

    payment_type: Literal["phone", "card"]                            # Тип реквизита — телефон или карта
    identifier: str                                                   # Номер телефона или карты (как есть)
    title: str                                                        # Заголовок варианта
    description: str                                                  # Подзаголовок/описание
    amount: Optional[int]                                             # Сумма перевода (если указана)
    bank_code: Optional[str]                                          # Код банка (по словарю BANKS) или None


@dataclass
class InlineBankErrorText:
    """
    Текст для "ошибочного" варианта, когда пользователь указал банк,
    которым он на самом деле не пользуется.

    Пример:
        title       = 'Вы не клиент "ПСБ"'
        description = 'Бот не нашёл ни одного номера или карты с таким банком.'
    """

    title: str                                                        # Заголовок ошибки
    description: str                                                  # Пояснение под заголовком


# ---------------------------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ФОРМАТИРОВАНИЯ
# ---------------------------------------------------------------------------


def _get_bank_display_title(bank_code: Optional[str]) -> Optional[str]:
    """
    Получаем "красивое" короткое название банка по его внутреннему коду.

    Используем:
    - сначала button_title (то, что пишем на кнопках — "Сбер", "Т-Банк", "ПСБ");
    - если его нет, message_title;
    - если банка в словаре нет — возвращаем None.
    """
    if not bank_code:                                                # Если код не передан
        return None                                                  # Нечего отображать

    bank = BANKS.get(bank_code)                                      # Пытаемся взять банк из словаря
    if not bank:                                                     # Если банк не нашли в словаре
        return None                                                  # Ничего не показываем

    # Берём короткое название на кнопке, если оно есть,
    # иначе — "длинное" имя для сообщений.
    return bank.get("button_title") or bank.get("message_title")     # Возвращаем человекочитаемое название


def _format_phone_short(phone: str) -> str:
    """
    Форматирование номера телефона для отображения в inline-списке.

    Требование:
    - показывать только ПОСЛЕДНИЕ 4 цифры в формате "22 44".

    Логика:
    - из исходной строки выбираем только цифры;
    - берём последние до 4 цифр;
    - если цифр 4 -> "12 34";
      если 3 -> "1 23";
      если 2 или 1 -> возвращаем как есть.
    """
    digits = "".join(ch for ch in str(phone) if ch.isdigit())        # Оставляем только цифры
    if not digits:                                                   # Если цифр вообще нет
        return str(phone)                                            # Возвращаем исходное строковое представление

    # Берём "хвост" из 4 цифр (или меньше, если номера короткий)
    core = digits[-4:]                                               # Последние до 4 цифр

    if len(core) == 4:                                               # Нормальный случай "1234" -> "12 34"
        return f"{core[:2]} {core[2:]}"
    elif len(core) >= 2:                                             # "123" или "12" -> разбиваем как "1 23" / "1 2"
        return f"{core[:-2]} {core[-2:]}"
    else:                                                            # Если всего 1 цифра
        return core


def _format_card_short(card_number: str) -> str:
    """
    Форматирование номера карты для отображения в inline-списке.

    Требование:
    - показывать только ПОСЛЕДНИЕ 4 цифры (без пробела).

    Примеры:
        "1234567812345678" -> "5678"
        "5555"             -> "5555"
        "123"              -> "123"
    """
    card_number = "".join(ch for ch in str(card_number) if ch.isdigit())  # Оставляем только цифры
    if len(card_number) <= 4:                                      # Если цифр 4 или меньше
        return card_number                                         # Показываем всё как есть
    return card_number[-4:]                                        # Иначе берём последние 4 цифры


def _build_phone_title(
    *,
    phone_display: str,
    amount: Optional[int],
    bank_title: Optional[str],
) -> str:
    """
    Формируем заголовок ДЛЯ ТЕЛЕФОНА.

    С учётом твоих изменений:

    - используем короткий номер phone_display (последние 4 цифры "22 44");
    - сумма и банк в заголовке остаются, как ты уже настроил:

      Есть сумма:
        - есть банк:
          "Перевод 500Р, номер 22 44 (Сбер)"
        - нет банка:
          "Перевод 500Р, номер 22 44"

      Нет суммы:
        - есть банк:
          "Перевод, номер 22 44 (Сбер, без суммы)"
        - нет банка:
          "Перевод, номер 22 44 (Без суммы)"
    """
    # Базовая часть заголовка — без скобок с банком/суммой
    if amount is not None:                                          # Если сумма указана
        base = f"Перевод {amount}₽, номер {phone_display}"          # Добавляем сумму в текст
    else:                                                           # Если суммы нет
        base = f"Перевод, телефон {phone_display}"                    # Формулировка без суммы

    # Формируем то, что будет в скобочках
    if amount is None:                                              # Сумма НЕ указана
        if bank_title:                                              # Есть известный банк
            suffix = f"({bank_title}, без суммы)"                   # Пример: "(Сбер, без суммы)"
        else:                                                       # Банка нет
            suffix = "(Без суммы)"                                  # Пример: "(Без суммы)"
    else:                                                           # Сумма указана
        if bank_title:                                              # Если банк известен
            suffix = f"({bank_title})"                              # Пример: "(Сбер)"
        else:                                                       # Банк не известен/не выбран
            suffix = ""                                             # Считаем, что скобочки не нужны

    # Склеиваем базовый текст и суффикс (если он есть)
    return f"{base} {suffix}".strip()                               # strip() на случай пустого суффикса


def _build_card_title(
    *,
    card_display: str,
    amount: Optional[int],
    bank_title: Optional[str],
) -> str:
    """
    Формируем заголовок ДЛЯ КАРТЫ.

    Аналогично телефону, но с текстом "карта":

      Есть сумма:
        - есть банк:
          "Перевод 500Р, карта 1234 (Т-Банк)"
        - нет банка:
          "Перевод 500Р, карта 1234"

      Нет суммы:
        - есть банк:
          "Перевод, карта 1234 (Т-Банк, без суммы)"
        - нет банка:
          "Перевод, карта 1234 (Без суммы)"
    """
    if amount is not None:                                          # Если сумма указана
        base = f"Перевод {amount}₽, карта {card_display}"
    else:                                                           # Если суммы нет
        base = f"Перевод, карта {card_display}"

    if amount is None:                                              # Нет суммы
        if bank_title:                                              # Есть банк
            suffix = f"({bank_title}, без суммы)"                   # "(Т-Банк, без суммы)"
        else:                                                       # Банка нет
            suffix = "(Без суммы)"                                  # "(Без суммы)"
    else:                                                           # Сумма указана
        if bank_title:                                              # Есть банк
            suffix = f"({bank_title})"                              # "(Т-Банк)"
        else:
            suffix = ""                                             # Скобочки не пишем

    return f"{base} {suffix}".strip()                               # Склеиваем и чистим лишний пробел


def _build_phone_description(
    phone_display: str,
    amount: Optional[int],
    bank_title: Optional[str],
) -> str:
    """
    Описание (подзаголовок) для варианта с телефоном.

    Требование:
    - номер показываем коротким (как в заголовке);
    - если есть сумма — добавляем "на сумму 500Р";
    - если есть банк — "в банк Сбер".

    Примеры:
        "Будет отправлен запрос перевода по номеру телефона 22 44 (на сумму 500Р, в банк Сбер)"
        "Будет отправлен запрос перевода по номеру телефона 22 44 (в банк Т-Банк)"
        "Будет отправлен запрос перевода по номеру телефона 22 44"
    """
    base = f"Будет отправлен запрос перевода по номеру телефона {phone_display}"

    details_parts: List[str] = []                                   # Список "кусочков" описания

    if amount is not None:                                          # Если есть сумма
        details_parts.append(f"на сумму {amount}₽")                 # Добавляем "на сумму 500Р"

    if bank_title:                                                  # Если задан банк
        details_parts.append(f"в банк {bank_title}")                # Добавляем "в банк Сбер"

    if details_parts:                                               # Если есть хоть один "куски"
        details = ", ".join(details_parts)                          # Склеиваем через запятую
        return f"{base} ({details})"                                # Добавляем в круглых скобках

    return base                                                     # Если нет ни суммы, ни банка — просто базовый текст


def _build_card_description(
    card_display: str,
    amount: Optional[int],
    bank_title: Optional[str],
) -> str:
    """
    Описание для варианта с картой.

    Аналогично телефону, только "на карту":

    Примеры:
        "Будет отправлен запрос перевода на карту 1234 (на сумму 500Р, в банк Т-Банк)"
        "Будет отправлен запрос перевода на карту 1234 (на сумму 500Р)"
        "Будет отправлен запрос перевода на карту 1234"
    """
    base = f"Будет отправлен запрос перевода на карту {card_display}"

    details_parts: List[str] = []                                   # Список деталей

    if amount is not None:
        details_parts.append(f"на сумму {amount}₽")

    if bank_title:
        details_parts.append(f"в банк {bank_title}")

    if details_parts:
        details = ", ".join(details_parts)
        return f"{base} ({details})"

    return base


# ---------------------------------------------------------------------------
# ОСНОВНАЯ ЛОГИКА ПО СБОРКЕ СПИСКА ВАРИАНТОВ
# ---------------------------------------------------------------------------


def _iter_user_phones_with_bank_filter(
    user: User,
    bank_code_filter: Optional[str],
) -> List[InlinePaymentOption]:
    """
    Собираем ВСЕ подходящие номера телефонов пользователя
    с учётом возможного фильтра по банку.

    Логика фильтра:
    - если bank_code_filter == None:
        * показываем все телефоны;
        * для отображения банка берём phone_data.main_bank (если есть).
    - если bank_code_filter задан:
        * показываем только те телефоны, у которых:
            - bank_code_filter == main_bank ИЛИ
            - bank_code_filter содержится в phone_data.banks;
        * для отображения банка используем ИМЕННО bank_code_filter
          (то есть даже если у телефона несколько банков).
    """
    results: List[InlinePaymentOption] = []                         # Список для накопления вариантов

    for phone, phone_data in user.phones.items():                   # Перебираем все телефоны пользователя
        # Определяем, подходит ли телефон под фильтр по банку
        if bank_code_filter is not None:                            # Если фильтр по банку задан
            banks_for_phone = list(phone_data.banks or [])          # Все банки, привязанные к телефону
            main_bank = phone_data.main_bank                        # Основной банк (если есть)

            # Телефон нам интересен, если:
            #  - фильтр совпадает с основным банком ИЛИ
            #  - фильтр есть в списке всех банков телефона.
            if (
                bank_code_filter != main_bank
                and bank_code_filter not in banks_for_phone
            ):
                continue                                            # Если не совпало — пропускаем телефон

            bank_code_to_use = bank_code_filter                    # Для отображения используем банк из фильтра
        else:
            # Фильтра по банку нет — просто берём основной банк (если он задан)
            bank_code_to_use = phone_data.main_bank

        # Формируем короткий вид номера (последние 4 цифры "22 44")
        phone_display = _format_phone_short(phone)
        bank_title = _get_bank_display_title(bank_code_to_use)     # "Сбер", "Т-Банк" и т.п.

        # Здесь заголовок/описание пока делаем с amount=None,
        # т.к. реальная сумма будет подставлена в build_inline_payment_options()
        title = _build_phone_title(
            phone_display=phone_display,
            amount=None,                                            # amount заполним позже
            bank_title=bank_title,
        )

        description = _build_phone_description(
            phone_display=phone_display,
            amount=None,                                            # суммы пока нет
            bank_title=bank_title,
        )

        # Сохраняем "сырой" вариант без суммы (она добавится позже)
        results.append(
            InlinePaymentOption(
                payment_type="phone",                              # Тип — телефон
                identifier=phone,                                  # Храним исходный номер (полный)
                title=title,                                       # Заголовок (без учёта суммы)
                description=description,                           # Описание
                amount=None,                                       # Сумму допишем позже
                bank_code=bank_code_to_use,                        # Код банка
            )
        )

    return results                                                 # Возвращаем список вариантов по телефонам


def _iter_user_cards_with_bank_filter(
    user: User,
    bank_code_filter: Optional[str],
) -> List[InlinePaymentOption]:
    """
    Собираем ВСЕ подходящие карты пользователя с учётом фильтра по банку.

    Логика фильтра:
    - если bank_code_filter == None:
        * показываем все карты;
        * для отображения банка берём card_data.bank.
    - если bank_code_filter задан:
        * показываем только те карты, у которых card_data.bank == bank_code_filter.
    """
    results: List[InlinePaymentOption] = []                        # Список для накопления вариантов

    for card_number, card_data in user.cards.items():              # Перебираем все карты пользователя
        card_bank_code = card_data.bank                            # Банк, привязанный к карте

        # Проверяем соответствие фильтру
        if bank_code_filter is not None and card_bank_code != bank_code_filter:
            continue                                               # Карта не подходит под фильтр — пропускаем

        card_display = _format_card_short(card_number)             # Короткое отображение (последние 4 цифры)
        bank_title = _get_bank_display_title(card_bank_code or bank_code_filter)

        title = _build_card_title(                                 # Строим заголовок для карты с amount=None
            card_display=card_display,
            amount=None,
            bank_title=bank_title,
        )
        description = _build_card_description(                     # И описание с amount=None
            card_display=card_display,
            amount=None,
            bank_title=bank_title,
        )

        results.append(
            InlinePaymentOption(
                payment_type="card",                               # Тип — карта
                identifier=card_number,                            # Храним полный номер карты
                title=title,                                       # Заголовок (без суммы)
                description=description,                           # Подзаголовок
                amount=None,                                       # Сумма будет добавлена выше
                bank_code=card_bank_code,                          # Код банка, привязанный к карте
            )
        )

    return results                                                 # Возвращаем список вариантов по картам


def build_inline_payment_options(
    *,
    user: User,
    parsed_query: ParsedInlineQuery,
) -> List[InlinePaymentOption]:
    """
    Главная функция модуля: собирает ВСЕ варианты для inline-списка.

    Вход:
        user         — доменная модель пользователя (с телефонами/картами);
        parsed_query — результат работы парсера (сумма, банк, candidate).

    Выход:
        список InlinePaymentOption, в котором уже:
        - заголовки и описания соответствуют схемам;
        - применён фильтр по банку (если он есть);
        - учтено наличие/отсутствие суммы.
    """
    amount = parsed_query.amount                                   # Сумма, которую ввёл пользователь (или None)
    bank_code_filter = parsed_query.bank_code                      # Банк из парсера (или None)

    # 1) Собираем все подходящие телефоны с учётом фильтра по банку
    phone_options = _iter_user_phones_with_bank_filter(
        user=user,
        bank_code_filter=bank_code_filter,
    )

    # 2) Собираем все подходящие карты с учётом фильтра по банку
    card_options = _iter_user_cards_with_bank_filter(
        user=user,
        bank_code_filter=bank_code_filter,
    )

    # Объединяем телефоны и карты в один список
    all_options: List[InlinePaymentOption] = phone_options + card_options

    # 3) Подставляем сумму в заголовки и дописываем сумму/банк в описания
    for option in all_options:
        # Определяем человекочитаемое название банка
        bank_title = _get_bank_display_title(option.bank_code or bank_code_filter)

        # Обновляем amount в самой структуре варианта
        option.amount = amount

        if option.payment_type == "phone":                        # Для телефонов
            phone_display = _format_phone_short(option.identifier)  # Короткое отображение ("22 44")

            option.title = _build_phone_title(
                phone_display=phone_display,
                amount=amount,
                bank_title=bank_title,
            )
            option.description = _build_phone_description(
                phone_display=phone_display,
                amount=amount,
                bank_title=bank_title,
            )
        else:                                                      # Для карт
            card_display = _format_card_short(option.identifier)   # Короткое отображение ("1234")

            option.title = _build_card_title(
                card_display=card_display,
                amount=amount,
                bank_title=bank_title,
            )
            option.description = _build_card_description(
                card_display=card_display,
                amount=amount,
                bank_title=bank_title,
            )

    return all_options                                             # Возвращаем готовый список вариантов


# ---------------------------------------------------------------------------
# ТЕКСТЫ ДЛЯ СЦЕНАРИЯ "ВЫ НЕ КЛИЕНТ ЭТОГО БАНКА"
# ---------------------------------------------------------------------------


def build_bank_not_client_error_text(bank_name: str) -> InlineBankErrorText:
    """
    Формируем текст для случая, когда пользователь указал банк,
    но у него НЕТ ни одного номера/карты с таким банком.
    """
    title = f'Вы не клиент "{bank_name}"'                         # Заголовок с названием банка в кавычках
    description = (                                               # Короткое пояснение под заголовком
        "Бот не нашёл ни одного номера телефона или карты, "
        "подключённых к этому банку."
    )

    return InlineBankErrorText(title=title, description=description)
