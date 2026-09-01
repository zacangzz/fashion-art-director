# ==============================================================================
# Stage 1: Build Frontend Assets (React + Vite)
# ==============================================================================
FROM node:22-alpine AS frontend-builder
WORKDIR /build

COPY src/frontend/package*.json ./
RUN npm ci

COPY src/frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Production Python Runtime with uv
# ==============================================================================
FROM python:3.11-slim AS runtime

# Install system utilities and SSL certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install Python virtual environment dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application source code
COPY src/ /app/src/

# Copy compiled frontend SPA from Stage 1 into the location expected by main.py
COPY --from=frontend-builder /build/dist /app/src/frontend/dist

# Configure runtime environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV PORT=8080
ENV HOST=0.0.0.0
ENV ENVIRONMENT=production

EXPOSE 8080

# Launch FastAPI app with Uvicorn on Cloud Run default port
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
