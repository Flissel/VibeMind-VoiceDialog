# VibeMind Voice Dialog

A voice conversation system powered by ElevenLabs Conversational AI, with optional audio-reactive visual effects.

## Features

- **Real-time voice conversations** with ElevenLabs AI agents
- **Microphone input** for natural spoken interaction
- **Audio-reactive visuals** (optional C++ OpenGL module)
- **Simple Python API** for easy integration

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy the template and add your ElevenLabs credentials:

```bash
copy .env.template .env
notepad .env
```

Required settings:
- `ELEVENLABS_API_KEY` - Get from [ElevenLabs API Keys](https://elevenlabs.io/app/settings/api-keys)
- `ELEVENLABS_AGENT_ID` - Create an agent at [ElevenLabs Conversational AI](https://elevenlabs.io/app/conversational-ai)

### 3. Run Voice Dialog

```bash
cd python
python voice_dialog_main.py
```

Speak into your microphone to start a conversation with your AI agent!

## How It Works

```
┌─────────────────────────────────────┐
│   Your Microphone                   │
└──────────────┬──────────────────────┘
               │ Audio stream (16kHz)
┌──────────────▼──────────────────────┐
│   VoiceDialog Client                │
│   - Sends audio to ElevenLabs       │
│   - Receives agent responses        │
└──────────────┬──────────────────────┘
               │ Agent audio
┌──────────────▼──────────────────────┐
│   Speaker Output                    │
│   + Optional Visual Effects         │
└─────────────────────────────────────┘
```

## Architecture

### Core Components

- **[voice_dialog_main.py](python/voice_dialog_main.py)** - Main application entry point
- **[elevenlabs_voice_dialog.py](python/elevenlabs_voice_dialog.py)** - ElevenLabs client wrapper
- **[audio_analyzer.py](python/audio_analyzer.py)** - Audio feature extraction for visuals
- **[config.py](python/config.py)** - Configuration management

### Optional Visual Module (C++)

The project includes an optional audio-reactive visual system built with C++ and OpenGL:

- Real-time particle effects (60 FPS)
- Fisheye lens distortion
- Dynamic colors responding to audio frequencies
- Bass → Blue/Purple, Mid → Green/Yellow, Treble → Red/Orange

See [Building the Visual Module](#building-the-visual-module-optional) for compilation instructions.

## Usage in Your Application

```python
import asyncio
from elevenlabs_voice_dialog import VoiceDialog
import sounddevice as sd

async def main():
    # Create voice dialog client
    dialog = VoiceDialog(
        agent_id="your_agent_id",
        on_agent_response=lambda audio: sd.play(audio, samplerate=22050),
        on_user_transcript=lambda text: print(f"You: {text}")
    )

    # Start conversation
    await dialog.start_conversation()

    # Send audio from microphone
    # (see voice_dialog_main.py for full implementation)

    # End when done
    await dialog.end_conversation()

asyncio.run(main())
```

## Building the Visual Module (Optional)

The audio-reactive visual system requires C++ compilation:

### Prerequisites

**Windows:**
```bash
vcpkg install glfw3:x64-windows glm:x64-windows glad:x64-windows pybind11:x64-windows
```

**Linux:**
```bash
sudo apt install libglfw3-dev libglm-dev python3-dev
pip install pybind11[global]
```

**macOS:**
```bash
brew install glfw glm pybind11
```

### Build Steps

```bash
mkdir build
cd build

# Configure
cmake .. -DCMAKE_TOOLCHAIN_FILE=[path to vcpkg]/scripts/buildsystems/vcpkg.cmake

# Build
cmake --build . --config Release

# Output: python/visual_sim_core.pyd (Windows) or python/visual_sim_core.so (Linux/Mac)
```

### Using Visuals

```python
import visual_sim_core
from audio_analyzer import AudioAnalyzer

# Create simulation
sim = visual_sim_core.AudioReactiveSimulation(num_particles=200)
sim.initialize(800, 600)
sim.set_fisheye_strength(0.6)

# Analyze audio and update visuals
analyzer = AudioAnalyzer()
features = analyzer.analyze(audio_chunk)

cpp_features = visual_sim_core.AudioFeatures()
cpp_features.amplitude = features.amplitude
cpp_features.bass = features.bass
cpp_features.mid = features.mid
cpp_features.treble = features.treble

sim.update_audio(cpp_features)
sim.render()
```

## Project Structure

```
VibeMind-VoiceDialog/
├── python/
│   ├── voice_dialog_main.py          # Main entry point
│   ├── elevenlabs_voice_dialog.py    # ElevenLabs client
│   ├── audio_analyzer.py             # Audio analysis
│   ├── config.py                     # Configuration
│   └── logger.py                     # Logging utilities
├── cpp/                              # Optional visual module
│   ├── include/
│   │   ├── audio_reactive_sim.hpp
│   │   └── particle.hpp
│   └── src/
│       ├── audio_reactive_sim.cpp
│       └── bindings.cpp
├── shaders/                          # GLSL shaders for visuals
│   ├── particle.vert/frag
│   └── fisheye.vert/frag
├── CMakeLists.txt                    # C++ build configuration
├── requirements.txt                  # Python dependencies
├── .env.template                     # Configuration template
└── README.md
```

## Configuration

Configuration is managed through environment variables in `.env`:

```bash
# Required
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_AGENT_ID=your_agent_id

# Optional
OPENAI_API_KEY=your_openai_key      # Fallback for additional features
LOG_LEVEL=INFO                       # DEBUG, INFO, WARNING, ERROR
LOG_FILE=voice_dialog.log           # Log file location
```

## Troubleshooting

### "ELEVENLABS_API_KEY not found"

Make sure you've created a `.env` file from `.env.template` and added your API key.

### Audio input not working

Check your microphone permissions and default device:

```python
import sounddevice as sd
print(sd.query_devices())
```

### Visual module not loading

Ensure you've built the C++ module:
- Windows: `python/visual_sim_core.pyd` should exist
- Linux/Mac: `python/visual_sim_core.so` should exist

The visual module is optional - voice dialog works without it.

## Performance

- **60 FPS** rendering with 200-500 particles (optional visuals)
- **Low latency** voice streaming via ElevenLabs SDK
- **Real-time** audio analysis with librosa

## License

MIT License

## Future Enhancements

- Multi-modal interactions
- Advanced audio-reactive effects
- Custom agent personalities
- Integration with other AI frameworks
