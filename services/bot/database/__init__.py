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
- add_or_update_card / remove_card — для управления банковскими картами пользователя;
- set_last_bot_message_id / get_last_bot_message_id — для хранения ID последнего сообщения бота
  УЖЕ В ФАЙЛЕ КОНКРЕТНОГО ЮЗЕРА (без отдельного last_messages.json).
"""

from __future__ import annotations  # Разрешаем "отложенные" аннотации типов

from typing import List, Optional, Tuple  # Типы для аннотаций

from .models import User, PhoneData, CardData          # Импортируем модели
from .storage import (                                 # Импортируем низкоуровневые функции работы с диском
    load_user,
    save_user,
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


# --- Банковские карты пользователя --- #


def add_or_update_card(
    user_id: int,
    card_number: str,
    bank: Optional[str],
    payment_system: Optional[str],
) -> None:
    """
    Добавить или обновить банковскую карту пользователя.

    Аргументы:
    - user_id: ID пользователя.
    - card_number: номер карты (желательно уже нормализованный, без пробелов).
    - bank: код банка (как в словаре BANKS) или None.
    - payment_system: код платёжной системы ("visa", "mir", "mc" и т.п.) или None.
    """
    user: User = get_user(user_id)                     # Берём (или создаём) пользователя

    card_number_str = str(card_number).strip()         # Приводим номер карты к "чистой" строке
    if not card_number_str:                            # Если строка пустая — просто выходим, нечего сохранять
        return

    existing_card = user.cards.get(card_number_str)    # Пытаемся найти уже существующую карту по этому номеру

    if existing_card is None:                          # Если карты ещё не было
        card = CardData(                               # Создаём новый объект CardData
            number=card_number_str,                    # Сохраняем номер карты
            bank=bank,                                 # Код банка или None
            payment_system=payment_system,             # Платёжная система или None
        )
    else:
        card = existing_card                           # Если карта уже есть — обновляем её поля
        card.bank = bank                               # Обновляем код банка
        card.payment_system = payment_system           # Обновляем платёжную систему

    user.cards[card_number_str] = card                 # Сохраняем/обновляем карту в словаре пользователя

    save_user(user)                                    # Фиксируем изменения на диске


def remove_card(
    user_id: int,
    card_number: str,
) -> None:
    """
    Удалить банковскую карту пользователя по номеру.

    Если карты с таким номером нет — функция ничего не делает.
    """
    user: User = get_user(user_id)                     # Берём (или создаём) пользователя

    card_number_str = str(card_number).strip()         # Нормализуем ключ (номер карты)
    if not card_number_str:                            # Если передали пустую строку
        return                                         # Ничего не удаляем

    if card_number_str in user.cards:                  # Проверяем, есть ли такая карта
        user.cards.pop(card_number_str, None)          # Удаляем запись из словаря
        save_user(user)                                # Сохраняем изменения (только если реально что-то удалили)


# --- Хранение ID последнего сообщения бота по chat_id --- #


def set_last_bot_message_id(
    chat_id: int,
    message_id: Optional[int],
) -> None:
    """
    Сохранить ID последнего сообщения бота для конкретного чата.

    ВАЖНО: теперь ID хранится ВНУТРИ файла пользователя (User.last_bot_message_id),
    а не в отдельном last_messages.json.

    Аргументы:
    - chat_id: ID чата (int). В приватных чатах совпадает с user_id.
    - message_id: ID сообщения бота (int) или None, если нужно "очистить" запись.
    """
    user: User = get_user(chat_id)                     # Для приватных чатов chat_id == user_id, берём/создаём пользователя

    if message_id is None:                             # Если нужно "очистить" сохранённый ID
        user.last_bot_message_id = None                # Обнуляем поле
    else:
        user.last_bot_message_id = int(message_id)     # Сохраняем ID последнего сообщения бота как int

    save_user(user)                                    # Фиксируем изменения на диске


def get_last_bot_message_id(chat_id: int) -> Optional[int]:
    """
    Получить ID последнего сообщения бота для заданного chat_id.

    Если пользователя/файла нет или ID ещё не сохранялся — возвращаем None.
    """
    existing: Optional[User] = load_user(chat_id)      # Пытаемся прочитать пользователя БЕЗ авто-создания

    if existing is None:                               # Если файл пользователя ещё не создавался
        return None                                    # Считаем, что и ID последнего сообщения нет

    return existing.last_bot_message_id                # Возвращаем сохранённый ID (или None)
