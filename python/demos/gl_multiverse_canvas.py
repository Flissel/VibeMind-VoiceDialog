"""
GL Multiverse Canvas - GPU-Accelerated Glass Bubble Renderer

Uses PyOpenGL + QOpenGLWidget for real GPU shader rendering.
Implements the same teardrop glass bubble effect as the C++ renderer,
but in pure Python for immediate use without compiling.
"""

import sys
import os
import math
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Callable

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QOpenGLWidget, QLabel, QHBoxLayout
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QSurfaceFormat

# OpenGL imports
from OpenGL.GL import *
from OpenGL.GL import shaders
import numpy as np

# Import data models
sys.path.insert(0, str(Path(__file__).parent))
from data import ProjectsRepository, IdeasRepository, CanvasRepository


@dataclass
class GLBubble:
    """Bubble data for OpenGL rendering"""
    id: int
    title: str
    position: tuple  # (x, y) normalized 0-1
    radius: float    # normalized
    color: tuple     # (r, g, b) 0-1
    opacity: float = 0.8
    depth: float = 0.0  # 0=close, 1=far
    shimmer_phase: float = 0.0
    pulse_phase: float = 0.0
    hovered: bool = False
    selected: bool = False
    project_id: Optional[str] = None

    def update(self, dt: float):
        """Update animation phases"""
        self.shimmer_phase += dt * 0.5
        self.pulse_phase += dt * 2.0
        if self.shimmer_phase > 6.28318:
            self.shimmer_phase -= 6.28318
        if self.pulse_phase > 6.28318:
            self.pulse_phase -= 6.28318

    def get_effective_radius(self) -> float:
        """Get radius with animations applied"""
        pulse = 1.0 + 0.02 * math.sin(self.pulse_phase)
        hover_scale = 1.1 if self.hovered else 1.0
        depth_scale = 1.0 - self.depth * 0.5
        return self.radius * pulse * hover_scale * depth_scale

    def contains(self, x: float, y: float) -> bool:
        """Hit test - check if point is inside the teardrop"""
        dx = x - self.position[0]
        dy = y - self.position[1]
        r = self.get_effective_radius()

        # Simplified circular hit test (good enough for interaction)
        dist_sq = dx * dx + dy * dy
        return dist_sq < r * r


# Shader sources embedded in Python
VERTEX_SHADER = """
#version 330 core

layout (location = 0) in vec2 aPos;
layout (location = 1) in vec2 aTexCoord;

out vec2 fragCoord;

uniform vec2 bubblePos;
uniform float bubbleRadius;
uniform float aspectRatio;

void main() {
    // Scale the quad by bubble radius
    vec2 scaledPos = aPos * bubbleRadius * 2.0;

    // Convert bubble position from 0-1 to clip space -1 to 1
    vec2 centerClip = bubblePos * 2.0 - 1.0;

    // Final position: center + scaled offset (corrected for aspect)
    vec2 finalPos;
    finalPos.x = centerClip.x + scaledPos.x;
    finalPos.y = centerClip.y + scaledPos.y / aspectRatio;

    gl_Position = vec4(finalPos, 0.0, 1.0);
    fragCoord = aPos;
}
"""

