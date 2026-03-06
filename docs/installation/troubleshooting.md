# Troubleshooting

## Installation Issues

### "OPENAI_API_KEY not found"

`.env` file is missing or not in the right location. It must be in the repository root:

```bash
cp .env.example .env
# Edit .env and add your key
```

### `pip install` fails on torch/transformers

These are optional (for DroPE reference resolution). Comment them out in `requirements.txt` if you don't need them:

```txt
# torch>=2.0.0
# transformers>=4.35.0
# accelerate>=0.24.0
```

### `npm install` fails in electron-app

Try clearing cache and reinstalling:

```bash
cd electron-app
rm -rf node_modules package-lock.json
npm install
```

### Submodule errors after clone

If you didn't use `--recursive`:

```bash
git submodule update --init --recursive
```

### Python version mismatch

VibeMind requires Python 3.11+. Check with:

```bash
python --version
```

If you have multiple versions, create the venv explicitly:

```bash
python3.11 -m venv .venv
```

## Runtime Issues

### No audio input detected

```python
# Check available devices
import sounddevice as sd
print(sd.query_devices())
```

- Ensure your microphone is set as default input
- On macOS: Allow microphone access in System Settings
- On Linux: Check PulseAudio/ALSA configuration and `audio` group membership

### Electron window is black/blank

Electron GPU acceleration may have issues. Try:

```bash
cd electron-app
./node_modules/electron/dist/electron.exe . --disable-gpu
```

### "Redis connection refused"

Either start Redis or enable sync mode:

```bash
# Option A: Start Redis
docker run -d -p 6379:6379 redis:alpine

# Option B: Use sync mode (no Redis needed)
# Set in .env:
FORCE_SYNC_MODE=true
```

### Python backend doesn't start from Electron

Check that your `.venv` is activated and Python is on PATH. The Electron app spawns Python from `main.js` — check the terminal output for errors.

### Intent classification returns wrong event type

Check `python/logs/intents/` for classification logs. Common issues:
- Voice input was misheard (ASR error) — enable `USE_INTENT_ANALYSIS=true`
- New command pattern not in classifier prompt — see [Adding Event Types](../development/adding-event-types.md)

### Port conflicts

Default ports used:

| Port | Service |
|------|---------|
| 9222-9224 | Electron CDP debug |
| 6379 | Redis |
| 8766 | MoireServer |
| 3480 | Minibook backend |
| 3481 | Minibook frontend |

Kill conflicting processes or change ports in configuration.
