#!/bin/bash
# VibeMind Electron Launcher
# Uses clean environment to avoid conflicts with bash variables

cd "$(dirname "$0")"

# Clear problematic environment variables and run Electron
env -i \
    PATH="$PATH" \
    HOME="$HOME" \
    USERPROFILE="$USERPROFILE" \
    APPDATA="$APPDATA" \
    LOCALAPPDATA="$LOCALAPPDATA" \
    SYSTEMROOT="$SYSTEMROOT" \
    ./node_modules/electron/dist/electron.exe .
