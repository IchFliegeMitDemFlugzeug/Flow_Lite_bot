(function (app) { // Изолируем модуль предзагрузки
  const namespace = app; // Пространство имён приложения

  namespace.preloadImages = function preloadImages(urls, callback) { // Экспортируем функцию предзагрузки
    let loaded = 0; // Счётчик загруженных картинок

    function handleDone() { // Общий обработчик завершения загрузки
      loaded += 1; // Увеличиваем счётчик
      if (loaded === urls.length) { // Проверяем, все ли обработаны
        callback(); // Вызываем колбэк
      } // Конец проверки
    } // Конец handleDone

    urls.forEach(function (url) { // Перебираем список URL
      const img = new Image(); // Создаём объект Image
      img.onload = handleDone; // На успешную загрузку
      img.onerror = handleDone; // На ошибку тоже считаем
      img.src = url; // Стартуем загрузку, присвоив src
    }); // Конец forEach
  }; // Конец preloadImages
})(window.App = window.App || {}); // Экспортируем модуль
