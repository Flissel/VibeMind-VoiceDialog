@echo off
REM VibeMind Debug Launcher
REM Starts Electron with CDP debug port and the Debug Agent

echo ================================================
echo VibeMind Debug Mode
echo ================================================
echo.

REM Set environment and get absolute path
set ELECTRON_RUN_AS_NODE=
cd /d %~dp0
set PROJECT_ROOT=%cd%

REM Check if port 9222 is already in use
netstat -an | findstr ":9222" > nul
if %errorlevel%==0 (
    echo Warning: Port 9222 already in use
    echo Killing existing process...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":9222"') do taskkill /F /PID %%a 2>nul
    timeout /t 2 /nobreak > nul
)

REM ================================================
REM Start MoireServer for advanced OCR (port 8766)
REM WINDOWED MODE - for debugging
REM ================================================
echo.
echo Checking MoireServer...
set MOIRE_ROOT=C:\Users\User\Desktop\Moire_tracker_v1\MoireTracker_v2

netstat -an | findstr ":8766" | findstr "LISTENING" > nul
if %errorlevel%==0 (
    echo MoireServer already running on port 8766
) else (
    echo Starting MoireServer...
    start "MoireServer" /D "%MOIRE_ROOT%" cmd /c npm start
    echo Waiting for MoireServer to start...
    timeout /t 5 /nobreak > nul
)

REM ================================================
REM Check Redis for Claude Orchestrator (port 6379)
REM ================================================
REM Check for port 6379 (works on English "LISTENING" and German "ABHÖREN")
netstat -an | findstr "0.0.0.0:6379" > nul
if %errorlevel%==0 (
    echo Redis running on port 6379
) else (
    echo Warning: Redis not running - Claude Orchestrator tools unavailable
)
echo.

REM Check if electron is installed
if not exist "electron-app\node_modules\electron\dist\electron.exe" (
    echo ERROR: Electron not installed!
    echo Run: cd electron-app ^&^& npm install
    pause
    exit /b 1
)

REM Start Electron with debug port (in new window)
echo Starting Electron with debug port 9222...
echo Project root: %PROJECT_ROOT%
start "VibeMind Electron" "%PROJECT_ROOT%\electron-app\node_modules\electron\dist\electron.exe" --remote-debugging-port=9222 "%PROJECT_ROOT%\electron-app"

REM Wait for Electron to start
echo Waiting for Electron to start...
timeout /t 5 /nobreak > nul

REM Info: Debug Agent will try multiple ports (9222, 9223, 9224)
echo Electron started. Debug Agent will automatically find the correct port.

echo.
echo ================================================
echo Starting Debug Agent...
echo ================================================
echo.
echo Logs will be saved to: logs\electron_debug\
echo Press Ctrl+C to stop
echo.

REM Start Debug Agent
cd python\debug
python electron_debug_agent.py

echo.
echo Debug session ended.
pause