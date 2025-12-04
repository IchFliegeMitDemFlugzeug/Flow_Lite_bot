# services/bot/handlers/settings/settings.py

"""
Хэндлеры и вспомогательные функции для экрана «Настройки».

Задачи:
- "переключить" текущее сообщение с ЛК на экран настроек (через edit_message_with_headline, без нового сообщения);
- перевести пользователя в состояние SettingsStates.setting_state;
- обработать нажатия на кнопки:
  - «Номера телефонов» (пока заглушка),
  - «Банковские карты» (пока заглушка),
  - «Назад в личный кабинет» (редактирует сообщение обратно на ЛК).
"""

from __future__ import annotations                               # Разрешаем "отложенные" аннотации типов

from typing import Optional                                      # Импортируем Optional для аннотаций

from aiogram import Router, F                                    # Router — роутер aiogram, F — фильтры по полям апдейта
from aiogram.types import (                                      # Импортируем типы Telegram-объектов
    Message,                                                     # Обычное сообщение (text / photo + caption и т.п.)
    CallbackQuery,                                               # Объект callback_query от инлайн-кнопки
)
from aiogram.fsm.context import FSMContext                       # FSMContext — контекст машины состояний

from ...texts.settings.settings import (                                  # Тексты для экрана настроек
    build_settings_text,                                         # Функция, формирующая текст настроек
)
from ...texts.personal_cabinet import (                          # Текст для личного кабинета
    build_personal_cabinet_text,                                 # Функция, формирующая текст ЛК
)
from ...keyboards.settings.settings import (                              # Клавиатура для настроек
    build_settings_keyboard,                                     # Функция построения клавиатуры настроек
    SETTINGS_PHONES_CALLBACK_DATA,                               # callback_data для кнопки «Номера телефонов»
    SETTINGS_CARDS_CALLBACK_DATA,                                # callback_data для кнопки «Банковские карты»
    SETTINGS_BACK_CALLBACK_DATA,                                 # callback_data для кнопки «Назад в личный кабинет»
)
from ...keyboards.personal_cabinet import (                      # Клавиатура личного кабинета
    build_personal_cabinet_keyboard,                             # Функция построения клавиатуры ЛК
)
from ...headlines.add_headline import (                          # Работа с сообщениями с картинкой-заголовком
    edit_message_with_headline,                                  # Редактирование media + caption + reply_markup
    HEADLINE_BASE,                                               # Базовый тип заголовка (base_headline.jpg)
)
from ...states.settings.settings import (                        # Состояния FSM для настроек
    SettingsStates,                                              # Класс с состояниями настроек
)


# Создаём отдельный роутер для настроек,
# который нужно подключить в main.py: dp.include_router(settings_router)
settings_router: Router = Router(
    name="settings",                                             # Имя роутера (для логирования и отладки)
)


async def send_settings_screen(
    message: Message,                                            # Сообщение, которое нужно "превратить" в экран настроек
    state: Optional[FSMContext] = None,                          # FSM-контекст пользователя (может быть None)
) -> None:
    """
    Переключить текущее сообщение на экран «Настройки» БЕЗ отправки нового сообщения.

    ВАЖНО:
    - сообщение с ЛК — это фото с caption (через send_message_with_headline);
    - поэтому редактировать его нужно через edit_message_with_headline (edit_media),
      а НЕ через edit_text / safe_edit_text.

    Логика:
    1) Определяем user_id по chat.id (в приватном чате совпадает с ID пользователя и именем JSON-файла).
    2) Формируем текст настроек (build_settings_text), всегда с полными реквизитами.
    3) Формируем клавиатуру настроек (build_settings_keyboard).
    4) Через edit_message_with_headline редактируем ЭТО ЖЕ сообщение:
       - меняем caption,
       - меняем инлайн-клавиатуру,
       - (по желанию можно сменить картинку, но пока оставляем HEADLINE_BASE).
    5) Обновляем FSM:
       - сохраняем last_bot_message_id,
       - выставляем состояние SettingsStates.setting_state.
    """

    # --- Шаг 1. Определяем user_id --- #
    # В приватном чате chat.id == user_id пользователя и == имени JSON-файла.
    # message.from_user.id здесь будет ID бота, потому что сообщение отправлено ботом.
    chat = message.chat                                              # Берём объект чата из сообщения
    if chat is not None:                                             # Проверяем, что чат существует (он всегда должен быть)
        user_id: int = chat.id                                       # Для нашей схемы БД используем chat.id как user_id
    else:
        # Теоретически такого быть не должно, но на всякий случай подстрахуемся:
        user_id = message.from_user.id                               # Фолбэк — берём from_user.id

    # --- Шаг 2. Формируем текст настроек --- #

    settings_text: str = build_settings_text(                        # Получаем текст экрана настроек
        user_id=user_id,                                             # Передаём определённый user_id
    )

    # --- Шаг 3. Формируем клавиатуру настроек --- #

    settings_keyboard = build_settings_keyboard()                    # Собираем инлайн-клавиатуру с тремя кнопками

    # --- Шаг 4. Редактируем текущее сообщение (media + caption + клавиатура) --- #

    edited_message: Message = await edit_message_with_headline(
        message=message,                                             # То же самое сообщение, где сейчас ЛК
        text=settings_text,                                          # Новый текст caption — экран настроек
        headline_type=HEADLINE_BASE,                                 # Тип заголовка (оставляем базовый)
        reply_markup=settings_keyboard,                              # Новая клавиатура — настройки
        parse_mode="Markdown",                                       # Разметка — Markdown (как в personal_cabinet_text)
    )

    # --- Шаг 5. Обновляем FSM --- #

    if state is not None:                                            # Если FSM-контекст существует
        # Сохраняем ID этого сообщения как last_bot_message_id
        await state.update_data(
            last_bot_message_id=edited_message.message_id,           # Сохраняем ID отредактированного сообщения
        )

        # Переводим пользователя в состояние настроек
        await state.set_state(
            SettingsStates.setting_state,                            # Единственное состояние для экрана настроек
        )


