ARG MANUAL_IMAGE_TAG="latest"

FROM 005789955001.dkr.ecr.us-east-1.amazonaws.com/polyswarm-transaction:$MANUAL_IMAGE_TAG AS transaction

FROM python:3.6-stretch
LABEL maintainer="PolySwarm Developers <info@polyswarm.io>"

ENV DOCKERIZE_VERSION v0.6.1

COPY --from=transaction /usr/src/app /polyswarm-transaction
RUN pip3 install --cache-dir=/tmp /polyswarm-transaction \
    && rm -rf /polyswarm-transaction

RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && rm dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz

WORKDIR /usr/src/app

COPY requirements.txt ./
COPY requirements-test.txt ./

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-test.txt

COPY . .

RUN pip install --no-cache-dir  . \
    # Build truth db for arbiter verbatim
    && cd docker \
    && verbatimdbgen
