# Debugging

## Log Locations

| Log | Location | Content |
|-----|----------|---------|
| Voice session | `python/voice_dialog.log` | Voice input/output, session events |
| Agent execution | `python/logs/agents/` | Backend agent tool calls |
| Intent classification | `python/logs/intents/` | Classifier input/output/confidence |
| Tool calls | `python/logs/tool_calls/` | Tool parameters and results |
| Electron debug | `python/debug/logs/` | CDP session logs |

## Debug Mode

Launch with Chrome DevTools Protocol on port 9222:

```bash
# Windows
start_vibemind_debug.bat

# Manual
cd electron-app
./node_modules/electron/dist/electron.exe --remote-debugging-port=9222 .
```

Then open `chrome://inspect` in Chrome to connect to the Electron renderer.

## Common Debug Scenarios

### Voice input not classifying correctly

1. Check `python/logs/intents/` for the raw input and classifier output
2. Verify the event type exists in `CLASSIFIER_PROMPT_TEMPLATE`
3. Test classification directly:
   ```python
   from swarm.orchestrator.intent_classifier import IntentClassifier
   ic = IntentClassifier()
   result = ic.classify("Erstelle Bubble Test")
   print(result)
   ```

### Tool execution failing

1. Check `python/logs/tool_calls/` for the error
2. Test the tool directly:
   ```python
   from spaces.ideas.tools.bubble_tools import create_bubble
   result = create_bubble(title="Test")
   print(result)
   ```

### IPC messages not reaching Electron

1. Check Python stdout for the JSON message
2. In Electron DevTools console, check for `ipcRenderer` events
3. Verify `main.js` is forwarding the message type

### Database issues

```python
from data.database import get_db
db = get_db()
# Direct SQL for debugging
cursor = db.execute("SELECT * FROM ideas LIMIT 5")
print(cursor.fetchall())
```

## Debug Agent

The project includes a debug agent that connects to the Electron CDP endpoint:

```bash
cd python/debug
python electron_debug_agent.py
```

See `python/debug/README.md` for more details.

## Environment Variable Debug

```python
from config import config
print(config.FORCE_SYNC_MODE)
print(config.USE_TOOL_ORCHESTRATOR)
# etc.
```
