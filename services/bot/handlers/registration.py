from __future__ import annotations  # Включаем "отложенные" аннотации типов (можно ссылаться на классы, объявленные ниже)

import asyncio                                              # Импортируем asyncio (сейчас напрямую не используется, но может пригодиться)

from aiogram import Router, F                               # Router — для регистрации хэндлеров; F — для фильтрации по полям апдейта
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove  # Типы сообщений, callback-запросов и "удалителя" reply-клавиатуры
from aiogram.filters import CommandStart                    # Фильтр, который срабатывает на команду /start
from aiogram.fsm.context import FSMContext                  # Контекст машины состояний FSM

from ..states.registration import RegistrationStates        # Импортируем набор состояний регистрации

from ..texts.registration import (                          # Импортируем шаблоны и тексты для всех этапов
    START_WELCOME_TEXT,                                     # Текст стартового экрана (для незарегистрированного пользователя)
    START_INFO_TEXT,                                        # Текст "Информация о сервисе"
    START_OVERVIEW_TEXT,                                    # Текст "Обзор бота"
    REQUEST_PHONE_TEXT,                                     # Текст запроса номера телефона
    BANK_CHOICE_TEXT_TEMPLATE,                              # Шаблон текста для шага "Выбор банков"
    NO_BANK_TEXT,                                           # Текст сценария "нет нужного банка"
    MAIN_BANK_CHOICE_TEXT_TEMPLATE,                         # Шаблон текста для шага "Выбор основного банка"
    BANK_CHOICE_DONE_TEXT_TEMPLATE,                         # Финальный текст после выбора основного банка
    NO_BANK_THANKS_TEXT,                                    # Текст благодарности при сценарии "нет нужного банка"
)

from ..keyboards.registration import (                      # Импортируем функции построения клавиатур
    build_start_keyboard,                                   # Инлайн-клавиатура стартового экрана
    build_request_phone_keyboard,                           # Reply-клавиатура "Отправить номер телефона"
    build_bank_choice_keyboard,                             # Инлайн-клавиатура для шага "Выбор банков"
    build_main_bank_choice_keyboard,                        # Инлайн-клавиатура для шага "Выбор основного банка"
    build_no_bank_keyboard,                                 # Инлайн-клавиатура сценария "нет нужного банка"
)

from ..tools.banks_wordbook import BANKS                    # Импортируем словарь банков (названия, эмодзи и т.д.)

from ..tools.safe_edit import (                             # Функции безопасного редактирования сообщений
    safe_edit_reply_markup,                                 # Безопасно меняет только инлайн-клавиатуру у сообщения
)

from ..tools.remove_keyboards import remove_previous_bot_keyboard  # Функция удаления клавиатуры у предыдущего сообщения бота

from bot.handlers.personal_cabinet import (             # Импортируем функцию показа экрана ЛК
    send_personal_cabinet_screen,                       # Универсальная функция отправки сообщения «личный кабинет»
)


from ..headlines.add_headline import (                      # Функции и константы для картинок-заголовков
    send_message_with_headline,                             # Отправка нового сообщения с картинкой-заголовком
    edit_message_with_headline,                             # Редактирование существующего сообщения с заменой картинки/текста
    HEADLINE_REG_1,                                         # Картинка для шага 1 (запрос номера телефона)
    HEADLINE_REG_2,                                         # Картинка для шага 2 (выбор банков)
    HEADLINE_REG_3,                                         # Картинка для шага 3 (выбор основного банка)
    HEADLINE_BASE,                                          # Базовая картинка (стартовый экран, общие сообщения)
)

from ..database import (                                    # Функции работы с БД (async)
    get_user,                                               # Получить (или создать) пользователя по user_id
    update_basic_user_info,                                 # Обновить базовую информацию о пользователе
    add_or_update_phone,                                    # Добавить/обновить номер телефона с банками и основным банком
    set_registration_progress,                              # Сохранить шаг регистрации и текущий номер телефона
    get_registration_progress,                              # Получить шаг регистрации и текущий номер из файла
)

from ..tools.phone_utils import extract_phone_from_message  # Импортируем функцию извлечения/нормализации номера из сообщения


# Создаем отдельный роутер для регистрационных хэндлеров
registration_router = Router(name="registration")           # Роутер с именем "registration" — удобно для отладки и структуры


async def _is_user_registered(user_id: int) -> bool:
    """
    Проверяем, считается ли пользователь ПОЛНОСТЬЮ зарегистрированным.

    Логика:
    - user.registration_step == "completed"
    - и есть хотя бы один номер с ненулевым списком банков.
    """

    user = await get_user(user_id)                                # Загружаем объект пользователя из "базы"

    if user.registration_step != "completed":               # Если шаг регистрации НЕ "completed"
        return False                                        # Сразу говорим, что регистрация не закончена

    for phone_data in user.phones.values():                 # Перебираем все номера телефона пользователя
        if phone_data.banks:                                # Если у номера есть хотя бы один банк
            return True                                     # Считаем, что юзер зарегистрирован

    return False                                            # Иначе — нет ни одного номера с банком, значит регистрация не завершена


