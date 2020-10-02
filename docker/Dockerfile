FROM python:3.7-slim-buster

ENV DEBIAN_FRONTEND=noninteractive
ENV CFLAGS="-pipe -mtune=skylake-avx512 -Os" CXXFLAGS="$CFLAGS" LDFLAGS="-Wl,-O1"
ENV COMMAND="microengine"

WORKDIR /usr/src/app

# Exclude documentation packages from being installed
RUN printf 'path-exclude /usr/share/%s/*\n' doc man groff info lintian linda > /etc/dpkg/dpkg.cfg.d/01_nodoc

RUN apt-get update -y \
    && apt-get install -qy --no-install-recommends apt-utils \
    && apt-get install -qy --no-install-recommends \
        ca-certificates \
        gnupg2 \
        coreutils netbase \
        procps \
        tar bzip2 xz-utils ncompress unzip \
        gcc libc-dev pkg-config make file \
        git-core \
        wget \
        g++


COPY . .
ARG PIP_INDEX_URL="https://pypi.python.org/simple"
RUN pip3 install --no-cache-dir -U wheel setuptools \
    && pip3 install --no-cache-dir \
      cytoolz[cython] \
      -r requirements.txt \
      -r requirements-test.txt \
      . \
    # Build truth db for arbiter verbatim
    && cd docker && verbatimdbgen \
    && apt-get -qy autoremove \
    && apt-get -q clean \
    && rm -r /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

CMD $COMMAND
