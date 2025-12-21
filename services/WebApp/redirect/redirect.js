(function (window, document) { // Изолируем код редиректа в IIFE
  document.addEventListener('DOMContentLoaded', function () { // Ждём, пока DOM станет доступным
    const statusText = document.getElementById('status-text'); // Получаем ссылку на текст статуса
    const fallbackLink = document.getElementById('fallback-link'); // Получаем ссылку для ручного перехода
    const query = new URLSearchParams(window.location.search); // Парсим параметры строки запроса
    const transferId = query.get('transfer_id') || ''; // Забираем transfer_id из адресной строки
    const bankId = query.get('bank_id') || ''; // Забираем id выбранного банка
    const telegramContext = window.TelegramBridge.getTelegramContext(); // Собираем контекст Telegram или браузера
    telegramContext.startParam = telegramContext.startParam || transferId; // Прокидываем transfer_id из параметров, если он есть

    window.ApiClient.sendRedirectEvent(telegramContext, bankId, 'redirect_open'); // Логируем открытие страницы редиректа

    window.BankLoader.loadBanks() // Загружаем список банков
      .then(function (banks) { // После получения данных
        const targetBank = banks.find(function (bank) { // Ищем банк по переданному id
          return bank.id === bankId; // Возвращаем совпадение по id
        }) || banks[0] || { // Если ничего не нашли или список пустой
          id: bankId || 'unknown', // Используем переданный id или unknown
          title: 'Ваш банк', // Название по умолчанию
          deeplink: '', // Deep link отсутствует
          fallback_url: 'https://www.google.com' // Безопасный fallback
        }; // Завершили выбор банка

        updateUi(targetBank); // Обновляем текст на странице
        tryOpenBank(targetBank); // Пробуем открыть приложение банка
      })
      .catch(function (error) { // Если не удалось получить список
        console.debug('Redirect: ошибка загрузки банков', error); // Пишем в debug
        const fallbackBank = { // Готовим запасной объект банка
          id: bankId || 'unknown', // Используем переданный id или unknown
          title: 'Ваш банк', // Отображаем нейтральное название
          deeplink: '', // Deep link отсутствует
          fallback_url: 'https://www.google.com' // Безопасный fallback на внешнюю ссылку
        }; // Конец запасного банка
        updateUi(fallbackBank); // Показываем сообщение пользователю
        tryOpenBank(fallbackBank); // Запускаем логику перехода
      });

    function updateUi(bank) { // Обновляем текстовые элементы страницы
      statusText.textContent = 'Открываем банк: ' + bank.title + '…'; // Показываем название банка
      fallbackLink.href = bank.fallback_url || bank.deeplink || '#'; // Ставим ссылку на fallback
      fallbackLink.addEventListener('click', function () { // Добавляем обработчик клика по fallback-ссылке
        window.ApiClient.sendRedirectEvent(telegramContext, bank.id, 'redirect_manual_click'); // Логируем ручной клик
      });
    }

    function tryOpenBank(bank) { // Пытаемся открыть банковское приложение
      window.ApiClient.sendRedirectEvent(telegramContext, bank.id, 'redirect_attempt'); // Логируем попытку открытия

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
        window.location.href = bank.deeplink; // Переходим по deep link
      } catch (error) { // Если что-то пошло не так
        console.debug('Redirect: не удалось открыть deeplink', error); // Пишем ошибку в debug
        switchToFallback(bank); // Переключаемся на веб
      }
    }

    function switchToFallback(bank) { // Переход на fallback URL
      window.ApiClient.sendRedirectEvent(telegramContext, bank.id, 'redirect_fallback'); // Логируем откат на веб
      if (bank.fallback_url) { // Если fallback указан
        window.location.href = bank.fallback_url; // Выполняем переход на веб-страницу
      }
    }
  });
})(window, document); // Передаём window и document внутрь IIFE