async def _get_phone_from_state_or_db(user_id: int, fsm_data: dict) -> str | None:
    """
    Универсальный способ получить НОМЕР ТЕЛЕФОНА, чтобы не получить 'неизвестен'.

    Приоритет:
    1) Берём phone из FSM (если там уже есть).
    2) Если нет — читаем (step, current_phone) из БД.
    3) Если current_phone не задан — пробуем user.current_phone или первый номер из user.phones.
    4) Если вообще ничего нет — возвращаем None.
    """

    phone = fsm_data.get("phone")                           # Пробуем взять номер из FSM
    if phone:                                               # Если в FSM номер есть
        return phone                                        # Сразу возвращаем его

    step, current_phone = await get_registration_progress(user_id)  # Читаем прогресс регистрации из файла
    if current_phone:                                       # Если в файле указан current_phone
        return current_phone                                # Используем его

    user = await get_user(user_id)                                # Загружаем пользователя из БД

    if user.current_phone:                                  # Если в объекте пользователя сохранён current_phone
        return user.current_phone                           # Возвращаем его

    if user.phones:                                         # Если у пользователя вообще есть какие-то телефоны
        return next(iter(user.phones.keys()))               # Берём первый попавшийся номер телефона

    return None                                             # Если нигде номера нет — возвращаем None


