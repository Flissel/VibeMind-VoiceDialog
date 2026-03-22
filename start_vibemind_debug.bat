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

REM Kill any existing Electron processes early
echo Cleaning up old Electron processes...
taskkill /F /IM electron.exe 2>nul

REM Kill stale Python processes holding camera/ports from previous crashes
echo Cleaning up stale Python processes on eyeTerm ports...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8099" ^| findstr "LISTENING"') do (
    echo Killing stale process on port 8099: PID %%a
    taskkill /F /PID %%a 2>nul
)

REM ================================================
REM Start MoireServer for advanced OCR (port 8766)
REM WINDOWED MODE - for debugging
REM ================================================
echo.
echo Checking MoireServer...
REM Set MOIRE_ROOT via environment variable or default to sibling directory
if not defined MOIRE_ROOT set MOIRE_ROOT=%PROJECT_ROOT%\..\MoireTracker_v2

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
REM Start Minibook Docker (ports 3480/3481)
REM ================================================
echo.
echo Checking Minibook...

netstat -an | findstr ":3480" | findstr "LISTENING" > nul
if %errorlevel%==0 (
    echo Minibook already running on port 3480
    goto :minibook_done
)
echo Starting Minibook Docker containers...
REM Use --no-build to avoid blocking on first-time image builds
REM Pre-build with: docker compose -f docker-compose.minibook.yml build
start /B cmd /c "docker compose -f "%PROJECT_ROOT%\docker-compose.minibook.yml" up -d 2>nul && echo Minibook started || echo Warning: Minibook Docker failed" > nul 2>&1
echo Minibook starting in background (Backend :3480, Frontend :3481^)
timeout /t 2 /nobreak > nul
:minibook_done

REM ================================================
REM Start MiroFish Docker (port 5001)
REM ================================================
echo.
echo Checking MiroFish...

netstat -an | findstr ":5001" | findstr "LISTENING" > nul
if %errorlevel%==0 (
    echo MiroFish already running on port 5001
    goto :mirofish_done
)
if exist "%PROJECT_ROOT%\docker-compose.mirofish.yml" (
    echo Starting MiroFish Docker containers...
    start /B cmd /c "docker compose -f "%PROJECT_ROOT%\docker-compose.mirofish.yml" up -d 2>nul && echo MiroFish started || echo Warning: MiroFish Docker failed" > nul 2>&1
    echo MiroFish starting in background (Flask :5001^)
    timeout /t 2 /nobreak > nul
) else (
    echo docker-compose.mirofish.yml not found, skipping MiroFish
)
:mirofish_done

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

REM ================================================
REM Use port 9223 for Electron DevTools
REM (9222 is Chrome/MoireServer default - causes race conditions)
REM ================================================
echo.
set DEBUG_PORT=9223

REM Start Electron with debug port (in new window)
echo Starting Electron with debug port %DEBUG_PORT%...
echo Project root: %PROJECT_ROOT%
start "VibeMind Electron" "%PROJECT_ROOT%\electron-app\node_modules\electron\dist\electron.exe" --remote-debugging-port=%DEBUG_PORT% "%PROJECT_ROOT%\electron-app"

REM Wait for Electron to fully start (Rowboat, Python backend, etc.)
echo Waiting for Electron to start (8s)...
timeout /t 8 /nobreak > nul

REM Verify DevTools port is up
netstat -an | findstr ":%DEBUG_PORT%" | findstr "LISTENING" > nul
if %errorlevel%==0 (
    echo Electron DevTools ready on port %DEBUG_PORT%
) else (
    echo Warning: DevTools port %DEBUG_PORT% not yet listening - Debug Agent will retry
)

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