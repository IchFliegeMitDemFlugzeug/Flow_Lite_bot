# services/bot/tools/remove_keyboards.py

"""
Утилита для удаления инлайн-клавиатуры у предыдущего сообщения бота.

Теперь логика такая:
1) Сначала берём last_bot_message_id из FSM (state.get_data()).
2) Если в FSM ничего нет (например, после перезапуска бота) —
   пробуем взять last_bot_message_id из файловой базы по chat_id.
"""

from __future__ import annotations                         # Разрешаем "отложенные" аннотации типов

from aiogram import Bot                                    # Тип бота
from aiogram.fsm.context import FSMContext                 # FSM-контекст для доступа к данным состояния

from ..database import get_last_bot_message_id             # Функция для чтения last_bot_message_id из БД


async def remove_previous_bot_keyboard(
    state: FSMContext,                                     # Контекст FSM (в нём храним служебные данные)
    bot: Bot,                                              # Экземпляр бота для вызова edit_message_reply_markup
    chat_id: int,                                          # ID чата, где нужно убрать клавиатуру
) -> None:
    """
    Убираем инлайн-клавиатуру у предыдущего сообщения бота.

    Порядок:
    1) Пытаемся взять ID сообщения из FSM по ключу "last_bot_message_id".
    2) Если в FSM ID нет — читаем ID из файловой БД по chat_id.
    3) Если ID так и не нашли — просто выходим.
    4) Если нашли — вызываем bot.edit_message_reply_markup(..., reply_markup=None).
    """

    # --- Шаг 1. Пытаемся прочитать ID сообщения из FSM --- #

    fsm_data = await state.get_data()                      # Получаем словарь с данными FSM для этого пользователя+чата

    last_id = fsm_data.get("last_bot_message_id")          # Пытаемся взять ID последнего сообщения бота из FSM

    # --- Шаг 2. Если в FSM нет ID — пробуем прочитать его из БД --- #

    if not last_id:                                        # Если last_id пустой/None/0
        last_id = await get_last_bot_message_id(chat_id=chat_id) # Пытаемся получить ID из файловой базы

    # --- Шаг 3. Если ID по-прежнему нет — выходим --- #

    if not last_id:                                        # Если ID так и не нашли
        return                                             # Нечего редактировать, просто выходим

    # --- Шаг 4. Пытаемся убрать клавиатуру у нужного сообщения --- #

    try:
        await bot.edit_message_reply_markup(               # Редактируем сообщение бота
            chat_id=chat_id,                               # В нужном чате
            message_id=int(last_id),                       # Указываем ID сообщения
            reply_markup=None,                             # Передаём None, чтобы убрать клавиатуру целиком
        )
    except Exception:
        # Если сообщение уже удалено, нет прав, неверный ID и т.д. —
        # игнорируем ошибку, чтобы не ронять хэндлер.
        pass
