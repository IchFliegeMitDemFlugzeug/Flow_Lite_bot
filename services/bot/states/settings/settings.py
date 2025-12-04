# states/settings/settings.py

# Импортируем класс StatesGroup и State из aiogram
# StatesGroup — это "группа" связанных состояний (машина состояний)
# State — отдельное состояние внутри группы
from aiogram.fsm.state import StatesGroup, State


class SettingsStates(StatesGroup):  # Объявляем класс с состояниями регистрации, наследуемся от StatesGroup
    # Каждое поле класса, равное State(), — это отдельное состояние FSM

    setting_state = State()   # Состояние: юзер вышел в настройки