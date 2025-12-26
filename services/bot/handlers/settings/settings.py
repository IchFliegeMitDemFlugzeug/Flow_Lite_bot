# services/bot/handlers/settings/settings_common.py

"""
Общие хэндлеры и вспомогательные функции для экранов «Настройки».

В этом файле:

- объявляется единый роутер settings_router для всех экранов настроек;
- есть три функции показа экранов:
    * send_settings_screen                — основной экран «Настройки»;
    * send_phone_numbers_settings_screen  — экран «Настройки номеров телефонов»;
    * send_cards_settings_screen          — экран «Настройки банковских карт»;
- обрабатываются ТОЛЬКО коллбэки кнопок ОСНОВНОГО экрана «Настройки»:
    * «Номера телефонов»;
    * «Банковские карты»;
    * «Назад в личный кабинет».

Коллбэки внутренних экранов (телефоны/карты) обрабатываются
в отдельных файлах:
- settings_phone_numbers.py
- settings_cards.py
"""

from __future__ import annotations                                   # Разрешаем отложенные аннотации типов

from typing import Optional                                          # Тип Optional для значений, которые могут быть None

from aiogram import Router, F                                        # Router — маршрутизатор, F — фильтры по полям апдейта
from aiogram.types import (                                          # Типы объектов Telegram
    Message,                                                         # Сообщение (текст, фото и т.п.)
    CallbackQuery,                                                   # CallbackQuery от инлайн-клавиатур
)
from aiogram.fsm.context import FSMContext                           # Контекст машины состояний FSM

from ...texts.settings.settings import (                             # Текст основного экрана «Настройки»
    build_settings_text,                                             # Функция формирования текста экрана «Настройки»
)
from ...texts.settings.phone_numbers import (                        # Текст экрана «Настройки номеров телефонов»
    build_phone_numbers_settings_text,                               # Функция формирования текста экрана телефонов
)
from ...texts.settings.cards import (                                # Текст экрана «Настройки банковских карт»
    build_cards_settings_text,                                       # Функция формирования текста экрана карт
)
from ...texts.personal_cabinet import (                              # Текст экрана «Личный кабинет»
    build_personal_cabinet_text,                                     # Функция формирования текста ЛК
)
from ...keyboards.settings.settings import (                         # Клавиатура основного экрана «Настройки»
    build_settings_keyboard,                                         # Функция построения клавиатуры основного экрана
    SETTINGS_PHONES_CALLBACK_DATA,                                   # callback_data кнопки «Номера телефонов»
    SETTINGS_CARDS_CALLBACK_DATA,                                    # callback_data кнопки «Банковские карты»
    SETTINGS_BACK_CALLBACK_DATA,                                     # callback_data кнопки «Назад в личный кабинет»
)
from ...keyboards.settings.phone_numbers import (                    # Клавиатура экрана «Настройки номеров телефонов»
    build_phone_numbers_settings_keyboard,                           # Функция построения клавиатуры экрана телефонов
)
from ...keyboards.settings.cards import (                            # Клавиатура экрана «Настройки банковских карт»
    build_cards_settings_keyboard,                                   # Функция построения клавиатуры экрана карт
)
from ...keyboards.personal_cabinet import (                          # Клавиатура экрана «Личный кабинет»
    build_personal_cabinet_keyboard,                                 # Функция построения клавиатуры ЛК
)
from ...headlines.add_headline import (                              # Работа с сообщениями с картинкой-заголовком
    edit_message_with_headline,                                      # Функция редактирования media + caption + reply_markup
    HEADLINE_LK,                                                     # Тип заголовка для Личного кабинета
    HEADLINE_SETTINGS,                                               # Тип заголовка для основного экрана «Настройки»
    HEADLINE_SETTINGS_PHONE_NUMBERS,                                 # Тип заголовка для экрана «Настройки номеров телефонов»
    HEADLINE_SETTINGS_CARDS,                                         # Тип заголовка для экрана «Настройки банковских карт»
)
from ...states.settings.settings import (                            # Состояния FSM, связанные с настройками
    SettingsStates,                                                  # Класс, внутри которого описаны состояния настроек
)


