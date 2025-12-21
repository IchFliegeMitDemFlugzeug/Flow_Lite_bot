"""Тесты для конструкторов deeplink-ссылок."""

import unittest  # Стандартный модуль тестов

from services.WebApp.link_builders.sber import build_sber_phone  # Проверяем сборку ссылки Сбера
from services.WebApp.link_builders.tinkoff import build_tinkoff_card  # Проверяем сборку ссылки Т-Банка
from services.WebApp.link_builders.vtb import build_vtb_generic  # Проверяем сборку ссылки ВТБ


class LinkBuilderTests(unittest.TestCase):  # Группа тестов для конструкторов
    def test_sber_phone_builder(self):  # Проверяем, что Сбер формирует корректную ссылку
        payload = {"identifier_type": "phone", "identifier_value": "+79998887766"}  # Задаём входные данные
        result = build_sber_phone(payload)  # Собираем ссылку
        self.assertIn("requisiteNumber=%2B79998887766".replace('%2B', '+'), result["deeplink"])  # Проверяем, что телефон попал в ссылку
        self.assertEqual(result["deeplink"], result["fallback_url"])  # Для Сбера deeplink и fallback совпадают
        self.assertTrue(result["link_id"].startswith("sber:"))  # Убеждаемся, что link_id содержит префикс банка

    def test_tinkoff_card_builder(self):  # Проверяем сборку ссылки для карты Т-Банка
        payload = {"identifier_type": "card", "identifier_value": "1111 2222 3333 4444"}  # Входная карта с пробелами
        result = build_tinkoff_card(payload)  # Собираем ссылки
        self.assertIn("1111222233334444", result["deeplink"])  # Номер карты должен быть без пробелов
        self.assertIn("cardNumber=1111222233334444", result["fallback_url"])  # В fallback должен быть номер карты
        self.assertTrue(result["link_id"].startswith("tbank:"))  # link_id должен содержать префикс банка

    def test_vtb_generic_builder_phone(self):  # Проверяем ВТБ при передаче телефона
        payload = {"identifier_type": "phone", "identifier_value": "+71234567890"}  # Телефон в международном формате
        result = build_vtb_generic(payload)  # Собираем ссылки
        self.assertIn("p2p/71234567890", result["deeplink"])  # Deep link должен содержать номер без плюса
        self.assertIn("phone=71234567890", result["fallback_url"])  # Fallback содержит номер
        self.assertIn("vtb:phone", result["link_id"])  # link_id отражает тип реквизита

    def test_vtb_generic_builder_card(self):  # Проверяем ВТБ при передаче карты
        payload = {"identifier_type": "card", "identifier_value": "5555-6666-7777-8888"}  # Карта с дефисами
        result = build_vtb_generic(payload)  # Собираем ссылки
        self.assertIn("transfer/card/5555666677778888", result["deeplink"])  # Deep link содержит очищенный номер
        self.assertIn("cardNumber=5555666677778888", result["fallback_url"])  # Fallback содержит номер карты
        self.assertIn("vtb:card", result["link_id"])  # link_id отражает, что это карта


if __name__ == '__main__':  # Точка входа для запуска из консоли
    unittest.main()  # Стартуем тесты
