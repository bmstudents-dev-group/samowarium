FROM python:3.11-slim

RUN rm -rf /var/lib/apt/lists/*

WORKDIR /samowarium

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY ./src ./src
