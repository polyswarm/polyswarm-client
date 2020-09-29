FROM python:3.7-slim-buster

WORKDIR /usr/src/app

COPY requirements.integration.txt .
RUN pip install -r requirements.integration.txt

COPY . .

ENV FLASK_APP=tests.integration.base

EXPOSE 5000

CMD python -m flask run --host 0.0.0.0
