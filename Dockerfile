# ============================================================
# Этап 5: Финальная интеграция — Docker production build
# ============================================================
FROM python:3.12-slim AS base

# Security: non-root user
RUN groupadd --system django && useradd --system --gid django django

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo zlib1g-dev libfreetype6 pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Python env
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv/app

# ---- deps ----
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && pip install -r requirements.txt

# ---- project ----
COPY --chown=django:django . .

# Collect static / security
ENV DEBUG=0 \
    SECURE_SSL_REDIRECT=1 \
    SECRET_KEY=CHANGE_ME \
    DATABASE_URL=postgresql://django:password@db:5432/dynamicpages \
    REDIS_URL=redis://redis:6379/0
USER django
CMD ["gunicorn", "dynamicpages.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
