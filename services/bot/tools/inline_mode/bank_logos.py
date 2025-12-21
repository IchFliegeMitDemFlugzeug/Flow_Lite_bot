# services/bot/tools/inline_mode/bank_logos.py

""" 
Утилиты для подстановки логотипов банков в INLINE-результаты.

ВАЖНОЕ ограничение Telegram:
- thumbnail_url в InlineQueryResultArticle должен быть ПУБЛИЧНЫМ HTTPS-URL;
- Telegram НЕ умеет брать картинку с локального пути на диске твоего бота.

Поэтому:
- сами файлы логотипов могут лежать в репозитории (как у тебя в services/bot/headlines/inline_mode/LOGO_*.jpg),
  но для inline-списка мы используем URL, по которому Telegram сможет скачать картинку.
- самый простой MVP-вариант — захостить эти же картинки на GitHub Pages (или на любом CDN) и указать базовый URL.

Этот модуль НЕ делает сетевых запросов — он только собирает URL по bank_code.
"""  # Докстринг — объясняет назначение модуля

from __future__ import annotations  # Позволяем использовать аннотации типов "вперёд" без кавычек

import os  # os нужен, чтобы читать переменные окружения (настройка base URL без правок кода)
from typing import Optional, Dict  # Optional и Dict — для типизации возвращаемых значений и словаря

# ---------------------------------------------------------------------------
# Настройка: где лежат логотипы по HTTPS
# ---------------------------------------------------------------------------

BANK_LOGOS_BASE_URL: str = os.getenv(  # Читаем базовый URL из переменной окружения (удобно менять на сервере)
    "BANK_LOGOS_BASE_URL",             # Имя переменной окружения
    "https://ichfliegemitdemflugzeug.github.io/Tbank_btn/", # Значение по умолчанию (TODO: заменить на реальный хостинг логотипов)
)  # ВАЖНО: должен заканчиваться на "/" чтобы корректно конкатенировать имя файла


# ---------------------------------------------------------------------------
# Маппинг: bank_code -> имя файла логотипа
# ---------------------------------------------------------------------------

LOGO_FILENAME_BY_BANK_CODE: Dict[str, str] = {  # Явный словарь сопоставления кодов банков и файлов
    "sber": "LOGO_SBER.png",                    # Сбер
    "tbank": "LOGO_TBANK.png",                  # Т-Банк
    "vtb": "LOGO_VTB.png",                      # ВТБ
    "alfa": "LOGO_ALFABANK.png",                # Альфа
    "mkb": "LOGO_MKB.png",                      # МКБ
    "psb": "LOGO_PSB.png",                      # ПСБ
    "gazprom": "LOGO_GAZPROMBANK.png",          # Газпромбанк
    "pochtab": "LOGO_POCHTABANK.png",           # Почта Банк
    "rshb": "LOGO_RSHB.png",                    # Россельхозбанк
    "sovcom": "LOGO_SOVKOMBANK.png",            # Совкомбанк
    # Ниже — задел под расширение словаря BANKS (если добавишь новые банки / логотипы)
    "mtsbank": "LOGO_MTSBANK.png",              # МТС Банк (если появится в словаре кодов)
}  # Если код банка не найден — логотип не подставляем (Telegram покажет результат без картинки)


def build_bank_logo_url(*, bank_code: Optional[str]) -> Optional[str]:
    """ 
    Возвращает HTTPS-URL логотипа для заданного bank_code.

    Args:
        bank_code: внутренний код банка (например: "sber", "tbank") или None.

    Returns:
        Полный URL логотипа (str) или None, если логотип для этого кода не настроен.
    """  # Докстринг — чтобы было понятно, что делает функция

    if not bank_code:  # Если кода банка нет (например, "любой банк")
        return None    # Тогда логотип не подставляем

    filename: Optional[str] = LOGO_FILENAME_BY_BANK_CODE.get(bank_code)  # Берём имя файла по коду банка

    if not filename:  # Если под этот банк файл не настроен
        return None   # Возвращаем None — результат будет без превью-картинки

    # Гарантируем, что base URL заканчивается "/" (на случай если пользователь забудет)
    base: str = BANK_LOGOS_BASE_URL if BANK_LOGOS_BASE_URL.endswith("/") else BANK_LOGOS_BASE_URL + "/"  # Нормализуем base URL

    return base + filename  # Склеиваем base URL и имя файла (например, https://.../LOGO_SBER.jpg)
