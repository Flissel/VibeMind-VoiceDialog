# Docker Installation

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/install/) v2+

## Quick Start

```bash
git clone --recursive https://github.com/Flissel/VibeMind-VoiceDialog.git
cd VibeMind-VoiceDialog

cp .env.example .env
# Edit .env with your OPENAI_API_KEY

docker compose up
```

## Services

The `docker-compose.yml` runs:

| Service | Port | Description |
|---------|------|-------------|
| `backend` | 8000 | Python backend (FastAPI) |
| `redis` | 6379 | Event stream processing |
| `minibook-backend` | 3480 | Minibook collaboration API |
| `minibook-frontend` | 3481 | Minibook web UI |

## Electron App (Local)

The Electron UI runs locally (not in Docker) since it needs display access:

```bash
cd electron-app
npm install
npm start
```

Configure it to connect to the Docker backend via `.env`:

```bash
FORCE_SYNC_MODE=false
REDIS_URL=redis://localhost:6379
```

## Building Images

```bash
docker compose build
```

## Troubleshooting

**Container won't start:**
```bash
docker compose logs backend
```

**Redis connection refused:**
Ensure Redis container is running: `docker compose ps`

**Audio not working:**
Docker containers don't have microphone access. The voice layer runs in the Electron app (local), not in Docker.
