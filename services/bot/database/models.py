# -*- coding: utf-8 -*-  # Указываем кодировку файла, чтобы корректно работать с кириллицей

"""
Простые модели данных для временной "базы данных" бота ПОТОК Lite.

Здесь мы описываем структуру того, что храним в JSON-файлах:
- данные по одному номеру телефона (PhoneData);
- данные по пользователю (UserData).
"""

from dataclasses import dataclass, field   # Импортируем dataclass и field для удобного описания моделей
from typing import Dict, List, Optional    # Импортируем типы для аннотаций (словарь, список, необязательное значение)


@dataclass
class PhoneData:
    """
    Данные по ОДНОМУ номеру телефона пользователя.
    Один номер телефона может быть привязан к нескольким банкам,
    и у него может быть выбран основной банк.
    """

    phone: str                             # Сам номер телефона в виде строки (например, "+79991234567")
    banks: List[str] = field(default_factory=list)         # Список кодов банков, в которых номер зарегистрирован
    main_bank: Optional[str] = None        # Код основного банка для этого номера (или None, если не выбран)

    def to_dict(self) -> Dict[str, object]:
        """
        Преобразуем объект PhoneData в обычный словарь, который можно сохранить в JSON.
        """
        return {
            "phone": self.phone,           # Сохраняем сам номер телефона
            "banks": list(self.banks),     # Сохраняем список банков (делаем копию на всякий случай)
            "main_bank": self.main_bank,   # Сохраняем код основного банка или None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "PhoneData":
        """
        Восстанавливаем объект PhoneData из словаря (который получили из JSON).
        """
        return cls(
            phone=str(data.get("phone", "")),      # Берём поле "phone" из словаря, по умолчанию пустая строка
            banks=list(data.get("banks", [])),     # Берём список "banks" или пустой список
            main_bank=data.get("main_bank"),       # Берём основной банк как есть (может быть None)
        )


@dataclass
class UserData:
    """
    Данные по ОДНОМУ пользователю бота.
    Для каждого пользователя создаётся отдельный JSON-файл, в котором хранится:

    - user_id           — Telegram ID пользователя;
    - first_name        — имя;
    - last_name         — фамилия;
    - username          — @username;
    - phones            — словарь {номер_телефона: PhoneData};
    - cards             — список номеров банковских карт (пока как простые строки);
    - registration_step — на каком шаге регистрации сейчас пользователь;
    - current_phone     — номер телефона, с которым прямо сейчас идёт регистрация.
    """

    user_id: int                                         # Уникальный Telegram ID пользователя
    first_name: Optional[str] = None                     # Имя пользователя (может быть None)
    last_name: Optional[str] = None                      # Фамилия пользователя (может быть None)
    username: Optional[str] = None                       # username пользователя (может быть None)

    phones: Dict[str, PhoneData] = field(default_factory=dict)  # Словарь номеров телефонов: {"+7999...": PhoneData}
    cards: List[str] = field(default_factory=list)       # Пока просто список строк с номерами карт

    registration_step: Optional[str] = None              # "phone" / "banks" / "main_bank" / "no_banks" / "completed" или None
    current_phone: Optional[str] = None                  # Номер телефона, с которым сейчас работает регистрация (или None)

    def to_dict(self) -> Dict[str, object]:
        """
        Преобразуем объект UserData в словарь для сохранения в JSON.
        """
        return {
            "user_id": self.user_id,                     # Сохраняем Telegram ID
            "first_name": self.first_name,               # Сохраняем имя
            "last_name": self.last_name,                 # Сохраняем фамилию
            "username": self.username,                   # Сохраняем username
            "phones": {                                  # Сериализуем словарь телефонов
                phone: phone_data.to_dict()              # Каждый PhoneData превращаем в словарь
                for phone, phone_data in self.phones.items()
            },
            "cards": list(self.cards),                   # Сохраняем список карт (делаем копию)
            "registration_step": self.registration_step, # Сохраняем текущий шаг регистрации
            "current_phone": self.current_phone,         # Сохраняем текущий номер телефона
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "UserData":
        """
        Восстанавливаем объект UserData из словаря (который получили из JSON-файла).
        """
        # Создаём пользователя с базовыми полями
        user = cls(
            user_id=int(data.get("user_id", 0)),         # Восстанавливаем user_id (по умолчанию 0)
            first_name=data.get("first_name"),           # Имя
            last_name=data.get("last_name"),             # Фамилия
            username=data.get("username"),               # username
        )

        # Восстанавливаем словарь телефонов, если он есть в данных
        phones_raw = data.get("phones", {}) or {}        # Берём поле "phones" или пустой словарь
        if isinstance(phones_raw, dict):                 # Убеждаемся, что это словарь
            for phone, phone_data_dict in phones_raw.items():  # Перебираем все записи
                try:
                    phone_obj = PhoneData.from_dict(phone_data_dict or {})  # Восстанавливаем PhoneData
                except Exception:
                    # Если по какой-то причине не удалось разобрать запись по телефону — пропускаем её
                    continue
                user.phones[phone] = phone_obj           # Кладём объект PhoneData в словарь пользователя

        # Восстанавливаем список карт (если есть)
        cards_raw = data.get("cards", []) or []          # Берём "cards" или пустой список
        if isinstance(cards_raw, list):                  # Если это список
            user.cards = [str(card) for card in cards_raw]  # Сохраняем каждый элемент как строку

        # Восстанавливаем шаг регистрации (если был сохранён)
        user.registration_step = data.get("registration_step")  # Просто читаем значение или None

        # Восстанавливаем текущий номер телефона (если был сохранён)
        user.current_phone = data.get("current_phone")  # Тоже читаем значение или None

        return user                                     # Возвращаем полностью заполненный объект UserData
