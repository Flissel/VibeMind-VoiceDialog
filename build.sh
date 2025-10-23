#!/bin/bash
# Build script for Linux/macOS

set -e

echo "=== Building Voice Dialog Visual System ==="
echo

# Create build directory
mkdir -p build
cd build

echo "Configuring CMake..."
cmake .. -DCMAKE_BUILD_TYPE=Release

echo
echo "Building project..."
cmake --build . --config Release

echo
echo "=== Build completed successfully! ==="
echo
echo "The Python module is located at: python/visual_sim_core.so"
echo
echo "To run the demo:"
echo "  cd python"
echo "  python3 demo.py"
echo
