(function (window) { // Оборачиваем код в IIFE, чтобы не засорять глобальную область имён
  const telegramApi = window.Telegram ? window.Telegram.WebApp : undefined; // Аккуратно берём объект Telegram WebApp, если он есть

  if (telegramApi) { // Если скрипт выполняется внутри Telegram Mini App
    try { // Пытаемся уведомить Telegram, что интерфейс готов
      telegramApi.ready(); // Сообщаем Telegram о готовности страницы
      telegramApi.expand(); // Просим раскрыть Mini App на всю доступную высоту
    } catch (error) { // Если готовность вызвать не удалось
      console.debug('TelegramBridge: ошибка готовности', error); // Выводим диагностическое сообщение в консоль
    }
  }

  function decodeTransferPayload(startParam) { // Аккуратно раскодируем transfer_id в объект
    if (!startParam) { // Если параметра нет
      return {}; // Возвращаем пустой объект
    }

    try { // Пытаемся раскодировать base64url → JSON
      const normalized = startParam.replace(/-/g, '+').replace(/_/g, '/'); // Возвращаем стандартные символы base64
      const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4); // Добавляем недостающие "=" для корректной декодировки
      const json = atob(padded); // Декодируем в строку JSON
      const parsed = JSON.parse(json); // Парсим строку в объект
      return parsed && typeof parsed === 'object' ? parsed : {}; // Возвращаем объект, если всё хорошо
    } catch (error) { // Если что-то пошло не так
      console.debug('TelegramBridge: не удалось раскодировать transfer_id', error); // Пишем диагностическое сообщение
      return {}; // Возвращаем пустой объект, чтобы приложение не падало
    }
  }

  function getTelegramContext() { // Функция собирает все данные окружения Telegram
    const initData = telegramApi ? telegramApi.initData || '' : ''; // Строка подписи initData из объекта Telegram
    const initDataUnsafe = telegramApi ? telegramApi.initDataUnsafe || {} : {}; // Безопасный объект initDataUnsafe с деталями
    const user = initDataUnsafe && initDataUnsafe.user ? initDataUnsafe.user : undefined; // Пользователь, если Telegram его передал
    const startParam = telegramApi && telegramApi.startParam ? telegramApi.startParam : initDataUnsafe.start_param; // Стартовый параметр или transfer_id
    const transferPayload = decodeTransferPayload(startParam); // Пытаемся извлечь полезную нагрузку из transfer_id
    const platform = telegramApi && telegramApi.platform ? telegramApi.platform : 'browser'; // Платформа, полученная из Telegram
    const version = telegramApi && telegramApi.version ? telegramApi.version : 'unknown'; // Версия Telegram WebApp
    const colorScheme = telegramApi && telegramApi.colorScheme ? telegramApi.colorScheme : 'light'; // Текущая цветовая схема Telegram
    const themeParams = telegramApi && telegramApi.themeParams ? telegramApi.themeParams : {}; // Объект с темой оформления

    return { // Возвращаем собранный объект контекста
      initData: initData, // Сырая строка initData
      initDataUnsafe: initDataUnsafe, // Объект initDataUnsafe с деталями
      user: user, // Пользовательские данные
      startParam: startParam, // Стартовый параметр/transfer_id
      transferPayload: transferPayload, // Полезная нагрузка, которая была упакована в start_param
      platform: platform, // Платформа, которую сообщает Telegram
      version: version, // Версия Telegram WebApp
      colorScheme: colorScheme, // Цветовая схема
      themeParams: themeParams // Параметры темы
    }; // Конец объекта контекста
  }

  function closeMiniApp() { // Функция аккуратно закрывает Mini App или возвращает пользователя назад
    if (telegramApi) { // Если работаем внутри Telegram
      telegramApi.close(); // Закрываем Mini App через API Telegram
      return; // Прерываем дальнейшее выполнение
    }
    window.history.back(); // В браузере без Telegram просто возвращаемся назад
  }

  window.TelegramBridge = { // Экспортируем функции в глобальный объект
    getTelegramContext: getTelegramContext, // Делаем доступной функцию получения контекста
    closeMiniApp: closeMiniApp // Делаем доступной функцию закрытия Mini App
  }; // Конец экспорта
})(window); // Передаём глобальный объект window внутрь IIFE
