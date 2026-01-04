@echo off
REM VibeMind Production Launcher
REM Starts services in headless/minimized mode

echo ================================================
echo VibeMind Production Mode
echo ================================================
echo.

REM Clear ELECTRON_RUN_AS_NODE if set (fixes Electron module loading)
set ELECTRON_RUN_AS_NODE=

cd /d %~dp0
set PROJECT_ROOT=%cd%
set MOIRE_ROOT=C:\Users\User\Desktop\Moire_tracker_v1\MoireTracker_v2

REM ================================================
REM Start MoireServer HEADLESS (minimized)
REM ================================================
echo Checking MoireServer...
netstat -an | findstr ":8766" | findstr "LISTENING" > nul
if %errorlevel%==0 (
    echo MoireServer already running on port 8766
) else (
    echo Starting MoireServer (headless)...
    start /MIN "MoireServer" /D "%MOIRE_ROOT%" cmd /c npm start
    echo Waiting for MoireServer to start...
    timeout /t 5 /nobreak > nul
)

REM ================================================
REM Check Redis for Claude Orchestrator (port 6379)
REM ================================================
netstat -an | findstr ":6379" | findstr "LISTENING" > nul
if %errorlevel%==0 (
    echo Redis running on port 6379
) else (
    echo Warning: Redis not running - Claude Orchestrator tools unavailable
)

REM ================================================
REM Check Electron
REM ================================================
if not exist "electron-app\node_modules\electron\dist\electron.exe" (
    echo ERROR: Electron not installed!
    echo Run: cd electron-app ^&^& npm install
    pause
    exit /b 1
)

REM ================================================
REM Start Electron (no debug port)
REM ================================================
echo.
echo Starting VibeMind...
"%PROJECT_ROOT%\electron-app\node_modules\electron\dist\electron.exe" "%PROJECT_ROOT%\electron-app"
