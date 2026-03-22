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
REM Set MOIRE_ROOT via environment variable or default to sibling directory
if not defined MOIRE_ROOT set MOIRE_ROOT=%PROJECT_ROOT%\..\MoireTracker_v2

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
docker compose -f "%PROJECT_ROOT%\docker-compose.minibook.yml" up -d 2>nul
if %errorlevel%==0 (
    echo Minibook started (Backend :3480, Frontend :3481^)
    timeout /t 3 /nobreak > nul
) else (
    echo Warning: Minibook Docker failed - collaboration disabled
)
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
    docker compose -f "%PROJECT_ROOT%\docker-compose.mirofish.yml" up -d 2>nul
    if %errorlevel%==0 (
        echo MiroFish started (Flask :5001^)
        timeout /t 2 /nobreak > nul
    ) else (
        echo Warning: MiroFish Docker failed - prediction engine disabled
    )
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
