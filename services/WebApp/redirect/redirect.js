(function (window, document) { // Изолируем код редиректа в IIFE
  document.addEventListener('DOMContentLoaded', function () { // Ждём, пока DOM станет доступным
    const statusText = document.getElementById('status-text'); // Получаем ссылку на текст статуса
    const fallbackLink = document.getElementById('fallback-link'); // Получаем ссылку для ручного перехода
    const query = new URLSearchParams(window.location.search); // Парсим параметры строки запроса
    const transferId = query.get('transfer_id') || ''; // Забираем transfer_id из адресной строки
    const bankId = query.get('bank_id') || ''; // Забираем id выбранного банка
    const linkToken = query.get('link_token') || ''; // Токен ссылки, выданный backend
    const deeplinkParam = query.get('deeplink') || ''; // Подстраховочный deeplink из query
    const fallbackParam = query.get('fallback_url') || ''; // Подстраховочный fallback из query
    const telegramContext = window.TelegramBridge.getTelegramContext(); // Собираем контекст Telegram или браузера
    telegramContext.startParam = telegramContext.startParam || transferId; // Прокидываем transfer_id из параметров, если он есть
    const userAgent = navigator.userAgent || ''; // Считываем user agent для определения платформы
    const isIOS = /iphone|ipad|ipod/i.test(userAgent); // Проверяем, что устройство — iOS
    const isSafari = isIOS && /safari/i.test(userAgent) && !/crios|fxios|edgios|opt\//i.test(userAgent); // Убеждаемся, что браузер — Safari, а не обёртка Chromium/Firefox

    window.ApiClient.sendRedirectEvent(telegramContext, bankId, 'redirect_open', 'redirect', { link_token: linkToken }); // Логируем открытие страницы редиректа

    resolveLink(linkToken, deeplinkParam, fallbackParam) // Определяем deeplink/fallback
      .then(function (bankLink) { // Когда получили итоговую ссылку
        const targetBank = { // Собираем объект для UI
          id: bankId || bankLink.bank_id || 'unknown', // Идентификатор банка
          title: 'Ваш банк', // Нейтральное название
          deeplink: bankLink.deeplink || '', // Итоговый deeplink
          fallback_url: bankLink.fallback_url || '' // Итоговый fallback
        }; // Заканчиваем объект банка
        updateUi(targetBank); // Обновляем текст на странице
        tryOpenBank(targetBank, linkToken); // Пробуем открыть приложение банка
      })
      .catch(function (error) { // Если не удалось добыть ссылку
        console.debug('Redirect: не удалось получить ссылку', error); // Пишем в debug
        const fallbackBank = { // Подготовка безопасного fallback
          id: bankId || 'unknown', // Идентификатор
          title: 'Ваш банк', // Название по умолчанию
          deeplink: '', // Нет deeplink
          fallback_url: fallbackParam || 'https://www.google.com' // Используем переданный fallback или нейтральную ссылку
        }; // Завершили объект fallback
        updateUi(fallbackBank); // Показываем fallback
        tryOpenBank(fallbackBank, linkToken); // Запускаем переход
      });

    function updateUi(bank) { // Обновляем текстовые элементы страницы
      statusText.textContent = 'Открываем банк: ' + bank.title + '…'; // Показываем название банка
      fallbackLink.href = bank.fallback_url || bank.deeplink || '#'; // Ставим ссылку на fallback
      fallbackLink.addEventListener('click', function () { // Добавляем обработчик клика по fallback-ссылке
        window.ApiClient.sendRedirectEvent(telegramContext, bank.id, 'redirect_manual_click'); // Логируем ручной клик
      });
    }

    function tryOpenBank(bank, token) { // Пытаемся открыть банковское приложение
      window.ApiClient.sendRedirectEvent(telegramContext, bank.id, 'redirect_attempt', 'redirect', { link_token: token }); // Логируем попытку открытия

      if (!bank.deeplink) { // Если deep link отсутствует
        return switchToFallback(bank); // Сразу уходим на fallback
      }

      const fallbackTimer = setTimeout(function () { // Настраиваем таймер отката
        switchToFallback(bank); // Переходим на fallback, если приложение не открылось
      }, 1100); // Ждём около секунды

      window.addEventListener('blur', function () { // Если вкладка потеряла фокус
        clearTimeout(fallbackTimer); // Сбрасываем таймер отката, значит приложение открылось
      }, { once: true }); // Слушаем только один раз

      try { // Пробуем открыть deep link
        if (isSafari) { // Для Safari используем скрытый iframe, чтобы избежать системной ошибки "не могу открыть ссылку"
          const iframe = document.createElement('iframe'); // Создаём iframe для незаметной навигации
          iframe.style.display = 'none'; // Прячем iframe, чтобы не ломать вёрстку
          iframe.src = bank.deeplink; // Указываем deep link как источник
          document.body.appendChild(iframe); // Вставляем iframe в DOM, чтобы запуск произошёл
          setTimeout(function () { // Через короткую паузу
            document.body.removeChild(iframe); // Удаляем iframe, чтобы не оставлять мусор в DOM
          }, 1500); // Держим iframe чуть дольше таймера fallback
        } else { // Во всех остальных браузерах
          window.location.href = bank.deeplink; // Перенаправляемся напрямую по deep link
        }
      } catch (error) { // Если что-то пошло не так
        console.debug('Redirect: не удалось открыть deeplink', error); // Пишем ошибку в debug
        switchToFallback(bank); // Переключаемся на веб
      }
    }

    function switchToFallback(bank) { // Переход на fallback URL
      window.ApiClient.sendRedirectEvent(telegramContext, bank.id, 'redirect_fallback'); // Логируем откат на веб
      const targetUrl = bank.fallback_url || bank.deeplink || ''; // Выбираем безопасный адрес: сначала fallback, затем deeplink
      if (targetUrl) { // Если адрес найден
        window.location.href = targetUrl; // Выполняем переход на веб-страницу или повторно в deeplink
      }
    }

    function resolveLink(token, deeplink, fallback) { // Получаем финальные ссылки для редиректа
      if (token) { // Если есть токен
        return window.ApiClient.fetchLinkByToken(token); // Запрашиваем ссылки у backend
      }
      return Promise.resolve({ deeplink: deeplink || '', fallback_url: fallback || '' }); // Используем параметры из URL
    }
  });
})(window, document); // Передаём window и document внутрь IIFE
