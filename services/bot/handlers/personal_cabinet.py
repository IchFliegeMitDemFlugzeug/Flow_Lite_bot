# services/bot/handlers/personal_cabinet.py

"""
Хэндлеры и вспомогательные функции для экрана «Личный кабинет».

Вся логика формирования текста вынесена в services/bot/texts/personal_cabinet.py.
Здесь:
- отправляем сообщения с картинкой-заголовком (через add_headline),
- подставляем правильную клавиатуру (через keyboards.personal_cabinet),
- убираем клавиатуру у предыдущего сообщения (через remove_keyboards),
- обрабатываем нажатия на кнопки личного кабинета.

ВАЖНО: Везде используем parse_mode="Markdown", чтобы было единообразно
с main.py (DefaultBotProperties) и add_headline.py.
"""

from __future__ import annotations  # Разрешаем ссылаться в аннотациях на объекты, объявленные ниже по файлу

from typing import Optional         # Optional нужен для аргументов, которые могут быть None

from aiogram import Router, F       # Router — контейнер для хэндлеров; F — фильтр по полям апдейта
from aiogram.types import (         # Импортируем основные типы Telegram-объектов
    Message,                        # Message — обычное текстовое/медиа сообщение
    CallbackQuery,                  # CallbackQuery — объект нажатия инлайн-кнопки
)
from aiogram.fsm.context import FSMContext  # FSMContext — контекст машины состояний для конкретного пользователя

# --- Наши внутренние модули ---

from ..texts.personal_cabinet import (      # Модуль с логикой построения текста личного кабинета
    build_personal_cabinet_text,            # Функция: собирает текст ЛК по user_id и флагу show_details
)
from ..keyboards.personal_cabinet import (  # Модуль с клавиатурами личного кабинета
    build_personal_cabinet_keyboard,        # Функция: строит инлайн-клавиатуру ЛК (Показать/Скрыть, Настройки и т.д.)
)
from ..headlines.add_headline import (      # Модуль работы с картинками-заголовками
    send_message_with_headline,             # Отправка НОВОГО сообщения с фото + caption
    edit_message_with_headline,             # Редактирование УЖЕ СУЩЕСТВУЮЩЕГО сообщения (фото + caption)
    HEADLINE_BASE,                          # Тип базовой картинки-заголовка (base_headline.jpg)
)
from ..tools.remove_keyboards import (      # Модуль с утилитами для работы с клавиатурами
    remove_previous_bot_keyboard,           # Функция: убирает клавиатуру у предыдущего сообщения бота по last_bot_message_id
)

# safe_edit.py здесь не нужен, потому что:
# - мы не редактируем отдельно клавиатуру,
# - а меняем целиком media (картинку) + caption через edit_message_with_headline,
# - ошибка "message is not modified" тут маловероятна: текст и/или клавиатура всегда меняются.


# Создаём отдельный роутер для личного кабинета.
# В main.py его нужно подключить через dp.include_router(personal_cabinet_router)
personal_cabinet_router: Router = Router(
    name="personal_cabinet",                # Имя роутера — просто ярлык для отладки
)


