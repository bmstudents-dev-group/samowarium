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

- Собрать образ и запустить контейнер:

```bash
docker compose -f docker/docker-compose.yml run --rm samowarium-container python src/samowarium.py
```

- В дальнейшем выполнять ребилд образа:

```bash
docker compose -f docker/docker-compose.yml build
```

- Для остановки:

```bash
docker compose -f docker/docker-compose.yml down -v
```