# --- РОУТЕР ДЛЯ НАСТРОЕК --- #

settings_router: Router = Router(                                    # Создаём экземпляр роутера
    name="settings",                                                 # Имя роутера (удобно для логирования/отладки)
)


# --- ФУНКЦИИ ПОКАЗА ЭКРАНОВ --- #

async def send_settings_screen(
    message: Message,                                                # Сообщение, которое нужно "превратить" в экран «Настройки»
    state: Optional[FSMContext] = None,                              # Контекст FSM пользователя (может быть None)
) -> None:
    """
    Переключить текущее сообщение на основной экран «Настройки» БЕЗ отправки нового сообщения.

    Логика:
    1) Определяем user_id по chat.id.
    2) Формируем текст экрана «Настройки».
    3) Формируем клавиатуру экрана «Настройки».
    4) Через edit_message_with_headline редактируем ЭТО ЖЕ сообщение (media + caption + reply_markup).
    5) Обновляем FSM: last_bot_message_id и состояние SettingsStates.setting_state.
    """

    # --- Шаг 1. user_id --- #
    chat = message.chat                                              # Берём объект чата из сообщения
    if chat is not None:                                             # Обычный приватный диалог
        user_id: int = chat.id                                       # Принимаем user_id = chat.id (так устроена БД)
    else:                                                            # На всякий случай страховка
        user_id = message.from_user.id                               # Если chat почему-то None — берём from_user.id

    # --- Шаг 2. текст настроек --- #
    settings_text: str = await build_settings_text(                        # Формируем строку с текстом экрана «Настройки»
        user_id=user_id,                                             # Передаём идентификатор пользователя
    )

    # --- Шаг 3. клавиатура настроек --- #
    settings_keyboard = build_settings_keyboard()                    # Строим инлайн-клавиатуру основного экрана

    # --- Шаг 4. редактирование сообщения --- #
    edited_message: Message = await edit_message_with_headline(
        message=message,                                             # То же сообщение (с картинкой и caption)
        text=settings_text,                                          # Новый caption — текст экрана «Настройки»
        headline_type=HEADLINE_SETTINGS,                             # Картинка-заголовок для настроек
        reply_markup=settings_keyboard,                              # Инлайн-клавиатура настроек
        parse_mode="Markdown",                                       # Используем Markdown-разметку
    )

    # --- Шаг 5. обновление FSM --- #
    if state is not None:                                            # Если контекст FSM передан
        await state.update_data(                                     # Обновляем словарь данных FSM
            last_bot_message_id=edited_message.message_id,           # Запоминаем ID текущего сообщения бота
        )
        await state.set_state(                                       # Устанавливаем состояние
            SettingsStates.setting_state,                            # Состояние "находимся в экране настроек"
        )


async def send_phone_numbers_settings_screen(
    message: Message,                                                # Сообщение, которое нужно превратить в экран телефонов
    state: Optional[FSMContext] = None,                              # Контекст FSM пользователя
) -> None:
    """
    Переключить текущее сообщение на экран «Настройки номеров телефонов».

    Логика:
    1) user_id по chat.id;
    2) текст — только по телефонам (build_phone_numbers_settings_text);
    3) клавиатура — build_phone_numbers_settings_keyboard;
    4) редактируем сообщение через edit_message_with_headline с HEADLINE_SETTINGS_PHONE_NUMBERS;
    5) обновляем FSM.
    """

    # --- user_id --- #
    chat = message.chat                                              # Объект чата
    if chat is not None:                                             # Если чат есть
        user_id: int = chat.id                                       # user_id = chat.id
    else:                                                            # Fallback-вариант
        user_id = message.from_user.id                               # user_id = ID отправителя

    # --- текст экрана телефонов --- #
    phones_text: str = await build_phone_numbers_settings_text(            # Формируем текст экрана «Настройки номеров телефонов»
        user_id=user_id,                                             # Передаём ID пользователя
    )

    # --- клавиатура экрана телефонов --- #
    phones_keyboard = build_phone_numbers_settings_keyboard()        # Клавиатура: добавить/удалить/банки/основной/назад

    # --- редактируем сообщение под экран телефонов --- #
    edited_message: Message = await edit_message_with_headline(
        message=message,                                             # То же сообщение
        text=phones_text,                                            # Новый caption — текст по номерам телефонов
        headline_type=HEADLINE_SETTINGS_PHONE_NUMBERS,               # Картинка-заголовок для экрана телефонов
        reply_markup=phones_keyboard,                                # Инлайн-клавиатура экрана телефонов
        parse_mode="Markdown",                                       # Markdown-разметка
    )

    # --- обновляем FSM --- #
    if state is not None:                                            # Если FSM используется
        await state.update_data(                                     # Обновляем данные FSM
            last_bot_message_id=edited_message.message_id,           # Запоминаем ID сообщения
        )
        await state.set_state(                                       # Состояние то же — "настройки"
            SettingsStates.setting_state,
        )


