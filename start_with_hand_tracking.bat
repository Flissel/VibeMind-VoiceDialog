@echo off
chcp 65001 > nul
echo ========================================
echo VIBEMIND - Multiverse mit Hand-Tracking
echo ========================================
echo.

REM Python 3.12 venv mit MediaPipe Support
set VENV_PATH=.venv312

REM Prüfe ob .venv312 existiert
if not exist "%VENV_PATH%\Scripts\python.exe" (
    echo ERROR: Virtual environment %VENV_PATH% nicht gefunden!
    echo Bitte erst: py -3.12 -m venv %VENV_PATH%
    echo Dann: %VENV_PATH%\Scripts\pip install -r requirements.txt mediapipe opencv-python
    pause
    exit /b 1
)

echo [1/4] Prüfe Python-Version...
%VENV_PATH%\Scripts\python -c "import sys; print(f'Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"

echo [2/4] Prüfe MediaPipe...
%VENV_PATH%\Scripts\python -c "import mediapipe; print(f'MediaPipe {mediapipe.__version__} OK')"
if errorlevel 1 (
    echo [FEHLER] MediaPipe nicht installiert!
    echo Bitte: %VENV_PATH%\Scripts\pip install mediapipe opencv-python websockets
    pause
    exit /b 1
)

echo [3/4] Starte Hand-Tracking-Server (ECHTE Webcam)...
start "VibeMind - Hand Tracking" cmd /k "cd python && ..\.venv312\Scripts\python hand_tracking_server.py"

echo.
echo Warte 3 Sekunden für Server-Start und Webcam-Init...
timeout /t 3 /nobreak > nul

echo.
echo [4/4] Starte Electron App...
cd electron-app
call npm start

echo.
echo VibeMind beendet.
pause