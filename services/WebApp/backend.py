"""Простой HTTP-сервер для приёма событий из Mini App.

Задача файла:
- принять POST /api/webapp от фронтенда Mini App,
- дополнить пакет данными об открывшем пользователе,
- попытаться записать пакет в БД теми же паттернами, что использует бот,
- НЕ падать, если таблица ещё не готова или БД вернула ошибку.

Сервер можно запустить локально командой:
    python services/WebApp/backend.py
и он начнёт слушать порт 8080.
"""

from __future__ import annotations  # Разрешаем отложенные аннотации типов для читаемости

import json  # json — читаем тело запросов и пишем диагностические ответы
import logging  # logging — пишем предупреждения вместо падения при ошибках БД
from http.server import BaseHTTPRequestHandler, HTTPServer  # Простой HTTP-сервер из стандартной библиотеки

from sqlalchemy import text  # text — формируем SQL в безопасном виде
from sqlalchemy.exc import SQLAlchemyError  # SQLAlchemyError — ловим любые ошибки уровня SQLAlchemy

from bot.database.storage import get_session  # get_session — тот же helper, что используют хэндлеры бота


logging.basicConfig(level=logging.INFO)  # Настраиваем базовый логгер, чтобы видеть события сервера
logger = logging.getLogger(__name__)  # Получаем логгер для этого файла


def _save_event_to_db(payload: dict) -> None:  # Пытаемся записать событие в БД
    transfer_id: str = str(payload.get("transfer_id") or "")  # Извлекаем transfer_id из полезной нагрузки
    inline_payload_json: str = json.dumps(payload.get("transfer_payload") or {}, ensure_ascii=False)  # Полный пакет из start_param
    inline_context_json: str = json.dumps(  # Собираем контекст инлайна в отдельное поле
        {
            "creator_tg_user_id": payload.get("inline_creator_tg_user_id"),  # Кто отправил сообщение
            "generated_at": payload.get("inline_generated_at"),  # Когда сформировали
            "parsed": payload.get("inline_parsed") or {},  # Распарсенные данные
            "option": payload.get("inline_option") or {},  # Реквизит
        },
        ensure_ascii=False,
    )

    opener = (payload.get("initDataUnsafe") or {}).get("user") or {}  # Достаём информацию о том, кто открыл Mini App
    opener_tg_user_id = opener.get("id")  # Telegram ID открывшего
    opener_json = json.dumps(opener, ensure_ascii=False)  # Полные данные об открывшем
    raw_init_data: str = payload.get("initData") or ""  # Сырая строка initData

    sql = text(  # Формируем SQL с UPSERT, чтобы не дублировать ключи
        """
        INSERT INTO inline_webapp_events
            (transfer_id, inline_payload_json, inline_context_json, opener_tg_user_id, opener_json, raw_init_data, created_at)
        VALUES
            (:transfer_id, :inline_payload_json, :inline_context_json, :opener_tg_user_id, :opener_json, :raw_init_data, CURRENT_TIMESTAMP)
        ON DUPLICATE KEY UPDATE
            inline_payload_json = VALUES(inline_payload_json),
            inline_context_json = VALUES(inline_context_json),
            opener_tg_user_id  = COALESCE(VALUES(opener_tg_user_id), opener_tg_user_id),
            opener_json        = COALESCE(VALUES(opener_json), opener_json),
            raw_init_data      = COALESCE(VALUES(raw_init_data), raw_init_data),
            created_at         = created_at;
        """
    )

    params = {  # Собираем параметры подстановки для SQL
        "transfer_id": transfer_id,
        "inline_payload_json": inline_payload_json,
        "inline_context_json": inline_context_json,
        "opener_tg_user_id": opener_tg_user_id,
        "opener_json": opener_json,
        "raw_init_data": raw_init_data,
    }

    try:  # Пытаемся выполнить запрос
        with get_session() as session:  # Открываем сессию SQLAlchemy
            session.execute(sql, params)  # Отправляем UPSERT в БД
        logger.info("WebApp API: событие %s записано в БД", transfer_id)  # Пишем подтверждение в лог
    except SQLAlchemyError as exc:  # Ловим ошибки БД
        logger.warning(  # Предупреждаем, но не падаем
            "WebApp API: ошибка БД при сохранении transfer_id=%s: %s",
            transfer_id,
            exc,
        )
    except Exception as exc:  # Ловим любые остальные ошибки
        logger.warning("WebApp API: неожиданная ошибка при сохранении transfer_id=%s: %s", transfer_id, exc)


class WebAppEventHandler(BaseHTTPRequestHandler):  # Класс обработчика HTTP-запросов
    def do_POST(self) -> None:  # Обрабатываем только POST-запросы
        if self.path != "/api/webapp":  # Проверяем путь
            self.send_response(404)  # Отдаём 404, если путь не совпадает
            self.end_headers()  # Закрываем ответ
            return  # Прекращаем обработку

        content_length = int(self.headers.get("content-length", 0))  # Получаем длину тела запроса
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""  # Читаем тело

        try:  # Пытаемся распарсить JSON
            payload = json.loads(raw_body.decode("utf-8") or "{}")  # Превращаем тело в dict
        except json.JSONDecodeError:  # Если парсинг не удался
            self.send_response(400)  # Отдаём 400 Bad Request
            self.end_headers()  # Закрываем ответ
            return  # Завершаем

        _save_event_to_db(payload)  # Пытаемся записать событие в БД (без падений)

        self.send_response(202)  # Возвращаем 202 Accepted — запрос принят
        self.end_headers()  # Закрываем ответ


def run_server() -> None:  # Точка запуска сервера
    server = HTTPServer(("0.0.0.0", 8080), WebAppEventHandler)  # Создаём HTTP-сервер на порту 8080
    logger.info("WebApp API: сервер запущен на http://0.0.0.0:8080/api/webapp")  # Пишем в лог адрес сервера
    try:  # Запускаем основной цикл сервера
        server.serve_forever()  # Работаем бесконечно, пока не остановят
    except KeyboardInterrupt:  # Корректно завершаем по Ctrl+C
        logger.info("WebApp API: остановка по сигналу клавиатуры")
    finally:  # Всегда закрываем сервер
        server.server_close()  # Закрываем сокет


if __name__ == "__main__":  # Запуск как самостоятельного модуля
    run_server()  # Стартуем сервер
