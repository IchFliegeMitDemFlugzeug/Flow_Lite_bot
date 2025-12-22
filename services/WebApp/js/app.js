(function (window, document) { // Изолируем основной код Mini App
  document.addEventListener('DOMContentLoaded', function () { // Запускаем логику после готовности DOM
    const bankListElement = document.querySelector('.bank-list'); // Находим контейнер для кнопок банков
    const backButton = document.querySelector('.back-btn'); // Находим кнопку "← Вернуться"
    const telegramContext = window.TelegramBridge.getTelegramContext(); // Собираем контекст Telegram (или браузера)

    window.ApiClient.sendWebAppOpen(telegramContext); // Отправляем событие открытия Mini App

    backButton.addEventListener('click', function () { // Навешиваем обработчик на кнопку возврата
      window.ApiClient.sendRedirectEvent(telegramContext, '', 'back_click', 'miniapp'); // Логируем клик по кнопке назад
      window.TelegramBridge.closeMiniApp(); // Корректно закрываем Mini App или возвращаемся назад
    });

    const transferId = telegramContext.startParam || (telegramContext.initDataUnsafe ? telegramContext.initDataUnsafe.start_param : ''); // Забираем transfer_id для запроса ссылок

    window.ApiClient.fetchBankLinks(transferId) // Запрашиваем готовые ссылки у backend
      .then(function (links) { // После успешной загрузки
        if (!links || !links.length) { // Если список пустой, включаем резервную загрузку
          return renderFromFallback(bankListElement, telegramContext); // Переключаемся на запасные банки
        }
        renderBanks(links, bankListElement, telegramContext); // Рисуем кнопки банков
        attachStretchEffect(bankListElement, '.btn'); // Добавляем эффект "растяжки" при прокрутке
        preloadAssetsAndAnimate(links); // Предзагружаем ассеты и запускаем анимации
        return null; // Возвращаем null, чтобы цепочка промисов считала работу завершённой
      })
      .catch(function (error) { // Если что-то пошло не так
        console.debug('App: не удалось отрисовать банки', error); // Сообщаем об ошибке в debug
        renderFromFallback(bankListElement, telegramContext); // Пытаемся отрисовать запасной список
      });
  });

  function renderBanks(banks, container, telegramContext) { // Создаём кнопки для каждого банка
    container.innerHTML = ''; // Очищаем контейнер перед вставкой
    banks.forEach(function (bank, index) { // Перебираем список банков
      const button = document.createElement('button'); // Создаём элемент кнопки
      button.className = 'btn'; // Назначаем класс стилизации
      button.setAttribute('type', 'button'); // Указываем тип кнопки
      button.dataset.bankId = bank.bank_id || bank.id || ''; // Сохраняем id банка в data-атрибуте

      const icon = document.createElement('img'); // Создаём картинку логотипа
      icon.src = bank.logo; // Устанавливаем путь к логотипу
      icon.alt = bank.title; // Добавляем альтернативный текст

      const title = document.createElement('span'); // Создаём элемент для текста
      title.className = 'btn-text'; // Назначаем класс текста
      title.textContent = bank.title; // Записываем название банка

      button.addEventListener('click', function () { // Реагируем на клик по конкретному банку
        const hasRedirect = Boolean(bank.link_token || bank.deeplink || bank.fallback_url); // Проверяем, есть ли данные для редиректа
        const shouldCloseOnly = bank.close_only || !hasRedirect; // Определяем, нужно ли просто закрыть Mini App

        window.ApiClient.sendBankClick(telegramContext, bank.bank_id || bank.id, { link_id: bank.link_id, link_token: bank.link_token }); // Отправляем событие выбора банка

        if (shouldCloseOnly) { // Если нужно просто закрыть приложение
          window.TelegramBridge.closeMiniApp(); // Закрываем Mini App без перехода
          return; // Завершаем обработчик
        }

        openRedirect(bank, telegramContext); // Перенаправляем пользователя на страницу редиректа
      });

      button.appendChild(icon); // Вставляем логотип внутрь кнопки
      button.appendChild(title); // Добавляем текст внутрь кнопки
      container.appendChild(button); // Помещаем готовую кнопку в список

      const delay = index * 0.05; // Высчитываем задержку анимации для ступенчатого появления
      button.style.animation = 'slideUp 0.6s ease-out both ' + delay + 's'; // Назначаем CSS-анимацию кнопке
    });
  }

  function renderFromFallback(container, telegramContext) { // Рисуем кнопки из запасного списка
    window.BankLoader.loadBanks() // Загружаем банки напрямую из локальной конфигурации
      .then(function (banks) { // После загрузки файла
        renderBanks(banks, container, telegramContext); // Рисуем кнопки
        attachStretchEffect(container, '.btn'); // Подключаем эффект растяжки
        preloadAssetsAndAnimate(banks); // Предзагружаем картинки и запускаем анимацию
      })
      .catch(function (error) { // Если даже fallback не сработал
        console.debug('App: fallback списка банков не доступен', error); // Сообщаем об ошибке в debug
      });
  }

  function openRedirect(bank, telegramContext) { // Формируем ссылку на страницу редиректа и открываем её
    const transferId = telegramContext.startParam || (telegramContext.initDataUnsafe ? telegramContext.initDataUnsafe.start_param : ''); // Достаём transfer_id
    const redirectUrl = new URL('./redirect/index.html', window.location.href); // Создаём URL страницы редиректа
    redirectUrl.searchParams.set('transfer_id', transferId || ''); // Пробрасываем transfer_id как параметр
    redirectUrl.searchParams.set('bank_id', bank.bank_id || bank.id || ''); // Передаём выбранный банк
    if (bank.link_token) { // Если backend выдал токен
      redirectUrl.searchParams.set('link_token', bank.link_token); // Добавляем токен ссылки
    }
    if (bank.deeplink) { // Если есть готовый deeplink
      redirectUrl.searchParams.set('deeplink', bank.deeplink); // Подстраховываем deeplink в URL
    }
    if (bank.fallback_url) { // Если указан fallback
      redirectUrl.searchParams.set('fallback_url', bank.fallback_url); // Добавляем fallback
    }

    const fullUrl = redirectUrl.toString(); // Получаем итоговую строку URL

    window.location.href = fullUrl; // В любом окружении переходим на страницу редиректа внутри WebView
  }

  function preloadAssetsAndAnimate(banks) { // Предзагружаем фон и логотипы, затем показываем кнопки
    const computedBg = window.getComputedStyle(document.body).backgroundImage; // Читаем CSS-фон страницы
    const bgUrl = computedBg && computedBg.startsWith('url(') ? computedBg.slice(5, -2) : ''; // Аккуратно извлекаем URL из строки
    const logoUrls = banks.map(function (bank) { // Собираем пути к логотипам
      const absoluteUrl = new URL(bank.logo, window.location.href); // Формируем абсолютный URL
      return absoluteUrl.toString(); // Возвращаем строковое представление URL
    });
    const assets = []; // Подготавливаем массив для всех путей
    if (bgUrl) { // Если фон найден
      assets.push(bgUrl); // Добавляем фон в список предзагрузки
    }
    assets.push.apply(assets, logoUrls); // Добавляем пути логотипов

    preloadImages(assets, function () { // Запускаем предзагрузку и передаём колбэк
      document.querySelectorAll('.btn').forEach(function (button) { // После загрузки проходимся по всем кнопкам
        const currentAnimation = button.style.animation; // Сохраняем назначенную анимацию
        button.style.animation = currentAnimation; // Переприсваиваем, чтобы убедиться в применении
      });
    });
  }

  function preloadImages(urls, onDone) { // Простая функция предзагрузки изображений
    if (!urls.length) { // Если массив пустой
      onDone(); // Сразу вызываем колбэк
      return; // Завершаем работу функции
    }
    let loaded = 0; // Счётчик обработанных изображений
    urls.forEach(function (url) { // Проходим по каждому пути
      const img = new Image(); // Создаём объект Image для загрузки
      img.onload = handleComplete; // При успешной загрузке увеличиваем счётчик
      img.onerror = handleComplete; // При ошибке тоже учитываем изображение
      img.src = url; // Стартуем загрузку, записав src
    });

    function handleComplete() { // Унифицированный обработчик завершения
      loaded += 1; // Увеличиваем счётчик
      if (loaded === urls.length) { // Когда загружены все изображения
        onDone(); // Вызываем переданный колбэк
      }
    }
  }

  function attachStretchEffect(listElement, buttonSelector) { // Добавляем "растяжку" списка при упоре
    let startY = 0; // Точка начала касания
    let touching = false; // Флаг активного касания

    listElement.addEventListener('touchstart', function (event) { // Фиксируем начало касания
      touching = true; // Включаем режим отслеживания
      startY = event.touches[0].clientY; // Запоминаем исходную координату Y
    });

    listElement.addEventListener('touchmove', function (event) { // Реагируем на движение пальца
      if (!touching) { // Если касание не активно
        return; // Выходим из обработчика
      }
      const delta = event.touches[0].clientY - startY; // Вычисляем смещение относительно старта
      const scale = 1 + Math.min(Math.abs(delta) / 200, 0.1); // Считаем коэффициент растяжки
      const atTop = listElement.scrollTop === 0 && delta > 0; // Проверяем упор в начало списка
      const atBottom = listElement.scrollTop + listElement.clientHeight >= listElement.scrollHeight && delta < 0; // Проверяем упор в конец списка
      if (atTop || atBottom) { // Если действительно упёрлись
        document.querySelectorAll(buttonSelector).forEach(function (button) { // Применяем стиль ко всем кнопкам
          button.style.transform = 'scaleY(' + scale + ')'; // Тянем кнопку по оси Y
        });
      }
    });

    listElement.addEventListener('touchend', function () { // Когда палец оторвали от экрана
      touching = false; // Выключаем режим отслеживания
      document.querySelectorAll(buttonSelector).forEach(function (button) { // Возвращаем кнопки к норме
        button.style.transition = 'transform 0.3s'; // Добавляем плавность
        button.style.transform = 'scaleY(1)'; // Сбрасываем растяжку
        setTimeout(function () { // После завершения анимации
          button.style.transition = ''; // Убираем transition, чтобы не мешал в дальнейшем
        }, 300); // Время совпадает с длительностью transition
      });
    });
  }
})(window, document); // Передаём объекты window и document внутрь IIFE
