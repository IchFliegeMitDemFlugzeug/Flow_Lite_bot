# services/bot/tools/tg_keyboards.py

from aiogram import Bot                      # Импортируем Bot, чтобы типизировать аргумент bot
from aiogram.fsm.context import FSMContext   # Импортируем FSMContext, чтобы читать данные FSM (в т.ч. last_bot_message_id)


async def remove_previous_bot_keyboard(
    state: FSMContext,                      # Контекст FSM — в нём храним служебные данные, в том числе ID последнего сообщения бота
    bot: Bot,                               # Экземпляр бота, через который будем вызывать edit_message_reply_markup
    chat_id: int,                           # ID чата, в котором нужно найти и отредактировать сообщение
) -> None:
    """
    Убираем клавиатуру у предыдущего сообщения бота, если в FSM сохранён его ID
    под ключом "last_bot_message_id".

    Логика:
    - читаем из FSM данные для текущего пользователя/чата;
    - берём из них last_bot_message_id;
    - если ID есть — вызываем bot.edit_message_reply_markup(..., reply_markup=None);
    - любые ошибки (сообщение удалено, недоступно и т.п.) тихо игнорируем.
    """
    data = await state.get_data()                 # Асинхронно получаем словарь всех данных FSM для этого пользователя
    last_id = data.get("last_bot_message_id")     # Пытаемся достать ID последнего сообщения бота из словаря FSM

    if not last_id:                               # Если ID нет (None или ключ отсутствует)
        return                                    # Нечего редактировать, сразу выходим

    try:                                          # Пытаемся выполнить редактирование клавиатуры у старого сообщения
        await bot.edit_message_reply_markup(
            chat_id=chat_id,                      # Указываем чат, в котором находится сообщение
            message_id=last_id,                   # Указываем ID сообщения, у которого нужно убрать клавиатуру
            reply_markup=None,                    # Передаём None, чтобы Telegram полностью убрал инлайн-клавиатуру
        )
    except Exception:
        # Если сообщение уже удалено, нет прав на редактирование или любая другая проблема —
        # просто игнорируем, чтобы не ронять хэндлер и не засорять логи служебными ошибками.
        pass
