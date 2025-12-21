(function (app) { // Оборачиваем в немедленно вызываемую функцию, чтобы не засорять глобальную область
  const namespace = app; // Берём ссылку на пространство имён приложения

  namespace.EVENT_ENDPOINT = 'https://example.com/api/events'; // URL-заглушка для отправки событий
  namespace.REDIRECT_PAGE = './redirect.html'; // Страница редиректа (расположена рядом с index.html)

  namespace.BANKS = [ // Массив с описанием банков и их ссылок
    { // Первый банк
      name: 'Сбербанк', // Человеческое имя банка
      icon: 'assets/images/LOGO_SBER.png', // Путь до иконки
      deepLink: 'https://www.sberbank.com/sms/pbpn?requisiteNumber=79309791051', // Deep link или ссылка приложения
      webUrl: 'https://www.sberbank.com/sms/pbpn?requisiteNumber=79309791051' // Fallback в веб
    },
    { // Второй банк
      name: 'Альфа-Банк', // Имя банка
      icon: 'assets/images/LOGO_ALFABANK.png', // Иконка
      deepLink: 'alfabank://account', // Deep link для мобильного приложения
      webUrl: 'https://web.alfabank.ru/dashboard' // Веб-страница
    },
    { // Т-Банк
      name: 'Т-Банк', // Имя
      icon: 'assets/images/LOGO_TBANK.png', // Иконка
      deepLink: 'tbank://main', // Приложение
      webUrl: 'https://www.tbank.ru/mybank/' // Веб
    },
    { // Россельхозбанк
      name: 'Россельхозбанк', // Имя
      icon: 'assets/images/LOGO_RSHB.png', // Иконка
      deepLink: 'rshbmbfl://', // Deep link
      webUrl: 'https://online.rshb.ru/cas-auth/index?forceAuth=true' // Веб-версия
    },
    { // Газпромбанк
      name: 'Газпромбанк', // Имя
      icon: 'assets/images/LOGO_GAZPROMBANK.png', // Иконка
      deepLink: 'gpbapp://', // Приложение
      webUrl: 'https://ib.online.gpb.ru/' // Fallback
    },
    { // ПСБ
      name: 'ПСБ', // Имя
      icon: 'assets/images/LOGO_PSB.png', // Иконка
      deepLink: 'psbmobile://auth/accounts', // Приложение
      webUrl: 'https://ib.psbank.ru/settings' // Веб
    },
    { // МКБ
      name: 'МКБ', // Имя
      icon: 'assets/images/LOGO_MKB.png', // Иконка
      deepLink: 'mkb2://deeplink', // Приложение
      webUrl: 'https://online.mkb.ru/login' // Веб
    },
    { // ВТБ
      name: 'ВТБ', // Имя
      icon: 'assets/images/LOGO_VTB.png', // Иконка
      deepLink: 'vtb://vtb.ru/i/', // Приложение
      webUrl: 'https://online.vtb.ru/login' // Веб
    },
    { // МТС Банк
      name: 'МТС Банк', // Имя
      icon: 'assets/images/LOGO_MTSBANK.png', // Иконка
      deepLink: 'mtsmoney://', // Приложение
      webUrl: 'https://sso.mtsbank.ru/login/mtsmoney/auth/' // Веб
    },
    { // Почта Банк
      name: 'Почта Банк', // Имя
      icon: 'assets/images/LOGO_POCHTABANK.png', // Иконка
      deepLink: 'bank100000000016://sbpay', // Приложение
      webUrl: 'https://my.pochtabank.ru/login' // Веб
    },
    { // Совкомбанк
      name: 'Совкомбанк', // Имя
      icon: 'assets/images/LOGO_SOVKOMBANK.png', // Иконка
      deepLink: 'ompshared://', // Приложение
      webUrl: 'https://bk.sovcombank.ru/ru/html/login.html' // Веб
    }
  ];
})(window.App = window.App || {}); // Экспортируем в пространство имён
