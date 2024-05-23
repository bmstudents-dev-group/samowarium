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

- Запустить образ:

```bash
DOCKER_TAG=latest docker compose up -d
```

- Для остановки:

```bash
docker compose down
```
