@echo off
REM Build script for Windows

echo === Building Voice Dialog Visual System ===
echo.

REM Check if build directory exists
if not exist build mkdir build

cd build

echo Configuring CMake...
cmake .. -DCMAKE_BUILD_TYPE=Release

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: CMake configuration failed!
    echo.
    echo If you're using vcpkg, try:
    echo cmake .. -DCMAKE_TOOLCHAIN_FILE=[path-to-vcpkg]\scripts\buildsystems\vcpkg.cmake
    echo.
    pause
    exit /b 1
)

echo.
echo Building project...
cmake --build . --config Release

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo === Build completed successfully! ===
echo.
echo The Python module is located at: python\visual_sim_core.pyd
echo.
echo To run the demo:
echo   cd python
echo   python demo.py
echo.
pause
