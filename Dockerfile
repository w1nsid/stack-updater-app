# Use uv base image with Python 3.11 on Alpine
FROM ghcr.io/astral-sh/uv:python3.11-alpine

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --compile-bytecode

COPY app/ ./app/
COPY main.py ./

EXPOSE 8080

# Launch the FastAPI app with uvicorn via uv (uses the synced venv)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]