cmake_minimum_required(VERSION 3.15)
project(VoiceDialogVisuals CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
find_package(OpenGL REQUIRED)
find_package(glfw3 REQUIRED)
find_package(pybind11 REQUIRED)

# GLM (header-only, might need to download separately)
# You can install via: vcpkg install glm
find_package(glm REQUIRED)

# GLAD (you'll need to include glad.c in your project or install via vcpkg)
# For now, assuming it's in a subdirectory or installed
# If not installed, download from https://glad.dav1d.de/

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/cpp/include
    ${OPENGL_INCLUDE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/external/glad/include  # Adjust path as needed
)

# Source files
set(SOURCES
    cpp/src/audio_reactive_sim.cpp
    external/glad/src/gl.c
)

# Python module using pybind11
pybind11_add_module(visual_sim_core
    cpp/src/bindings.cpp
    ${SOURCES}
)

# Link libraries
target_link_libraries(visual_sim_core PRIVATE
    OpenGL::GL
    glfw
)

# Set output directory
set_target_properties(visual_sim_core PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/python
)

# Copy shaders to build directory and python directory
file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/shaders
     DESTINATION ${CMAKE_BINARY_DIR})
file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/shaders
     DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}/python)
