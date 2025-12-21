(function (app) { // Изолируем модуль анимаций
  const namespace = app; // Пространство имён

  namespace.startButtonAnimation = function startButtonAnimation() { // Экспортируем запуск анимации
    document.querySelectorAll('.btn').forEach(function (button, index) { // Перебираем все кнопки
      const delay = index * 0.05; // Считаем задержку для каждой кнопки
      button.style.animation = 'slideUp 0.6s ease-out both ' + delay + 's'; // Применяем CSS-анимацию
    }); // Конец forEach
  }; // Конец startButtonAnimation

  namespace.attachStretchEffect = function attachStretchEffect(listSelector, buttonsSelector) { // Экспортируем эффект растяжки
    const list = document.querySelector(listSelector); // Находим список по селектору
    const buttons = document.querySelectorAll(buttonsSelector); // Находим все кнопки
    let startY = 0; // Координата начала касания
    let touching = false; // Флаг активного касания

    list.addEventListener('touchstart', function (event) { // Обработчик начала касания
      touching = true; // Отмечаем начало
      startY = event.touches[0].clientY; // Фиксируем исходный Y
    }); // Конец touchstart

    list.addEventListener('touchmove', function (event) { // Обработчик движения пальца
      if (!touching) { // Если касание не активно
        return; // Ничего не делаем
      } // Конец проверки
      const delta = event.touches[0].clientY - startY; // Считаем смещение
      const scale = 1 + Math.min(Math.abs(delta) / 200, 0.1); // Рассчитываем коэффициент растяжки
      if ((list.scrollTop === 0 && delta > 0) || (list.scrollTop + list.clientHeight >= list.scrollHeight && delta < 0)) { // Проверяем упор
        buttons.forEach(function (button) { // Перебираем кнопки
          button.style.transform = 'scaleY(' + scale + ')'; // Применяем растяжку по Y
        }); // Конец forEach
      } // Конец условия упора
    }); // Конец touchmove

    list.addEventListener('touchend', function () { // Обработчик окончания касания
      touching = false; // Сбрасываем флаг
      buttons.forEach(function (button) { // Для каждой кнопки
        button.style.transition = 'transform 0.3s'; // Добавляем плавность возврата
        button.style.transform = 'scaleY(1)'; // Возвращаем исходный масштаб
        setTimeout(function () { // По завершении анимации
          button.style.transition = ''; // Убираем transition, чтобы не мешал дальше
        }, 300); // Таймер соответствует длительности анимации
      }); // Конец forEach
    }); // Конец touchend
  }; // Конец attachStretchEffect
})(window.App = window.App || {}); // Экспортируем модуль