async def _restore_registration_step_from_db(
    message: Message,
    state: FSMContext,
) -> bool:
    """
    Пытаемся восстановить шаг регистрации пользователя из БД
    и "вернуть" его на тот же экран после перезапуска бота или /start.

    Возвращаем:
    - True  — если шаг успешно восстановлен (мы уже отправили нужное сообщение);
    - False — если восстановить нечего (надо показывать обычный стартовый экран).
    """

    user_id = message.from_user.id                          # Берём Telegram ID пользователя
    user = await get_user(user_id)                                # Загружаем его запись из "базы"

    step, current_phone = await get_registration_progress(user_id)  # Читаем сохраненный шаг и текущий номер телефона

    if step is None:                                        # Если шаг не сохранён
        return False                                        # Нечего восстанавливать

    if step == "completed":                                 # Если регистрация уже завершена
        return False                                        # Восстановление шага не требуется

    # --- Шаг "phone" (ожидание номера телефона) --- #
    if step == "phone":
        await state.set_state(RegistrationStates.waiting_for_phone)  # Ставим FSM-состояние ожидания телефона

        sent_message = await send_message_with_headline(    # Отправляем сообщение "Шаг 1 — отправьте номер"
            message=message,
            text=REQUEST_PHONE_TEXT,
            headline_type=HEADLINE_REG_1,
            reply_markup=build_request_phone_keyboard(),
            parse_mode="Markdown",
        )

        await state.update_data(last_bot_message_id=sent_message.message_id)  # Сохраняем ID сообщения бота
        return True                                         # Говорим, что восстановление успешно

    # --- Шаг "banks" (выбор банков) --- #
    if step == "banks":
        phone = current_phone                               # Берём current_phone как рабочий номер
        if not phone:                                       # Если он не задан
            if user.phones:                                 # Если вообще есть телефоны в БД
                phone = next(iter(user.phones.keys()))      # Берём первый номер
            else:                                           # Если телефонов нет вовсе
                await set_registration_progress(user_id, "phone", None)  # Откатываем шаг до "phone"
                await state.set_state(RegistrationStates.waiting_for_phone)  # FSM в состояние ожидания телефона
                sent_message = await send_message_with_headline(  # Шлём запрос номера
                    message=message,
                    text=REQUEST_PHONE_TEXT,
                    headline_type=HEADLINE_REG_1,
                    reply_markup=build_request_phone_keyboard(),
                    parse_mode="Markdown",
                )
                await state.update_data(last_bot_message_id=sent_message.message_id)
                return True

        phone_data = user.phones.get(phone)                 # Берём данные по этому номеру (если есть)
        selected_banks = phone_data.banks if phone_data else []  # Список выбранных банков
        main_bank = phone_data.main_bank if phone_data else None  # Основной банк (может быть None)

        await state.update_data(                            # Сохраняем данные в FSM
            phone=phone,
            selected_banks=selected_banks,
            main_bank=main_bank,
        )

        await state.set_state(RegistrationStates.waiting_for_banks)  # FSM в состояние выбора банков

        text = BANK_CHOICE_TEXT_TEMPLATE.format(phone=phone)  # Формируем текст шага "Выбор банков"

        sent_message = await send_message_with_headline(    # Отправляем сообщение с картинкой reg_2
            message=message,
            text=text,
            headline_type=HEADLINE_REG_2,
            reply_markup=build_bank_choice_keyboard(selected_banks=selected_banks),
            parse_mode="Markdown",
        )

        await state.update_data(last_bot_message_id=sent_message.message_id)
        return True

    # --- Шаг "main_bank" (выбор основного банка) --- #
    if step == "main_bank":
        phone = current_phone                               # Берём current_phone
        if not phone or phone not in user.phones:           # Если номер не задан или его нет в словаре
            await set_registration_progress(user_id, "banks", None)  # Откатываемся до шага "banks"
            return await _restore_registration_step_from_db(message, state)  # Рекурсивно восстанавливаем "banks"

        phone_data = user.phones.get(phone)                 # Берём данные по номеру
        selected_banks = phone_data.banks if phone_data else []
        main_bank = phone_data.main_bank if phone_data else None

        if not selected_banks:                              # Если по номеру не выбрано ни одного банка
            await set_registration_progress(user_id, "banks", phone)  # Возвращаемся к шагу выбора банков
            return await _restore_registration_step_from_db(message, state)

        await state.update_data(                            # Сохраняем в FSM номер, банки и основной банк
            phone=phone,
            selected_banks=selected_banks,
            main_bank=main_bank,
        )

        await state.set_state(RegistrationStates.waiting_for_main_bank)  # FSM в состояние выбора основного банка

        readable_banks = [                                  # Формируем список "человеческих" названий банков
            BANKS[code]["message_title"]
            for code in selected_banks
            if code in BANKS
        ]
        banks_list_str = ", ".join(readable_banks)          # Склеиваем в строку через запятую

        text = MAIN_BANK_CHOICE_TEXT_TEMPLATE.format(       # Формируем текст шага "Выбор основного банка"
            phone=phone,
            banks_list=banks_list_str,
        )

        keyboard = build_main_bank_choice_keyboard(         # Строим клавиатуру выбора основного банка
            available_banks=selected_banks,
            main_bank=main_bank,
        )

        sent_message = await send_message_with_headline(    # Отправляем сообщение с картинкой reg_3
            message=message,
            text=text,
            headline_type=HEADLINE_REG_3,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

        await state.update_data(last_bot_message_id=sent_message.message_id)
        return True

    # --- Шаг "no_banks" (сценарий "нет нужного банка") --- #
    if step == "no_banks":
        # Пытаемся понять, с каким номером мы работали
        phone = current_phone                               # Текущий номер из прогресса
        if not phone and user.phones:                       # Если он не задан, но есть телефоны
            phone = next(iter(user.phones.keys()))          # Берём первый номер

        # На этом шаге номер в тексте не нужен, но "на будущее" сохраним его в FSM
        await state.update_data(phone=phone)                # Сохраняем номер (если он вообще есть)

        await state.set_state(RegistrationStates.no_banks)  # Ставим состояние FSM "нет нужного банка"

        sent_message = await send_message_with_headline(    # Отправляем текст сценария "нет нужного банка"
            message=message,
            text=NO_BANK_TEXT,
            headline_type=HEADLINE_BASE,
            reply_markup=build_no_bank_keyboard(),
            parse_mode="Markdown",
        )

        await state.update_data(last_bot_message_id=sent_message.message_id)
        return True

    # Если шаг какой-то неизвестный — считаем, что восстановить ничего не можем
    return False


# --- ХЭНДЛЕР /start --- #

@registration_router.message(CommandStart())                # Этот хэндлер срабатывает при получении команды /start
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    Стартовая точка.

    1) Обновляем базовую информацию о пользователе в БД.
    2) Убираем клавиатуру у предыдущего сообщения бота (если было).
    3) Сбрасываем FSM.
    4) Если регистрация завершена — отправляем экран «Личный кабинет».
    5) Если незавершена, но есть сохранённый шаг — восстанавливаем его.
    6) Иначе показываем стартовый экран с документами.
    """

    await update_basic_user_info(                                # Обновляем базовые данные пользователя в БД
        user_id=message.from_user.id,                      # ID пользователя из Telegram
        first_name=message.from_user.first_name,           # Имя пользователя
        last_name=message.from_user.last_name,             # Фамилия пользователя (может быть None)
        username=message.from_user.username,               # Никнейм пользователя (может быть None)
    )

    await remove_previous_bot_keyboard(                    # Убираем клавиатуру у предыдущего сообщения бота, если она была
        state=state,                                       # Передаём FSM-контекст (оттуда возьмём last_bot_message_id)
        bot=message.bot,                                   # Объект бота
        chat_id=message.chat.id,                           # ID чата, в котором работаем
    )

    await state.clear()                                    # Полностью очищаем FSM (и состояние, и данные)

    user_id = message.from_user.id                         # Сохраняем user_id в локальную переменную для удобства

    # --- Ключевая развилка: зарегистрирован / не зарегистрирован --- #

    if await _is_user_registered(user_id):                       # Проверяем, считается ли пользователь полностью зарегистрированным
        # Если да — сразу показываем экран «Личный кабинет».
        # Вся логика показа ЛК живёт в отдельном модуле personal_cabinet.
        await send_personal_cabinet_screen(
            message=message,                               # Используем входящее сообщение /start как точку отправки ЛК
            state=state,                                   # Передаём FSM-контекст (функция сама установит last_bot_message_id)
        )
        return                                             # Выходим из хэндлера, регистрация нам не нужна

    # --- Если пользователь НЕ зарегистрирован полностью --- #

    # Пытаемся восстановить шаг регистрации из БД (после рестарта бота или повторного /start)
    restored = await _restore_registration_step_from_db(
        message=message,                                   # Входящее сообщение /start
        state=state,                                       # FSM-контекст
    )

    if restored:                                           # Если шаг успешно восстановлен
        return                                             # Больше ничего делать не нужно — нужный экран уже отправлен

    # Если восстановить нечего — это "самый первый" /start и регистрация ещё не начата.
    # Показываем стартовый экран с краткой инфой и кнопкой "Начать пользоваться".
    sent_message = await send_message_with_headline(
        message=message,                                   # Отправляем стартовый экран в ответ на /start
        text=START_WELCOME_TEXT,                           # Текст приветствия и юридической информации
        headline_type=HEADLINE_BASE,                       # Базовая картинка-заголовок
        reply_markup=build_start_keyboard(),               # Инлайн-клавиатура стартового экрана
        parse_mode="Markdown",                             # Включаем Markdown (там используются форматирования)
    )

    await state.update_data(                               # Сохраняем ID отправленного сообщения
        last_bot_message_id=sent_message.message_id,       # Пишем его в FSM, чтобы потом убрать клавиатуру
    )


# --- CALLBACK-И СТАРТОВОГО ЭКРАНА --- #

@registration_router.callback_query(                        # Хэндлер callback-запросов
    F.data.startswith("start:"),                            # Фильтр: обрабатываем только callback_data, начинающиеся с "start:"
)
async def process_start_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатываем кнопки стартового экрана:

    - "start:info"     — показать текст «Информация»;
    - "start:overview" — показать «Обзор бота»;
    - "start:begin"    — начать регистрацию (Шаг 1 из 3).
    """

    data = callback.data                                   # Берём сырую callback_data (например, "start:info")
    _, action = data.split(":", maxsplit=1)                # Отделяем "start" от действия ("info", "overview", "begin")

    user_id = callback.from_user.id                        # Берём user_id

    if action == "info":                                   # Кнопка "Информация"
        await callback.answer()                            # Закрываем "часики" на кнопке

        await edit_message_with_headline(                  # Редактируем текущее сообщение
            message=callback.message,
            text=START_INFO_TEXT,
            headline_type=HEADLINE_BASE,
            reply_markup=build_start_keyboard(),
            parse_mode="Markdown",
        )

        await state.update_data(last_bot_message_id=callback.message.message_id)
        return

    if action == "overview":                               # Кнопка "Обзор бота"
        await callback.answer()                            # Закрываем "часики"

        await edit_message_with_headline(
            message=callback.message,
            text=START_OVERVIEW_TEXT,
            headline_type=HEADLINE_BASE,
            reply_markup=build_start_keyboard(),
            parse_mode="Markdown",
        )

        await state.update_data(last_bot_message_id=callback.message.message_id)
        return

    if action == "begin":                                  # Кнопка "Начать пользоваться"
        await callback.answer()                            # Закрываем "часики"

        await set_registration_progress(user_id, "phone", None)  # В БД фиксируем: шаг "phone", текущий номер не задан

        await state.set_state(RegistrationStates.waiting_for_phone)  # FSM в состояние ожидания телефона

        sent_message = await send_message_with_headline(   # Отправляем сообщение "Шаг 1 — отправьте номер"
            message=callback.message,
            text=REQUEST_PHONE_TEXT,
            headline_type=HEADLINE_REG_1,
            reply_markup=build_request_phone_keyboard(),
            parse_mode="Markdown",
        )

        await state.update_data(last_bot_message_id=sent_message.message_id)
        return


