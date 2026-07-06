# Dockerfile for FerryTrmnl
# Build from project root: docker build -f deployment/Dockerfile -t ferrytrmnl .
# Run: docker run -p 5050:5050 --env-file .env ferrytrmnl

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5050

# Version metadata (passed in at build time, surfaced in the web UI footer)
ARG APP_VERSION=dev
ARG GIT_SHA=""
ENV APP_VERSION=${APP_VERSION} \
    GIT_SHA=${GIT_SHA}

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY web/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY web/app.py .

# Create a non-root user
RUN useradd -m -u 1000 ferrytrmnl && \
    chown -R ferrytrmnl:ferrytrmnl /app

USER ferrytrmnl

# Expose the port
EXPOSE 5050

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5050/health || exit 1

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "4", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