# --- Заглушки для кнопок на экране настроек --- #


@settings_router.callback_query(                                     # Хэндлер для кнопки «Номера телефонов»
    F.data == SETTINGS_PHONES_CALLBACK_DATA,                         # Срабатывает, если callback_data == "settings:phones"
)
async def on_settings_phones_button(
    callback: CallbackQuery,                                         # Объект callback-запроса от инлайн-кнопки
    state: FSMContext,                                               # FSM-контекст пользователя (на будущее)
) -> None:
    """
    Кнопка «Номера телефонов».

    Пока это заглушка: просто закрываем "часики".
    В дальнейшем здесь можно будет открыть отдельный подэкран управления номерами телефонов.
    """

    await callback.answer()                                          # Закрываем индикатор ожидания без доп. действий


@settings_router.callback_query(                                     # Хэндлер для кнопки «Банковские карты»
    F.data == SETTINGS_CARDS_CALLBACK_DATA,                          # Срабатывает, если callback_data == "settings:cards"
)
async def on_settings_cards_button(
    callback: CallbackQuery,                                         # Объект callback-запроса от инлайн-кнопки
    state: FSMContext,                                               # FSM-контекст (на будущее)
) -> None:
    """
    Кнопка «Банковские карты».

    Пока заглушка: просто закрываем "часики".
    В дальнейшем здесь можно будет реализовать экран управления банковскими картами.
    """

    await callback.answer()                                          # Закрываем индикатор ожидания


@settings_router.callback_query(                                     # Хэндлер для кнопки «Назад в личный кабинет»
    F.data == SETTINGS_BACK_CALLBACK_DATA,                           # Срабатывает, если callback_data == "settings:back_to_lk"
)
async def on_settings_back_button(
    callback: CallbackQuery,                                         # Объект callback-запроса
    state: FSMContext,                                               # FSM-контекст (читаем из него флаг show_details и т.п.)
) -> None:
    """
    Кнопка «Назад в личный кабинет».

    Логика:
    1) Закрываем "часики".
    2) Читаем из FSM флаг lk_show_details (показывать реквизиты или нет в ЛК).
    3) Формируем текст личного кабинета по этим данным.
    4) Формируем клавиатуру личного кабинета.
    5) Редактируем ЭТО ЖЕ сообщение обратно на ЛК через edit_message_with_headline.
    6) Обновляем last_bot_message_id в FSM.
    """

    await callback.answer()                                          # Сразу закрываем "часики" на кнопке

    message: Optional[Message] = callback.message                    # Берём сообщение, в котором сейчас экран «Настройки»
    if message is None:                                              # На всякий случай проверяем, что сообщение есть
        return                                                       # Если по какой-то причине его нет — просто выходим

    # --- Шаг 2. Читаем флаг show_details из FSM --- #

    fsm_data = await state.get_data()                                # Получаем все данные FSM для пользователя
    show_details: bool = bool(                                       # Преобразуем к bool на всякий случай
        fsm_data.get("lk_show_details", False)                       # По умолчанию False (реквизиты скрыты)
    )

    # --- Шаг 3. Формируем текст личного кабинета --- #

    user_id: int = callback.from_user.id                             # ID пользователя, на которого заведен JSON-файл в БД

    personal_text: str = build_personal_cabinet_text(                # Строим текст ЛК
        user_id=user_id,                                             # Передаём ID пользователя
        show_details=show_details,                                   # Передаём флаг видимости реквизитов
    )

    # --- Шаг 4. Формируем клавиатуру личного кабинета --- #

    personal_keyboard = build_personal_cabinet_keyboard(             # Собираем клавиатуру ЛК
        show_details=show_details,                                   # Кнопка "Показать/Скрыть реквизиты" завязана на этот флаг
    )

    # --- Шаг 5. Редактируем текущее сообщение обратно на ЛК --- #

    edited_message: Message = await edit_message_with_headline(
        message=message,                                             # То же самое сообщение, где сейчас экран настроек
        text=personal_text,                                          # Новый caption — текст личного кабинета
        headline_type=HEADLINE_BASE,                                 # Тип заголовка оставляем базовый
        reply_markup=personal_keyboard,                              # Новая клавиатура — клавиатура ЛК
        parse_mode="Markdown",                                       # Используем Markdown (как в personal_cabinet_text)
    )

    # --- Шаг 6. Обновляем last_bot_message_id в FSM --- #

    await state.update_data(
        last_bot_message_id=edited_message.message_id,               # Фиксируем ID отредактированного сообщения
    )

    # Состояние SettingsStates.setting_state можно оставить —
    # хэндлеры ЛК у тебя и так завязаны на callback_data, а не на конкретное состояние.
