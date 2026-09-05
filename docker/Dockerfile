# Сборка pycades (расширение CAdES для Python) + FastAPI-сервис подписи.
#
# Контекст сборки — корень проекта:
#   docker build -f docker/Dockerfile -t pycades:latest .
#
# Перед сборкой положите дистрибутив КриптоПро CSP в csp/linux-amd64_deb.tgz

ARG UBUNTU_VERSION=24.04
FROM ubuntu:${UBUNTU_VERSION}

# Версия pycades. Тег из https://github.com/CryptoPro/pycades
# Не используйте main: upstream в марте 2026 переехал на новую структуру каталогов,
# и сборка может измениться в любой момент.
ARG PYCADES_REF=v0.1.70300

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Europe/Moscow \
    LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        cmake \
        build-essential \
        libboost-all-dev \
        python3 \
        python3-dev \
        python3-venv \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------- КриптоПро CSP
COPY csp/linux-amd64_deb.tgz /tmp/csp.tgz
COPY scripts/install-csp.sh /usr/local/bin/install-csp.sh
RUN chmod +x /usr/local/bin/install-csp.sh \
    && /usr/local/bin/install-csp.sh /tmp/csp.tgz \
    && rm -f /tmp/csp.tgz

ENV PATH="/opt/cprocsp/bin/amd64:/opt/cprocsp/sbin/amd64:${PATH}" \
    LD_LIBRARY_PATH="/opt/cprocsp/lib/amd64:/opt/cprocsp/lib"

# --------------------------------------------------------------------- pycades
RUN git clone --depth 1 --branch "${PYCADES_REF}" \
        https://github.com/CryptoPro/pycades.git /usr/src/pycades \
    && cmake -S /usr/src/pycades -B /usr/src/pycades/build \
    && cmake --build /usr/src/pycades/build -j"$(nproc)" \
    && mkdir -p /opt/pycades \
    && find /usr/src/pycades/build -name 'pycades*.so' -exec cp {} /opt/pycades/pycades.so \; \
    && cp -r /usr/src/pycades/samples /opt/pycades/samples \
    && test -f /opt/pycades/pycades.so \
    && rm -rf /usr/src/pycades/build

ENV PYTHONPATH="/opt/pycades" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ------------------------------------------------------------------ приложение
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

COPY app /app
WORKDIR /app

EXPOSE 8011

# Проверка, что расширение импортируется и CSP отвечает
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8011/health || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]
