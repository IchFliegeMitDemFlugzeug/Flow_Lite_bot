# services/bot/database/models.py

"""
Модели данных для файловой "базы данных" бота.

Задача:
- описать структуру пользователя (User) и телефона (PhoneData);
- уметь превращать их в словарь (для JSON) и обратно.
"""

from __future__ import annotations  # Разрешаем ссылаться на классы, объявленные ниже

from dataclasses import dataclass, field  # dataclass — удобный способ описать "структуру" данных
from typing import Dict, List, Optional   # Типы для аннотаций (словарь, список, Optional)


@dataclass
class PhoneData:
    """
    Информация по одному номеру телефона пользователя.
    """
    banks: List[str] = field(default_factory=list)          # Список кодов банков, привязанных к номеру
    main_bank: Optional[str] = None                         # Код основного банка (или None)

    def to_dict(self) -> dict:
        """
        Преобразуем объект PhoneData в обычный словарь для сохранения в JSON.
        """
        return {
            "banks": list(self.banks),                      # Явно приводим к list, чтобы не было сюрпризов
            "main_bank": self.main_bank,                    # Просто сохраняем строку или None
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "PhoneData":
        """
        Восстанавливаем PhoneData из словаря (например, прочитанного из JSON).
        Если данных нет или формат неожиданный — аккуратно возвращаем объект по умолчанию.
        """
        if not isinstance(data, dict):                      # Если пришло не dict, считаем, что данных нет
            return cls()                                    # Возвращаем объект с настройками по умолчанию

        banks_raw = data.get("banks", [])                   # Берём список банков (если нет — пустой список)
        if not isinstance(banks_raw, list):                 # Если в JSON лежит не список
            banks: List[str] = []                           # То защищаемся и делаем пустой список
        else:
            # Приводим каждый элемент к строке (на всякий случай)
            banks = [str(b) for b in banks_raw]

        main_bank_raw = data.get("main_bank")               # Берём из словаря main_bank (если есть)
        main_bank = str(main_bank_raw) if main_bank_raw is not None else None

        return cls(
            banks=banks,                                    # Список кодов банков
            main_bank=main_bank,                            # Код основного банка или None
        )


@dataclass
class User:
    """
    Модель пользователя, который хранится в файловой "базе".
    """
    id: int                                                 # Telegram user_id (обязательное поле)

    first_name: Optional[str] = None                        # Имя (как в Telegram)
    last_name: Optional[str] = None                         # Фамилия
    username: Optional[str] = None                          # username (@nickname) или None

    registration_step: Optional[str] = None                 # Текущий шаг регистрации (например, "phone", "banks", "completed")
    current_phone: Optional[str] = None                     # "Текущий" номер телефона, с которым сейчас работаем

    phones: Dict[str, PhoneData] = field(default_factory=dict)
    # Словарь "номер телефона" -> PhoneData

    def to_dict(self) -> dict:
        """
        Преобразуем User в словарь для сохранения в JSON.
        """
        return {
            "id": int(self.id),                             # user_id явно приводим к int
            "first_name": self.first_name,                  # Имя как есть
            "last_name": self.last_name,                    # Фамилия
            "username": self.username,                      # username
            "registration_step": self.registration_step,    # Строка шага регистрации или None
            "current_phone": self.current_phone,            # Текущий номер телефона или None
            "phones": {
                phone: phone_data.to_dict()                 # Каждый PhoneData превращаем в словарь
                for phone, phone_data in self.phones.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "User":
        """
        Создаём User из словаря, прочитанного из JSON.
        Если формат неожиданной — по максимуму восстанавливаем адекватные значения.
        """
        if not isinstance(data, dict):                      # Если почему-то пришло не dict — создаём "пустого" юзера
            raise ValueError("User.from_dict ожидает dict с полями пользователя")

        user_id_raw = data.get("id")                        # Берём поле id из словаря
        if user_id_raw is None:                             # Если его нет — это критическая ошибка
            raise ValueError("В JSON пользователя отсутствует поле 'id'")

        user_id = int(user_id_raw)                          # Принудительно приводим к int

        phones_raw = data.get("phones", {})                 # Берём словарь телефонов (или пустой)
        if not isinstance(phones_raw, dict):                # Если там не dict — защищаемся
            phones_raw = {}

        phones: Dict[str, PhoneData] = {}                   # Сюда будем складывать восстановленные PhoneData

        for phone, phone_dict in phones_raw.items():        # Перебираем номера телефона и их данные
            phone_str = str(phone)                          # Ключ (номер) приводим к строке
            phones[phone_str] = PhoneData.from_dict(phone_dict)  # Восстанавливаем PhoneData из словаря

        return cls(
            id=user_id,                                     # user_id
            first_name=data.get("first_name"),              # Имя (может быть None)
            last_name=data.get("last_name"),                # Фамилия (может быть None)
            username=data.get("username"),                  # username (может быть None)
            registration_step=data.get("registration_step"),# Шаг регистрации (строка или None)
            current_phone=data.get("current_phone"),        # Текущий номер телефона (или None)
            phones=phones,                                  # Восстановленный словарь телефонов
        )
