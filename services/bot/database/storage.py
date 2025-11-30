# services/bot/database/storage.py

"""
Низкоуровневые функции работы с файловой "базой данных".

Здесь:
- сохраняем и читаем пользователей в / из JSON-файлов;
- отдельно храним last_bot_message_id по chat_id в файле last_messages.json.
"""

from __future__ import annotations  # Разрешаем аннотации на будущие версии Python

import json                         # JSON — формат хранения данных на диске
from pathlib import Path            # Path — удобная работа с путями
from typing import Dict, Optional   # Типы для аннотаций

from .models import User            # Импортируем модель User для работы с пользователями


# Определяем базовую папку для модуля database (папка, где лежит этот файл)
BASE_DIR: Path = Path(__file__).resolve().parent

# Папка, где будем хранить пользователей (по одному JSON-файлу на пользователя)
USERS_DIR: Path = BASE_DIR / "users"

# Файл, в котором будем хранить ID последнего сообщения бота по каждому chat_id
LAST_MESSAGES_FILE: Path = BASE_DIR / "last_messages.json"

# Гарантируем, что папка для пользователей существует
USERS_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> dict:
    """
    Вспомогательная функция: аккуратно прочитать JSON-файл и вернуть dict.

    Если файла нет или JSON битый — возвращаем пустой словарь.
    """
    if not path.exists():                                   # Если файл не существует
        return {}                                           # Возвращаем пустой dict

    try:
        with path.open("r", encoding="utf-8") as f:         # Открываем файл на чтение в кодировке UTF-8
            return json.load(f)                             # Пытаемся распарсить JSON и вернуть dict
    except Exception:
        # При любой ошибке чтения/парсинга возвращаем пустой dict,
        # чтобы не ломать работу бота из-за повреждённого файла.
        return {}


def _save_json(path: Path, data: dict) -> None:
    """
    Вспомогательная функция: безопасно сохранить dict в JSON-файл.
    """
    with path.open("w", encoding="utf-8") as f:             # Открываем файл на запись
        json.dump(data, f, ensure_ascii=False, indent=2)    # Сохраняем JSON с отступами и кириллицей


def load_user(user_id: int) -> Optional[User]:
    """
    Прочитать пользователя из JSON-файла.

    Возвращаем:
    - объект User, если файл существует и корректен;
    - None, если файла нет или он битый.
    """
    path: Path = USERS_DIR / f"{int(user_id)}.json"         # Формируем путь вида users/123456789.json

    if not path.exists():                                   # Если файла нет — пользователя нет
        return None

    raw_data: dict = _load_json(path)                       # Читаем JSON как dict

    if not raw_data:                                        # Если словарь пустой (ошибка или файл пустой)
        return None                                         # Считаем, что пользователя нет/файл некорректен

    try:
        user = User.from_dict(raw_data)                     # Пытаемся восстановить User из dict
    except Exception:
        # Если формат неожиданно битый, лучше вернуть None,
        # чтобы не ломать остальной код.
        return None

    return user                                             # Возвращаем восстановленного пользователя


def save_user(user: User) -> None:
    """
    Сохранить объект User в JSON-файл.
    """
    path: Path = USERS_DIR / f"{int(user.id)}.json"         # Путь до файла конкретного пользователя
    data: dict = user.to_dict()                            # Превращаем User в dict
    _save_json(path, data)                                  # Сохраняем dict в JSON


def load_last_messages() -> Dict[str, int]:
    """
    Прочитать карту {chat_id: last_bot_message_id} из JSON.

    Ключи храним как строки (так проще и надёжнее для JSON).
    """
    raw_data: dict = _load_json(LAST_MESSAGES_FILE)         # Читаем словарь из файла

    if not isinstance(raw_data, dict):                      # Если там лежит не dict
        return {}                                           # Возвращаем пустую карту

    result: Dict[str, int] = {}                             # Готовим результат

    for chat_id_str, message_id in raw_data.items():        # Перебираем пары ключ-значение
        try:
            chat_id_key = str(chat_id_str)                  # Ключ всегда превращаем в строку
            message_id_int = int(message_id)                # Значение пытаемся привести к int
        except Exception:
            continue                                        # Если не получилось — просто пропускаем такую запись

        result[chat_id_key] = message_id_int                # Сохраняем корректную пару в результат

    return result                                           # Возвращаем карту корректных значений


def save_last_messages(mapping: Dict[str, int]) -> None:
    """
    Сохранить карту {chat_id: last_bot_message_id} в JSON-файл.
    """
    # Здесь mapping уже должен быть в виде {строка chat_id: int message_id}
    _save_json(LAST_MESSAGES_FILE, mapping)                 # Просто сохраняем dict как JSON
