# ПОТОК Lite

## BIN/IIN-подсказки для банковских карт

В проект добавлен безопасный локальный модуль определения карты по BIN/IIN (`services/bot/tools/bin_lookup.py`). Он проверяет номер по алгоритму Луна, определяет платёжную систему и ищет банк в локальном справочнике `services/bot/config/bin_db.json`.

Переменные окружения для внешних BIN-провайдеров:

- `HANDYAPI_KEY` — ключ HandyAPI BIN List; если ключ не задан, провайдер пропускается.
- `HANDYAPI_BASE_URL` — необязательный базовый URL HandyAPI.
- `BINSEARCHLOOKUP_KEY` — ключ BINSearchLookup; если ключ не задан, провайдер пропускается.
- `BINSEARCHLOOKUP_BASE_URL` — необязательный базовый URL BINSearchLookup.
- `BIN_LOOKUP_EXTERNAL_ENABLED=true/false` — включает или выключает внешние запросы; при `false` работают только локальный справочник и локальное определение платёжной системы.

Важно: модуль не отправляет наружу полный номер карты. Для внешних запросов используются только первые 8 цифр BIN, затем первые 6 цифр BIN при необходимости.

Импорт локального CSV-справочника BINList.io:

```bash
python scripts/import_binlist_io_csv.py --input path/to/binlist.csv --output services/bot/config/bin_db.json
```
