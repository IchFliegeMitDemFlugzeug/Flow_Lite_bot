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
            deeplink: 'https://www.sberbank.com/sms/pbpn?requisiteNumber=79309791051', // Ссылка оплаты по номеру телефона
            fallback_url: 'https://www.sberbank.com/sms/pbpn?requisiteNumber=79309791051' // Рабочий fallback в браузере
          },
          {
            id: 'tbank', // Идентификатор банка
            title: 'Т-Банк', // Название
            logo: 'assets/img/banks/tbank.png', // Логотип
            deeplink: 'https://www.tbank.ru/mybank/payments/persons/phone/?internal_source=homePayments_transferByPhoneSmall_suggest&predefined=%7B%22phone%22%3A%22%2B79160794459%22%7D', // Переход на оплату по телефону
            fallback_url: 'https://www.tbank.ru/mybank/payments/persons/phone/?internal_source=homePayments_transferByPhoneSmall_suggest&predefined=%7B%22phone%22%3A%22%2B79160794459%22%7D' // Fallback совпадает с deeplink
          },
          {
            id: 'vtb', // Идентификатор банка
            title: 'ВТБ', // Название
            logo: 'assets/img/banks/vtb.png', // Логотип
            deeplink: 'https://online.vtb.ru/i/cell/ppl/9309791051', // Deeplink на оплату по телефону
            fallback_url: 'https://online.vtb.ru/transfers/transferByPhone?isStandaloneScenario=true&actionType=generalTargetSearch&tab=SWITCH_TO_OP_4808&isForeingNumber=false&isInternalTargetSearch=false&predefinedValues%5BpredefinedPhoneNumber%5D=%2B7%20916%20079-44-59&stage=INPUT' // Безопасный fallback для браузера
          },
          { id: 'alfabank', title: 'Альфа-Банк', logo: 'assets/img/banks/alfabank.png', close_only: true }, // Остальные пока только закрывают Mini App
          { id: 'rshb', title: 'Россельхозбанк', logo: 'assets/img/banks/rshb.png', close_only: true }, // Заглушка закрытия
          { id: 'gazprombank', title: 'Газпромбанк', logo: 'assets/img/banks/gazprombank.png', close_only: true }, // Заглушка закрытия
          { id: 'psb', title: 'ПСБ', logo: 'assets/img/banks/psb.png', close_only: true }, // Заглушка закрытия
          { id: 'mkb', title: 'МКБ', logo: 'assets/img/banks/mkb.png', close_only: true }, // Заглушка закрытия
          { id: 'mtsbank', title: 'МТС Банк', logo: 'assets/img/banks/mtsbank.png', close_only: true }, // Заглушка закрытия
          { id: 'pochtabank', title: 'Почта Банк', logo: 'assets/img/banks/pochtabank.png', close_only: true }, // Заглушка закрытия
          { id: 'sovcombank', title: 'Совкомбанк', logo: 'assets/img/banks/sovcombank.png', close_only: true } // Заглушка закрытия
        ];
      });
  }

  window.BankLoader = { // Экспортируем API загрузчика банков
    loadBanks: loadBanks // Делаем доступной функцию загрузки
  }; // Завершаем экспорт
})(window); // Передаём window внутрь IIFE