FRAGMENT_SHADER = """
#version 330 core

in vec2 fragCoord;

out vec4 FragColor;

uniform vec3 bubbleColor;
uniform float bubbleOpacity;
uniform float shimmerPhase;
uniform bool hovered;
uniform bool selected;
uniform float time;

void main() {
    vec2 p = fragCoord;

    // === TEARDROP SHAPE ===
    // Point at top (negative Y), round body at bottom (positive Y)

    // Circle body - centered slightly below origin
    vec2 bodyCenter = vec2(0.0, 0.15);
    float bodyRadius = 0.6;
    float bodyDist = length(p - bodyCenter);

    // Point/tip region
    float tipY = -0.9;
    float inBody = bodyDist - bodyRadius;

    // Teardrop: blend circle with narrowing toward top
    float narrowing = smoothstep(bodyCenter.y - bodyRadius, tipY, p.y);
    float teardropWidth = bodyRadius * (1.0 - narrowing * 0.85);
    float tipDist = abs(p.x) - teardropWidth;

    // Combined shape
    float shape;
    if (p.y > bodyCenter.y - bodyRadius * 0.5) {
        shape = inBody;  // Use circle for bottom half
    } else {
        shape = max(tipDist, tipY - p.y);  // Use tapered shape for top
        shape = min(shape, inBody);  // Blend with circle
    }

    // Discard outside
    if (shape > 0.02) {
        discard;
    }

    // === 3D SPHERE LIGHTING ===

    // Map to sphere surface for 3D normal
    vec2 sphereP = (p - vec2(0.0, 0.1)) / 0.7;
    float r2 = sphereP.x * sphereP.x + sphereP.y * sphereP.y;

    // Calculate Z (depth into screen)
    float z = 0.0;
    if (r2 < 1.0) {
        z = sqrt(1.0 - r2);
    }

    // Surface normal
    vec3 normal = normalize(vec3(sphereP.x, sphereP.y, z + 0.5));

    // Light from top-left-front
    vec3 lightDir = normalize(vec3(-0.4, -0.5, 1.0));
    vec3 viewDir = vec3(0.0, 0.0, 1.0);

    // Diffuse
    float diffuse = max(dot(normal, lightDir), 0.0);

    // Specular (Blinn-Phong)
    vec3 halfVec = normalize(lightDir + viewDir);
    float specular = pow(max(dot(normal, halfVec), 0.0), 32.0);

    // Fresnel rim
    float fresnel = 1.0 - max(dot(normal, viewDir), 0.0);
    fresnel = pow(fresnel, 2.5);

    // === COLORING ===

    // Base color with shading
    vec3 baseColor = bubbleColor * (0.2 + diffuse * 0.5);

    // Specular highlight (white)
    vec3 specHighlight = vec3(1.0) * specular * 1.5;

    // Rim glow
    vec3 rimGlow = (bubbleColor * 0.5 + vec3(0.5)) * fresnel * 0.8;

    // Top-left bright spot
    vec2 highlightPos = vec2(-0.25, -0.3);
    float highlight = exp(-length(p - highlightPos) * 5.0) * 0.8;

    // Bottom-right reflection
    vec2 reflectPos = vec2(0.2, 0.4);
    float reflect2 = exp(-length(p - reflectPos) * 4.0) * 0.3;

    // Animated shimmer
    float angle = shimmerPhase + time * 1.5;
    vec2 shimmerPos = vec2(cos(angle), sin(angle)) * 0.25;
    float shimmer = exp(-length(p - shimmerPos) * 6.0) * 0.25;

    // Inner depth gradient
    float innerGlow = (1.0 - z) * 0.15;

    // === EFFECTS ===
    float hoverBoost = hovered ? 0.2 : 0.0;
    float selectPulse = selected ? (0.5 + 0.5 * sin(time * 4.0)) * 0.3 : 0.0;

    // === COMBINE ===
    vec3 finalColor = baseColor;
    finalColor += specHighlight;
    finalColor += rimGlow;
    finalColor += vec3(1.0) * highlight;
    finalColor += vec3(1.0) * reflect2;
    finalColor += bubbleColor * shimmer;
    finalColor += bubbleColor * innerGlow;
    finalColor += bubbleColor * hoverBoost;
    finalColor += vec3(1.0, 0.9, 0.7) * selectPulse;

    // === ALPHA ===
    float alpha = 0.4 + fresnel * 0.5 + specular * 0.4;
    alpha = clamp(alpha, 0.3, 0.95);

    if (hovered) alpha = min(alpha + 0.2, 1.0);

    // Soft edge
    float edgeSoft = smoothstep(0.02, -0.02, shape);
    alpha *= edgeSoft;

    FragColor = vec4(finalColor, alpha * bubbleOpacity);
}
"""


