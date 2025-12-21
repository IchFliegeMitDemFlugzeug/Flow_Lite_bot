"""Реестр конструкторов deeplink-ссылок для банков.

Каждая функция-строитель принимает словарь с полями идентификатора
получателя и возвращает deeplink вместе с fallback-ссылкой. Регистрация
происходит в `BUILDER_REGISTRY`, чтобы backend мог по `builder` из
`banks.json` быстро найти нужную функцию.
"""

from __future__ import annotations  # Разрешаем отложенные аннотации для читаемости

from typing import Callable, Dict  # Импортируем типы для реестра

from .sber import build_sber_universal  # Строитель ссылок для Сбера по телефону или карте
from .tinkoff import build_tinkoff_phone  # Строитель ссылок для Т-Банка по телефону
from .vtb import build_vtb_universal  # Универсальный строитель ссылок для ВТБ
from services.WebApp.schemas.link_payload import LinkBuilderRequest, LinkBuilderResult  # Общие схемы запросов и ответов

# Реестр доступных конструкторов по идентификатору из banks.json
BUILDER_REGISTRY: Dict[str, Callable[[LinkBuilderRequest], LinkBuilderResult]] = {
    "sber_universal": build_sber_universal,  # Сбербанк: перевод по телефону или карте
    "tinkoff_phone": build_tinkoff_phone,  # Т-Банк: перевод по номеру телефона
    "vtb_universal": build_vtb_universal,  # ВТБ: универсальные ссылки для телефона или карты
}


def get_builder(builder_id: str) -> Callable[[LinkBuilderRequest], LinkBuilderResult] | None:
    """Возвращает функцию-конструктор по её идентификатору.

    Если конструктор не зарегистрирован, отдаём `None`, чтобы backend
    мог записать ошибку и предложить безопасный fallback.
    """

    return BUILDER_REGISTRY.get(builder_id)  # Ищем конструктор в реестре

