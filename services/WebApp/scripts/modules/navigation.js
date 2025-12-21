(function (app) { // Изолируем модуль навигации
  const namespace = app; // Сохраняем пространство имён

  namespace.closePage = function closePage() { // Функция закрытия страницы
    if (window.Telegram && Telegram.WebApp) { // Проверяем, что это Telegram Mini App
      Telegram.WebApp.close(); // Закрываем приложение через API Telegram
      return; // Прерываем выполнение
    } // Конец проверки Telegram
    window.history.back(); // В обычном браузере просто возвращаемся назад
  }; // Конец closePage

  function buildRedirectUrl(deepLink, webUrl, platform) { // Сборка URL страницы редиректа
    const redirectUrl = new URL(namespace.REDIRECT_PAGE, window.location.href); // Создаём объект URL на основе относительного пути
    redirectUrl.searchParams.set('dl', deepLink); // Кладём deep link в параметр dl
    redirectUrl.searchParams.set('wl', webUrl); // Кладём веб-URL в параметр wl
    redirectUrl.searchParams.set('p', platform); // Добавляем платформу
    return redirectUrl.toString(); // Возвращаем готовую строку
  } // Конец buildRedirectUrl

  namespace.tryOpenDeepLink = function tryOpenDeepLink(deepLink, webUrl) { // Попытка открытия deep link в обычном браузере
    const start = Date.now(); // Фиксируем время старта
    let fallbackTimer = null; // Переменная под таймер отката

    function fallbackToWeb() { // Функция перехода на веб
      window.location.href = webUrl; // Перенаправляем на веб-версию
    } // Конец fallbackToWeb

    fallbackTimer = setTimeout(function () { // Запускаем таймер проверки
      if (!document.hidden && Date.now() - start > 1100) { // Если вкладка активна и прошло достаточно времени
        fallbackToWeb(); // Выполняем откат
      } // Конец условия
    }, 1200); // Задаём паузу в 1.2 секунды

    document.addEventListener( // Слушаем смену видимости вкладки
      'visibilitychange', // Событие смены видимости
      function () { // Обработчик события
        if (document.hidden && fallbackTimer) { // Если вкладка ушла в фон и таймер активен
          clearTimeout(fallbackTimer); // Сбрасываем таймер
          fallbackTimer = null; // Обнуляем ссылку на таймер
        } // Конец условия
      }, // Конец обработчика
      { once: true } // Слушатель одноразовый
    ); // Конец addEventListener

    window.location.href = deepLink; // Пробуем открыть приложение банка
  }; // Конец tryOpenDeepLink

  namespace.openLink = function openLink(deepLink, webUrl, bankName) { // Функция обработки клика по банку
    const isTelegram = !!(window.Telegram && Telegram.WebApp); // Определяем, внутри ли Telegram
    const userAgent = navigator.userAgent || ''; // Берём userAgent
    const isAndroid = /Android/i.test(userAgent); // Проверяем Android
    const isIOS = /iPhone|iPad|iPod/i.test(userAgent); // Проверяем iOS
    const platform = isAndroid ? 'android' : isIOS ? 'ios' : 'other'; // Собираем строку платформы

    namespace.sendEvent('bank_click', { bank: bankName, platform: platform }); // Отправляем событие выбора банка

    if (isTelegram) { // Ветка для Telegram Mini App
      const redirectUrl = buildRedirectUrl(deepLink, webUrl, platform); // Строим ссылку на страницу редиректа
      Telegram.WebApp.openLink(redirectUrl, { try_instant_view: false }); // Открываем ссылку через API Telegram
      setTimeout(function () { // Ставим таймер закрытия мини-приложения
        Telegram.WebApp.close(); // Закрываем Mini App
      }, 300); // 300 мс достаточно для старта перехода
      return; // Выходим, чтобы не выполнять нижнюю ветку
    } // Конец ветки Telegram

    namespace.tryOpenDeepLink(deepLink, webUrl); // В обычном браузере пробуем открыть deep link
  }; // Конец openLink
})(window.App = window.App || {}); // Экспортируем модуль
