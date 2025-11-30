# services/bot/database/__init__.py

"""
Публичный интерфейс файловой "базы данных" бота.

Здесь функции, которыми пользуются хэндлеры:
- get_user
- update_basic_user_info
- add_or_update_phone
- set_registration_progress
- get_registration_progress
ПЛЮС:
- set_last_bot_message_id / get_last_bot_message_id — для хранения ID последнего сообщения бота по chat_id.
"""

from __future__ import annotations  # Разрешаем "отложенные" аннотации типов

from typing import List, Optional, Tuple  # Типы для аннотаций

from .models import User, PhoneData                    # Импортируем модели
from .storage import (                                 # Импортируем низкоуровневые функции работы с диском
    load_user,
    save_user,
    load_last_messages,
    save_last_messages,
)


def get_user(user_id: int) -> User:
    """
    Получить (или создать) пользователя по user_id.

    Если файл существует — читаем и возвращаем его.
    Если нет — создаём "пустого" пользователя и сразу сохраняем.
    """
    existing: Optional[User] = load_user(user_id)      # Пытаемся прочитать пользователя с диска

    if existing is not None:                           # Если файл существует и корректен
        return existing                                # Возвращаем его

    # Файла нет — создаём нового пользователя "с нуля"
    user = User(id=int(user_id))                       # Создаём пользователя с заданным user_id
    save_user(user)                                    # Сразу сохраняем его, чтобы файл появился на диске
    return user                                        # Возвращаем созданного пользователя


def update_basic_user_info(
    user_id: int,
    first_name: Optional[str],
    last_name: Optional[str],
    username: Optional[str],
) -> None:
    """
    Обновить базовые данные о пользователе (имя, фамилия, username).
    """
    user: User = get_user(user_id)                     # Берём (или создаём) пользователя из "базы"

    user.first_name = first_name                       # Обновляем имя
    user.last_name = last_name                         # Обновляем фамилию
    user.username = username                           # Обновляем username

    save_user(user)                                    # Сохраняем пользователя обратно в JSON


def add_or_update_phone(
    user_id: int,
    phone: str,
    banks: List[str],
    main_bank: Optional[str],
) -> None:
    """
    Добавить или обновить номер телефона пользователя.

    Аргументы:
    - user_id: ID пользователя.
    - phone: строка с номером телефона (в "нормализованном" виде).
    - banks: список кодов выбранных банков.
    - main_bank: код основного банка (или None, если основной ещё не выбран).
    """
    user: User = get_user(user_id)                     # Загружаем пользователя

    phone_str = str(phone)                             # Номер телефона приводим к строке (на всякий случай)

    existing_phone_data: Optional[PhoneData] = user.phones.get(phone_str)
    # Берём существующую запись по этому номеру, если есть

    if existing_phone_data is None:                    # Если записи по этому номеру не было
        phone_data = PhoneData()                       # Создаём новый объект PhoneData
    else:
        phone_data = existing_phone_data               # Иначе работаем с существующим объектом

    phone_data.banks = list(banks)                     # Обновляем список банков (копия списка)
    phone_data.main_bank = main_bank                   # Обновляем основной банк

    user.phones[phone_str] = phone_data                # Записываем PhoneData в словарь телефонов пользователя

    save_user(user)                                    # Сохраняем пользователя на диск


def set_registration_progress(
    user_id: int,
    step: Optional[str],
    current_phone: Optional[str],
) -> None:
    """
    Сохранить прогресс регистрации пользователя:
    - step: строка с шагом ("phone", "banks", "main_bank", "completed" и т.д.) или None;
    - current_phone: номер телефона, с которым сейчас работаем, или None.
    """
    user: User = get_user(user_id)                     # Берём пользователя из "базы"

    user.registration_step = step                      # Обновляем шаг регистрации
    user.current_phone = current_phone                 # Обновляем текущий номер (может быть None)

    save_user(user)                                    # Сохраняем изменения


def get_registration_progress(user_id: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Прочитать прогресс регистрации пользователя.

    Возвращает кортеж:
    (registration_step, current_phone)
    """
    user: User = get_user(user_id)                     # Загружаем пользователя

    return user.registration_step, user.current_phone  # Возвращаем две строки (или None/None)


# --- Хранение ID последнего сообщения бота по chat_id --- #


def set_last_bot_message_id(
    chat_id: int,
    message_id: Optional[int],
) -> None:
    """
    Сохранить ID последнего сообщения бота для конкретного чата.

    Аргументы:
    - chat_id: ID чата (int).
    - message_id: ID сообщения бота (int) или None, если нужно "очистить" запись.
    """
    mapping = load_last_messages()                     # Загружаем текущую карту {chat_id: message_id}
    chat_key = str(chat_id)                            # Приводим chat_id к строке (ключ в JSON)

    if message_id is None:                             # Если передали None
        mapping.pop(chat_key, None)                    # Удаляем запись для этого чата (если была)
    else:
        mapping[chat_key] = int(message_id)            # Сохраняем/обновляем ID сообщения для этого чата

    save_last_messages(mapping)                        # Сохраняем обновлённую карту на диск


def get_last_bot_message_id(chat_id: int) -> Optional[int]:
    """
    Получить ID последнего сообщения бота для заданного chat_id.

    Если записи нет — возвращаем None.
    """
    mapping = load_last_messages()                     # Читаем карту {chat_id: message_id}
    chat_key = str(chat_id)                            # Приводим chat_id к строке

    value = mapping.get(chat_key)                      # Берём значение (если есть)

    if value is None:                                  # Если записи нет — возвращаем None
        return None

    try:
        return int(value)                              # Пытаемся привести к int и вернуть
    except Exception:
        return None                                    # Если значение битое — считаем, что ID нет
