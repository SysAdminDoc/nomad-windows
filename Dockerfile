# N.O.M.A.D. Headless Server
# Run without desktop GUI — Flask serves on port 8080
FROM python:3.12-slim

LABEL maintainer="Project N.O.M.A.D." \
      description="Offline survival command center — headless server mode" \
      version="1.0.0"

# System deps for pyserial, Pillow, crypto
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for cache efficiency
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy application
COPY . .

# Create non-root user and data directory
RUN useradd -r -s /bin/false nomad && mkdir -p /data && chown -R nomad:nomad /app /data

# Environment
ENV NOMAD_DATA_DIR=/data \
    NOMAD_HEADLESS=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

USER nomad

# Run headless server
CMD ["python", "nomad_headless.py"]
