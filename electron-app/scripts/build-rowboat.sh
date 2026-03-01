#!/usr/bin/env bash
#
# build-rowboat.sh — Build Rowboat workspace packages and produce:
#   1. Renderer dist (apps/renderer/dist/)
#   2. Preload bundle (apps/preload/dist/preload.js)
#   3. Services CJS bundle (electron-app/rowboat-services.cjs)
#
# Usage: bash scripts/build-rowboat.sh
# Run from electron-app/ directory.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ELECTRON_APP_DIR="$(dirname "$SCRIPT_DIR")"
ROWBOAT_X_DIR="$ELECTRON_APP_DIR/../python/spaces/rowboat/rowboat/apps/x"

echo "=== Rowboat Build Pipeline ==="
echo "    Workspace: $ROWBOAT_X_DIR"
echo ""

# --- Step 0: Check pnpm ---
if ! command -v pnpm &>/dev/null; then
    echo "[0/7] pnpm not found, installing globally..."
    npm install -g pnpm
fi
echo "[0/7] pnpm: $(pnpm --version)"

# --- Step 1: Install dependencies ---
echo "[1/7] Installing dependencies..."
cd "$ROWBOAT_X_DIR"
pnpm install --frozen-lockfile 2>/dev/null || pnpm install

# --- Step 2: Build @x/shared ---
echo "[2/7] Building @x/shared..."
cd "$ROWBOAT_X_DIR/packages/shared"
pnpm run build

# --- Step 3: Build @x/core ---
echo "[3/7] Building @x/core..."
cd "$ROWBOAT_X_DIR/packages/core"
pnpm run build

# --- Step 4: Build preload ---
echo "[4/7] Building preload..."
cd "$ROWBOAT_X_DIR/apps/preload"
pnpm run build

# --- Step 5: Build renderer ---
echo "[5/7] Building renderer (Vite)..."
cd "$ROWBOAT_X_DIR/apps/renderer"
pnpm run build

# --- Step 6: Build main (TypeScript only, for services-only.js) ---
echo "[6/7] Compiling main process TypeScript..."
cd "$ROWBOAT_X_DIR/apps/main"
rm -rf dist
npx tsc

# --- Step 7: Bundle services-only → rowboat-services.cjs ---
echo "[7/7] Bundling services for VibeMind..."
cd "$ROWBOAT_X_DIR/apps/main"
node bundle-services.mjs

echo ""
echo "=== Build Complete ==="

# Verify outputs
RENDERER_DIST="$ROWBOAT_X_DIR/apps/renderer/dist/index.html"
PRELOAD_DIST="$ROWBOAT_X_DIR/apps/preload/dist/preload.js"
SERVICES_CJS="$ELECTRON_APP_DIR/rowboat-services.cjs"

OK=true
for f in "$RENDERER_DIST" "$PRELOAD_DIST" "$SERVICES_CJS"; do
    if [ -f "$f" ]; then
        echo "    OK: $(basename "$f")"
    else
        echo "    MISSING: $f"
        OK=false
    fi
done

if [ "$OK" = true ]; then
    echo ""
    echo "All outputs verified. Ready to launch VibeMind."
else
    echo ""
    echo "Some outputs are missing. Check errors above."
    exit 1
fi
