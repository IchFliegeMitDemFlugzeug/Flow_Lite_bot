from __future__ import annotations                       # Разрешаем "отложенные" аннотации типов (удобно для type hints)

from pathlib import Path                                 # Импортируем Path для удобной и кроссплатформенной работы с путями

from aiogram.types import (                             # Импортируем нужные Telegram-типы из aiogram
    Message,                                            # Тип объекта сообщения Telegram
    FSInputFile,                                        # Тип для локального файла (картинка на диске)
    InputMediaPhoto,                                    # Тип media-объекта для редактирования фото + подписи
)

from ..database import set_last_bot_message_id          # Функция из нашей "БД": сохраняет ID последнего сообщения бота


# --- Константы типов заголовков --- #

HEADLINE_REG_1: str = "reg_1"                          # Тип заголовка для шага регистрации №1 (ввод телефона)
HEADLINE_REG_2: str = "reg_2"                          # Тип заголовка для шага регистрации №2 (выбор банков)
HEADLINE_REG_3: str = "reg_3"                          # Тип заголовка для шага регистрации №3 (выбор основного банка)
HEADLINE_BASE: str = "base"                            # Базовый тип заголовка для остальных экранов (личный кабинет и т.п.)


# --- Пути к файлам картинок --- #

# Папка, в которой лежит этот файл add_headline.py.
# В ней же лежат наши картинки: base_headline.jpg, reg_1.jpg, reg_2.jpg, reg_3.jpg.
HEADLINES_DIR: Path = Path(__file__).resolve().parent   # Например: .../services/bot/headlines

# Карта "тип заголовка" -> Path к нужному jpg-файлу.
# Имена файлов взяты из дерева проекта: base_headline.jpg, reg_1.jpg, reg_2.jpg, reg_3.jpg.
HEADLINE_FILES: dict[str, Path] = {
    HEADLINE_REG_1: HEADLINES_DIR / "reg_1.jpg",        # Картинка для шага регистрации №1
    HEADLINE_REG_2: HEADLINES_DIR / "reg_2.jpg",        # Картинка для шага регистрации №2
    HEADLINE_REG_3: HEADLINES_DIR / "reg_3.jpg",        # Картинка для шага регистрации №3
    HEADLINE_BASE: HEADLINES_DIR / "base_headline.jpg", # Базовая картинка для других экранов
}


def _get_fs_input_file(headline_type: str) -> FSInputFile:
    """
    Вспомогательная функция: по типу заголовка вернуть FSInputFile с нужной картинкой.

    Если тип неизвестен (опечатка или новое значение), используем базовую картинку HEADLINE_BASE.
    """

    # Берём из словаря путь к файлу по ключу headline_type.
    # Если такой ключ не найден — подставляем путь для HEADLINE_BASE.
    path: Path = HEADLINE_FILES.get(headline_type, HEADLINE_FILES[HEADLINE_BASE])

    # Оборачиваем путь в FSInputFile — это специальный тип aiogram для отправки локальных файлов
    return FSInputFile(path)


async def send_message_with_headline(
    message: Message,                                      # Исходное сообщение пользователя (на него "отвечаем")
    text: str,                                             # Текст caption (подпись под картинкой)
    headline_type: str = HEADLINE_BASE,                    # Тип заголовка (по умолчанию базовый)
    reply_markup=None,                                     # Инлайн-клавиатура (или None)
    parse_mode: str = "Markdown",                          # Режим разметки: используем Markdown (как в main.py)
) -> Message:
    """
    Отправить НОВОЕ сообщение с картинкой-заголовком и подписью.

    Возвращает объект Message отправленного сообщения.
    """

    # Получаем объект FSInputFile с нужной картинкой по типу заголовка
    photo: FSInputFile = _get_fs_input_file(headline_type)

    # Отправляем фото как "ответ" на исходное сообщение пользователя
    sent_message: Message = await message.answer_photo(
        photo=photo,                                       # Файл-картинка
        caption=text,                                      # Подпись под картинкой
        reply_markup=reply_markup,                         # Инлайн-клавиатура, если есть
        parse_mode=parse_mode,                             # Режим разбора разметки (Markdown)
    )

    # После успешной отправки сохраняем ID этого сообщения как "последнее сообщение бота" для данного чата.
    # Это нужно, чтобы позже можно было удалить у него клавиатуру, даже после перезапуска бота.
    if message.chat:                                       # Проверяем, что у исходного message есть chat (должен быть всегда)
        set_last_bot_message_id(
            chat_id=message.chat.id,                       # ID чата
            message_id=sent_message.message_id,            # ID только что отправленного сообщения бота
        )

    # Возвращаем отправленное сообщение наружу (чтобы хэндлер мог сохранить его ID в FSM и т.п.)
    return sent_message


async def edit_message_with_headline(
    message: Message,                                      # Существующее сообщение бота, которое нужно отредактировать
    text: str,                                             # Новый текст caption под картинкой
    headline_type: str = HEADLINE_BASE,                    # Тип заголовка (можно сменить картинку при редактировании)
    reply_markup=None,                                     # Новая клавиатура (или None)
    parse_mode: str = "Markdown",                          # Режим разметки (Markdown)
) -> Message:
    """
    Отредактировать УЖЕ СУЩЕСТВУЮЩЕЕ сообщение бота с картинкой-заголовком.

    Меняем:
    - картинку (если headline_type поменялся),
    - текст caption,
    - инлайн-клавиатуру.
    """

    # Получаем нужную картинку по типу заголовка
    photo: FSInputFile = _get_fs_input_file(headline_type)

    # Формируем объект InputMediaPhoto для edit_media:
    # в нём задаём и сам файл, и новый caption, и режим разметки.
    media: InputMediaPhoto = InputMediaPhoto(
        media=photo,                                       # Сам файл-картинка
        caption=text,                                      # Новый текст под картинкой
        parse_mode=parse_mode,                             # Режим разбора разметки (Markdown)
    )

    # Вызываем edit_media на исходном сообщении бота:
    # - меняем media (картинку + caption)
    # - при необходимости меняем клавиатуру (reply_markup)
    edited_message: Message = await message.edit_media(
        media=media,                                       # Новый media-объект
        reply_markup=reply_markup,                         # Новая клавиатура (или None)
    )

    # Обновляем запись о "последнем сообщении бота" для данного чата.
    # ID сообщения, по сути, тот же, но полезно синхронизировать.
    if message.chat:
        set_last_bot_message_id(
            chat_id=message.chat.id,                      # ID чата
            message_id=edited_message.message_id,         # ID (тот же, но фиксируем как актуальный)
        )

    # Возвращаем отредактированное сообщение наружу
    return edited_message
