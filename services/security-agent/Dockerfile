FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy poetry configuration
COPY pyproject.toml poetry.lock* ./

# Install dependencies (only main dependencies, not dev)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --only main

COPY . .

# Expose port
EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
