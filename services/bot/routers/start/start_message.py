# Импортируем Router — объект, который будет содержать обработчики для этого блока
from aiogram import Router

# Импортируем тип Message, который представляет входящее сообщение от пользователя
from aiogram.types import Message

# Импортируем фильтр CommandStart, чтобы ловить именно команду /start
from aiogram.filters import CommandStart

# Импортируем ReplyKeyboardMarkup и KeyboardButton,
# чтобы создать обычную (реплай) клавиатуру под сообщением
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


# Создаём экземпляр роутера именно для стартового сообщения.
# В каждый такой роутер мы будем складывать обработчики для одного экрана или логического блока.
router: Router = Router()


# Константа с текстом приветствия (текст, который увидит пользователь при /start)
START_MESSAGE_TEXT: str = (
    "Привет! Я бот ПОТОК Lite.\n\n"
    "Я помогу удобно отправлять запросы на перевод прямо в чатах Telegram.\n"
    "Сначала давай пройдём быструю регистрацию."
)


def build_start_keyboard() -> ReplyKeyboardMarkup:
    """
    Функция-конструктор клавиатуры для стартового сообщения.

    Здесь мы создаём Reply-клавиатуру с одной-двумя кнопками,
    которые отправят текстовые сообщения от имени пользователя.
    """

    # Создаём кнопку "Начать регистрацию"
    start_registration_button: KeyboardButton = KeyboardButton(
        text="Начать регистрацию"
    )

    # Здесь можно добавить и другие кнопки, если потребуется.
    # Например, кнопку "Помощь":
    help_button: KeyboardButton = KeyboardButton(
        text="Помощь"
    )

    # Формируем разметку клавиатуры.
    # Параметр resize_keyboard=True говорит Telegram-клиенту "поджать" клавиатуру по размеру.
    keyboard: ReplyKeyboardMarkup = ReplyKeyboardMarkup(
        keyboard=[
            # Первый ряд клавиатуры: две кнопки
            [start_registration_button, help_button],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,  # False, чтобы клавиатура не пропадала сразу после нажатия
    )

    # Возвращаем готовую клавиатуру
    return keyboard


# Регистрируем обработчик для команды /start с помощью декоратора роутера
@router.message(CommandStart())
async def handle_start_command(message: Message) -> None:
    """
    Обработчик команды /start.

    1. Отправляет пользователю приветственный текст.
    2. Прикрепляет к сообщению клавиатуру с кнопкой "Начать регистрацию".
    """

    # Получаем готовую клавиатуру, вызвав функцию build_start_keyboard
    reply_kb: ReplyKeyboardMarkup = build_start_keyboard()

    # Отправляем пользователю сообщение с текстом и клавиатурой
    await message.answer(
        text=START_MESSAGE_TEXT,
        reply_markup=reply_kb,
    )
