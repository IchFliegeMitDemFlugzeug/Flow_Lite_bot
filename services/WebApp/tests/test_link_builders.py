"""Тесты для конструкторов deeplink-ссылок."""

import unittest  # Стандартный модуль тестов

from services.WebApp.link_builders.sber import build_sber_universal  # Проверяем сборку ссылки Сбера
from services.WebApp.link_builders.tinkoff import build_tinkoff_phone  # Проверяем сборку ссылки Т-Банка
from services.WebApp.link_builders.vtb import build_vtb_universal  # Проверяем сборку ссылки ВТБ


class LinkBuilderTests(unittest.TestCase):  # Группа тестов для конструкторов
    def test_sber_builder(self):  # Проверяем, что Сбер формирует корректную ссылку
        payload = {"identifier_type": "phone", "identifier_value": "+79998887766"}  # Задаём входные данные
        result = build_sber_universal(payload)  # Собираем ссылку
        self.assertIn("requisiteNumber=79998887766", result["deeplink"])  # Проверяем, что телефон попал в ссылку без плюса
        self.assertEqual(result["deeplink"], result["fallback_url"])  # Для Сбера deeplink и fallback совпадают
        self.assertTrue(result["link_id"].startswith("sber:"))  # Убеждаемся, что link_id содержит префикс банка

    def test_tinkoff_phone_builder(self):  # Проверяем сборку ссылки для телефона Т-Банка
        payload = {"identifier_type": "phone", "identifier_value": "+79998887766"}  # Телефон с плюсом
        result = build_tinkoff_phone(payload)  # Собираем ссылки
        self.assertIn("%2B79998887766", result["deeplink"])  # Номер телефона должен попасть в параметр predefined
        self.assertEqual(result["deeplink"], result["fallback_url"])  # Deeplink и fallback совпадают
        self.assertIn("tbank:phone", result["link_id"])  # link_id должен содержать тип и банк

    def test_vtb_universal_builder_phone(self):  # Проверяем ВТБ при передаче телефона
        payload = {"identifier_type": "phone", "identifier_value": "+71234567890"}  # Телефон в международном формате
        result = build_vtb_universal(payload)  # Собираем ссылки
        self.assertIn("/71234567890", result["deeplink"])  # Deep link должен содержать номер без плюса
        self.assertIn("vtb:phone", result["link_id"])  # link_id отражает тип реквизита
        self.assertTrue(result["fallback_url"].startswith("https://online.vtb.ru/transfers/"))  # Fallback не пустой и ведёт на сайт ВТБ

    def test_vtb_universal_builder_card(self):  # Проверяем ВТБ при передаче карты
        payload = {"identifier_type": "card", "identifier_value": "5555-6666-7777-8888"}  # Карта с дефисами
        result = build_vtb_universal(payload)  # Собираем ссылки
        self.assertIn("/5555666677778888", result["deeplink"])  # Deep link содержит очищенный номер
        self.assertIn("vtb:card", result["link_id"])  # link_id отражает, что это карта


if __name__ == '__main__':  # Точка входа для запуска из консоли
    unittest.main()  # Стартуем тесты
