FROM python:3.12-slim

RUN rm -rf /var/lib/apt/lists/*

WORKDIR /samowarium

COPY yoyo.ini .

RUN apt-get update

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY ./migrations ./migrations
COPY ./src .
COPY ./get_logs .
COPY ./get_users .