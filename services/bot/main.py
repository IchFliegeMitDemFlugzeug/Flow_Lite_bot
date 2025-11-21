# main.py

import asyncio  # Модуль asyncio нужен для запуска асинхронного кода (event loop)

from aiogram import Bot, Dispatcher  # Bot — клиент Telegram, Dispatcher — маршрутизатор апдейтов
from aiogram.fsm.storage.memory import MemoryStorage  # Хранилище состояний в памяти процесса
from aiogram.client.default import DefaultBotProperties

from .handlers.registration import registration_router  # Импортируем наш роутер с хэндлерами регистрации

# Здесь, как правило, хранят токен бота.
# В реальном проекте лучше брать его из переменных окружения.
BOT_TOKEN = "8540412036:AAE5LPyfzrpf0RrNq6MneOAfNzjF1i4JiYI"  # TODO: замените на реальный токен


async def main() -> None:
    """
    Главная асинхронная функция приложения.
    Здесь создаём бота, диспетчер, регистрируем роутеры и запускаем polling.
    """

    # Создаём объект Bot.
    # Аргумент token — строка с токеном, полученным у BotFather.
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="Markdown"),
    )

    # Создаём хранилище состояний (FSM).
    # MemoryStorage хранит всё в оперативной памяти процесса.
    # Для продакшена обычно используют RedisStorage или БД.
    storage = MemoryStorage()

    # Создаём Dispatcher — объект, который получает апдейты и раздаёт их хэндлерам.
    dp = Dispatcher(storage=storage)

    # Регистрируем наш роутер с регистрацией в диспетчере.
    dp.include_router(registration_router)

    # Запускаем режим long polling, чтобы бот начал получать апдейты от Telegram.
    await dp.start_polling(bot)


if __name__ == "__main__":
    # Стандартная "точка захода" в программу.
    # asyncio.run запускает нашу main() как корутину в event loop.
    asyncio.run(main())
