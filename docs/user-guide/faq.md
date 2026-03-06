# FAQ

## General

**What is VibeMind?**
A voice-controlled workspace where you speak ideas into a 3D multiverse of bubbles. It uses AI to classify your intent, execute actions, and organize your thoughts visually.

**What languages does it support?**
German (primary) and English. The intent classifier handles both. You can mix languages freely.

**Do I need an internet connection?**
Yes — the OpenAI Realtime API requires internet for voice processing and intent classification. The database and UI work locally.

**Is my voice data stored?**
Voice audio is processed by OpenAI's Realtime API (see their privacy policy). Transcribed text is stored locally in SQLite for conversation history. No audio is stored locally.

## Setup

**What's the minimum I need to get started?**
Python 3.11+, Node.js 18+, and an OpenAI API key. Set `FORCE_SYNC_MODE=true` for zero-dependency local mode.

**Do I need Redis?**
No — sync mode (`FORCE_SYNC_MODE=true`) works without Redis. Redis is only needed for async event processing in production.

**Do I need all the submodules?**
No — core features (Ideas, voice, 3D UI) work without any submodules. Submodules enable extra spaces (Coding, Rowboat, etc.).

**How much does it cost to run?**
OpenAI Realtime API charges per token/minute of audio. Basic usage is ~$0.06/minute of conversation. Intent classification uses standard GPT-4o pricing.

## Usage

**Can I type instead of speaking?**
Yes — the Electron UI has a text input. Messages sent there bypass the voice layer and go directly to intent classification.

**How do I navigate?**
Say "Geh in [Bubble Name]" to enter a bubble. Say "Zurueck" to go back. Or click bubbles in the 3D scene.

**Can I export my ideas?**
Ideas are stored in SQLite (`python/vibemind.db`). You can query them directly or use the summarize/whitepaper tools to generate formatted output.

**What are the format types?**
note, action_list, pros_cons, hierarchy, specs, kanban, mindmap, swot, user_story, flowchart

## Troubleshooting

**"No audio device found"**
Check your microphone permissions and run `python -c "import sounddevice as sd; print(sd.query_devices())"` to verify.

**Voice commands aren't being recognized**
Check `python/logs/intents/` for what the classifier received. The input might be misheard. Enable `USE_INTENT_ANALYSIS=true` for better preprocessing.

**The 3D scene is blank**
Try launching with `--disable-gpu` flag. Some GPU drivers have issues with WebGL in Electron.

See [docs/installation/troubleshooting.md](../installation/troubleshooting.md) for more.
