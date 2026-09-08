# syntax=docker/dockerfile:1.5

# --------------------
# Stage 1 – builder
# --------------------
FROM python:3.13-slim AS builder
WORKDIR /app

# Install build‑time dependencies (gcc, libpq-dev) needed for wheels
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy only requirement files first for caching
COPY requirements.txt .
COPY vendor ./vendor
RUN pip install --no-cache-dir --target=/install -r requirements.txt

# --------------------
# Stage 2 – runtime
# --------------------
FROM python:3.13-slim AS runtime
WORKDIR /app

# Create non‑root user
RUN useradd --create-home --uid 1001 appuser && \
    mkdir -p /app/storage && chown -R appuser:appuser /app
USER appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local/lib/python3.13/site-packages

# Copy application source code
COPY --chown=appuser:appuser . .

# Expose the application port (default FastAPI)
EXPOSE 8000

# Use Gunicorn with Uvicorn workers for production
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--workers", "4", "--bind", "0.0.0.0:8000"]
