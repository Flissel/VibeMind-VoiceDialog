# macOS Installation

## 1. Install Dependencies

```bash
# Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 3.11+ and Node.js
brew install python@3.11 node git
```

## 2. Clone Repository

```bash
git clone --recursive https://github.com/Flissel/VibeMind-VoiceDialog.git
cd VibeMind-VoiceDialog
```

## 3. Python Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Apple Silicon (M1/M2/M3):** If torch fails, install with: `pip install torch --index-url https://download.pytorch.org/whl/cpu`

## 4. Electron App

```bash
cd electron-app
npm install
cd ..
```

## 5. Configure & Launch

```bash
cp .env.example .env
# Edit .env with your OPENAI_API_KEY
cd electron-app && npm start
```

## Optional: C++ Visual Module

```bash
brew install glfw glm pybind11 cmake
mkdir build && cd build
cmake ..
cmake --build . --config Release
```

## Optional: Redis

```bash
brew install redis
brew services start redis
# Set FORCE_SYNC_MODE=false in .env
```

## Microphone Permissions

macOS requires microphone access. When prompted, allow the Terminal/Electron app to use the microphone. Check in System Settings > Privacy & Security > Microphone.
