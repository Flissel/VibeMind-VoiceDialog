# Voice Dialog - Audio-Reactive Visual System

An audio-reactive visual simulation system with fisheye effects and dynamic colors that respond to voice and audio input. Built with C++ (OpenGL) for performance and Python for easy integration.

## Features

- **Real-time particle system** (100-1000+ particles at 60 FPS)
- **Fisheye lens effect** with audio-reactive distortion
- **Dynamic color mapping** based on audio frequencies:
  - Bass → Blue/Purple tones
  - Mid → Green/Yellow tones
  - Treble → Red/Orange tones
- **Beat detection** with visual pulses
- **Microphone input** support for live audio
- **C++/Python integration** via pybind11

## Architecture

```
┌─────────────────────────────────────┐
│   Python Application Layer          │
│   - Audio analysis (librosa)        │
│   - Demo application                │
└──────────────┬──────────────────────┘
               │ pybind11
┌──────────────▼──────────────────────┐
│   C++ Visual Simulation             │
│   - OpenGL rendering (60 FPS)       │
│   - Particle system                 │
│   - Fisheye shader                  │
│   - Audio-reactive colors           │
└─────────────────────────────────────┘
```

## Prerequisites

### Windows

Install dependencies via [vcpkg](https://vcpkg.io/):

```bash
vcpkg install glfw3:x64-windows
vcpkg install glm:x64-windows
vcpkg install glad:x64-windows
vcpkg install pybind11:x64-windows
```

### Linux

```bash
sudo apt install libglfw3-dev libglm-dev python3-dev
pip install pybind11[global]
```

### macOS

```bash
brew install glfw glm pybind11
```

## Building

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Build C++ module

```bash
# Create build directory
mkdir build
cd build

# Configure with CMake
cmake ..

# Or on Windows with vcpkg:
cmake .. -DCMAKE_TOOLCHAIN_FILE=[path to vcpkg]/scripts/buildsystems/vcpkg.cmake

# Build
cmake --build . --config Release

# On Windows, the output will be: python/visual_sim_core.pyd
# On Linux/Mac: python/visual_sim_core.so
```

### 3. Install GLAD (if not using vcpkg)

Download GLAD from https://glad.dav1d.de/ with:
- Language: C/C++
- GL Version: 3.3+
- Profile: Core

Extract to `external/glad/`

## Running the Demo

```bash
cd python
python demo.py
```

### Controls

- **SPACE** - Toggle audio input (microphone)
- **UP/DOWN** - Adjust fisheye strength
- **ESC** - Quit

## Usage in Your Application

```python
import visual_sim_core
from audio_analyzer import AudioAnalyzer
import glfw

# Initialize GLFW and create window
glfw.init()
window = glfw.create_window(800, 600, "My App", None, None)
glfw.make_context_current(window)

# Create simulation
sim = visual_sim_core.AudioReactiveSimulation(num_particles=200)
sim.initialize(800, 600)
sim.set_fisheye_strength(0.6)

# Create audio analyzer
analyzer = AudioAnalyzer()

# Main loop
while not glfw.window_should_close(window):
    # Get audio data (from microphone, ElevenLabs, etc.)
    audio_chunk = get_audio_data()  # Your audio source

    # Analyze audio
    features = analyzer.analyze(audio_chunk)

    # Convert to C++ struct
    cpp_features = visual_sim_core.AudioFeatures()
    cpp_features.amplitude = features.amplitude
    cpp_features.bass = features.bass
    cpp_features.mid = features.mid
    cpp_features.treble = features.treble
    cpp_features.spectrum = features.spectrum
    cpp_features.beat_detected = features.beat_detected

    # Update and render
    sim.update_audio(cpp_features)
    sim.update(delta_time)
    sim.render()

    glfw.swap_buffers(window)
    glfw.poll_events()

# Cleanup
sim.cleanup()
glfw.terminate()
```

## Integration with ElevenLabs Voice Agent

```python
from elevenlabs import Voice, generate
import visual_sim_core
from audio_analyzer import AudioAnalyzer
import numpy as np

# Setup simulation (as above)
sim = visual_sim_core.AudioReactiveSimulation(200)
analyzer = AudioAnalyzer()

# Generate speech with ElevenLabs
audio_stream = generate(
    text="Hello, I'm your voice assistant!",
    voice=Voice(voice_id="your_voice_id"),
    stream=True
)

# Process each audio chunk
for audio_chunk in audio_stream:
    # Convert to numpy array
    audio_np = np.frombuffer(audio_chunk, dtype=np.float32)

    # Analyze
    features = analyzer.analyze(audio_np)

    # Update visuals
    cpp_features = visual_sim_core.AudioFeatures()
    # ... (set features)
    sim.update_audio(cpp_features)
    sim.render()

    # Play audio
    play_audio(audio_chunk)
```

## Project Structure

```
voice_dialog/
├── cpp/
│   ├── include/
│   │   ├── audio_features.hpp
│   │   ├── particle.hpp
│   │   └── audio_reactive_sim.hpp
│   └── src/
│       ├── audio_reactive_sim.cpp
│       └── bindings.cpp
├── shaders/
│   ├── particle.vert
│   ├── particle.frag
│   ├── fisheye.vert
│   └── fisheye.frag
├── python/
│   ├── audio_analyzer.py
│   └── demo.py
├── CMakeLists.txt
├── requirements.txt
└── README.md
```

## Performance

- **60 FPS** with 200-500 particles on modern hardware
- **C++ handles** all rendering and physics
- **Python handles** audio analysis and application logic
- **Minimal overhead** thanks to pybind11

## Troubleshooting

### "visual_sim_core not found"

Make sure you've built the C++ module first:
```bash
mkdir build && cd build && cmake .. && cmake --build .
```

The module should be in `python/visual_sim_core.pyd` (Windows) or `python/visual_sim_core.so` (Linux/Mac).

### "Failed to load shaders"

Ensure the `shaders/` directory is in your working directory or build directory.

### Audio input not working

Check that your microphone permissions are enabled and that `sounddevice` can access your default input device:
```python
import sounddevice as sd
print(sd.query_devices())
```

## License

MIT License

## Future Enhancements

- Autogen multi-agent integration
- Desktop assistant capabilities
- OCR and symbol detection
- MCP server integration
- Advanced audio-reactive effects
