# Samowarium

Клиент [Самовара](https://student.bmstu.ru/) внутри телеги.

## Для разработки

- Переименовать `.env.example` -> `.env` и выставить токен для бота.
необязательные переменные:
```
ENV=...          # отображается в /about
VERSION=...      # отображается в /about
ENCRYPTION=...   # используется для сохранения паролей
```

- Использовать python3.12 и выше. 

- Установить зависимости:

```bash
# если используется другая версия python, то установить соответствующий пакет
apt-get update && apt-get install python3.12-dev
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
DOCKER_TAG=latest docker compose build
```

- Или получить из регистра:

```bash
DOCKER_TAG=latest docker compose pull
```

- Запустить сервис (не забыть создать `.env` файл с переменными):

```bash
DOCKER_TAG=latest docker compose up -d
```

- Остановить сервис:

```bash
docker compose down
```

- Вывести логи

```bash
docker exec <контейнер> ./get_logs
```

- Вывести пользователей

```bash
docker exec <контейнер> ./get_users
```