class GLBubbleCanvas(QOpenGLWidget):
    """GPU-accelerated glass bubble canvas using OpenGL shaders"""

    bubble_clicked = pyqtSignal(int)  # Emits bubble ID
    bubble_double_clicked = pyqtSignal(int)

    # Bubble colors by status
    COLORS = {
        "active": (0.3, 0.8, 1.0),    # Cyan
        "paused": (1.0, 0.7, 0.2),    # Amber
        "completed": (0.3, 1.0, 0.5), # Green
        "default": (0.5, 0.5, 0.8),   # Light purple
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bubbles: List[GLBubble] = []
        self.hovered_id = -1
        self.selected_id = -1
        self.time = 0.0
        self.last_time = time.time()

        # OpenGL resources
        self.shader_program = None
        self.vao = None
        self.vbo = None
        self.ebo = None
        self.initialized = False

        # Uniform locations
        self.loc_time = -1
        self.loc_bubble_pos = -1
        self.loc_bubble_radius = -1
        self.loc_bubble_color = -1
        self.loc_bubble_opacity = -1
        self.loc_shimmer_phase = -1
        self.loc_hovered = -1
        self.loc_selected = -1
        self.loc_aspect_ratio = -1

        # Animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(16)  # ~60 FPS

        # Enable mouse tracking for hover
        self.setMouseTracking(True)

    def initializeGL(self):
        """Initialize OpenGL resources"""
        try:
            # Compile shaders
            vertex = shaders.compileShader(VERTEX_SHADER, GL_VERTEX_SHADER)
            fragment = shaders.compileShader(FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
            self.shader_program = shaders.compileProgram(vertex, fragment)

            # Get uniform locations
            self.loc_time = glGetUniformLocation(self.shader_program, "time")
            self.loc_bubble_pos = glGetUniformLocation(self.shader_program, "bubblePos")
            self.loc_bubble_radius = glGetUniformLocation(self.shader_program, "bubbleRadius")
            self.loc_bubble_color = glGetUniformLocation(self.shader_program, "bubbleColor")
            self.loc_bubble_opacity = glGetUniformLocation(self.shader_program, "bubbleOpacity")
            self.loc_shimmer_phase = glGetUniformLocation(self.shader_program, "shimmerPhase")
            self.loc_hovered = glGetUniformLocation(self.shader_program, "hovered")
            self.loc_selected = glGetUniformLocation(self.shader_program, "selected")
            self.loc_aspect_ratio = glGetUniformLocation(self.shader_program, "aspectRatio")

            # Create quad geometry
            vertices = np.array([
                # positions    # texcoords
                -1.0, -1.0,    0.0, 0.0,
                 1.0, -1.0,    1.0, 0.0,
                 1.0,  1.0,    1.0, 1.0,
                -1.0,  1.0,    0.0, 1.0,
            ], dtype=np.float32)

            indices = np.array([
                0, 1, 2,
                2, 3, 0,
            ], dtype=np.uint32)

            # Create VAO, VBO, EBO
            self.vao = glGenVertexArrays(1)
            self.vbo = glGenBuffers(1)
            self.ebo = glGenBuffers(1)

            glBindVertexArray(self.vao)

            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

            # Position attribute
            glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * 4, ctypes.c_void_p(0))
            glEnableVertexAttribArray(0)

            # Texcoord attribute
            glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * 4, ctypes.c_void_p(2 * 4))
            glEnableVertexAttribArray(1)

            glBindVertexArray(0)

            # Enable blending
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            self.initialized = True
            print("[GLBubbleCanvas] OpenGL initialized successfully")

        except Exception as e:
            print(f"[GLBubbleCanvas] Failed to initialize OpenGL: {e}")
            import traceback
            traceback.print_exc()

    def paintGL(self):
        """Render the bubbles"""
        if not self.initialized:
            return

        # Clear background (dark cosmic)
        glClearColor(0.02, 0.02, 0.05, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        # Use shader
        glUseProgram(self.shader_program)
        glBindVertexArray(self.vao)

        # Set global uniforms
        glUniform1f(self.loc_time, self.time)
        aspect = self.height() / max(self.width(), 1)
        glUniform1f(self.loc_aspect_ratio, aspect)

        # Sort bubbles by depth (far to near)
        sorted_bubbles = sorted(self.bubbles, key=lambda b: b.depth, reverse=True)

        # Render each bubble
        for bubble in sorted_bubbles:
            self._render_bubble(bubble)

        glBindVertexArray(0)

    def _render_bubble(self, bubble: GLBubble):
        """Render a single bubble"""
        glUniform2f(self.loc_bubble_pos, bubble.position[0], bubble.position[1])
        glUniform1f(self.loc_bubble_radius, bubble.get_effective_radius())
        glUniform3f(self.loc_bubble_color, *bubble.color)
        glUniform1f(self.loc_bubble_opacity, bubble.opacity)
        glUniform1f(self.loc_shimmer_phase, bubble.shimmer_phase)
        glUniform1i(self.loc_hovered, 1 if bubble.hovered else 0)
        glUniform1i(self.loc_selected, 1 if bubble.selected else 0)

        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

    def resizeGL(self, w, h):
        """Handle resize"""
        glViewport(0, 0, w, h)

    def _on_timer(self):
        """Animation timer callback"""
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        self.time += dt

        # Update bubble animations
        for bubble in self.bubbles:
            bubble.update(dt)
            bubble.hovered = (bubble.id == self.hovered_id)
            bubble.selected = (bubble.id == self.selected_id)

        self.update()  # Request repaint

    def mouseMoveEvent(self, event):
        """Handle mouse movement for hover detection"""
        x = event.x() / max(self.width(), 1)
        y = 1.0 - event.y() / max(self.height(), 1)  # Flip Y

        # Find hovered bubble
        hit_id = -1
        for bubble in reversed(self.bubbles):  # Check from front to back
            if bubble.contains(x, y):
                hit_id = bubble.id
                break

        if hit_id != self.hovered_id:
            self.hovered_id = hit_id
            if hit_id >= 0:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, event):
        """Handle mouse click"""
        if event.button() == Qt.LeftButton:
            x = event.x() / max(self.width(), 1)
            y = 1.0 - event.y() / max(self.height(), 1)

            for bubble in reversed(self.bubbles):
                if bubble.contains(x, y):
                    self.selected_id = bubble.id
                    self.bubble_clicked.emit(bubble.id)
                    return

            self.selected_id = -1

    def mouseDoubleClickEvent(self, event):
        """Handle double click to enter bubble"""
        if event.button() == Qt.LeftButton and self.selected_id >= 0:
            self.bubble_double_clicked.emit(self.selected_id)

    def set_bubbles(self, bubbles: List[GLBubble]):
        """Set the list of bubbles to render"""
        self.bubbles = bubbles

    def add_bubble(self, bubble: GLBubble):
        """Add a bubble"""
        self.bubbles.append(bubble)

    def clear_bubbles(self):
        """Clear all bubbles"""
        self.bubbles.clear()
        self.hovered_id = -1
        self.selected_id = -1

    def refresh_from_database(self):
        """Load bubbles from database"""
        self.bubbles.clear()

        # Load projects as bubbles
        projects_repo = ProjectsRepository()
        projects = projects_repo.list(limit=50)

        n = len(projects)
        for i, project in enumerate(projects):
            # Calculate ego perspective position
            row = i % 3  # 0=front, 1=middle, 2=back
            col = i // 3

            depth = row / 2.0 if row > 0 else 0.0
            y = 0.3 + depth * 0.4  # Front at bottom, back at top

            # Spread based on row
            cols_in_row = (n + 2 - row) // 3
            x_offset = (col - cols_in_row / 2) * 0.25 * (1.0 - depth * 0.3)
            x = 0.5 + x_offset

            # Color based on status
            color = self.COLORS.get(project.status, self.COLORS["default"])

            bubble = GLBubble(
                id=i,
                title=project.name,
                position=(x, y),
                radius=0.08 * (1.0 - depth * 0.3),
                color=color,
                depth=depth,
                shimmer_phase=i * 0.7,
                project_id=project.id
            )
            self.bubbles.append(bubble)

        print(f"[GLBubbleCanvas] Loaded {len(self.bubbles)} bubbles from database")


