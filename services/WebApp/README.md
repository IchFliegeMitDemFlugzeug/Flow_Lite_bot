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
