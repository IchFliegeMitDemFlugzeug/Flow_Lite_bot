"""Локальный HTTP-сервер для раздачи `index.html` прямо из каталога WebApp.

Запуск:
    python services/WebApp/serve_index.py --port 8000
по умолчанию слушает 8000 порт и использует текущую директорию с `index.html`.
"""

from __future__ import annotations  # Разрешаем отложенные аннотации для совместимости с будущими версиями

import argparse  # argparse — разбираем аргументы командной строки (порт и путь)
import logging  # logging — выводим понятные сообщения о запуске и запросах
from functools import partial  # partial — создаём обработчик с заранее заданной директорией
from http.server import HTTPServer, SimpleHTTPRequestHandler  # HTTPServer и SimpleHTTPRequestHandler — базовые классы для простого HTTP
from pathlib import Path  # Path — удобно работать с путями к файлам и директориям


logging.basicConfig(level=logging.INFO)  # Настраиваем базовый логгер, чтобы видеть информацию в консоли
logger = logging.getLogger(__name__)  # Получаем логгер конкретно для этого файла


class QuietSimpleHandler(SimpleHTTPRequestHandler):  # Класс обработчика запросов с минимальными логами
    def log_message(self, format: str, *args) -> None:  # Переопределяем вывод логов запросов
        logger.info("%s - - %s", self.client_address[0], format % args)  # Пишем короткое сообщение о запросе в общий логгер


def parse_args() -> argparse.Namespace:  # Функция разбора аргументов командной строки
    parser = argparse.ArgumentParser(  # Создаём парсер аргументов
        description="Запускает простой HTTP-сервер прямо из каталога WebApp",  # Пояснение для пользователя
    )
    parser.add_argument(  # Добавляем аргумент порта
        "--port",  # Имя аргумента в командной строке
        type=int,  # Тип значения — целое число
        default=8000,  # Значение по умолчанию — порт 8000
        help="Порт, на котором слушать (по умолчанию 8000)",  # Подсказка в --help
    )
    parser.add_argument(  # Добавляем аргумент пути к директории
        "--root",  # Имя аргумента
        type=Path,  # Тип — объект Path
        default=Path(__file__).resolve().parent,  # По умолчанию — текущая папка WebApp
        help="Путь до каталога с index.html (по умолчанию директория рядом со скриптом)",  # Подсказка в --help
    )
    return parser.parse_args()  # Возвращаем распарсенные аргументы


def run_server(port: int, root: Path) -> None:  # Функция запуска HTTP-сервера
    resolved_root = root.resolve()  # Получаем абсолютный путь к каталогу
    handler = partial(QuietSimpleHandler, directory=str(resolved_root))  # Создаём обработчик, закреплённый за выбранной директорией
    httpd = HTTPServer(("0.0.0.0", port), handler)  # Создаём сервер, слушающий все интерфейсы на заданном порту
    logger.info("Статический сервер запущен на http://0.0.0.0:%s из %s", port, resolved_root)  # Сообщаем адрес и директорию
    logger.info("Откройте в браузере http://localhost:%s, чтобы увидеть index.html", port)  # Даём подсказку для открытия страницы
    try:  # Запускаем сервер в бесконечном цикле до прерывания
        httpd.serve_forever()  # Начинаем обслуживать запросы
    except KeyboardInterrupt:  # Корректно обрабатываем остановку через Ctrl+C
        logger.info("Остановка сервера по сигналу клавиатуры")  # Сообщаем, что сервер останавливается
    finally:  # В любом случае закрываем сервер
        httpd.server_close()  # Освобождаем порт и ресурсы


def main() -> None:  # Основная точка входа
    args = parse_args()  # Получаем аргументы командной строки
    run_server(port=args.port, root=args.root)  # Запускаем сервер с указанными параметрами


if __name__ == "__main__":  # Проверяем, что файл запущен напрямую
    main()  # Выполняем основную функцию
