# Quick Start Guide

Get VibeMind running and speak your first command in 5 minutes.

## 1. Install (2 minutes)

```bash
git clone --recursive https://github.com/Flissel/VibeMind-VoiceDialog.git
cd VibeMind-VoiceDialog
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd electron-app && npm install && cd ..
```

## 2. Configure (1 minute)

```bash
cp .env.example .env
```

Edit `.env` and set:
```
OPENAI_API_KEY=sk-your-key-here
FORCE_SYNC_MODE=true
```

## 3. Launch (30 seconds)

```bash
cd electron-app
npm start
```

A dark window with a 3D scene opens. The Python backend starts automatically in the terminal.

## 4. Speak (try these)

Make sure your microphone is active, then say:

| Say This | What Happens |
|----------|-------------|
| "Erstelle eine Bubble Marketing" | Creates a bubble called "Marketing" |
| "Geh in Marketing" | Navigates into the Marketing bubble |
| "Notiere API Design Review" | Creates an idea inside Marketing |
| "Notiere Competitor Analysis" | Creates another idea |
| "Verlinke die Ideen sinnvoll" | AI auto-links related ideas |
| "Zurueck" | Exits back to the top level |
| "Zeig mir meine Bubbles" | Lists all bubbles |

## 5. What You See

- **Bubbles** appear as 3D glass spheres in the scene
- **Ideas** appear as smaller nodes inside bubbles
- **Links** appear as lines connecting related ideas
- Click bubbles to navigate, or use voice commands

## Next Steps

- [Voice Commands](voice-commands.md) — Full command reference
- [Ideas Space](ideas-space.md) — Deep dive into bubble/idea management
- [Configuration](configuration.md) — Enable more features
- [FAQ](faq.md) — Common questions
