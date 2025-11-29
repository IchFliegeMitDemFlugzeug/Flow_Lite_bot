# -*- coding: utf-8 -*-  # Кодировка файла

"""
Публичный интерфейс для работы с "базой данных" бота.

Из других модулей бота мы импортируем функции только из ЭТОГО файла, например:

    from ..database import get_user, add_or_update_phone

Внутри уже спрятана реализация на JSON-файлах.
"""

from .models import UserData, PhoneData                        # Экспортируем модели данных
from .storage import (                                         # Экспортируем функции работы с файловой "базой"
    get_user,
    load_user,
    save_user,
    update_basic_user_info,
    add_or_update_phone,
    add_card,
    remove_card,
    set_registration_progress,
    get_registration_progress,
)

__all__ = [                                                    # Явно указываем, что можно импортировать из этого модуля
    "UserData",
    "PhoneData",
    "get_user",
    "load_user",
    "save_user",
    "update_basic_user_info",
    "add_or_update_phone",
    "add_card",
    "remove_card",
    "set_registration_progress",
    "get_registration_progress",
]
