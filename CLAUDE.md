# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**VibeMind Voice Dialog** is a real-time voice conversation system powered by ElevenLabs Conversational AI. The primary goal is to enable natural spoken interactions between users and AI agents, with optional audio-reactive visual effects.

**Core Components:**
- Python voice dialog system using ElevenLabs SDK
- Microphone input → AI agent → Speaker output pipeline
- Optional C++ audio-reactive visual module (OpenGL particle system)
- Simple configuration management via environment variables

## Quick Start

### First-Time Setup

```bash
cd C:\Users\User\Desktop\Voice_dialog_vibemind\VibeMind-VoiceDialog

# Create .env file from template
copy .env.template .env

# Edit .env and add your ElevenLabs credentials
notepad .env
```

Required credentials:
- `ELEVENLABS_API_KEY` - From [ElevenLabs API Keys](https://elevenlabs.io/app/settings/api-keys)
- `ELEVENLABS_AGENT_ID` - Create agent at [ElevenLabs Conversational AI](https://elevenlabs.io/app/conversational-ai)

### Install Dependencies

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Run Voice Dialog

```bash
cd python
python voice_dialog_main.py
```

Speak into your microphone - the AI agent will respond with voice!

## Architecture

### Voice Dialog System

The system follows a simple pipeline:

```
Microphone (16kHz)
    ↓
VoiceDialog Client (elevenlabs_voice_dialog.py)
    ↓
ElevenLabs Conversational AI (cloud)
    ↓
Agent Audio Response (22kHz)
    ↓
Speaker Output + Optional Visuals
```

**Key Files:**

1. **[python/voice_dialog_main.py](python/voice_dialog_main.py)** - Main entry point
   - Manages audio capture loop with sounddevice
   - Coordinates microphone → ElevenLabs → speaker pipeline
   - Handles user interrupts (Ctrl+C)

2. **[python/elevenlabs_voice_dialog.py](python/elevenlabs_voice_dialog.py)** - ElevenLabs client wrapper
   - Wraps ElevenLabs Conversational AI SDK
   - Manages conversation session lifecycle
   - Provides callbacks for agent responses and user transcripts

3. **[python/audio_analyzer.py](python/audio_analyzer.py)** - Audio feature extraction
   - Extracts amplitude, frequency bands (bass/mid/treble)
   - Beat detection
   - Used for optional visual effects

4. **[python/config.py](python/config.py)** - Configuration management
   - Loads settings from `.env` file
   - Validates required credentials (API keys, agent ID)
   - Manages logging configuration

### Optional Visual Module (C++)

The project includes an optional audio-reactive visual system:

- **Location:** `cpp/src/` and `cpp/include/`
- **Technology:** C++ with OpenGL, exposed to Python via pybind11
- **Features:** Particle system, fisheye effects, frequency-based colors
- **Not Required:** Voice dialog works without building this module

## Common Commands

### Running the Voice Dialog

```bash
cd python
python voice_dialog_main.py
```

**Controls:**
- Speak into microphone to talk
- Ctrl+C to exit

### Testing Configuration

```bash
cd python
python -c "from config import get_config, validate_config; print(get_config()); validate_config(strict=True)"
```

### Building Visual Module (Optional)

**Prerequisites (Windows):**
```bash
vcpkg install glfw3:x64-windows glm:x64-windows glad:x64-windows pybind11:x64-windows
```

**Build:**
```bash
mkdir build
cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=[path to vcpkg]/scripts/buildsystems/vcpkg.cmake
cmake --build . --config Release

# Output: python/visual_sim_core.pyd
```

## Configuration

All configuration is managed through `.env` file:

```bash
# Required
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_AGENT_ID=your_agent_id

# Optional
OPENAI_API_KEY=your_openai_key      # Future use
LOG_LEVEL=INFO                       # DEBUG, INFO, WARNING, ERROR
LOG_FILE=voice_dialog.log
```

**Important:** Never commit `.env` to version control! Use `.env.template` as the reference.

## Code Structure

```
VibeMind-VoiceDialog/
├── python/
│   ├── voice_dialog_main.py          # Main application entry
│   ├── elevenlabs_voice_dialog.py    # ElevenLabs client wrapper
│   ├── audio_analyzer.py             # Audio feature extraction
│   ├── config.py                     # Configuration management
│   └── logger.py                     # Structured logging
├── cpp/                              # Optional visual module
│   ├── include/
│   │   ├── audio_reactive_sim.hpp    # Main simulation class
│   │   ├── audio_features.hpp        # Audio data structures
│   │   └── particle.hpp              # Particle system
│   └── src/
│       ├── audio_reactive_sim.cpp    # OpenGL rendering
│       └── bindings.cpp              # pybind11 Python bindings
├── shaders/                          # GLSL shaders (optional)
│   ├── particle.vert/frag            # Particle rendering
│   └── fisheye.vert/frag             # Fisheye effect
├── CMakeLists.txt                    # C++ build configuration
├── requirements.txt                  # Python dependencies
├── .env.template                     # Configuration template
└── .gitignore                        # Includes .env
```

## Key Implementation Details

### ElevenLabs Integration

The `VoiceDialog` class wraps the ElevenLabs SDK:

```python
# Initialize
dialog = VoiceDialog(
    agent_id="your_agent_id",
    on_agent_response=lambda audio: play_audio(audio),
    on_user_transcript=lambda text: print(f"You: {text}")
)

# Start conversation
await dialog.start_conversation()

# Send audio chunks from microphone
await dialog.send_audio(audio_data)

# End when done
await dialog.end_conversation()
```

**Audio Format:**
- Input (microphone): 16kHz, mono, numpy float32 array
- Output (agent): 22kHz, varies by agent configuration

### Audio Capture Loop

The main application uses `sounddevice.InputStream` for real-time capture:

```python
def audio_callback(indata, frames, time, status):
    # Called for each 1-second chunk
    audio_data = indata.copy().flatten()
    asyncio.create_task(dialog.send_audio(audio_data))

with sd.InputStream(samplerate=16000, channels=1,
                    callback=audio_callback, blocksize=chunk_size):
    while running:
        await asyncio.sleep(0.1)
```

### Optional Visual Effects

If the C++ module is built, audio features can drive visuals:

```python
from audio_analyzer import AudioAnalyzer
import visual_sim_core

analyzer = AudioAnalyzer()
sim = visual_sim_core.AudioReactiveSimulation(200)

# In audio callback:
features = analyzer.analyze(audio_chunk)
cpp_features = visual_sim_core.AudioFeatures()
cpp_features.amplitude = features.amplitude
cpp_features.bass = features.bass
cpp_features.mid = features.mid
cpp_features.treble = features.treble

sim.update_audio(cpp_features)
sim.render()
```

## Common Pitfalls

1. **Missing API Keys**: If you see "ELEVENLABS_API_KEY not found", check that `.env` exists and contains valid credentials.

2. **Microphone Access**: Windows may require microphone permissions. Check Settings → Privacy → Microphone.

3. **Audio Device Selection**: If audio input/output isn't working, check available devices:
   ```python
   import sounddevice as sd
   print(sd.query_devices())
   ```

4. **Agent Not Responding**: Verify your agent is active in ElevenLabs dashboard. Check conversation logs for errors.

5. **Visual Module Missing**: This is expected! The visual module is optional. Voice dialog works without it.

## Development Workflow

### Making Changes to Voice Dialog

1. Edit Python files in `python/` directory
2. No build step required (pure Python)
3. Run `python voice_dialog_main.py` to test
4. Check logs in `voice_dialog.log` if issues occur

### Making Changes to Visual Module

1. Edit C++ files in `cpp/src/` or `cpp/include/`
2. Rebuild:
   ```bash
   cd build
   cmake --build . --config Release
   ```
3. Output overwrites `python/visual_sim_core.pyd`
4. Restart Python application to load new module

### Testing

Currently no automated tests. Manual testing workflow:

1. Start voice dialog: `python voice_dialog_main.py`
2. Speak test phrases
3. Verify agent responds appropriately
4. Check console output for errors
5. Review `voice_dialog.log` for detailed logs

## Platform Notes

### Windows

- **Tested on:** Windows 10/11
- **Python:** 3.8+
- **Build Tools:** Visual Studio 2022 (for C++ module)
- **Audio:** Uses Windows audio APIs via sounddevice

### Linux/Mac

- **Status:** Not extensively tested, but should work
- **Dependencies:** Install system packages (see README.md)
- **C++ Module:** Uses GLFW (cross-platform)
- **Note:** Adjust file paths in config if needed

## Related Documentation

- **[README.md](README.md)** - User-facing documentation with setup instructions
- **[requirements.txt](requirements.txt)** - Python dependencies with version constraints
- **[.env.template](.env.template)** - Configuration template with examples

## Future Enhancements

Potential areas for expansion:

- Multiple conversation modes (chat, command, assistant)
- Custom agent personalities and voices
- Integration with other AI frameworks
- Advanced visual effects synchronized with speech patterns
- Multi-language support
- Voice activity detection (VAD) for better turn-taking

## Troubleshooting Guide

### "Module 'elevenlabs' not found"

```bash
pip install elevenlabs>=1.0.0
```

### "sounddevice not working"

On Windows, ensure you have audio drivers installed. On Linux:
```bash
sudo apt install portaudio19-dev
pip install --upgrade sounddevice
```

### "Conversation session failed"

- Verify API key is valid and has credits
- Check agent ID exists in ElevenLabs dashboard
- Ensure internet connection is stable
- Review ElevenLabs service status

### High Latency in Responses

- ElevenLabs latency depends on internet speed and server load
- Audio chunk size affects responsiveness (current: 1 second chunks)
- Consider adjusting `chunk_duration` in `voice_dialog_main.py`

## Contact & Support

For issues specific to:
- **ElevenLabs SDK:** Check [ElevenLabs Documentation](https://docs.elevenlabs.io/)
- **This repository:** Create an issue on GitHub

---

**Note for Claude Code:** This repository is focused exclusively on voice dialog functionality. Desktop interaction, research agents, and code agents have been removed. If asked about MoireTracker, IPC, or multi-agent orchestration, clarify that this functionality is not part of the current codebase.
