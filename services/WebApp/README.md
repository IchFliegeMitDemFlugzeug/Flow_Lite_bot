# Mini App (Telegram)

Эта директория содержит веб-приложение для Telegram Mini App. Входная точка — `services/WebApp/index.html`, который остаётся совместим с GitHub Pages (все пути относительные).

## Структура
- `index.html` — главная страница Mini App.
- `css/app.css` — стили интерфейса и анимаций.
- `js/telegram.js` — работа с Telegram WebApp API.
- `js/api.js` — отправка событий на backend (заглушка URL по умолчанию).
- `js/banks.js` — загрузка списка банков из `config/banks.json` с запасным вариантом.
- `js/app.js` — основная логика отрисовки и навигации.
- `config/banks.json` — конфигурация банков (deeplink + fallback ссылки).
- `assets/` — фон и логотипы.
- `redirect/` — страница редиректа, которая пытается открыть приложение банка и делает мягкий fallback.

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
