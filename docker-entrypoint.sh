#!/bin/sh
set -e

echo ">>> Waiting for database..."
until python -c "
import os, psycopg2
try:
    psycopg2.connect(os.environ['DATABASE_URL'])
    print('DB ready')
except Exception as e:
    print(f'DB not ready: {e}')
    exit(1)
" 2>/dev/null; do
    sleep 1
done

echo ">>> Running database migrations..."
alembic -c backend/alembic.ini upgrade head

echo ">>> Starting server..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
