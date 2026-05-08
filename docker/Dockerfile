# ─────────────────────────────────────────────────────────────────
# Dockerfile — Royal Land PMS (Local Dev)
# Python 3.13-slim + WeasyPrint system deps + Gunicorn
# ─────────────────────────────────────────────────────────────────

FROM python:3.13-slim

# Prevent .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────
# WeasyPrint 68.x needs Pango, GDK-Pixbuf, GLib, shared-mime-info
# cffi 2.x needs gcc + libffi-dev for compilation
# fonts-liberation provides basic Latin fonts for PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint core
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libglib2.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    # Fonts for PDF
    fonts-liberation \
    fonts-dejavu-core \
    # cffi build deps
    gcc \
    libffi-dev \
    # psycopg2-binary runtime dep
    libpq5 \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────
COPY requirements.dev.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.dev.txt

# ── Application code ──────────────────────────────────────────────
COPY . .

# ── Static files ──────────────────────────────────────────────────
# Collected at build time so nginx can serve them immediately
# DJANGO_SETTINGS_MODULE is set here only for collectstatic;
# runtime value comes from docker-compose env_file
RUN DJANGO_SETTINGS_MODULE=config.settings.development \
    SECRET_KEY=collectstatic-placeholder \
    DB_NAME=placeholder \
    DB_USER=placeholder \
    DB_PASSWORD=placeholder \
    DB_HOST=placeholder \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Gunicorn: 3 workers is fine for local dev
# timeout 120s gives WeasyPrint enough time to render large PDFs
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "config.wsgi:application"]