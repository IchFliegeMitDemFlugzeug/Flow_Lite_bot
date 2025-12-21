(function (app) { // Изолируем основной модуль
  const namespace = app; // Берём ссылку на пространство имён

  function renderBanks() { // Рендерим список банков
    const list = document.querySelector('.bank-list'); // Находим контейнер списка
    list.innerHTML = ''; // Очищаем контейнер

    namespace.BANKS.forEach(function (bank) { // Перебираем массив банков
      const button = document.createElement('button'); // Создаём кнопку
      button.className = 'btn'; // Назначаем класс стилизации

      const icon = document.createElement('img'); // Создаём элемент картинки
      icon.src = bank.icon; // Прописываем путь к иконке
      icon.alt = bank.name; // Добавляем альтернативный текст

      const title = document.createElement('span'); // Создаём элемент для текста
      title.className = 'btn-text'; // Назначаем класс текста
      title.textContent = bank.name; // Записываем название банка

      button.addEventListener('click', function () { // Обработчик клика по кнопке
        namespace.openLink(bank.deepLink, bank.webUrl, bank.name); // Вызываем открытие ссылок и события
      }); // Конец обработчика клика

      button.appendChild(icon); // Добавляем иконку внутрь кнопки
      button.appendChild(title); // Добавляем текст внутрь кнопки
      list.appendChild(button); // Вставляем кнопку в список
    }); // Конец forEach по банкам
  } // Конец renderBanks

  function preloadAssetsAndAnimate() { // Предзагрузка ассетов и запуск анимации
    const bgCss = window.getComputedStyle(document.body).backgroundImage; // Берём вычисленный фон
    const bgUrl = bgCss.slice(5, -2); // Извлекаем URL из строки url("...")
    const imgEls = Array.from(document.querySelectorAll('img')); // Собираем все теги img
    const imgUrls = imgEls.map(function (img) { // Преобразуем в список URL
      return img.src; // Возвращаем путь каждой картинки
    }); // Конец map
    const allUrls = [bgUrl].concat(imgUrls); // Склеиваем фон и остальные картинки
    namespace.preloadImages(allUrls, namespace.startButtonAnimation); // Предзагружаем и запускаем анимацию
  } // Конец preloadAssetsAndAnimate

  function init() { // Главная точка входа
    if (window.Telegram && Telegram.WebApp) { // Проверяем наличие Telegram WebApp
      Telegram.WebApp.ready(); // Сообщаем Telegram о готовности
    } // Конец проверки Telegram

    const backButton = document.querySelector('.back-btn'); // Находим кнопку возврата
    backButton.addEventListener('click', function () { // Вешаем обработчик клика
      namespace.sendEvent('back_click', { from: 'header' }); // Логируем событие возврата
      namespace.closePage(); // Закрываем страницу корректно
    }); // Конец обработчика кнопки

    renderBanks(); // Рисуем кнопки банков
    namespace.attachStretchEffect('.bank-list', '.btn'); // Подключаем эффект растяжки списка
    preloadAssetsAndAnimate(); // Предзагружаем ассеты и стартуем анимацию
  } // Конец init

  document.addEventListener('DOMContentLoaded', init); // Запускаем init после загрузки DOM
})(window.App = window.App || {}); // Экспортируем модуль
