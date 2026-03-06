# Windows Installation

## 1. Install Python 3.11+

Download from [python.org](https://www.python.org/downloads/) or use pyenv-win:

```powershell
# Option A: pyenv-win (recommended for managing versions)
pip install pyenv-win --target %USERPROFILE%\.pyenv
pyenv install 3.11.0
pyenv global 3.11.0

# Option B: Direct download
# https://www.python.org/downloads/ — check "Add to PATH" during install
```

Verify: `python --version` should show 3.11+

## 2. Install Node.js 18+

Download from [nodejs.org](https://nodejs.org/) (LTS recommended).

Verify: `node --version` and `npm --version`

## 3. Clone Repository

```powershell
git clone --recursive https://github.com/Flissel/VibeMind-VoiceDialog.git
cd VibeMind-VoiceDialog
```

## 4. Python Environment

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> **Note:** Some packages (torch, mediapipe) are large. The full install is ~4GB. For a lighter install, comment out optional dependencies in `requirements.txt`.

## 5. Electron App

```powershell
cd electron-app
npm install
cd ..
```

## 6. Configuration

```powershell
copy .env.example .env
notepad .env
```

Set at minimum:
```
OPENAI_API_KEY=sk-your-key-here
FORCE_SYNC_MODE=true
```

## 7. Launch

```powershell
cd electron-app
npm start
```

Or use the batch launchers:
```powershell
start_vibemind_production.bat    # Headless, no debug
start_vibemind_debug.bat         # With Chrome DevTools port 9222
```

## 8. Verify

- Electron window should open with a dark 3D scene
- Python backend log appears in the terminal
- Speak "Erstelle eine Bubble Test" — a bubble should appear

## Optional: C++ Visual Module

```powershell
vcpkg install glfw3:x64-windows glm:x64-windows glad:x64-windows pybind11:x64-windows
mkdir build && cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=[vcpkg-root]/scripts/buildsystems/vcpkg.cmake
cmake --build . --config Release
```

Output: `python/visual_sim_core.pyd`

## Optional: Redis

Download [Redis for Windows](https://github.com/tporadowski/redis/releases) or use Docker:

```powershell
docker run -d -p 6379:6379 redis:alpine
```

Then set `FORCE_SYNC_MODE=false` in `.env`.
