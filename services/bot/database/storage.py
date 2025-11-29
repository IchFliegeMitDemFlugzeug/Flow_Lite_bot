# -*- coding: utf-8 -*-  # Указываем кодировку файла

"""
Простейшее файловое "хранилище" для данных пользователей.

Важные моменты:
- Для КАЖДОГО пользователя создаётся ОТДЕЛЬНЫЙ JSON-файл.
- Все файлы лежат в папке "users" рядом с этим модулем.
- Функции из этого модуля не являются асинхронными, но их можно спокойно
  вызывать из async-кода (aiogram) — операции небольшие и быстрые.
"""

import json                                         # Модуль json — для чтения/записи JSON-файлов
from pathlib import Path                            # Path — удобная работа с путями
from typing import Optional                         # Optional — для аннотаций типов

from .models import UserData, PhoneData             # Импортируем наши модели UserData и PhoneData


# Базовая папка, где лежит этот модуль (services/bot/database)
BASE_DIR: Path = Path(__file__).resolve().parent    # Определяем путь к текущей папке

# Папка, в которой будут храниться ВСЕ JSON-файлы пользователей
USERS_DIR: Path = BASE_DIR / "users"                # Путь вида ".../database/users"

# Создаём папку USERS_DIR, если она ещё не существует
USERS_DIR.mkdir(parents=True, exist_ok=True)        # parents=True — создаст все недостающие папки, exist_ok=True — не ругаться, если уже есть


def _get_user_file_path(user_id: int) -> Path:
    """
    Вспомогательная функция: возвращает путь к JSON-файлу конкретного пользователя.

    Пример: для user_id=123 файл будет называться "123.json" и лежать в папке USERS_DIR.
    """
    return USERS_DIR / f"{user_id}.json"            # Склеиваем путь к файлу "users/<user_id>.json"


def load_user(user_id: int) -> Optional[UserData]:
    """
    Загружаем данные пользователя из JSON-файла.

    Если файл не существует — возвращаем None.
    """
    file_path = _get_user_file_path(user_id)        # Строим путь к файлу пользователя

    if not file_path.exists():                      # Если файл не найден
        return None                                 # Возвращаем None (пользователь ещё не сохранялся)

    with file_path.open("r", encoding="utf-8") as f:  # Открываем файл на чтение в кодировке UTF-8
        raw_data = json.load(f)                     # Загружаем словарь из JSON

    return UserData.from_dict(raw_data)             # Превращаем словарь в объект UserData и возвращаем его


def save_user(user: UserData) -> None:
    """
    Сохраняем данные пользователя в его JSON-файл.

    Если файла не было — он будет создан.
    """
    file_path = _get_user_file_path(user.user_id)   # Определяем путь к файлу конкретного пользователя

    USERS_DIR.mkdir(parents=True, exist_ok=True)    # Ещё раз убеждаемся, что папка существует (на всякий случай)

    with file_path.open("w", encoding="utf-8") as f:  # Открываем файл на запись в UTF-8
        json.dump(                                  # Сохраняем данные в JSON
            user.to_dict(),                         # Преобразуем объект UserData в словарь
            f,                                      # Файловый объект
            ensure_ascii=False,                     # Не экранируем кириллицу
            indent=2,                               # Красивые отступы в JSON (удобно читать руками)
        )


def get_user(user_id: int) -> UserData:
    """
    Универсальная функция получения пользователя.

    Если файл существует — возвращаем данные из него.
    Если файла нет — создаём нового пользователя с данным user_id и сразу сохраняем его.
    """
    user = load_user(user_id)                       # Пытаемся загрузить пользователя из файла
    if user is None:                                # Если пользователя ещё не было
        user = UserData(user_id=user_id)            # Создаём новый объект UserData
        save_user(user)                             # Сразу же сохраняем его в файл
    return user                                     # Возвращаем объект UserData