# --- ШАГ 1: ОБРАБОТКА НОМЕРА ТЕЛЕФОНА --- #

@registration_router.message(                               # Хэндлер на обычные сообщения
    RegistrationStates.waiting_for_phone                    # Срабатывает только когда FSM в состоянии waiting_for_phone
)
async def process_phone(message: Message, state: FSMContext) -> None:
    """
    Обрабатываем ответ пользователя с номером телефона (контакт или текст).
    После этого переходим к экрану «Выбор банков».
    """

    phone = extract_phone_from_message(message)             # Пытаемся вытащить и нормализовать номер из сообщения

    if not phone:                                           # Если номер извлечь НЕ удалось
        await remove_previous_bot_keyboard(                 # Убираем клавиатуру у предыдущего сообщения бота
            state=state,
            bot=message.bot,
            chat_id=message.chat.id,
        )

        sent_message = await send_message_with_headline(    # Отправляем сообщение об ошибке
            message=message,
            text="Не удалось определить номер телефона. Пожалуйста, отправьте его ещё раз.",
            headline_type=HEADLINE_BASE,
            reply_markup=None,
            parse_mode="Markdown",
        )

        await state.update_data(last_bot_message_id=sent_message.message_id)
        return                                              # Остаёмся в состоянии waiting_for_phone

    await state.update_data(phone=phone)                    # Сохраняем номер телефона в FSM

    user_id = message.from_user.id                          # Берём user_id

    await add_or_update_phone(                                    # Сохраняем номер в БД (пока без банков и без основного банка)
        user_id=user_id,
        phone=phone,
        banks=[],
        main_bank=None,
    )

    await set_registration_progress(user_id, "banks", phone)      # Фиксируем, что мы на шаге "banks" и работаем с этим номером

    await state.update_data(                                # Инициализируем в FSM пустой список банков и отсутствие основного банка
        selected_banks=[],
        main_bank=None,
    )

    await state.set_state(RegistrationStates.waiting_for_banks)  # FSM в состояние "выбор банков"

    text = BANK_CHOICE_TEXT_TEMPLATE.format(phone=phone)    # Формируем текст "Вы ввели номер ... На какой банк..."

    await remove_previous_bot_keyboard(                     # Убираем клавиатуру у предыдущего сообщения бота
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
    )

    sent_message = await send_message_with_headline(        # Отправляем сообщение с картинкой reg_2 и клавиатурой выбора банков
        message=message,
        text=text,
        headline_type=HEADLINE_REG_2,
        reply_markup=build_bank_choice_keyboard(selected_banks=[]),
        parse_mode="Markdown",
    )

    await state.update_data(last_bot_message_id=sent_message.message_id)