async def send_cards_settings_screen(
    message: Message,                                                # Сообщение, которое нужно превратить в экран карт
    state: Optional[FSMContext] = None,                              # Контекст FSM пользователя
) -> None:
    """
    Переключить текущее сообщение на экран «Настройки банковских карт».

    Логика:
    1) user_id по chat.id;
    2) текст — только по картам (build_cards_settings_text);
    3) клавиатура — build_cards_settings_keyboard;
    4) редактируем сообщение с HEADLINE_SETTINGS_CARDS;
    5) обновляем FSM.
    """

    # --- user_id --- #
    chat = message.chat                                              # Объект чата
    if chat is not None:                                             # Обычный случай
        user_id: int = chat.id                                       # user_id = chat.id
    else:                                                            # Fallback
        user_id = message.from_user.id                               # user_id = ID отправителя

    # --- текст экрана карт --- #
    cards_text: str = await build_cards_settings_text(                     # Текст экрана «Настройки банковских карт»
        user_id=user_id,                                             # Передаём ID пользователя
    )

    # --- клавиатура экрана карт --- #
    cards_keyboard = build_cards_settings_keyboard()                 # Клавиатура: добавить/удалить/назад

    # --- редактируем сообщение под экран карт --- #
    edited_message: Message = await edit_message_with_headline(
        message=message,                                             # То же сообщение
        text=cards_text,                                             # Новый caption — список карт
        headline_type=HEADLINE_SETTINGS_CARDS,                       # Картинка-заголовок для экрана карт
        reply_markup=cards_keyboard,                                 # Инлайн-клавиатура экрана карт
        parse_mode="Markdown",                                       # Markdown-разметка
    )

    # --- обновляем FSM --- #
    if state is not None:                                            # Если FSM используется
        await state.update_data(                                     # Обновляем данные FSM
            last_bot_message_id=edited_message.message_id,           # Запоминаем ID сообщения
        )
        await state.set_state(                                       # Оставляем состояние "настройки"
            SettingsStates.setting_state,
        )


# --- ХЭНДЛЕРЫ КНОПОК ОСНОВНОГО ЭКРАНА «НАСТРОЙКИ» --- #

@settings_router.callback_query(                                     # Хэндлер кнопки «Номера телефонов»
    F.data == SETTINGS_PHONES_CALLBACK_DATA,                         # Фильтр по callback_data
)
async def on_settings_phones_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # Контекст FSM пользователя
) -> None:
    """
    Кнопка «Номера телефонов» на ОСНОВНОМ экране «Настройки».

    Здесь только:
    - закрываем "часики";
    - переключаем текущее сообщение на экран «Настройки номеров телефонов»
      через send_phone_numbers_settings_screen().
    """

    await callback.answer()                                          # Останавливаем анимацию "часиков" на кнопке

    message: Optional[Message] = callback.message                    # Сообщение, в котором показан экран «Настройки»
    if message is None:                                              # Если почему-то сообщения нет
        return                                                       # Нечего редактировать — выходим

    await send_phone_numbers_settings_screen(                        # Переключаем сообщение на экран телефонов
        message=message,                                             # То же сообщение
        state=state,                                                 # Контекст FSM
    )


