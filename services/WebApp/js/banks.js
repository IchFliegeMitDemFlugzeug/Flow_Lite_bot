(function (window) { // Изолируем загрузчик банков в IIFE
  function loadBanks() { // Публичная функция загрузки списка банков
    const configPath = window.location.pathname.includes('/redirect/') ? '../config/banks.json' : './config/banks.json'; // Подбираем относительный путь до конфигурации
    const requestUrl = new URL(configPath, window.location.href).toString(); // Формируем абсолютный URL до файла

    return fetch(requestUrl, { cache: 'no-cache' }) // Запрашиваем JSON с описанием банков
      .then(function (response) { // Обрабатываем ответ сервера
        if (!response.ok) { // Если HTTP-статус неуспешный
          throw new Error('Не удалось загрузить banks.json'); // Выбрасываем ошибку для перехода к fallback
        }
        return response.json(); // Парсим тело ответа как JSON
      })
      .catch(function (error) { // Если загрузка или парсинг не удались
        console.debug('BankLoader: ошибка загрузки, используем запасной список', error); // Сообщаем в debug
        return [ // Возвращаем статический список, чтобы UI не ломался
          {
            id: 'sber', // Идентификатор банка
            title: 'Сбербанк', // Название банка
            logo: 'assets/img/banks/sber.png', // Путь к логотипу
            deeplink: 'https://www.sberbank.com/sms/pbpn?requisiteNumber=79309791051', // Deep link или ссылка
            fallback_url: 'https://www.sberbank.com/sms/pbpn?requisiteNumber=79309791051' // Веб-версия
          },
          {
            id: 'alfabank', // Идентификатор банка
            title: 'Альфа-Банк', // Название
            logo: 'assets/img/banks/alfabank.png', // Логотип
            deeplink: 'alfabank://account', // Deep link
            fallback_url: 'https://web.alfabank.ru/dashboard' // Веб-страница
          },
          {
            id: 'tbank', // Идентификатор банка
            title: 'Т-Банк', // Название
            logo: 'assets/img/banks/tbank.png', // Логотип
            deeplink: 'tbank://main', // Deep link
            fallback_url: 'https://www.tbank.ru/mybank/' // Веб-страница
          },
          {
            id: 'rshb', // Идентификатор банка
            title: 'Россельхозбанк', // Название
            logo: 'assets/img/banks/rshb.png', // Логотип
            deeplink: 'rshbmbfl://', // Deep link
            fallback_url: 'https://online.rshb.ru/cas-auth/index?forceAuth=true' // Веб-страница
          },
          {
            id: 'gazprombank', // Идентификатор банка
            title: 'Газпромбанк', // Название
            logo: 'assets/img/banks/gazprombank.png', // Логотип
            deeplink: 'gpbapp://', // Deep link
            fallback_url: 'https://ib.online.gpb.ru/' // Веб-страница
          },
          {
            id: 'psb', // Идентификатор банка
            title: 'ПСБ', // Название
            logo: 'assets/img/banks/psb.png', // Логотип
            deeplink: 'psbmobile://auth/accounts', // Deep link
            fallback_url: 'https://ib.psbank.ru/settings' // Веб-страница
          },
          {
            id: 'mkb', // Идентификатор банка
            title: 'МКБ', // Название
            logo: 'assets/img/banks/mkb.png', // Логотип
            deeplink: 'mkb2://deeplink', // Deep link
            fallback_url: 'https://online.mkb.ru/login' // Веб-страница
          },
          {
            id: 'vtb', // Идентификатор банка
            title: 'ВТБ', // Название
            logo: 'assets/img/banks/vtb.png', // Логотип
            deeplink: 'vtb://vtb.ru/i/', // Deep link
            fallback_url: 'https://online.vtb.ru/login' // Веб-страница
          },
          {
            id: 'mtsbank', // Идентификатор банка
            title: 'МТС Банк', // Название
            logo: 'assets/img/banks/mtsbank.png', // Логотип
            deeplink: 'mtsmoney://', // Deep link
            fallback_url: 'https://sso.mtsbank.ru/login/mtsmoney/auth/' // Веб-страница
          },
          {
            id: 'pochtabank', // Идентификатор банка
            title: 'Почта Банк', // Название
            logo: 'assets/img/banks/pochtabank.png', // Логотип
            deeplink: 'bank100000000016://sbpay', // Deep link
            fallback_url: 'https://my.pochtabank.ru/login' // Веб-страница
          },
          {
            id: 'sovcombank', // Идентификатор банка
            title: 'Совкомбанк', // Название
            logo: 'assets/img/banks/sovcombank.png', // Логотип
            deeplink: 'ompshared://', // Deep link
            fallback_url: 'https://bk.sovcombank.ru/ru/html/login.html' // Веб-страница
          }
        ];
      });
  }

  window.BankLoader = { // Экспортируем API загрузчика банков
    loadBanks: loadBanks // Делаем доступной функцию загрузки
  }; // Завершаем экспорт
})(window); // Передаём window внутрь IIFE
