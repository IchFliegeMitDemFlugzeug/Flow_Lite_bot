"""Строитель deeplink-ссылок для Т-Банка (бывший Тинькофф)."""

from __future__ import annotations  # Поддерживаем отложенные аннотации для согласованности

import json  # Сериализуем объект predefined
from urllib.parse import quote  # Кодируем JSON параметра predefined в URL

from services.WebApp.schemas.link_payload import LinkBuilderRequest, LinkBuilderResult  # Импортируем схемы запросов и ответов


def build_tinkoff_phone(payload: LinkBuilderRequest) -> LinkBuilderResult:
    """Собирает ссылку на оплату по телефону в Т-Банк."""

    raw_phone = payload.get("identifier_value", "")  # Забираем номер телефона из запроса
    digits_only = "".join(ch for ch in raw_phone if ch.isdigit())  # Убираем пробелы и посторонние символы
    normalized_phone = digits_only if digits_only.startswith("7") else "7" + digits_only.lstrip("8")  # Приводим к виду 7XXXXXXXXXX
    predefined_json = {"phone": f"+{normalized_phone}"}  # Готовим объект для параметра predefined
    encoded_predefined = quote(json.dumps(predefined_json, ensure_ascii=False))  # Кодируем JSON в URL без потери символов

    deeplink = (
        "https://www.tbank.ru/mybank/payments/persons/phone/"
        "?internal_source=homePayments_transferByPhoneSmall_suggest"
        f"&predefined={encoded_predefined}"
    )  # Строим ссылку, совпадающую с публичным шаблоном
    fallback_url = deeplink  # Для Т-Банка веб-ссылка совпадает с deeplink и открывается в браузере
    link_id = f"tbank:phone:{normalized_phone}"  # Уникальный идентификатор для логов

    return {
        "deeplink": deeplink,  # Deeplink/веб-ссылка на оплату по телефону
        "fallback_url": fallback_url,  # Запасной URL для браузера
        "link_id": link_id,  # Идентификатор ссылки для телеметрии
    }
