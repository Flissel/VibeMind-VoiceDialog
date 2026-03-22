FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY python/ ./python/
COPY .env.example ./.env

# Default environment
ENV FORCE_SYNC_MODE=true
ENV FAST_STARTUP=true
ENV PYTHONUNBUFFERED=1

WORKDIR /app/python

CMD ["python", "electron_backend.py"]
