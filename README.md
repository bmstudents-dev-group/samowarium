# Samowarium

Клиент [Самовара](https://student.bmstu.ru/) внутри телеги.

## Для разработки

- Переименовать `.env.example` -> `.env` и выставить токен для бота.

- необязательные переменные в .env:

```
ENV=              # название окружения, в котором работает программа (unknown, если не задано)
VERSION=          # название версии программы (none, если не задано)
ENCRYPTION=       # ключ шифрования для базы данных (генерируется при запуске, если не задано)
DEBUG=            # выставляет уровень логирования DEBUG (INFO, если не задано)
ENABLE_PROMETHEUS_METRICS_SERVER=   # запускает сервер для получения метрик (не запускает, если не задано)
PROMETHEUS_METRICS_SERVER_PORT=     # указывает порт для сервера метрик (53000, если не задано)  
```

- Использовать python3.12 и выше. 

- Установить зависимости:

```bash
pip install -r requirements.txt
```

- Запустить бота:

```bash
python3 ./src/samowarium.py
```

- Сделать миграцию:

```bash
yoyo new -m "migration name"
```

## Для работы с Docker

- Собрать образ:

```bash
docker compose build
```

- Или получить из регистра:

```bash
docker compose pull
```

- Запустить сервис (не забыть создать `.env` файл с переменными):

```bash
docker compose up -d
```

- Остановить сервис:

```bash
docker compose down
```