def update_basic_user_info(
    user_id: int,
    first_name: Optional[str],
    last_name: Optional[str],
    username: Optional[str],
) -> UserData:
    """
    Обновляем базовую информацию о пользователе (имя, фамилия, username).

    Возвращаем актуальный объект UserData.
    """
    user = get_user(user_id)                        # Получаем (или создаём) пользователя
    user.first_name = first_name                    # Обновляем имя
    user.last_name = last_name                      # Обновляем фамилию
    user.username = username                        # Обновляем username
    save_user(user)                                 # Сохраняем изменения в файл
    return user                                     # Возвращаем обновлённый объект


def add_or_update_phone(
    user_id: int,
    phone: str,
    banks: list[str],
    main_bank: Optional[str],
) -> UserData:
    """
    Добавляем новый номер телефона пользователю или обновляем существующий.

    - phone      — номер телефона (строка, например "+79991234567");
    - banks      — список кодов банков для этого номера;
    - main_bank  — код основного банка или None.
    """
    user = get_user(user_id)                        # Получаем пользователя

    existing_phone = user.phones.get(phone)         # Пытаемся найти существующую запись по этому номеру
    if existing_phone is None:                      # Если записи ещё нет
        existing_phone = PhoneData(phone=phone)     # Создаём новый объект PhoneData

    # Обновляем поля объекта PhoneData
    existing_phone.phone = phone                    # На всякий случай перезаписываем номер
    # Удаляем дубликаты банков, сохраняя порядок (через dict.fromkeys)
    existing_phone.banks = list(dict.fromkeys(banks))
    existing_phone.main_bank = main_bank            # Обновляем основной банк (может быть None)

    # Кладём обновлённый объект в словарь телефонов пользователя
    user.phones[phone] = existing_phone

    save_user(user)                                 # Сохраняем пользователя в файл
    return user                                     # Возвращаем объект UserData


def add_card(user_id: int, card_number: str) -> UserData:
    """
    Добавляем номер банковской карты пользователю.

    Сейчас храним карты просто как список строк.
    """
    user = get_user(user_id)                        # Получаем пользователя
    if card_number not in user.cards:               # Если этой карты ещё нет в списке
        user.cards.append(card_number)              # Добавляем её
        save_user(user)                             # Сохраняем изменения
    return user                                     # Возвращаем пользователя


def remove_card(user_id: int, card_number: str) -> UserData:
    """
    Удаляем номер банковской карты из списка пользователя (если он там есть).
    """
    user = get_user(user_id)                        # Получаем пользователя
    if card_number in user.cards:                   # Если карта присутствует в списке
        user.cards.remove(card_number)              # Удаляем её
        save_user(user)                             # Сохраняем изменения
    return user                                     # Возвращаем пользователя


def set_registration_progress(
    user_id: int,
    step: Optional[str],
    current_phone: Optional[str] = None,
) -> UserData:
    """
    Сохраняем в файле "на каком шаге регистрации сейчас пользователь"
    и, при необходимости, номер телефона, с которым он работает.

    Параметры:
    - step          — строка с названием шага ("phone", "banks", "main_bank", "no_banks", "completed") или None;
    - current_phone — номер телефона, с которым сейчас идёт регистрация (или None, если хотим сбросить).
    """
    user = get_user(user_id)                        # Загружаем пользователя

    user.registration_step = step                   # Обновляем шаг регистрации

    if current_phone is not None:                   # Если передали конкретный номер телефона
        user.current_phone = current_phone          # Сохраняем его как "текущий"
    elif step is None:                              # Если шаг сбрасываем в None
        user.current_phone = None                   # Заодно сбрасываем и текущий телефон

    save_user(user)                                 # Сохраняем изменения в файл
    return user                                     # Возвращаем пользователя


def get_registration_progress(user_id: int) -> tuple[Optional[str], Optional[str]]:
    """
    Возвращаем кортеж (registration_step, current_phone) для указанного пользователя.

    Если пользователь ещё не создавался — будет создан пустой UserData с None в этих полях.
    """
    user = get_user(user_id)                        # Получаем пользователя
    return user.registration_step, user.current_phone  # Возвращаем шаг регистрации и текущий телефон
