# services/bot/tools/safe_edit.py

from aiogram.types import Message          # Импортируем тип Message, чтобы типизировать аргумент message
from aiogram.exceptions import TelegramBadRequest  # Импортируем исключение, которое aiogram кидает при ошибке Telegram Bad Request


async def safe_edit_text(
    message: Message,                      # Сообщение Telegram, которое мы хотим отредактировать
    **kwargs,                              # Именованные аргументы, которые будут переданы дальше в message.edit_text()
) -> None:
    """
    Безопасное редактирование ТЕКСТА сообщения: игнорируем только кейс,
    когда Telegram возвращает ошибку "message is not modified".
    Все остальные ошибки пробрасываем дальше.
    """
    try:                                    # Открываем блок try, чтобы перехватить возможные ошибки TelegramBadRequest
        await message.edit_text(**kwargs)   # Пытаемся отредактировать текст (и при необходимости клавиатуру) сообщения
    except TelegramBadRequest as e:         # Ловим исключение TelegramBadRequest от aiogram
        # Если Telegram вернул именно "Bad Request: message is not modified", значит
        # новый текст и разметка полностью совпадают с текущими, и редактировать нечего.
        if "message is not modified" in e.message:  # Проверяем текст ошибки
            return                          # Тихо выходим, не засоряя логи
        raise                               # Если ошибка другая — пробрасываем её дальше, чтобы не скрывать реальные проблемы


async def safe_edit_reply_markup(
    message: Message,                      # Сообщение Telegram, у которого хотим изменить ТОЛЬКО клавиатуру
    **kwargs,                              # Именованные аргументы (обычно reply_markup=...), которые передадим в edit_reply_markup()
) -> None:
    """
    Безопасное редактирование ТОЛЬКО КЛАВИАТУРЫ у сообщения:
    игнорируем ошибку "message is not modified", остальные — пробрасываем.
    """
    try:                                    # Блок try для перехвата возможных ошибок от Telegram
        await message.edit_reply_markup(**kwargs)  # Пытаемся изменить только инлайн-клавиатуру у сообщения
    except TelegramBadRequest as e:         # Ловим исключение TelegramBadRequest
        # Аналогично safe_edit_text игнорируем ситуацию, когда Telegram говорит,
        # что сообщение не изменилось (markup такой же, как был).
        if "message is not modified" in e.message:  # Проверяем текст ошибки на "message is not modified"
            return                          # Ничего не делаем, выходим из функции
        raise                               # Любая другая ошибка — пробрасываем дальше
