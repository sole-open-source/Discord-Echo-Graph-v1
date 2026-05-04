FROM python:3.12.3-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir supervisor

COPY src/ src/

RUN mkdir -p /app/.logs

COPY supervisord.conf /etc/supervisord.conf
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
