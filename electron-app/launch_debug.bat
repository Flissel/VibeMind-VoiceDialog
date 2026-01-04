@echo off
REM Launch Electron with Debug/Inspect Port
REM This script explicitly clears ELECTRON_RUN_AS_NODE and starts with inspect

REM Clear the problematic environment variable
set ELECTRON_RUN_AS_NODE=

REM Get the script directory
set SCRIPT_DIR=%~dp0

REM Change to the project root directory (for .env access)
cd /d %SCRIPT_DIR%..

echo Starting Electron with debug port 9222...
echo Working directory: %cd%
echo Script dir: %SCRIPT_DIR%

REM Run electron with inspect flag
REM IMPORTANT: --inspect must come BEFORE the app path
%SCRIPT_DIR%node_modules\electron\dist\electron.exe --inspect=9222 %SCRIPT_DIR%

echo.
echo Electron closed.
pause