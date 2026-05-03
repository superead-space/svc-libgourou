FROM ubuntu:jammy AS builder

RUN apt-get update && \
  DEBIAN_FRONTEND=noninteractive TZ="Etc/UTC" \
  apt-get install -y --no-install-recommends \
  build-essential \
  bash \
  git \
  ca-certificates \
  libzip-dev \
  libssl-dev \
  libcurl4-gnutls-dev \
  libpugixml-dev

WORKDIR /usr/src

RUN git clone git://soutade.fr/libgourou.git \
  && cd libgourou \
  && make BUILD_STATIC=1 STATIC_UTILS=1


FROM ubuntu:jammy AS release

COPY --from=builder /usr/src/libgourou/utils/acsmdownloader \
                    /usr/src/libgourou/utils/adept_activate \
                    /usr/src/libgourou/utils/adept_remove \
                    /usr/src/libgourou/utils/adept_loan_mgt \
                    /usr/local/bin/

RUN apt-get update && \
  DEBIAN_FRONTEND=noninteractive TZ="Etc/UTC" \
  apt-get install -y --no-install-recommends \
    libpugixml1v5 \
    libzip4 \
    libssl3 \
    libcurl4-gnutls-dev \
    python3 \
    python3-pip \
    ca-certificates \
  && apt-get autoclean \
  && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 -s /bin/bash libgourou \
  && mkdir -p /home/libgourou/files /home/libgourou/.adept \
  && chown -R libgourou:libgourou /home/libgourou

WORKDIR /opt/svc-libgourou
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY server ./server
COPY scripts /home/libgourou/scripts
RUN chown -R libgourou:libgourou /opt/svc-libgourou /home/libgourou/scripts

USER libgourou
WORKDIR /home/libgourou

ENV DATA_DIR=/home/libgourou/files \
    ADEPT_DIR=/home/libgourou/.adept \
    REQUEST_TIMEOUT=180 \
    MAX_CONCURRENT=1 \
    LOG_LEVEL=info \
    PYTHONPATH=/opt/svc-libgourou \
    PYTHONUNBUFFERED=1

EXPOSE 3000

CMD ["python3", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "3000"]