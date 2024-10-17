# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
WORKDIR /app/reasonreport
CMD flask run --debug -h 0.0.0.0 -p 5000