class GLMultiverseWindow(QMainWindow):
    """Main window for GL Multiverse Canvas"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GL Multiverse Canvas - Glass Bubbles")
        self.setGeometry(100, 100, 1200, 800)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QLabel("GL Multiverse Canvas - GPU Accelerated Glass Bubbles")
        header.setStyleSheet("""
            QLabel {
                background: #1a1a2e;
                color: #00ffff;
                padding: 10px;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        layout.addWidget(header)

        # GL Canvas
        self.canvas = GLBubbleCanvas()
        self.canvas.bubble_clicked.connect(self._on_bubble_clicked)
        self.canvas.bubble_double_clicked.connect(self._on_bubble_double_clicked)
        layout.addWidget(self.canvas)

        # Status bar
        self.status = QLabel("Click a bubble to select, double-click to enter")
        self.status.setStyleSheet("""
            QLabel {
                background: #1a1a2e;
                color: #888;
                padding: 5px;
            }
        """)
        layout.addWidget(self.status)

        # Load data
        self.canvas.refresh_from_database()

        # If no projects, add demo bubbles
        if not self.canvas.bubbles:
            self._add_demo_bubbles()

    def _add_demo_bubbles(self):
        """Add demo bubbles if database is empty"""
        colors = [
            (0.3, 0.8, 1.0),   # Cyan
            (1.0, 0.4, 0.7),   # Pink
            (0.5, 1.0, 0.5),   # Green
            (1.0, 0.8, 0.3),   # Gold
            (0.7, 0.5, 1.0),   # Purple
        ]

        titles = ["Idea 1", "Project A", "Canvas", "Research", "Design"]

        for i in range(5):
            row = i % 3
            col = i // 3
            depth = row / 2.0 if row > 0 else 0.0

            bubble = GLBubble(
                id=i,
                title=titles[i],
                position=(0.3 + col * 0.2, 0.3 + depth * 0.3),
                radius=0.1 * (1.0 - depth * 0.3),
                color=colors[i],
                depth=depth,
                shimmer_phase=i * 1.2
            )
            self.canvas.add_bubble(bubble)

        print("[GLMultiverseWindow] Added 5 demo bubbles")

    def _on_bubble_clicked(self, bubble_id: int):
        """Handle bubble click"""
        for b in self.canvas.bubbles:
            if b.id == bubble_id:
                self.status.setText(f"Selected: {b.title}")
                return

    def _on_bubble_double_clicked(self, bubble_id: int):
        """Handle double click to enter bubble"""
        for b in self.canvas.bubbles:
            if b.id == bubble_id:
                self.status.setText(f"Entering: {b.title}")
                return


def main():
    """Run the GL Multiverse Canvas"""
    # Set OpenGL version
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setSamples(4)  # Anti-aliasing
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = GLMultiverseWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
