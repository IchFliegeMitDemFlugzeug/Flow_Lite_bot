(function (app) { // Оборачиваем в функцию для изоляции
  const namespace = app; // Сохраняем ссылку на пространство имён

  namespace.sendEvent = function sendEvent(eventName, payload) { // Экспортируем функцию отправки событий
    const eventData = { // Готовим объект события
      name: eventName, // Имя события
      data: payload, // Полезные данные
      timestamp: Date.now() // Метка времени
    }; // Конец объекта события

    if (!namespace.EVENT_ENDPOINT) { // Проверяем, задан ли endpoint
      console.debug('EVENT: endpoint не задан, событие пропущено'); // Сообщаем в debug и выходим
      return; // Прерываем выполнение
    } // Конец проверки endpoint

    try { // Пробуем выполнить fetch
      fetch(namespace.EVENT_ENDPOINT, { // Отправляем POST на указанный адрес
        method: 'POST', // Метод запроса
        headers: { 'Content-Type': 'application/json' }, // Заголовок JSON
        body: JSON.stringify(eventData) // Тело запроса в формате JSON
      })
        .then(function () { // Обработчик успешного ответа
          return null; // Возвращаем пустое значение (UI не трогаем)
        })
        .catch(function (error) { // Обрабатываем ошибку сети/сервера
          console.debug('EVENT: отправка не удалась', error); // Логируем в debug
        }); // Конец цепочки then/catch
    } catch (error) { // Ловим любые синхронные исключения
      console.debug('EVENT: исключение при отправке', error); // Сообщаем в debug
    } // Конец блока try/catch
  }; // Конец функции sendEvent
})(window.App = window.App || {}); // Завершаем модуль