# --- ШАГ 2: ВЫБОР БАНКОВ --- #

@registration_router.callback_query(                        # Хэндлер callback-запросов
    RegistrationStates.waiting_for_banks,                   # Срабатывает только в состоянии waiting_for_banks
    F.data.startswith("bank:"),                             # И только если callback_data начинается с "bank:"
)
async def process_bank_choice(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Обрабатываем нажатия на кнопки инлайн-клавиатуры «Выбор банков» (шаг 2).

    Возможные callback.data:
    - "bank:<code>"   — переключить выбор конкретного банка;
    - "bank:no_such"  — сценарий «нет нужного банка 😟»;
    - "bank:next"     — завершить выбор банков и перейти к выбору основного банка.
    """

    data = callback.data                                   # Берём строку callback_data (например, "bank:sber")
    _, action = data.split(":", maxsplit=1)                # Отделяем префикс "bank" от значения

    fsm_data = await state.get_data()                      # Читаем текущие данные FSM

    user_id = callback.from_user.id                        # Берём user_id

    phone = await _get_phone_from_state_or_db(user_id, fsm_data) # Пытаемся аккуратно достать номер из FSM или БД
    if not phone:                                          # Если даже тут не удалось восстановить номер
        phone = "неизвестен"                               # Подстрахуемся, чтобы не упасть в format()

    selected_banks: list[str] = fsm_data.get(              # Список уже выбранных банков
        "selected_banks",
        [],
    )

    # --- Сценарий "Нет нужного банка" --- #
    if action == "no_such":
        await set_registration_progress(user_id, "no_banks", phone)  # В БД: шаг "no_banks" и этот номер

        no_banks_keyboard = build_no_bank_keyboard()       # Строим клавиатуру сценария "нет банка"

        await callback.answer()                            # Закрываем "часики" на кнопке

        await edit_message_with_headline(                  # Меняем текст и картинку на сценарий "нет нужного банка"
            message=callback.message,
            text=NO_BANK_TEXT,
            headline_type=HEADLINE_BASE,
            reply_markup=no_banks_keyboard,
            parse_mode="Markdown",
        )

        await state.set_state(RegistrationStates.no_banks) # FSM в состояние no_banks
        await state.update_data(
            phone=phone,                                   # Запомним номер и тут, чтобы при Back не было "неизвестен"
            last_bot_message_id=callback.message.message_id,
        )
        return

    # --- Кнопка "Далее" (переход к выбору основного банка) --- #
    if action == "next":
        if not selected_banks:                             # Если пользователь не выбрал ни одного банка
            await callback.answer(
                "Пожалуйста, выберите хотя бы один банк или нажмите «Нет нужного банка 😟».",
                show_alert=True,
            )
            return

        await add_or_update_phone(                               # В БД сохраняем список банков для этого номера
            user_id=user_id,
            phone=phone,
            banks=selected_banks,
            main_bank=None,
        )

        await set_registration_progress(user_id, "main_bank", phone)  # В БД: шаг "main_bank"

        readable_banks = [                                 # Формируем список "человеческих" названий банков
            BANKS[code]["message_title"]
            for code in selected_banks
            if code in BANKS
        ]
        banks_list_str = ", ".join(readable_banks)         # Склеиваем их в одну строку

        main_bank_text = MAIN_BANK_CHOICE_TEXT_TEMPLATE.format(
            phone=phone,
            banks_list=banks_list_str,
        )

        main_bank_keyboard = build_main_bank_choice_keyboard(   # Строим клавиатуру выбора основного банка
            available_banks=selected_banks,
            main_bank=None,
        )

        await state.update_data(                            # Обновляем данные FSM
            phone=phone,
            selected_banks=selected_banks,
            main_bank=None,
        )

        await state.set_state(RegistrationStates.waiting_for_main_bank)  # FSM в состояние выбора основного банка

        await callback.answer()                             # Закрываем "часики"

        await edit_message_with_headline(                   # Меняем текст/картинку на шаг 3
            message=callback.message,
            text=main_bank_text,
            headline_type=HEADLINE_REG_3,
            reply_markup=main_bank_keyboard,
            parse_mode="Markdown",
        )

        await state.update_data(last_bot_message_id=callback.message.message_id)
        return

    # --- Переключение конкретного банка в мультивыборе --- #
    bank_code = action                                     # В этом случае action — код банка (например "sber")

    if bank_code in selected_banks:                        # Если банк уже выбран
        selected_banks.remove(bank_code)                   # Убираем его из списка
    else:
        selected_banks.append(bank_code)                   # Иначе добавляем

    await state.update_data(                               # Обновляем список выбранных банков в FSM
        phone=phone,
        selected_banks=selected_banks,
    )

    await add_or_update_phone(                                   # Синхронизируем список банков с БД
        user_id=user_id,
        phone=phone,
        banks=selected_banks,
        main_bank=None,
    )

    new_keyboard = build_bank_choice_keyboard(             # Перестраиваем клавиатуру с галочками
        selected_banks=selected_banks,
    )

    await callback.answer()                                # Закрываем "часики"

    await safe_edit_reply_markup(                          # Обновляем только клавиатуру у текущего сообщения
        callback.message,
        reply_markup=new_keyboard,
    )

    await state.update_data(last_bot_message_id=callback.message.message_id)


# --- ШАГ 3: ВЫБОР ОСНОВНОГО БАНКА --- #


@registration_router.callback_query(                        # Регистрируем хэндлер на callback-запросы
    RegistrationStates.waiting_for_main_bank,               # Хэндлер срабатывает только в состоянии выбора основного банка
    F.data.startswith("main_bank:"),                        # И только если callback_data начинается с "main_bank:"
)
async def process_main_bank_choice(
    callback: CallbackQuery,                                # Объект callback-запроса (нажатие на инлайн-кнопку)
    state: FSMContext,                                      # Контекст машины состояний для текущего пользователя
) -> None:
    """
    Обрабатываем нажатия на кнопки инлайн-клавиатуры «Выбор основного банка».

    Возможные callback.data:
    - "main_bank:<code>" — выбор конкретного банка как основного;
    - "main_bank:back"   — вернуться к шагу выбора банков;
    - "main_bank:next"   — подтвердить выбор и завершить регистрацию.
    """

    data: str = callback.data                              # Считываем строку callback_data (например, "main_bank:sber")
    _, action = data.split(":", maxsplit=1)                # Отделяем префикс "main_bank" от действия/кода (получаем "sber"/"back"/"next")

    fsm_data: dict = await state.get_data()                # Получаем все текущие данные FSM (phone, selected_banks, main_bank и т.п.)

    user_id: int = callback.from_user.id                   # Берём user_id из объекта callback (ID телеграм-пользователя)

    # --- Аккуратно достаём номер телефона из FSM или БД --- #
    phone: str | None = await _get_phone_from_state_or_db(       # Универсальная функция: пытается взять номер из FSM или БД
        user_id=user_id,                                   # Передаём user_id, чтобы можно было обратиться к записи пользователя в БД
        fsm_data=fsm_data,                                 # Передаём текущие данные FSM
    )
    if not phone:                                          # Если номер получить не удалось (на всякий случай)
        phone = "неизвестен"                               # Подстраховка, чтобы не было None в форматировании текста

    # --- Список уже выбранных банков --- #
    selected_banks: list[str] = fsm_data.get(              # Достаем из FSM список выбранных банків
        "selected_banks",                                  # Ключ, под которым мы сохраняли выбранные банки
        [],                                                # Если в FSM ничего нет — по умолчанию пустой список
    )

    # --- Текущий основной банк (может быть None) --- #
    main_bank: str | None = fsm_data.get(                  # Пробуем получить из FSM текущий выбранный основной банк
        "main_bank",                                       # Ключ в FSM
        None,                                              # Если ещё не выбирали основной банк — будет None
    )

    # =========================
    #   ВЕТКА: КНОПКА «НАЗАД»
    # =========================
    if action == "back":                                   # Если пользователь нажал кнопку "Назад"
        await set_registration_progress(                         # Обновляем состояние регистрации в БД
            user_id,                                       # user_id пользователя
            "banks",                                       # Шаг регистрации — "banks" (выбор банков)
            phone,                                         # Текущий номер телефона, с которым идём на этот шаг
        )

        await state.set_state(                             # Переводим FSM в состояние выбора банков
            RegistrationStates.waiting_for_banks,          # Состояние, в котором работает хэндлер выбора банков
        )

        text: str = BANK_CHOICE_TEXT_TEMPLATE.format(      # Формируем текст экрана "Выбор банков" (Шаг 2)
            phone=phone,                                   # Подставляем номер телефона в шаблон
        )

        keyboard = build_bank_choice_keyboard(             # Строим клавиатуру выбора банков
            selected_banks=selected_banks,                 # Передаём список уже отмеченных банков для галочек
        )

        await callback.answer()                            # Закрываем "часики" на кнопке (ответ без текста)

        await edit_message_with_headline(                  # Редактируем текущие сообщение (меняем текст/картинку/клавиатуру)
            message=callback.message,                      # Сообщение, под которым была кнопка
            text=text,                                     # Новый текст шага выбора банков
            headline_type=HEADLINE_REG_2,                  # Картинка-заголовок для шага 2
            reply_markup=keyboard,                         # Новая клавиатура выбора банков
            parse_mode="Markdown",                         # Разрешаем Markdown
        )

        await state.update_data(                           # Обновляем данные FSM
            phone=phone,                                   # Сохраняем номер телефона
            last_bot_message_id=callback.message.message_id,  # Запоминаем ID отредактированного сообщения бота
        )
        return                                             # Выходим из функции, остальные ветки не выполняем

    # =========================================
    #   ВЕТКА: КНОПКА «ДАЛЕЕ» (ЗАВЕРШИТЬ)
    # =========================================
    if action == "next":                                   # Если пользователь нажал кнопку "Далее" (завершить)
        # На всякий случай: если основной банк ещё не выбран,
        # а список выбранных банков не пуст — ставим основным первый банк из списка.
        if main_bank is None and selected_banks:           # Если основного банка нет, но есть хоть один выбранный банк
            main_bank = selected_banks[0]                  # Назначаем основным первый по списку

        await add_or_update_phone(                               # Сохраняем настройки телефона и банков в БД
            user_id=user_id,                               # ID пользователя
            phone=phone,                                   # Номер телефона
            banks=selected_banks,                          # Список выбранных банков
            main_bank=main_bank,                           # Основной банк
        )

        await set_registration_progress(                         # Фиксируем в БД, что регистрация завершена
            user_id,                                       # user_id пользователя
            "completed",                                   # Шаг регистрации — "completed"
            None,                                          # current_phone нам больше не нужен — передаём None
        )

        final_text: str = BANK_CHOICE_DONE_TEXT_TEMPLATE   # Текст финального экрана после завершения регистрации

        await callback.answer()                            # Закрываем "часики" на кнопке

        await callback.message.delete()                    # Удаляем сообщение с клавиатурой выбора основного банка

        await remove_previous_bot_keyboard(                # Убираем клавиатуру у предыдущего сообщения бота (если была)
            state=state,                                   # FSM-контекст (оттуда берётся last_bot_message_id)
            bot=callback.message.bot,                      # Объект бота
            chat_id=callback.message.chat.id,              # ID текущего чата
        )

        sent_message: Message = await send_message_with_headline(
            message=callback.message,                      # Отправляем финальное сообщение в этот же чат
            text=final_text,                               # Текст "Регистрация завершена..."
            headline_type=HEADLINE_BASE,                   # Базовая картинка-заголовок
            reply_markup=ReplyKeyboardRemove(),            # Убираем все reply-клавиатуры у пользователя
            parse_mode="Markdown",                         # Разрешаем Markdown
        )

        await state.update_data(                           # Обновляем данные FSM
            last_bot_message_id=sent_message.message_id,   # Запоминаем ID финального сообщения бота
        )

        # ---- ПАУЗА И ПЕРЕХОД В ЛИЧНЫЙ КАБИНЕТ ---- #
        await asyncio.sleep(3)                             # Делаем неблокирующую паузу 3 секунды

        await send_personal_cabinet_screen(                # Показываем экран «Личный кабинет»
            message=callback.message,                      # Используем исходное сообщение callback'а для контекста чата
            state=state,                                   # Передаём FSM-контекст (для работы с last_bot_message_id)
        )

        await state.clear()                                # Полностью очищаем FSM (регистрация завершена)
        return                                             # Выходим из хэндлера

    # ======================================
    #   ВЕТКА: ВЫБОР КОНКРЕТНОГО БАНКА
    #   (main_bank:<code>)
    # ======================================
    bank_code: str = action                                # В этом случае action — это код банка (например, "sber")

    main_bank = bank_code                                  # Считаем этот банк новым выбранным основным

    await state.update_data(                               # Обновляем данные FSM
        phone=phone,                                       # Сохраняем номер телефона (на всякий случай)
        main_bank=main_bank,                               # Сохраняем код основного банка
    )

    await add_or_update_phone(                                   # Синхронизируем выбор с БД
        user_id=user_id,                                   # ID пользователя
        phone=phone,                                       # Номер телефона
        banks=selected_banks,                              # Список выбранных банков
        main_bank=main_bank,                               # Новый основной банк
    )

    new_keyboard = build_main_bank_choice_keyboard(        # Строим обновлённую клавиатуру выбора основного банка
        available_banks=selected_banks,                    # Список всех выбранных пользователем банков
        main_bank=main_bank,                               # Код банка, который сейчас основой (поставим галочку)
    )

    await callback.answer()                                # Закрываем "часики" на кнопке

    await safe_edit_reply_markup(                          # Обновляем ТОЛЬКО клавиатуру (текст сообщения не трогаем)
        callback.message,                                  # Сообщение, к которому подвешена клавиатура
        reply_markup=new_keyboard,                         # Новая клавиатура с отмеченным основным банком
    )

    await state.update_data(                               # Обновляем FSM
        last_bot_message_id=callback.message.message_id,   # Сохраняем ID сообщения с обновлённой клавиатурой
    )


# --- СЦЕНАРИЙ "НЕТ НУЖНОГО БАНКА" (callback-и "no_bank:*") --- #

@registration_router.callback_query(                                # Хэндлер callback-запросов
    RegistrationStates.no_banks,                                    # Срабатывает только в состоянии no_banks
    F.data.startswith("no_bank:"),                                  # И только если callback_data начинается с "no_bank:"
)
async def no_bank(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """
    Обработка кнопок в сценарии, когда пользователь НЕ нашёл нужный банк.

    - "no_bank:back"  — вернуться к шагу выбора банков;
    - "no_bank:start" — начать регистрацию с самого начала.
    """

    data = callback.data                                           # Например, "no_bank:back"
    _, action = data.split(":", maxsplit=1)                        # Отделяем префикс "no_bank" от действия

    user_id = callback.from_user.id                                # user_id пользователя

    fsm_data = await state.get_data()                              # Берём текущие данные FSM
    phone = await _get_phone_from_state_or_db(user_id, fsm_data)         # Пытаемся достать номер
    if not phone:
        phone = "неизвестен"                                       # На всякий случай

    if action == "back":                                           # Кнопка "Назад"
        await set_registration_progress(user_id, "banks", phone)         # В БД: шаг "banks" и этот номер

        await state.set_state(RegistrationStates.waiting_for_banks)  # FSM в состояние выбора банков

        selected_banks: list[str] = fsm_data.get(                  # Пробуем достать список банков из FSM
            "selected_banks",
            [],
        )

        text = BANK_CHOICE_TEXT_TEMPLATE.format(phone=phone)       # Формируем текст шага 2

        await callback.answer()                                    # Закрываем "часики"

        await edit_message_with_headline(                          # Меняем сообщение обратно на "Выбор банков"
            message=callback.message,
            text=text,
            headline_type=HEADLINE_REG_2,
            reply_markup=build_bank_choice_keyboard(selected_banks=selected_banks),
            parse_mode="Markdown",
        )

        await state.update_data(
            phone=phone,
            last_bot_message_id=callback.message.message_id,
        )
        return

    if action == "start":                                          # Кнопка "Начать заново"
        await set_registration_progress(user_id, "phone", None)          # В БД: шаг "phone"

        await callback.message.delete()                            # Удаляем текущее сообщение
        await state.clear()                                        # Полностью очищаем FSM

        await remove_previous_bot_keyboard(                        # Убираем клавиатуру у предыдущего сообщения бота
            state=state,
            bot=callback.message.bot,
            chat_id=callback.message.chat.id,
        )

        await state.set_state(RegistrationStates.waiting_for_phone)  # FSM в состояние ожидания телефона

        sent_message = await send_message_with_headline(           # Отправляем сообщение "Шаг 1 — отправьте номер"
            message=callback.message,
            text=REQUEST_PHONE_TEXT,
            headline_type=HEADLINE_REG_1,
            reply_markup=build_request_phone_keyboard(),
            parse_mode="Markdown",
        )

        await state.update_data(last_bot_message_id=sent_message.message_id)
        return


# --- СЦЕНАРИЙ "НЕТ НУЖНОГО БАНКА" — ПОЛЬЗОВАТЕЛЬ ПИШЕТ ТЕКСТ --- #

@registration_router.message(                                       # Хэндлер сообщений
    RegistrationStates.no_banks,                                    # Срабатывает только в состоянии no_banks
)
async def process_name(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Пользователь прислал текст в состоянии "нет нужного банка".
    Здесь можно логировать/сохранять введённое название банка и благодарить пользователя.
    """

    # Здесь при желании можно записать message.text в отдельное хранилище "запросов банков".

    await remove_previous_bot_keyboard(                             # Убираем клавиатуру у предыдущего сообщения бота
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
    )

    sent_message = await send_message_with_headline(                # Отправляем текст благодарности
        message=message,
        text=NO_BANK_THANKS_TEXT,
        headline_type=HEADLINE_BASE,
        reply_markup=build_no_bank_keyboard(),
        parse_mode="Markdown",
    )

    await state.update_data(last_bot_message_id=sent_message.message_id)
