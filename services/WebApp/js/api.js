(function (window) { // Изолируем клиент API в IIFE
  const API_BASE_URL = 'http://localhost:8080/api/webapp'; // Локальный эндпоинт backend.py для приёма событий

  function buildPayload(context, eventType, bankId, page, extra) { // Собираем единый объект полезной нагрузки
    const safeContext = context || {}; // Гарантируем наличие объекта контекста
    const transferPayload = safeContext.transferPayload || {}; // Достаём раскодированный пакет из transfer_id
    const inlinePayload = transferPayload.payload || {}; // Внутренние данные о переводе

    const basePayload = { // Структура, общая для всех событий
      transfer_id: safeContext.startParam || (safeContext.initDataUnsafe ? safeContext.initDataUnsafe.start_param : '') || '', // Идентификатор операции/передачи
      transfer_payload: transferPayload, // Полный пакет, который пришёл через start_param
      inline_creator_tg_user_id: inlinePayload.creator_tg_user_id || null, // Кто отправил инлайн-сообщение
      inline_generated_at: inlinePayload.generated_at || '', // Когда сообщение сформировано
      inline_parsed: inlinePayload.parsed || {}, // Распарсенные данные запроса (банк, сумма)
      inline_option: inlinePayload.option || {}, // Конкретный выбранный реквизит
      event_type: eventType, // Имя события, например webapp_open
      ts: new Date().toISOString(), // Метка времени в ISO-формате
      initData: safeContext.initData || '', // Полная строка initData из Telegram
      initDataUnsafe: safeContext.initDataUnsafe || {}, // Детализированные поля initDataUnsafe
      userAgent: navigator.userAgent || '', // User-Agent браузера для диагностики
      language: navigator.language || '', // Текущая локаль браузера
      platform: navigator.platform || '', // Платформа устройства от браузера
      page: page, // На какой странице было событие (miniapp или redirect)
      bank_id: bankId || '' // Идентификатор выбранного банка, если применимо
    }; // Завершаем базовый объект
    return Object.assign({}, basePayload, extra || {}); // Объединяем базу с дополнительными полями
  }

  function safePost(jsonBody) { // Отправляем POST-запрос с защитой от ошибок
    if (!API_BASE_URL) { // Если URL-заглушка не задан
      console.debug('ApiClient: BASE_URL не указан, пропускаем отправку'); // Сообщаем в debug и выходим
      return; // Прекращаем выполнение
    }
    try { // Ловим синхронные исключения
      fetch(API_BASE_URL, { // Делаем POST на базовый URL
        method: 'POST', // Используем метод POST
        headers: { 'Content-Type': 'application/json' }, // Передаём JSON в теле
        body: JSON.stringify(jsonBody) // Сериализуем объект в строку
      })
        .then(function () { // Обрабатываем успешный ответ
          return null; // Ничего не делаем с ответом, UI не трогаем
        })
        .catch(function (error) { // Отлавливаем сетевые ошибки
          console.debug('ApiClient: отправка не удалась', error); // Пишем в debug, чтобы не мешать UX
        }); // Завершаем обработку промиса
    } catch (error) { // Ловим исключения при запуске fetch
      console.debug('ApiClient: исключение при отправке', error); // Сообщаем в debug и продолжаем работу
    }
  }

  function sendWebAppOpen(context) { // Публичная функция для события открытия Mini App
    const payload = buildPayload(context, 'webapp_open', '', 'miniapp'); // Собираем полезную нагрузку
    safePost(payload); // Отправляем событие на сервер с защитой
  }

  function sendBankClick(context, bankId) { // Публичная функция для события клика по банку
    const payload = buildPayload(context, 'bank_click', bankId, 'miniapp'); // Собираем полезную нагрузку
    safePost(payload); // Отправляем событие
  }

  function sendRedirectEvent(context, bankId, eventType, pageOverride) { // Публичная функция для событий страницы редиректа
    const payload = buildPayload(context, eventType || 'redirect_open', bankId, pageOverride || 'redirect'); // Собираем полезную нагрузку
    safePost(payload); // Отправляем событие
  }

  window.ApiClient = { // Экспортируем функции наружу
    sendWebAppOpen: sendWebAppOpen, // Экспорт события открытия Mini App
    sendBankClick: sendBankClick, // Экспорт события клика по банку
    sendRedirectEvent: sendRedirectEvent // Экспорт событий на странице редиректа
  }; // Конец экспорта
})(window); // Передаём window в IIFE
