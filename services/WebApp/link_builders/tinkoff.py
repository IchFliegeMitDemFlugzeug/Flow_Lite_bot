"""Строитель deeplink-ссылок для Т-Банка (бывший Тинькофф)."""

from __future__ import annotations  # Поддерживаем отложенные аннотации для согласованности

from services.WebApp.schemas.link_payload import LinkBuilderRequest, LinkBuilderResult  # Импортируем схемы запросов и ответов


def build_tinkoff_card(payload: LinkBuilderRequest) -> LinkBuilderResult:
    """Собирает ссылку на перевод по номеру карты в Т-Банк."""

    raw_card = payload.get("identifier_value", "")  # Достаём номер карты из запроса
    digits_only = "".join(ch for ch in raw_card if ch.isdigit())  # Убираем пробелы и прочие символы
    deeplink = f"tbank://transfer/card?number={digits_only}"  # Deep link в приложение Т-Банка
    fallback_url = f"https://www.tbank.ru/cards/transfer/?cardNumber={digits_only}"  # Веб-версия перевода
    link_id = f"tbank:{digits_only}"  # Идентификатор ссылки для логов

    return {
        "deeplink": deeplink,  # Deep link в Т-Банк
        "fallback_url": fallback_url,  # Запасная веб-ссылка на перевод
        "link_id": link_id,  # Уникальный идентификатор для телеметрии
    }

