FROM python:3.11-slim

WORKDIR /samowarium

COPY requirements.txt .
COPY ./src ./src

RUN rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt
