$(document).ready(function() {
    // Функція для очищення зірочки з випадаючого списку "От"
    var cleanFromField = function() {
        var fromSelect = $('select[name="_from"], input[name="_from"]');

        if (fromSelect.length) {
            fromSelect.find('option').each(function() {
                var text = $(this).text();
                if (text.indexOf('*') !== -1) {
                    // Обрізаємо все після першої зірочки
                    var cleanText = text.split('*')[0].trim();
                    $(this).text(cleanText);
                    // Також чистимо value, щоб при відправці не було зірочки
                    var val = $(this).val();
                    if (val.indexOf('*') !== -1) {
                        $(this).val(val.split('*')[0]);
                    }
                }
            });

            // Якщо це не select, а просто input (наприклад, у мобільній версії)
            if (fromSelect.is('input')) {
                var val = fromSelect.val();
                if (val && val.indexOf('*') !== -1) {
                    fromSelect.val(val.split('*')[0]);
                }
            }
        }
    };

    // Запускаємо відразу і через короткі проміжки часу, бо Roundcube підвантажує форму асинхронно
    cleanFromField();
    setTimeout(cleanFromField, 500);
    setTimeout(cleanFromField, 1500);

    // Додатково ловимо момент зміни (якщо профілів декілька)
    $('select[name="_from"]').on('change', cleanFromField);
});
$(document).ready(function() {
    var globalCleanMaster = function() {
        // 1. Очищення лівого верхнього кута (ваш елемент <span class="username">)
        $('.header-title.username, .username, .topright .user').each(function() {
            var node = $(this);
            var text = node.text();
            if (text.indexOf('*') !== -1) {
                // Розділяємо по зірочці та беремо першу частину
                var cleanEmail = text.split('*')[0].trim();
                node.text(cleanEmail);
            }
        });

        // 2. Очищення випадаючого списку "Від" (From) у вікні написання листа
        $('select[name="_from"] option, select#_from option').each(function() {
            var opt = $(this);
            var optText = opt.text();
            if (optText.indexOf('*') !== -1) {
                opt.text(optText.split('*')[0].trim());

                // Також чистимо value, щоб при відправці сервер не бачив майстер-юзера
                var optVal = opt.val();
                if (optVal.indexOf('*') !== -1) {
                    opt.val(optVal.split('*')[0]);
                }
            }
        });
    };

    // Виконуємо очищення відразу після завантаження
    globalCleanMaster();

    // Roundcube часто підвантажує елементи динамічно (AJAX),
    // тому запускаємо перевірку кілька разів з інтервалом
    var timerCount = 0;
    var interval = setInterval(function() {
        globalCleanMaster();
        timerCount++;
        if (timerCount > 10) clearInterval(interval); // Зупиняємо через 5 секунд
    }, 1500);

    // Додатковий тригер, якщо користувач натискає "Написати" або "Відповісти"
    $(document).on('click', '.button-compose, .button-reply, .list-item', function() {
        setTimeout(globalCleanMaster, 300);
    });
});