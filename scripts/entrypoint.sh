#!/bin/sh
# =============================================================================
# scripts/entrypoint.sh — Production container startup
# Runs inside the app container on every start.
# Steps: wait-for-db → migrate → collectstatic → gunicorn
# =============================================================================
set -e

echo "==> [entrypoint] Waiting for PostgreSQL…"
# Simple TCP wait — avoids needing wait-for-it.sh binary dependency.
# pg_isready is not available (no postgresql-client installed); use Python.
python - <<'EOF'
import socket, time, os, sys
host = os.environ.get("DB_HOST", "db")
port = int(os.environ.get("DB_PORT", "5432"))
retries = 30
for i in range(retries):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"  PostgreSQL is up at {host}:{port}")
            sys.exit(0)
    except OSError:
        print(f"  Waiting for {host}:{port} ({i+1}/{retries})…")
        time.sleep(2)
print("ERROR: PostgreSQL did not become ready in time.")
sys.exit(1)
EOF

echo "==> [entrypoint] Running migrations…"
python manage.py migrate --noinput

echo "==> [entrypoint] Collecting static files…"
python manage.py collectstatic --noinput --clear

echo "==> [entrypoint] Starting Gunicorn…"
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --threads 2 \
    --worker-class gthread \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile - \
    --log-level info