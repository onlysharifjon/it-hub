FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copy only dependency files first (better layer caching)
COPY pyproject.toml poetry.lock ./

# Install runtime deps only, directly into system Python (no venv in container)
RUN poetry config virtualenvs.create false \
    && PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring \
       poetry install --no-interaction --no-root --without dev

# Copy source code
COPY . .

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
