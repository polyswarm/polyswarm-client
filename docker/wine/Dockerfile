FROM polyswarm-client

ENV DEBIAN_FRONTEND=noninteractive

RUN dpkg --add-architecture i386 \
    && curl -s -L https://dl.winehq.org/wine-builds/winehq.key | apt-key add - 2>/dev/null \
    && echo 'deb http://dl.winehq.org/wine-builds/debian/ buster main' >> /etc/apt/sources.list \
    && apt-get update

# libfaudio0 isn't packaged by Debian packaging authority, so we install it
# ourselves here.
# NOTE: This package is *not* required for the operation of WINE itself, it may
# make sense to start building a source package with ./configure script that excludes
# unnessasary packages like libfaudio
COPY vendor/libfaudio/* /tmp/libfaudio/
RUN apt-get install -y --no-install-recommends --autoremove --purge \
    /tmp/libfaudio/*.deb

# Install WINE 5.10 & utilities
RUN apt-get install -y --install-recommends --autoremove --purge \
    # cabextract \
    # winbind \
    xdotool \
    xvfb \
    winehq-staging=5.10~buster \
    # exclude each of the following's i386 & amd64 package
    $(perl -e 'map { print("$_-\n", "$_:i386-\n"); } qw{ \
        libcapi20-3 \
        libglu1 libglu1-mesa libosmesa6 \
        libgtk-3-0 \
        libsane libsane1 \
        libv4l-0 \
        va-driver va-driver-all vdpau-driver-all \
    }')

# cleanup
RUN apt-get clean -y && rm -rf /var/lib/apt/lists/*

# unpack mono & gecko
WORKDIR /usr/share/wine/
RUN set -eux; \
  mkdir mono gecko && \
  WINEHQ="https://dl.winehq.org/wine"; \
  (curl -s -L "$WINEHQ/wine-mono/5.1.0/wine-mono-5.1.0-x86.tar.xz" | tar -C mono/ -xJ) & \
  (curl -s -L "$WINEHQ/wine-gecko/2.47.1/wine-gecko-2.47.1-x86.tar.bz2"     | tar -C gecko/ -xj) & \
  (curl -s -L "$WINEHQ/wine-gecko/2.47.1/wine-gecko-2.47.1-x86_64.tar.bz2"  | tar -C gecko/ -xj) & \
  wait

# winetricks & custom wineserver wrappers
COPY /bin/* /usr/local/bin/

WORKDIR /usr/local/wine

# Specifies the Windows architecture to support. It can be set either to 'win32'
# (support only 32-bit applications), or to 'win64' (support both 64-bit
# applications and  32-bit ones through WoW)
ARG PLATFORM=win32
ENV WINEPREFIX=/usr/local/wine/$PLATFORM/ WINEARCH=$PLATFORM
RUN WINESERVER=/usr/local/bin/wineserver-transient wineboot -i -u \
    && wineserver-wait -v
RUN WINESERVER=/usr/local/bin/wineserver-transient xvfb-run winetricks -q vcrun2019 \
    && wineserver-wait -v

ENV WINEDEBUG="-all"
WORKDIR /usr/src/app
