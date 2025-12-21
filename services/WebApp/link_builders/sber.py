"""Строитель deeplink-ссылок для Сбербанка.

На основе переданного идентификатора собираем рабочую ссылку формата
`https://www.sberbank.com/sms/pbpn?requisiteNumber=<значение>`, которая
подходит и для номера телефона, и для номера карты. Fallback совпадает
с deeplink, поэтому пользователь всегда откроет корректную страницу.
"""

from __future__ import annotations  # Включаем отложенные аннотации для читаемости

from services.WebApp.schemas.link_payload import LinkBuilderRequest, LinkBuilderResult  # Импортируем типы запросов и ответов


def build_sber_universal(payload: LinkBuilderRequest) -> LinkBuilderResult:
    """Собирает ссылку для Сбера по телефону или карте."""

    raw_value = payload.get("identifier_value", "")  # Берём исходное значение реквизита
    digits_only = "".join(ch for ch in raw_value if ch.isdigit())  # Оставляем только цифры
    normalized_value = digits_only  # Сохраняем очищенное значение как единый формат для ссылки

    deeplink = f"https://www.sberbank.com/sms/pbpn?requisiteNumber={normalized_value}"  # Формируем ссылку с параметром requisiteNumber
    fallback_url = deeplink  # Fallback совпадает с deeplink и работает в браузере
    link_id = f"sber:{payload.get('identifier_type', 'unknown')}:{normalized_value}"  # Уникальный идентификатор для телеметрии

    return {
        "deeplink": deeplink,  # Deep link/веб-ссылка Сбера
        "fallback_url": fallback_url,  # Запасной URL при проблемах с deep link
        "link_id": link_id,  # Идентификатор ссылки для логов
    }
