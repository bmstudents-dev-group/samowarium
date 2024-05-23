# Samowarium

Клиент [Самовара](https://student.bmstu.ru/) внутри телеги.

## Для разработки

- Переименовать `.env.example` -> `.env` и выставить токен для бота.

- Установить зависимости:

```bash
pip install -r requirements.txt
```

- Запустить бота:

```bash
python3 ./src/samowarium.py
```

## Для сборки Docker-контейнера

- Собрать образ:

```bash
DOCKER_TAG=latest docker compose build
```

- Или получить из регистра:

```bash
DOCKER_TAG=latest docker compose pull
```

- Запустить сервис:

```bash
DOCKER_TAG=latest docker compose up -d
```

- Остановить сервис
```bash
docker compose down
```