@settings_router.callback_query(                                     # Хэндлер кнопки «Банковские карты»
    F.data == SETTINGS_CARDS_CALLBACK_DATA,                          # Фильтр по callback_data
)
async def on_settings_cards_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # Контекст FSM пользователя
) -> None:
    """
    Кнопка «Банковские карты» на ОСНОВНОМ экране «Настройки».

    Действия:
    - закрываем "часики";
    - переключаем текущее сообщение на экран «Настройки банковских карт»
      через send_cards_settings_screen().
    """

    await callback.answer()                                          # Закрываем "часики" на кнопке

    message: Optional[Message] = callback.message                    # Сообщение, где сейчас основной экран «Настройки»
    if message is None:                                              # Если сообщения нет
        return                                                       # Выходим

    await send_cards_settings_screen(                                # Переключаем сообщение на экран карт
        message=message,                                             # То же сообщение
        state=state,                                                 # Контекст FSM
    )


@settings_router.callback_query(                                     # Хэндлер кнопки «Назад в личный кабинет»
    F.data == SETTINGS_BACK_CALLBACK_DATA,                           # Фильтр по callback_data
)
async def on_settings_back_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # Контекст FSM (храним show_details и т.п.)
) -> None:
    """
    Кнопка «Назад в личный кабинет» на ОСНОВНОМ экране «Настройки».

    Логика:
    1) Закрываем "часики".
    2) Достаём из FSM флаг lk_show_details (показывать/скрывать реквизиты в ЛК).
    3) Формируем текст ЛК.
    4) Формируем клавиатуру ЛК.
    5) Редактируем текущее сообщение обратно на ЛК.
    6) Обновляем last_bot_message_id в FSM.
    """

    await callback.answer()                                          # Закрываем индикатор ожидания

    message: Optional[Message] = callback.message                    # Сообщение, в котором сейчас экран «Настройки»
    if message is None:                                              # Если его нет
        return                                                       # Нечего редактировать — выходим

    # --- читаем данные FSM --- #
    fsm_data = await state.get_data()                                # Получаем словарь с данными FSM

    # Флаг видимости реквизитов в ЛК (True — показывать, False — скрывать).
    show_details: bool = bool(
        fsm_data.get("lk_show_details", False),                      # Если ключа нет — по умолчанию False
    )

    # --- формируем текст ЛК --- #
    user_id: int = callback.from_user.id                             # ID пользователя (ключ JSON-файла)

    personal_text: str = await build_personal_cabinet_text(                # Формируем текст ЛК
        user_id=user_id,                                             # Передаём ID пользователя
        show_details=show_details,                                   # Учитываем флаг видимости реквизитов
    )

    # --- формируем клавиатуру ЛК --- #
    personal_keyboard = build_personal_cabinet_keyboard(             # Строим инлайн-клавиатуру ЛК
        show_details=show_details,                                   # Кнопка "Показать/Скрыть реквизиты" зависит от флага
    )

    # --- редактируем сообщение обратно на ЛК --- #
    edited_message: Message = await edit_message_with_headline(
        message=message,                                             # То же сообщение, где был экран «Настройки»
        text=personal_text,                                          # Новый caption — текст Личного кабинета
        headline_type=HEADLINE_LK,                                   # Картинка-заголовок для ЛК
        reply_markup=personal_keyboard,                              # Инлайн-клавиатура ЛК
        parse_mode="Markdown",                                       # Markdown-разметка
    )

    # --- обновляем FSM --- #
    await state.update_data(                                         # Обновляем данные FSM
        last_bot_message_id=edited_message.message_id,               # Сохраняем ID сообщения
    )
    # Состояние можно оставить SettingsStates.setting_state —
    # обработчики ЛК завязаны на callback_data, а не на конкретное состояние.
# ВАЖНО: эти импорты должны быть в самом конце файла, после
# объявления settings_router и всех функций/хэндлеров выше.

#from . import phone_numbers   # Импортируем модуль хэндлеров экрана телефонов
#from . import cards           # Импортируем модуль хэндлеров экрана банковских карт
