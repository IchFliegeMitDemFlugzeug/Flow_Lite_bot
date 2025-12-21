# Mini App (Telegram)

Эта директория содержит веб-приложение для Telegram Mini App. Входная точка — `services/WebApp/index.html`, который остаётся совместим с GitHub Pages (все пути относительные).

## Структура
- `index.html` — главная страница Mini App.
- `css/app.css` — стили интерфейса и анимаций.
- `js/telegram.js` — работа с Telegram WebApp API.
- `js/api.js` — отправка событий на backend (заглушка URL по умолчанию).
- `js/banks.js` — устаревшая загрузка списка банков из `config/banks.json` (после перехода на API не используется напрямую).
- `js/app.js` — основная логика отрисовки и навигации.
- `config/banks.json` — конфигурация банков (визуальные данные и имя конструктора ссылки).
- `assets/` — фон и логотипы.
- `redirect/` — страница редиректа, которая пытается открыть приложение банка и делает мягкий fallback.

## Новый поток получения ссылок
1. Mini App получает `transfer_id` из `start_param` и запрашивает `GET /api/links?transfer_id=...`.
2. Бэкенд определяет тип реквизита (телефон/карта), выбирает конструкторы из `services/WebApp/link_builders` и собирает deeplink + fallback.
3. В ответе фронтенд получает массив `{ bank_id, title, logo, link_id, link_token, deeplink, fallback_url }` и рисует кнопки.
4. При клике Mini App открывает `redirect/index.html?transfer_id=...&bank_id=...&link_token=...` (deeplink/fallback можно пробросить в параметрах для подстраховки).
5. Страница редиректа при наличии `link_token` делает запрос `GET /api/links/{token}`, берёт deeplink/fallback и пытается открыть приложение банка с откатом на веб.

Сами конструкторы лежат в `services/WebApp/link_builders`, а общие типы — в `services/WebApp/schemas/link_payload.py`.

## Как проверить
1. Откройте `services/WebApp/index.html` локально или через GitHub Pages.
2. Кнопки банков ведут на `redirect/index.html?transfer_id=...&bank_id=...`.
3. Скрипты отправки событий работают в "тихом" режиме: при ошибке только `console.debug`.
4. Для синтаксической проверки можно выполнить `node --check services/WebApp/js/*.js services/WebApp/redirect/redirect.js`.
5. Чтобы поднять локальный сервер прямо из этой папки, выполните `python services/WebApp/serve_index.py` (при желании добавьте `--port 9000`).

## Публикация через GitHub Pages из текущей папки
1. Включите Pages в настройках репозитория: Settings → Pages → Source → **GitHub Actions**.
2. Внесите нужные изменения в `services/WebApp` и сделайте push в `main` — workflow сам соберёт артефакт из этой папки и задеплоит его на GitHub Pages (ветка `gh-pages`).
3. После первого успешного запуска в разделе Pages появится ссылка вида `https://<ваш_логин>.github.io/<имя_репозитория>/` — она открывает `index.html` прямо из `services/WebApp`.
4. Все пути в проекте относительные, поэтому страница корректно работает и в подпапке GitHub Pages.
