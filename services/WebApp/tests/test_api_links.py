"""Интеграционные тесты HTTP-эндпоинтов backend.py."""

import json  # Работаем с JSON-ответами
import threading  # Запускаем сервер в отдельном потоке
import time  # Ждём, пока сервер поднимется
import unittest  # Библиотека тестирования
from http.server import HTTPServer  # HTTP-сервер для запуска хэндлера
from urllib import request  # Для отправки HTTP-запросов

from services.WebApp import backend  # Импортируем модуль backend для использования хэндлера


class ApiLinkTests(unittest.TestCase):  # Набор тестов для API ссылок
    @classmethod
    def setUpClass(cls):  # Поднимаем тестовый сервер один раз
        cls.server = HTTPServer(('localhost', 0), backend.WebAppEventHandler)  # Создаём сервер на свободном порту
        cls.port = cls.server.server_address[1]  # Сохраняем выбранный порт
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)  # Поток для обслуживания запросов
        cls.thread.start()  # Запускаем сервер
        time.sleep(0.1)  # Даём серверу время стартовать

    @classmethod
    def tearDownClass(cls):  # Завершаем работу сервера
        cls.server.shutdown()  # Останавливаем serve_forever
        cls.server.server_close()  # Освобождаем порт
        cls.thread.join()  # Дожидаемся завершения потока

    def _get(self, path):  # Утилита отправки GET-запроса
        url = f'http://localhost:{self.port}{path}'  # Формируем полный URL
        try:  # Пытаемся выполнить запрос
            with request.urlopen(url) as response:  # Отправляем запрос и получаем ответ
                body = response.read().decode('utf-8')  # Читаем тело ответа
                return response.status, json.loads(body)  # Возвращаем статус и распарсенный JSON
        except request.HTTPError as error:  # Если сервер вернул ошибку (например, 400)
            body = error.read().decode('utf-8')  # Читаем тело ошибки
            return error.code, json.loads(body)  # Возвращаем статус ошибки и JSON

    def test_links_endpoint_returns_links(self):  # Проверяем успешный ответ /api/links
        status, data = self._get('/api/links?transfer_id=79998887766')  # Запрашиваем ссылки по телефону
        self.assertEqual(status, 200)  # Ожидаем HTTP 200
        self.assertIn('links', data)  # В ответе должен быть список links
        self.assertGreater(len(data['links']), 0)  # Список не должен быть пустым
        first = data['links'][0]  # Берём первый элемент
        self.assertIn('link_token', first)  # Должен присутствовать токен
        self.assertIn('deeplink', first)  # Должен присутствовать deeplink

    def test_links_endpoint_rejects_bad_id(self):  # Проверяем ошибку при плохом transfer_id
        status, data = self._get('/api/links?transfer_id=abc')  # Передаём некорректный идентификатор
        self.assertEqual(status, 400)  # Ожидаем статус 400
        self.assertIn('error', data)  # В ответе должно быть поле error

    def test_link_token_endpoint(self):  # Проверяем, что по токену возвращаются ссылки
        status, data = self._get('/api/links?transfer_id=79998887766')  # Получаем список ссылок
        token = data['links'][0]['link_token']  # Достаём токен первой ссылки
        status_token, payload = self._get(f'/api/links/{token}')  # Запрашиваем deeplink по токену
        self.assertEqual(status_token, 200)  # Ожидаем 200
        self.assertIn('deeplink', payload)  # В ответе должен быть deeplink
        self.assertIn('fallback_url', payload)  # В ответе должен быть fallback_url

    def test_close_only_banks_present(self):  # Проверяем, что заглушечные банки тоже приходят
        status, data = self._get('/api/links?transfer_id=79998887766')  # Запрашиваем ссылки по телефону
        self.assertEqual(status, 200)  # Ожидаем успешный ответ
        ids = {item['bank_id'] for item in data['links']}  # Собираем множество всех id банков
        self.assertIn('alfabank', ids)  # Альфа-Банк должен присутствовать как заглушка
        close_only_bank = next(item for item in data['links'] if item['bank_id'] == 'alfabank')  # Достаём объект банка
        self.assertTrue(close_only_bank.get('close_only'))  # Убеждаемся, что проставлен флаг close_only
        self.assertFalse(close_only_bank.get('link_token'))  # Токен у заглушки должен быть пустым


if __name__ == '__main__':  # Запуск тестов напрямую
    unittest.main()  # Выполняем тесты
