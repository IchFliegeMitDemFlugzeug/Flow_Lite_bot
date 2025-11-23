from pathlib import Path  # Импортируем Path для удобной и кроссплатформенной работы с путями к файлам

from aiogram.types import (  # Импортируем необходимые типы из aiogram
    Message,                 # Тип сообщения Telegram, чтобы типизировать аргументы функций
    FSInputFile,             # Тип для передачи файла с диска (локальная картинка)
    InputMediaPhoto,         # Тип для редактирования media-содержимого сообщения (фото + подпись)
)


# --- Константы типов заголовков (чтобы в хэндлерах не работать с "голыми" строками) --- #

HEADLINE_REG_1 = "reg_1"     # Картинка-заголовок для шага регистрации №1 (запрос телефона)
HEADLINE_REG_2 = "reg_2"     # Картинка-заголовок для шага регистрации №2 (выбор банков)
HEADLINE_REG_3 = "reg_3"     # Картинка-заголовок для шага регистрации №3 (выбор основного банка)
HEADLINE_BASE = "base"       # Базовая картинка-заголовок для всех остальных сообщений


# --- Подготовка путей к файлам картинок --- #

HEADLINES_DIR: Path = Path(__file__).resolve().parent  # Определяем директорию, где лежит этот файл и картинки

HEADLINES_FILES: dict[str, Path] = {                   # Словарь: "тип заголовка" -> путь к файлу
    HEADLINE_REG_1: HEADLINES_DIR / "reg_1.jpg",       # Путь к файлу reg_1.jpg
    HEADLINE_REG_2: HEADLINES_DIR / "reg_2.jpg",       # Путь к файлу reg_2.jpg
    HEADLINE_REG_3: HEADLINES_DIR / "reg_3.jpg",       # Путь к файлу reg_3.jpg
    HEADLINE_BASE: HEADLINES_DIR / "base_headline.jpg" # Путь к файлу base_headline.jpg
}


def _get_fs_input_file(headline_type: str) -> FSInputFile:
    """
    Внутренняя вспомогательная функция:
    по строковому типу заголовка возвращает объект FSInputFile с нужной картинкой.

    :param headline_type: Один из ключей:
                          "reg_1", "reg_2", "reg_3", "base".
    :return: FSInputFile с путём к соответствующему JPG-файлу.
    """
    path: Path = HEADLINES_FILES.get(                  # Получаем путь к файлу по ключу
        headline_type,                                 # Ключ заголовка, который запросили
        HEADLINES_FILES[HEADLINE_BASE],                # Если не нашли — берём базовый заголовок
    )
    return FSInputFile(path)                           # Оборачиваем путь в FSInputFile (aiogram сам откроет файл при отправке)


async def send_message_with_headline(
    message: Message,                                  # Сообщение, от которого делаем "ответ" (answer)
    text: str,                                         # Текст, который пойдёт в caption под картинкой
    headline_type: str,                                # Тип заголовка: "reg_1" / "reg_2" / "reg_3" / "base"
    reply_markup=None,                                 # Любая клавиатура (reply или inline), если нужна
    parse_mode: str | None = "Markdown",                     # Режим парсинга текста: "Markdown", "HTML" или None
):
    """
    Отправляет НОВОЕ сообщение с картинкой-заголовком (photo + caption).

    Возвращает объект отправленного сообщения, чтобы его ID можно было
    сохранить в FSM как last_bot_message_id.
    """
    photo: FSInputFile = _get_fs_input_file(headline_type)  # Получаем нужную картинку по типу заголовка

    sent_message: Message = await message.answer_photo(     # Отправляем фото как "ответ" на текущее сообщение
        photo=photo,                                        # Картинка-заголовок
        caption=text,                                       # Текст под картинкой (caption)
        reply_markup=reply_markup,                          # Клавиатура, если есть
        parse_mode=parse_mode,                              # Режим парсинга разметки
    )

    return sent_message                                     # Возвращаем отправленное сообщение наружу


async def edit_message_with_headline(
    message: Message,                                       # Существующее сообщение, которое нужно отредактировать
    text: str,                                              # Новый текст (caption) под картинкой
    headline_type: str,                                     # Новый тип заголовка: "reg_1" / "reg_2" / "reg_3" / "base"
    reply_markup=None,                                      # Новая клавиатура, если нужно её заменить
    parse_mode: str | None = None,                          # Режим парсинга текста: "Markdown", "HTML" или None
):
    """
    Редактирует УЖЕ ОТПРАВЛЕННОЕ сообщение с фото:
    одновременно меняет картинку (media) и подпись (caption), а также клавиатуру.

    Используется, когда нужно, например:
    - с шага выбора банков (reg_2) перейти на шаг выбора главного банка (reg_3);
    - или из сценария "нет банка" вернуть пользователя на шаг выбора банков и т.п.
    """

    photo: FSInputFile = _get_fs_input_file(headline_type)  # Получаем нужную картинку по типу заголовка

    media: InputMediaPhoto = InputMediaPhoto(               # Формируем новый объект media для редактирования сообщения
        media=photo,                                        # Указываем сам файл с картинкой
        caption=text,                                       # Новый текст под картинкой
        parse_mode=parse_mode,                              # Режим парсинга разметки для caption
    )

    edited_message: Message = await message.edit_media(     # Вызываем edit_media у самого сообщения
        media=media,                                        # Передаём новый media-объект (фото + caption)
        reply_markup=reply_markup,                          # При необходимости меняем клавиатуру
    )

    return edited_message                                   # Возвращаем отредактированное сообщение наружу
