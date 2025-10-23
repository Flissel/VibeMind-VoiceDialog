# Quick Start Guide

Get the audio-reactive visual system running in 5 minutes!

## Step 1: Install Dependencies

### Windows

Install vcpkg first (if you haven't):
```powershell
git clone https://github.com/microsoft/vcpkg
cd vcpkg
.\bootstrap-vcpkg.bat
```

Then install packages:
```powershell
.\vcpkg install glfw3:x64-windows glm:x64-windows glad:x64-windows pybind11:x64-windows
```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install build-essential cmake libglfw3-dev libglm-dev python3-dev python3-pip
pip3 install pybind11[global]
```

### macOS

```bash
brew install cmake glfw glm pybind11
```

## Step 2: Install Python Packages

```bash
pip install -r requirements.txt
```

## Step 3: Build the Project

### Windows

```batch
build.bat
```

### Linux/macOS

```bash
chmod +x build.sh
./build.sh
```

## Step 4: Run the Demo

```bash
cd python
python demo.py
```

## What You'll See

A window with colorful particles that:
- Move and swirl in patterns
- Change colors dynamically
- Display fisheye lens distortion
- Respond to audio (press SPACE to enable microphone)

## Controls

- **SPACE** - Enable/disable microphone input
- **UP** - Increase fisheye effect
- **DOWN** - Decrease fisheye effect
- **ESC** - Exit

## Next Steps

### Integrate with ElevenLabs

```python
from elevenlabs import Voice, generate
import visual_sim_core
from audio_analyzer import AudioAnalyzer

# Your code here...
```

See README.md for complete examples.

### Add to Autogen Agent

```python
import autogen
from voice_visual_system import VoiceVisualSystem

class VisualAgent(autogen.ConversableAgent):
    def __init__(self):
        super().__init__(name="Visual_Agent")
        self.visuals = VoiceVisualSystem()

    async def speak(self, text):
        await self.visuals.speak_with_visuals(text)
```

### Customize

Edit `cpp/src/audio_reactive_sim.cpp` to:
- Change particle behavior
- Modify color schemes
- Adjust fisheye parameters
- Add new visual effects

Then rebuild with `build.bat` or `build.sh`.

## Troubleshooting

**"visual_sim_core not found"**
- Make sure the build succeeded
- Check that `python/visual_sim_core.pyd` (Windows) or `python/visual_sim_core.so` (Linux/Mac) exists

**"Failed to load shaders"**
- Run `python demo.py` from the `python/` directory
- Or copy the `shaders/` folder to your working directory

**Black screen**
- Check OpenGL support: `glxinfo | grep OpenGL` (Linux)
- Update graphics drivers
- Try reducing number of particles

**No audio input**
- Check microphone permissions
- Run: `python -c "import sounddevice; print(sounddevice.query_devices())"`

## Support

For issues or questions, check:
- README.md for detailed documentation
- CMakeLists.txt for build configuration
- demo.py for usage examples
