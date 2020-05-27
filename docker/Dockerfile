# This loads version 3.6.8
FROM python:3.6-stretch
LABEL maintainer="PolySwarm Developers <info@polyswarm.io>"

ENV DOCKERIZE_VERSION v0.6.1

RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && rm dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN pip install -U pip wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN pip install --no-cache-dir  . \
    # Build truth db for arbiter verbatim
    && cd docker \
    && verbatimdbgen