async def send_personal_cabinet_screen(
    message: Message,                       # Сообщение, относительно которого будем отправлять экран ЛК
    state: Optional[FSMContext] = None,     # FSM-контекст пользователя; может быть None (на всякий случай)
) -> None:
    """
    Универсальная функция отправки экрана «Личный кабинет».

    Шаги:
    1) Берём из FSM флаг lk_show_details (показывать реквизиты или нет), по умолчанию False.
    2) Если FSM есть — убираем клавиатуру у предыдущего сообщения бота через remove_previous_bot_keyboard.
    3) Собираем текст ЛК build_personal_cabinet_text(user_id, show_details).
    4) Строим клавиатуру ЛК build_personal_cabinet_keyboard(show_details).
    5) Отправляем новое сообщение с картинкой-заголовком send_message_with_headline(..., parse_mode="Markdown").
    6) Сохраняем ID этого сообщения и флаг lk_show_details в FSM (last_bot_message_id, lk_show_details).
    """

    # По умолчанию считаем, что реквизиты скрыты (кнопка будет "Показать реквизиты")
    show_details: bool = False

    if state is not None:                   # Если нам передали FSM-контекст
        fsm_data = await state.get_data()   # Читаем все данные FSM как словарь

        # Забираем флаг видимости реквизитов, если он уже был сохранён
        # Если в FSM его ещё нет — по умолчанию False (реквизиты скрыты)
        show_details = bool(fsm_data.get("lk_show_details", False))

        # Перед отправкой нового сообщения убираем клавиатуру у ПРЕДЫДУЩЕГО сообщения бота
        # Это как раз тот случай, когда используется remove_keyboards.py
        await remove_previous_bot_keyboard(
            state=state,                    # Передаём FSM-контекст, чтобы функция могла достать last_bot_message_id
            bot=message.bot,                # Экземпляр бота берём из объекта message
            chat_id=message.chat.id,        # ID чата, в котором нужно убрать клавиатуру
        )

    # Формируем текст личного кабинета (внутри уже учтён show_details)
    # ВАЖНО: build_personal_cabinet_text должен возвращать КОРРЕКТНЫЙ Markdown:
    #  - для жирного использовать ОДИНАРНЫЕ звёздочки: *текст*, а не **текст**;
    #  - не генерировать последовательность "***" (например, "Телефон *** 44-55"),
    #    либо оборачивать её в `код`, иначе Telegram выдаст ошибку разбора разметки.
    cabinet_text: str = build_personal_cabinet_text(
        user_id=message.from_user.id,       # Передаём Telegram ID пользователя
        show_details=show_details,          # Флаг "показать реквизиты" / "скрыть реквизиты"
    )

    # Строим инлайн-клавиатуру для экрана ЛК
    keyboard = build_personal_cabinet_keyboard(
        show_details=show_details,          # От этого зависит текст кнопки "Показать/Скрыть реквизиты"
    )

    # Отправляем новое сообщение с картинкой-заголовком
    sent_message: Message = await send_message_with_headline(
        message=message,                    # Отправляем "в ответ" на переданное message
        text=cabinet_text,                  # Текст личного кабинета (Markdown)
        headline_type=HEADLINE_BASE,        # Тип заголовка — базовый
        reply_markup=keyboard,              # Клавиатура ЛК
        parse_mode="Markdown",              # ЯВНО указываем Markdown (как в add_headline по умолчанию и в main.py)
    )

    if state is not None:                   # Если FSM-контекст есть
        # Сохраняем ID нового сообщения бота и текущее состояние флага видимости реквизитов
        await state.update_data(
            last_bot_message_id=sent_message.message_id,  # ID сообщения, у которого в будущем будем убирать клавиатуру
            lk_show_details=show_details,                 # Текущее значение флага "показывать реквизиты"
        )


@personal_cabinet_router.callback_query(    # Регистрируем хэндлер на callback-запросы
    F.data == "lk:open",                    # Срабатывает, когда callback_data == "lk:open"
)
async def on_personal_cabinet_button(
    callback: CallbackQuery,                # Объект callback-запроса (нажатие по инлайн-кнопке)
    state: FSMContext,                      # FSM-контекст пользователя
) -> None:
    """
    Обработка нажатия на кнопку «Личный кабинет».

    Логика:
    - закрываем "часики" на кнопке;
    - пересобираем и отправляем экран личного кабинета.
    """

    await callback.answer()                 # Закрываем индикатор ожидания ("часики") на кнопке

    # Переиспользуем общую функцию отправки ЛК (всё, как при /start)
    await send_personal_cabinet_screen(
        message=callback.message,           # Используем сообщение, под которым расположена кнопка
        state=state,                        # Передаём FSM-контекст (для last_bot_message_id и lk_show_details)
    )


