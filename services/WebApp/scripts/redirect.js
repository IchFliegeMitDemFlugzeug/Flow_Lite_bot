(function () { // Изолируем код редиректа
  const currentUrl = new URL(window.location.href); // Создаём объект URL для чтения параметров
  const deepLink = currentUrl.searchParams.get('dl') || ''; // Забираем deep link из параметров
  const webUrl = currentUrl.searchParams.get('wl') || ''; // Забираем веб-URL для отката
  const platform = currentUrl.searchParams.get('p') || 'unknown'; // Забираем платформу

  try { // Пробуем отправить событие открытия страницы
    if (window.App && window.App.sendEvent) { // Проверяем, доступна ли функция отправки
      window.App.sendEvent('redirect_page_open', { platform: platform, dl: deepLink, wl: webUrl }); // Шлём событие
    } // Конец проверки наличия App
  } catch (error) { // Ловим ошибки
    console.debug('Redirect: не удалось отправить событие открытия', error); // Логируем в debug
  } // Конец try/catch

  function fallbackToWeb() { // Функция отката на веб
    try { // Пытаемся отправить событие отката
      if (window.App && window.App.sendEvent) { // Проверяем наличие sendEvent
        window.App.sendEvent('redirect_fallback', { platform: platform }); // Шлём событие отката
      } // Конец проверки
    } catch (error) { // Ловим ошибки
      console.debug('Redirect: ошибка отправки события отката', error); // Сообщаем в debug
    } // Конец блока try/catch
    if (webUrl) { // Если есть веб-URL
      window.location.href = webUrl; // Переходим на веб
    } // Конец проверки webUrl
  } // Конец fallbackToWeb

  const fallbackTimer = setTimeout(function () { // Таймер, который запустит откат
    if (!document.hidden) { // Если вкладка остаётся активной
      fallbackToWeb(); // Выполняем откат
    } // Конец условия
  }, 1200); // Ждём 1.2 секунды

  document.addEventListener( // Слушаем смену видимости
    'visibilitychange', // Событие смены видимости
    function () { // Обработчик
      if (document.hidden) { // Если вкладка ушла в фон
        clearTimeout(fallbackTimer); // Отключаем таймер отката
      } // Конец условия
    }, // Конец обработчика
    { once: true } // Один раз и хватит
  ); // Конец addEventListener

  if (deepLink) { // Если deep link передан
    window.location.href = deepLink; // Пробуем открыть приложение
  } else { // Если deep link пустой
    fallbackToWeb(); // Сразу идём на веб
  } // Конец проверки deepLink
})(); // Завершаем IIFE
