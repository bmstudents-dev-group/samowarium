FROM python:3.11-slim

WORKDIR /samowarium

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        sudo && \
    rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt
