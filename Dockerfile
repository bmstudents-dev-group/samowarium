FROM python:3.11-slim

RUN rm -rf /var/lib/apt/lists/*

WORKDIR /samowarium

COPY yoyo.ini .

RUN apt-get update && apt-get install python3.11-dev 

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY ./migrations ./migrations
COPY ./src .
