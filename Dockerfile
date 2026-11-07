# ==============================================================================
# Production Dockerfile for HEICto-
# Compatible with Render, Railway, Fly.io, Google Cloud Run, and Docker VPS
# ==============================================================================

FROM python:3.12-slim-bookworm

# Install libheif system dependencies for high-performance HEIC processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libheif-dev \
    libde265-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Set environment
ENV PORT=5173
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

EXPOSE 5173

# Healthcheck for container orchestrators
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + str(os.environ.get('PORT', 5173)) + '/health')" || exit 1

# Start server
CMD ["python3", "app.py"]

