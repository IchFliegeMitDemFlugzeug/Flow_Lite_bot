"""Типы данных для генерации ссылок."""

from __future__ import annotations  # Включаем отложенные аннотации

from typing import TypedDict  # Используем TypedDict для статической структуры данных


class LinkBuilderRequest(TypedDict, total=False):
    """Запрос в конструктор ссылок."""

    identifier_type: str  # Тип реквизита: phone или card
    identifier_value: str  # Значение реквизита (телефон или карта)
    amount: str | None  # Необязательная сумма перевода
    comment: str | None  # Необязательный комментарий для перевода
    extra: dict | None  # Дополнительные поля, если они понадобятся конструктору


class LinkBuilderResult(TypedDict):
    """Ответ конструктора ссылок."""

    deeplink: str  # Ссылка для открытия приложения банка
    fallback_url: str  # Запасная ссылка на веб-страницу
    link_id: str  # Уникальный идентификатор для телеметрии

