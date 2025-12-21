"""Строитель deeplink-ссылок для ВТБ."""

from __future__ import annotations  # Включаем отложенные аннотации

from services.WebApp.schemas.link_payload import LinkBuilderRequest, LinkBuilderResult  # Импортируем схемы запросов и ответов


def build_vtb_generic(payload: LinkBuilderRequest) -> LinkBuilderResult:
    """Формирует ссылки ВТБ для телефона или карты."""

    identifier_type = payload.get("identifier_type", "")  # Узнаём тип реквизита
    identifier_value = payload.get("identifier_value", "")  # Получаем значение реквизита
    digits_only = "".join(ch for ch in identifier_value if ch.isdigit())  # Очищаем строку от лишних символов

    if identifier_type == "card":  # Если передана карта
        deeplink = f"vtb://transfer/card/{digits_only}"  # Deep link для перевода по карте
        fallback_url = f"https://online.vtb.ru/payments/card2card?cardNumber={digits_only}"  # Веб-страница для перевода по карте
    else:  # Если тип не карта, считаем, что это телефон
        normalized_phone = digits_only if digits_only.startswith("7") else "7" + digits_only  # Приводим номер к виду 7XXXXXXXXXXX
        deeplink = f"vtb://p2p/{normalized_phone}"  # Deep link для перевода по телефону
        fallback_url = f"https://online.vtb.ru/payments/p2p?phone={normalized_phone}"  # Веб-страница для перевода по телефону

    link_id = f"vtb:{identifier_type}:{digits_only}"  # Уникальный идентификатор ссылки для логов

    return {
        "deeplink": deeplink,  # Deep link в приложение ВТБ
        "fallback_url": fallback_url,  # Запасная ссылка в браузере
        "link_id": link_id,  # Идентификатор ссылки для телеметрии
    }

