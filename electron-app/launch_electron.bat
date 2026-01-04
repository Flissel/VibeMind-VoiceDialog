@echo off
REM VibeMind Electron Launcher
REM Important: ELECTRON_RUN_AS_NODE must be unset for proper Electron operation

set ELECTRON_RUN_AS_NODE=

REM Change to the project root directory (parent of electron-app)
cd /d %~dp0..

REM Run electron from the electron-app folder
node_modules\electron\dist\electron.exe electron-app
