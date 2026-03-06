# Linux Installation

## Ubuntu / Debian

### 1. Install Dependencies

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip nodejs npm git
# Audio support
sudo apt install portaudio19-dev python3-dev libasound2-dev
```

### 2. Clone & Setup

```bash
git clone --recursive https://github.com/Flissel/VibeMind-VoiceDialog.git
cd VibeMind-VoiceDialog

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd electron-app && npm install && cd ..
```

### 3. Configure & Launch

```bash
cp .env.example .env
nano .env   # Set OPENAI_API_KEY
cd electron-app && npm start
```

---

## Fedora / RHEL

### 1. Install Dependencies

```bash
sudo dnf install python3.11 nodejs npm git portaudio-devel python3-devel
```

Then follow the same clone, setup, and launch steps as Ubuntu.

---

## Optional: C++ Visual Module

```bash
sudo apt install libglfw3-dev libglm-dev python3-dev cmake   # Debian/Ubuntu
sudo dnf install glfw-devel glm-devel python3-devel cmake     # Fedora

pip install pybind11[global]
mkdir build && cd build
cmake ..
cmake --build . --config Release
```

## Optional: Redis

```bash
sudo apt install redis-server    # Debian/Ubuntu
sudo dnf install redis           # Fedora
sudo systemctl start redis
# Set FORCE_SYNC_MODE=false in .env
```

## Audio Device Notes

If `sounddevice` can't find your microphone:

```bash
# List devices
python -c "import sounddevice as sd; print(sd.query_devices())"

# PulseAudio users may need
sudo apt install pulseaudio-utils
```

Ensure your user is in the `audio` group: `sudo usermod -aG audio $USER`
