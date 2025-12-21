"""Строитель deeplink-ссылок для Сбербанка.

Здесь мы собираем SMS/P2P-ссылку на перевод по номеру телефона. Формат
ссылки взят из публичного шаблона Сбербанка и может использоваться как
deep link и как fallback в браузере.
"""

from __future__ import annotations  # Включаем отложенные аннотации для читаемости

from services.WebApp.schemas.link_payload import LinkBuilderRequest, LinkBuilderResult  # Импортируем типы запросов и ответов


def build_sber_phone(payload: LinkBuilderRequest) -> LinkBuilderResult:
    """Собирает ссылку на перевод по телефону в Сбербанк."""

    raw_phone = payload.get("identifier_value", "")  # Забираем исходный телефон из запроса
    digits_only = "".join(ch for ch in raw_phone if ch.isdigit() or ch == "+")  # Оставляем только цифры и плюс
    normalized_phone = digits_only if digits_only.startswith("+") else "+" + digits_only  # Приводим номер к формату +7...

    deeplink = f"https://www.sberbank.com/sms/pbpn?requisiteNumber={normalized_phone}"  # Шаблон для SMS/DeepLink
    fallback_url = deeplink  # Для Сбера ссылка fallback совпадает с deeplink
    link_id = f"sber:{normalized_phone}"  # Уникальный идентификатор ссылки для логов

    return {
        "deeplink": deeplink,  # Deep link для открытия приложения Сбера
        "fallback_url": fallback_url,  # Веб-страница для перехода, если приложение не открылось
        "link_id": link_id,  # Идентификатор ссылки для телеметрии
    }

