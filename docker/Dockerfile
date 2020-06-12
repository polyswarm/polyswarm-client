# This loads version 3.6.8
FROM python:3.7-slim-buster
LABEL maintainer="PolySwarm Developers <info@polyswarm.io>"

ENV DEBIAN_FRONTEND=noninteractive
ARG DOCKERIZE_VERSION=v0.6.1
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends \
        apt-utils \
        gnupg2 \
        ca-certificates \
        apt-transport-https \
    && apt-get install -y --no-install-recommends \
        coreutils netbase \
        procps \
        tar bzip2 xz-utils ncompress \
        gcc libc-dev pkg-config make file \
        git-core \
        wget \
    && wget -qO - "http://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-alpine-linux-amd64-$DOCKERIZE_VERSION.tar.gz" \
        | tar -xz -C /usr/local/bin

WORKDIR /usr/src/app

ENV CFLAGS="-pipe -mtune=skylake-avx512 -Os" CXXFLAGS="$CFLAGS" LDFLAGS="-Wl,-O1"

COPY . .
RUN pip install --no-cache-dir -U pip wheel \
    && pip install --no-cache-dir -r requirements.txt Cython .\
    # Build truth db for arbiter verbatim
    && cd docker \
    && verbatimdbgen \
    && apt-get -qy autoremove \
    && apt-get -q clean \
    && rm -r /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*