@personal_cabinet_router.callback_query(    # Хэндлер для переключателя "Показать/Скрыть реквизиты"
    F.data == "lk:toggle_details",          # Срабатывает, когда callback_data == "lk:toggle_details"
)
async def on_toggle_details_button(
    callback: CallbackQuery,                # Callback-запрос от инлайн-кнопки
    state: FSMContext,                      # FSM-контекст пользователя
) -> None:
    """
    Обработка нажатия на кнопку «Показать реквизиты» / «Скрыть реквизиты».

    Действия:
    1) Берём текущее значение lk_show_details из FSM.
    2) Инвертируем его (False -> True, True -> False).
    3) Пересобираем текст ЛК и клавиатуру под новое состояние.
    4) Редактируем СУЩЕСТВУЮЩЕЕ сообщение с помощью edit_message_with_headline.
    5) Обновляем lk_show_details и last_bot_message_id в FSM.
    """

    await callback.answer()                 # Закрываем "часики" на кнопке

    fsm_data = await state.get_data()       # Получаем текущие данные FSM

    # Текущее значение флага (если его нет — считаем False, то есть реквизиты скрыты)
    current_show_details: bool = bool(fsm_data.get("lk_show_details", False))

    # Новое значение — просто инверсия текущего
    new_show_details: bool = not current_show_details

    # Пересобираем текст личного кабинета с учётом нового флага
    new_text: str = build_personal_cabinet_text(
        user_id=callback.from_user.id,      # ID пользователя берём из callback.from_user.id
        show_details=new_show_details,      # Новое состояние видимости реквизитов
    )

    # Пересобираем клавиатуру под новое состояние
    new_keyboard = build_personal_cabinet_keyboard(
        show_details=new_show_details,      # Теперь текст кнопки будет противоположный (Показать/Скрыть)
    )

    # Редактируем СУЩЕСТВУЮЩЕЕ сообщение (картинка остаётся HEADLINE_BASE, меняем только caption и клавиатуру)
    edited_message: Message = await edit_message_with_headline(
        message=callback.message,           # Сообщение, внутри которого была нажата кнопка
        text=new_text,                      # Новый caption (Markdown)
        headline_type=HEADLINE_BASE,        # Тип заголовка не меняем — остаётся базовый
        reply_markup=new_keyboard,          # Новая инлайн-клавиатура ЛК
        parse_mode="Markdown",              # Важно: опять Markdown, чтобы *жирный* работал
    )

    # Обновляем данные FSM: сохраняем новое значение флага и ID сообщения
    await state.update_data(
        lk_show_details=new_show_details,   # Новое состояние "показывать реквизиты"
        last_bot_message_id=edited_message.message_id,  # ID (тот же, но фиксируем для remove_previous_bot_keyboard)
    )


@personal_cabinet_router.callback_query(    # Хэндлер для кнопки «Настройки»
    F.data == "lk:settings",                # Срабатывает, когда callback_data == "lk:settings"
)
async def on_settings_button(
    callback: CallbackQuery,                # Callback-запрос от инлайн-кнопки
    state: FSMContext,                      # FSM-контекст (зарезервирован на будущее использование)
) -> None:
    """
    Кнопка «Настройки».

    Пока это заглушка: просто закрываем "часики".
    Позже отсюда можно будет открывать отдельный экран настроек.
    """

    await callback.answer()                 # Закрываем индикатор ожидания и ничего больше не делаем


@personal_cabinet_router.callback_query(    # Хэндлер для кнопки «Квитанции»
    F.data == "lk:receipts",                # Срабатывает, когда callback_data == "lk:receipts"
)
async def on_receipts_button(
    callback: CallbackQuery,                # Callback-запрос
    state: FSMContext,                      # FSM-контекст (на будущее)
) -> None:
    """
    Кнопка «Квитанции».

    Сейчас это заглушка: просто закрываем "часики".
    В дальнейшем тут можно показать список квитанций или фильтры.
    """

    await callback.answer()                 # Закрываем индикатор ожидания


@personal_cabinet_router.callback_query(    # Хэндлер для кнопки «Информация»
    F.data == "lk:info",                    # Срабатывает, когда callback_data == "lk:info"
)
async def on_info_button(
    callback: CallbackQuery,                # Callback-запрос
    state: FSMContext,                      # FSM-контекст (на будущее)
) -> None:
    """
    Кнопка «Информация».

    Пока тоже заглушка — закрываем "часики".
    Позже сюда можно добавить справку/FAQ.
    """

    await callback.answer()                 # Закрываем индикатор ожидания
