"""Строитель deeplink-ссылок для ВТБ."""

from __future__ import annotations  # Включаем отложенные аннотации

from services.WebApp.schemas.link_payload import LinkBuilderRequest, LinkBuilderResult  # Импортируем схемы запросов и ответов


def build_vtb_universal(payload: LinkBuilderRequest) -> LinkBuilderResult:
    """Формирует deeplink и безопасный fallback для ВТБ."""

    identifier_type = payload.get("identifier_type", "")  # Узнаём тип реквизита (phone/card)
    identifier_value = payload.get("identifier_value", "")  # Получаем значение реквизита
    digits_only = "".join(ch for ch in identifier_value if ch.isdigit())  # Очищаем строку от лишних символов

    normalized_digits = digits_only  # Сохраняем очищенные цифры для вставки в ссылку
    deeplink = f"https://online.vtb.ru/i/cell/ppl/{normalized_digits}"  # Используем рабочий deeplink-шаблон ВТБ

    fallback_url = (
        "https://online.vtb.ru/transfers/transferByPhone?isStandaloneScenario=true"
        "&actionType=generalTargetSearch&tab=SWITCH_TO_OP_4808&isForeingNumber=false"
        "&isInternalTargetSearch=false&predefinedValues%5BpredefinedPhoneNumber%5D=%2B7%20916%20079-44-59&stage=INPUT"
    )  # Мягкий fallback, не дающий ошибку в браузерах
    link_id = f"vtb:{identifier_type}:{normalized_digits}"  # Уникальный идентификатор ссылки для логов

    return {
        "deeplink": deeplink,  # Deep link для открытия приложения ВТБ
        "fallback_url": fallback_url,  # Перенаправление в веб при проблемах с deep link
        "link_id": link_id,  # Идентификатор ссылки для телеметрии
    }
