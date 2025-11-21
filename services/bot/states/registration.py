# states/registration.py

# Импортируем класс StatesGroup и State из aiogram
# StatesGroup — это "группа" связанных состояний (машина состояний)
# State — отдельное состояние внутри группы
from aiogram.fsm.state import StatesGroup, State


class RegistrationStates(StatesGroup):  # Объявляем класс с состояниями регистрации, наследуемся от StatesGroup
    # Каждое поле класса, равное State(), — это отдельное состояние FSM

    waiting_for_phone = State()   # Состояние: ждём, пока пользователь отправит номер телефона
    waiting_for_banks = State()   # Состояние: номер уже есть, ждём выбор банков для этого номера
    waiting_for_main_bank = State()  # Состояние: номер есть, банки выбраны, ждем основной банк