"""
Vibemind Multiverse Canvas

A simplified 2-level visualization:
- Multiverse view: Project bubbles floating in dark void + orphan idea particles
- Universe view: Inside a bubble showing canvas nodes (ideas, notes, images)

Voice-first navigation: "Go to project X", "Show all projects"
"""

import sys
import math
import random
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGraphicsView,
    QGraphicsScene, QGraphicsItem, QGraphicsEllipseItem,
)
from PyQt5.QtCore import (
    Qt, QRectF, QPointF, QTimer, QPropertyAnimation,
    QEasingCurve, pyqtSignal, QObject,
)
from PyQt5.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QRadialGradient,
    QLinearGradient, QPainterPath,
)

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('\\', 1)[0])

from data import (
    IdeasRepository, ProjectsRepository, CanvasRepository,
    Idea, Project, CanvasNode,
)


# =============================================================================
# CONSTANTS
# =============================================================================

# Colors
BACKGROUND_COLOR = QColor(10, 10, 18)  # Near-black #0A0A12
BUBBLE_COLORS = {
    'active': QColor(0, 200, 220),     # Cyan
    'paused': QColor(255, 180, 50),    # Amber
    'completed': QColor(80, 220, 120), # Green
    'archived': QColor(120, 120, 140), # Gray
}
PARTICLE_COLOR = QColor(180, 200, 255)  # Light blue-white

# Bubble sizes
BUBBLE_BASE_RADIUS = 60
BUBBLE_MAX_RADIUS = 130
BUBBLE_MIN_RADIUS = 45

# Particle sizes
PARTICLE_RADIUS = 8

# Animation
ANIMATION_FPS = 30
ZOOM_DURATION_MS = 800

# Star count for background
STAR_COUNT = 600

# Layout
LAYOUT_SPACING = 80  # Minimum spacing between bubbles


# =============================================================================
# STARFIELD BACKGROUND (reused pattern from cosmic_canvas.py)
# =============================================================================

class StarfieldBackground:
    """Twinkling starfield for the multiverse void"""

    def __init__(self, scene_rect: QRectF):
        self.stars: List[Dict] = []
        self._generate_stars(scene_rect)

    def _generate_stars(self, scene_rect: QRectF):
        """Generate random stars within scene bounds"""
        for _ in range(STAR_COUNT):
            self.stars.append({
                'x': random.uniform(scene_rect.left(), scene_rect.right()),
                'y': random.uniform(scene_rect.top(), scene_rect.bottom()),
                'hue': random.randint(180, 240),  # Blue-cyan range
                'size': random.uniform(1, 3),
                'base_brightness': random.uniform(0.3, 1.0),
                'fade_phase': random.uniform(0, 2 * np.pi),
                'fade_speed': random.uniform(0.02, 0.08),
            })

    def update(self, dt: float = 0.033):
        """Update star twinkle animation"""
        for star in self.stars:
            star['fade_phase'] += star['fade_speed']

    def draw(self, painter: QPainter, visible_rect: QRectF):
        """Draw visible stars with twinkling effect"""
        margin = 100
        expanded_rect = visible_rect.adjusted(-margin, -margin, margin, margin)

        for star in self.stars:
            if not expanded_rect.contains(QPointF(star['x'], star['y'])):
                continue

            # Calculate twinkle alpha using sine wave
            phase_normalized = (star['fade_phase'] % (np.pi * 2)) / (np.pi * 2)
            if phase_normalized < 0.25:
                fade_alpha = np.sin(phase_normalized / 0.25 * np.pi)
            else:
                fade_alpha = 0.0

            alpha = int(star['base_brightness'] * 255 * (0.3 + 0.7 * fade_alpha))
            alpha = max(30, min(255, alpha))

            # HSV to RGB conversion
            h = star['hue'] / 360.0
            s = 0.3
            v = star['base_brightness']

            c = v * s
            x = c * (1 - abs((h * 6) % 2 - 1))
            m = v - c

            if h < 1/6:
                r, g, b = c, x, 0
            elif h < 2/6:
                r, g, b = x, c, 0
            elif h < 3/6:
                r, g, b = 0, c, x
            elif h < 4/6:
                r, g, b = 0, x, c
            elif h < 5/6:
                r, g, b = x, 0, c
            else:
                r, g, b = c, 0, x

            color = QColor(
                int((r + m) * 255),
                int((g + m) * 255),
                int((b + m) * 255),
                alpha
            )

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(
                QPointF(star['x'], star['y']),
                star['size'], star['size']
            )


# =============================================================================
# BUBBLE (Generic)
# =============================================================================

class Bubble(QGraphicsItem):
    """
    Glass-like sphere in the multiverse.
    Transparent, shiny, with specular highlights.
    Can represent a project, welcome message, or any content.
    """

    def __init__(
        self,
        bubble_id: str,
        title: str,
        message: str = "",
        color: QColor = None,
        radius: float = BUBBLE_BASE_RADIUS,
        progress: float = 0.0,
        project: Project = None,
    ):
        super().__init__()
        self.bubble_id = bubble_id
        self.title = title
        self.message = message
        self.color = color or BUBBLE_COLORS['active']
        self.base_radius = max(BUBBLE_MIN_RADIUS, min(BUBBLE_MAX_RADIUS, radius))
        self.radius = self.base_radius  # Current display radius (can be scaled)
        self.depth = 0.0  # Depth for ego perspective (0=close, 1=far)
        self.progress = progress
        self.project = project  # Optional linked project

        # Animation state
        self.glow_phase = random.uniform(0, 2 * np.pi)
        self.hover = False

        # Enable interaction
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

    @classmethod
    def from_project(cls, project: Project, content_count: int = 0) -> 'Bubble':
        """Create a bubble from a Project"""
        base = BUBBLE_BASE_RADIUS
        content_bonus = min(content_count * 5, 50)
        progress_bonus = project.progress * 0.2
        radius = base + content_bonus + progress_bonus

        return cls(
            bubble_id=project.id,
            title=project.name,
            message=project.description or "",
            color=BUBBLE_COLORS.get(project.status, BUBBLE_COLORS['active']),
            radius=radius,
            progress=project.progress,
            project=project,
        )

    @classmethod
    def welcome(cls) -> 'Bubble':
        """Create the welcome bubble"""
        return cls(
            bubble_id="welcome",
            title="Welcome to Vibemind",
            message="Say 'create a project' to add your first universe",
            color=QColor(100, 180, 255),  # Soft blue
            radius=90,
            progress=0,
        )

    def boundingRect(self) -> QRectF:
        # Include space for glow, title, and teardrop shape (tip at top)
        margin = 70
        r = self.radius
        body_center_y = r * 0.2
        tip_y = -r * 1.4
        bottom_y = body_center_y + r

        return QRectF(
            -r - margin,
            tip_y - margin,
            (r + margin) * 2,
            (bottom_y - tip_y) + margin * 2 + 50  # Extra for title below
        )

    def _create_teardrop_path(self, r: float) -> QPainterPath:
        """Create a teardrop shape path - pointed at top, round at bottom"""
        path = QPainterPath()

        # Teardrop: pointed tip at top, round body at bottom
        tip_y = -r * 1.4  # Point at top
        body_center_y = r * 0.2  # Body center shifted down

        # Start at the tip
        path.moveTo(0, tip_y)

        # Left curve from tip to body (bezier curve)
        path.cubicTo(
            -r * 0.4, tip_y + r * 0.5,  # Control point 1
            -r, body_center_y - r * 0.3,  # Control point 2
            -r, body_center_y  # End at left side of body
        )

        # Bottom arc (semi-circle)
        path.cubicTo(
            -r, body_center_y + r * 0.8,  # Control point 1
            -r * 0.5, body_center_y + r,  # Control point 2
            0, body_center_y + r  # Bottom center
        )
        path.cubicTo(
            r * 0.5, body_center_y + r,  # Control point 1
            r, body_center_y + r * 0.8,  # Control point 2
            r, body_center_y  # Right side of body
        )

        # Right curve from body back to tip
        path.cubicTo(
            r, body_center_y - r * 0.3,  # Control point 1
            r * 0.4, tip_y + r * 0.5,  # Control point 2
            0, tip_y  # Back to tip
        )

        path.closeSubpath()
        return path

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        r = self.radius
        glow_intensity = 1.3 if self.hover else 1.0

        # Create teardrop path
        teardrop = self._create_teardrop_path(r)
        body_center_y = r * 0.2  # Body center for gradient positioning

        # 1. OUTER GLOW (soft ambient light - 3 layers)
        for i in range(3):
            glow_alpha = int((35 - i * 10) * glow_intensity)
            glow_r = r * (1.3 + i * 0.2)
            glow_path = self._create_teardrop_path(glow_r)

            glow_gradient = QRadialGradient(QPointF(0, body_center_y), glow_r * 1.5)
            glow_gradient.setColorAt(0, QColor(
                self.color.red(), self.color.green(), self.color.blue(), glow_alpha
            ))
            glow_gradient.setColorAt(0.5, QColor(
                self.color.red(), self.color.green(), self.color.blue(), glow_alpha // 3
            ))
            glow_gradient.setColorAt(1, QColor(0, 0, 0, 0))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(glow_gradient))
            painter.drawPath(glow_path)

        # 2. GLASS BODY (transparent teardrop with rim lighting)
        glass_gradient = QRadialGradient(QPointF(0, body_center_y), r * 1.3)
        # Center: very transparent
        glass_gradient.setColorAt(0.0, QColor(
            self.color.red(), self.color.green(), self.color.blue(), 35
        ))
        # Middle: slightly more visible
        glass_gradient.setColorAt(0.5, QColor(
            self.color.red(), self.color.green(), self.color.blue(), 55
        ))
        # Edge: rim lighting effect
        glass_gradient.setColorAt(0.8, QColor(
            self.color.red(), self.color.green(), self.color.blue(), 110
        ))
        # Outer edge: bright rim
        glass_gradient.setColorAt(0.95, QColor(
            min(255, self.color.red() + 60),
            min(255, self.color.green() + 60),
            min(255, self.color.blue() + 60),
            150
        ))
        glass_gradient.setColorAt(1.0, QColor(255, 255, 255, 70))

        painter.setBrush(QBrush(glass_gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1.5))
        painter.drawPath(teardrop)

        # 3. SPECULAR HIGHLIGHT (upper left shine on body)
        highlight_center = QPointF(-r * 0.3, body_center_y - r * 0.3)
        highlight_radius = r * 0.5

        highlight_gradient = QRadialGradient(highlight_center, highlight_radius)
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 200))
        highlight_gradient.setColorAt(0.3, QColor(255, 255, 255, 100))
        highlight_gradient.setColorAt(0.6, QColor(255, 255, 255, 30))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))

        painter.setBrush(QBrush(highlight_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(highlight_center, highlight_radius, highlight_radius * 0.6)

        # 4. SMALL BRIGHT SPOT (top of body)
        spot_center = QPointF(-r * 0.2, body_center_y - r * 0.5)
        spot_radius = r * 0.12

        spot_gradient = QRadialGradient(spot_center, spot_radius)
        spot_gradient.setColorAt(0, QColor(255, 255, 255, 255))
        spot_gradient.setColorAt(0.5, QColor(255, 255, 255, 150))
        spot_gradient.setColorAt(1, QColor(255, 255, 255, 0))

        painter.setBrush(QBrush(spot_gradient))
        painter.drawEllipse(spot_center, spot_radius, spot_radius)

        # 5. TIP HIGHLIGHT (shine on the teardrop tip)
        tip_highlight = QPointF(-r * 0.08, -r * 1.1)
        tip_radius = r * 0.15

        tip_gradient = QRadialGradient(tip_highlight, tip_radius)
        tip_gradient.setColorAt(0, QColor(255, 255, 255, 180))
        tip_gradient.setColorAt(0.5, QColor(255, 255, 255, 60))
        tip_gradient.setColorAt(1, QColor(255, 255, 255, 0))

        painter.setBrush(QBrush(tip_gradient))
        painter.drawEllipse(tip_highlight, tip_radius, tip_radius * 0.8)

        # 6. BOTTOM REFLECTION (subtle)
        reflection_center = QPointF(r * 0.2, body_center_y + r * 0.5)
        reflection_radius = r * 0.2

        reflection_gradient = QRadialGradient(reflection_center, reflection_radius)
        reflection_gradient.setColorAt(0, QColor(255, 255, 255, 45))
        reflection_gradient.setColorAt(1, QColor(255, 255, 255, 0))

        painter.setBrush(QBrush(reflection_gradient))
        painter.drawEllipse(reflection_center, reflection_radius, reflection_radius * 0.5)

        # 7. PROGRESS INDICATOR (arc at bottom of body)
        if self.progress > 0:
            arc_radius = r + 8
            arc_rect = QRectF(
                -arc_radius,
                body_center_y - arc_radius,
                arc_radius * 2,
                arc_radius * 2
            )

            # Background arc (subtle)
            painter.setPen(QPen(QColor(255, 255, 255, 35), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawArc(arc_rect, -30 * 16, -120 * 16)  # Bottom arc only

            # Progress arc (glowing)
            painter.setPen(QPen(QColor(100, 255, 150, 200), 3))
            span_angle = int(self.progress / 100 * 120 * 16)
            painter.drawArc(arc_rect, -30 * 16, -span_angle)

        # 8. CENTER CONTENT (progress % or message)
        text_center_y = body_center_y
        if self.progress > 0:
            # Progress percentage
            font_size = max(12, int(14 * (r / BUBBLE_BASE_RADIUS)))
            painter.setFont(QFont("Segoe UI", font_size, QFont.Bold))
            text_rect = QRectF(-r, text_center_y - r * 0.4, r * 2, r * 0.8)
            # Shadow
            painter.setPen(QPen(QColor(0, 0, 0, 100)))
            painter.drawText(text_rect.adjusted(1, 1, 1, 1), Qt.AlignCenter, f"{int(self.progress)}%")
            # Text
            painter.setPen(QPen(QColor(255, 255, 255, 240)))
            painter.drawText(text_rect, Qt.AlignCenter, f"{int(self.progress)}%")
        elif self.message:
            # Message text
            font_size = max(7, int(8 * (r / BUBBLE_BASE_RADIUS)))
            painter.setFont(QFont("Segoe UI", font_size))
            msg_rect = QRectF(-r + 10, text_center_y - r * 0.3, (r - 10) * 2, r * 0.9)
            # Shadow
            painter.setPen(QPen(QColor(0, 0, 0, 80)))
            painter.drawText(msg_rect.adjusted(1, 1, 1, 1), Qt.AlignCenter | Qt.TextWordWrap, self.message)
            # Text
            painter.setPen(QPen(QColor(255, 255, 255, 220)))
            painter.drawText(msg_rect, Qt.AlignCenter | Qt.TextWordWrap, self.message)

        # 9. TITLE TEXT (below teardrop)
        font_size = max(9, int(11 * (r / BUBBLE_BASE_RADIUS)))
        painter.setFont(QFont("Segoe UI", font_size, QFont.Bold))
        title_rect = QRectF(-r - 50, body_center_y + r + 15, (r + 50) * 2, 30)

        # Truncate title
        display_title = self.title
        max_len = int(25 * (r / BUBBLE_BASE_RADIUS))
        if len(display_title) > max_len:
            display_title = display_title[:max_len - 2] + "..."

        # Title shadow
        painter.setPen(QPen(QColor(0, 0, 0, 120)))
        painter.drawText(title_rect.adjusted(1, 1, 1, 1), Qt.AlignCenter, display_title)

        # Title text
        painter.setPen(QPen(QColor(255, 255, 255, 240)))
        painter.drawText(title_rect, Qt.AlignCenter, display_title)

    def hoverEnterEvent(self, event):
        self.hover = True
        self.update()

    def hoverLeaveEvent(self, event):
        self.hover = False
        self.update()

    def update_animation(self):
        """Update glow animation phase"""
        self.glow_phase += 0.05


# =============================================================================
# ORPHAN PARTICLE
# =============================================================================

class OrphanParticle(QGraphicsItem):
    """
    Small glowing dot for ideas not assigned to any project.
    Drifts slowly and twinkles in the void.
    """

    def __init__(self, idea: Idea):
        super().__init__()
        self.idea = idea
        self.radius = PARTICLE_RADIUS

        # Animation state
        self.twinkle_phase = random.uniform(0, 2 * np.pi)
        self.twinkle_speed = random.uniform(0.03, 0.08)
        self.drift_x = random.uniform(-0.3, 0.3)
        self.drift_y = random.uniform(-0.3, 0.3)

        # Tooltip shows idea title
        self.setToolTip(idea.title)
        self.setAcceptHoverEvents(True)

    def boundingRect(self) -> QRectF:
        margin = 20
        return QRectF(-margin, -margin, margin * 2, margin * 2)

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        # Calculate twinkle alpha
        twinkle = 0.5 + 0.5 * math.sin(self.twinkle_phase)
        alpha = int(120 + 120 * twinkle)

        # Outer glow
        glow_gradient = QRadialGradient(QPointF(0, 0), self.radius * 3)
        glow_gradient.setColorAt(0, QColor(
            PARTICLE_COLOR.red(),
            PARTICLE_COLOR.green(),
            PARTICLE_COLOR.blue(),
            alpha // 2
        ))
        glow_gradient.setColorAt(1, QColor(0, 0, 0, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(glow_gradient))
        painter.drawEllipse(QPointF(0, 0), self.radius * 3, self.radius * 3)

        # Core
        painter.setBrush(QBrush(QColor(
            PARTICLE_COLOR.red(),
            PARTICLE_COLOR.green(),
            PARTICLE_COLOR.blue(),
            alpha
        )))
        painter.drawEllipse(QPointF(0, 0), self.radius, self.radius)

    def update_animation(self, scene_rect: QRectF):
        """Update twinkle and drift"""
        self.twinkle_phase += self.twinkle_speed

        # Apply drift
        new_x = self.x() + self.drift_x
        new_y = self.y() + self.drift_y

        # Bounce off boundaries
        margin = 500
        if new_x < scene_rect.left() + margin or new_x > scene_rect.right() - margin:
            self.drift_x = -self.drift_x
        if new_y < scene_rect.top() + margin or new_y > scene_rect.bottom() - margin:
            self.drift_y = -self.drift_y

        self.setPos(new_x, new_y)


# =============================================================================
# MULTIVERSE SCENE
# =============================================================================

class MultiverseScene(QGraphicsScene):
    """
    Scene showing bubbles and orphan particles in the void.
    Starts with a welcome bubble, more can be added via add_bubble().
    """

    def __init__(self):
        super().__init__()

        # Set large scene rect for infinite feel
        self.setSceneRect(-3000, -3000, 6000, 6000)
        self.setBackgroundBrush(QBrush(BACKGROUND_COLOR))

        # Starfield
        self.starfield = StarfieldBackground(self.sceneRect())

        # Items
        self.bubbles: Dict[str, Bubble] = {}
        self.particles: Dict[str, OrphanParticle] = {}

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draw starfield background"""
        painter.fillRect(rect, BACKGROUND_COLOR)
        self.starfield.draw(painter, rect)

    def add_welcome_bubble(self):
        """Add the initial welcome bubble"""
        welcome = Bubble.welcome()
        welcome.setPos(0, 0)
        self.addItem(welcome)
        self.bubbles[welcome.bubble_id] = welcome

    def add_bubble(
        self,
        bubble_id: str,
        title: str,
        message: str = "",
        color: QColor = None,
        radius: float = BUBBLE_BASE_RADIUS,
        progress: float = 0.0,
    ) -> Bubble:
        """
        Add a new bubble to the multiverse.

        Args:
            bubble_id: Unique identifier for the bubble
            title: Title displayed below the bubble
            message: Optional message displayed inside (if no progress)
            color: Bubble color (defaults to cyan)
            radius: Bubble size
            progress: Progress percentage (0-100)

        Returns:
            The created Bubble object
        """
        bubble = Bubble(
            bubble_id=bubble_id,
            title=title,
            message=message,
            color=color,
            radius=radius,
            progress=progress,
        )
        self.addItem(bubble)
        self.bubbles[bubble_id] = bubble

        # Re-layout all bubbles
        self._layout_bubbles()

        return bubble

    def add_project_bubble(self, project: Project, content_count: int = 0) -> Bubble:
        """Add a bubble from a Project object"""
        bubble = Bubble.from_project(project, content_count)
        self.addItem(bubble)
        self.bubbles[bubble.bubble_id] = bubble
        self._layout_bubbles()
        return bubble

    def remove_bubble(self, bubble_id: str) -> bool:
        """Remove a bubble by ID"""
        if bubble_id in self.bubbles:
            self.removeItem(self.bubbles[bubble_id])
            del self.bubbles[bubble_id]
            self._layout_bubbles()
            return True
        return False

    def load_from_database(self):
        """Load projects and orphan ideas from database"""
        # Clear existing items
        for bubble in self.bubbles.values():
            self.removeItem(bubble)
        for particle in self.particles.values():
            self.removeItem(particle)
        self.bubbles.clear()
        self.particles.clear()

        # Load projects as bubbles
        projects_repo = ProjectsRepository()
        canvas_repo = CanvasRepository()
        projects = projects_repo.list(limit=50)

        for project in projects:
            # Count content in this project
            content_count = len([
                n for n in canvas_repo.list_nodes()
                if n.linked_project_id == project.id
            ])
            bubble = Bubble.from_project(project, content_count)
            self.addItem(bubble)
            self.bubbles[bubble.bubble_id] = bubble

        # If no projects, add welcome bubble
        if not self.bubbles:
            self.add_welcome_bubble()
        else:
            # Layout bubbles
            self._layout_bubbles()

        # Load orphan ideas as particles
        ideas_repo = IdeasRepository()
        all_ideas = ideas_repo.list(limit=100)
        all_nodes = canvas_repo.list_nodes()

        # Find ideas not linked to any project
        linked_idea_ids = set()
        for node in all_nodes:
            if node.linked_idea_id and node.linked_project_id:
                linked_idea_ids.add(node.linked_idea_id)

        for idea in all_ideas:
            if idea.promoted_to_project_id is None and idea.id not in linked_idea_ids:
                particle = OrphanParticle(idea)
                # Random position in outer regions
                angle = random.uniform(0, 2 * np.pi)
                distance = random.uniform(800, 1500)
                particle.setPos(
                    distance * math.cos(angle),
                    distance * math.sin(angle)
                )
                self.addItem(particle)
                self.particles[idea.id] = particle

    def _layout_bubbles(self):
        """
        Arrange bubbles in ego perspective - like standing in a room
        surrounded by teardrops floating at different depths.

        Layout: Arc/dome around viewer (center-bottom of view)
        - Y position = depth (top = far/small, bottom = close/large)
        - X position = spread across view
        """
        bubbles = list(self.bubbles.values())
        if not bubbles:
            return

        n = len(bubbles)

        if n == 1:
            # Single bubble - center it
            bubble = bubbles[0]
            bubble.depth = 0.3
            bubble.radius = bubble.base_radius * 1.0
            bubble.setPos(0, -100)
            return

        # Define depth rows (0 = front/close, 1 = back/far)
        # Bubbles distributed across 3 depth levels
        max_rows = min(3, n)
        row_depths = [0.2, 0.5, 0.8]  # Front, middle, back

        # Calculate how many bubbles per row
        bubbles_per_row = [0] * max_rows
        for i in range(n):
            row = i % max_rows
            bubbles_per_row[row] += 1

        # Base Y positions for each depth row (ego view: bottom = close)
        base_y = [-400, -200, 50]  # Back row at top, front row at bottom

        # Horizontal spacing varies by depth
        base_spacing = [200, 280, 380]  # Tighter at back, wider at front

        # Size scale varies by depth
        size_scales = [0.5, 0.75, 1.0]  # Smaller at back, larger at front

        # Track position within each row
        row_positions = [0] * max_rows

        for i, bubble in enumerate(bubbles):
            row = i % max_rows
            col = row_positions[row]
            row_positions[row] += 1

            # Number of bubbles in this row
            count_in_row = bubbles_per_row[row]

            # Calculate position
            depth = row_depths[row]
            bubble.depth = depth

            # Size based on depth
            scale = size_scales[row]
            bubble.radius = bubble.base_radius * scale

            # Y position (with slight variation for organic feel)
            y = base_y[row] + random.uniform(-20, 20)

            # X position (centered distribution)
            spacing = base_spacing[row]
            total_width = (count_in_row - 1) * spacing
            start_x = -total_width / 2
            x = start_x + col * spacing

            # Add slight random offset for organic feel
            x += random.uniform(-30, 30)

            bubble.setPos(x, y)

        # Update Z-order: front bubbles on top
        for bubble in bubbles:
            bubble.setZValue(1.0 - bubble.depth)

    def update_animation(self):
        """Update all animations"""
        self.starfield.update()

        for bubble in self.bubbles.values():
            bubble.update_animation()
            bubble.update()

        for particle in self.particles.values():
            particle.update_animation(self.sceneRect())
            particle.update()

        # Invalidate background for starfield redraw
        self.invalidate(self.sceneRect(), QGraphicsScene.BackgroundLayer)


# =============================================================================
# MULTIVERSE VIEW
# =============================================================================

class MultiverseView(QGraphicsView):
    """Graphics view for ego-perspective multiverse - NO drag, click to enter"""

    bubble_clicked = pyqtSignal(str)  # Emits bubble_id

    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)

        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # NO drag mode - ego perspective is fixed
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)

        # Cursor
        self.setCursor(Qt.ArrowCursor)

        self._zoom = 1.0
        self._min_zoom = 0.5
        self._max_zoom = 1.5

    def wheelEvent(self, event):
        """Handle zoom with mouse wheel (limited range for ego view)"""
        factor = 1.08

        if event.angleDelta().y() > 0:
            if self._zoom < self._max_zoom:
                self._zoom *= factor
                self.scale(factor, factor)
        else:
            if self._zoom > self._min_zoom:
                self._zoom /= factor
                self.scale(1 / factor, 1 / factor)

    def mousePressEvent(self, event):
        """Handle click to enter bubble"""
        if event.button() == Qt.LeftButton:
            # Find item at click position
            scene_pos = self.mapToScene(event.pos())
            items = self.scene().items(scene_pos)

            for item in items:
                if isinstance(item, Bubble):
                    print(f"Clicked bubble: {item.title}")
                    self.bubble_clicked.emit(item.bubble_id)
                    return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Update cursor on hover"""
        scene_pos = self.mapToScene(event.pos())
        items = self.scene().items(scene_pos)

        has_bubble = any(isinstance(item, Bubble) for item in items)
        self.setCursor(Qt.PointingHandCursor if has_bubble else Qt.ArrowCursor)

        super().mouseMoveEvent(event)


# =============================================================================
# MULTIVERSE WINDOW
# =============================================================================

class MultiverseWindow(QWidget):
    """
    Main window with 2-level navigation:
    - Multiverse view (outer): All project bubbles + orphan particles
    - Universe view (inner): Inside a single project's canvas
    """

    _instance = None

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vibemind Multiverse")
        self.setMinimumSize(1200, 800)

        # State
        self.view_mode = "multiverse"  # "multiverse" or "universe"
        self.current_project_id: Optional[str] = None

        # Setup UI
        self._setup_ui()

        # Animation timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.start(1000 // ANIMATION_FPS)

        # Start with welcome bubble
        self.multiverse_scene.add_welcome_bubble()

    def _setup_ui(self):
        """Setup the UI layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Multiverse scene and view
        self.multiverse_scene = MultiverseScene()
        self.multiverse_view = MultiverseView(self.multiverse_scene)
        self.multiverse_view.bubble_clicked.connect(self._on_bubble_clicked)

        layout.addWidget(self.multiverse_view)

    def _update_animation(self):
        """Update animations each frame"""
        if self.view_mode == "multiverse":
            self.multiverse_scene.update_animation()

    def refresh_from_database(self):
        """Reload all data from database"""
        self.multiverse_scene.load_from_database()

    def _on_bubble_clicked(self, project_id: str):
        """Handle bubble double-click - enter universe view"""
        self.enter_project(project_id)

    def enter_project(self, project_id: str):
        """Navigate into a project's universe (zoom into bubble)"""
        if project_id not in self.multiverse_scene.bubbles:
            return

        self.current_project_id = project_id
        self.view_mode = "universe"

        bubble = self.multiverse_scene.bubbles[project_id]

        # Animate zoom to bubble
        # For now, simple instant zoom - can add animation later
        self.multiverse_view.centerOn(bubble)
        self.multiverse_view.resetTransform()
        self.multiverse_view.scale(3.0, 3.0)

        # TODO: Switch to universe scene showing project contents
        print(f"Entered bubble: {bubble.title}")

    def exit_to_multiverse(self):
        """Return to multiverse view (zoom out)"""
        self.view_mode = "multiverse"
        self.current_project_id = None

        # Reset zoom
        self.multiverse_view.resetTransform()
        self.multiverse_view.centerOn(0, 0)

        print("Returned to multiverse view")

    def add_bubble(
        self,
        bubble_id: str,
        title: str,
        message: str = "",
        color: QColor = None,
        radius: float = BUBBLE_BASE_RADIUS,
        progress: float = 0.0,
    ) -> Bubble:
        """Add a new bubble to the multiverse (convenience method)"""
        return self.multiverse_scene.add_bubble(
            bubble_id=bubble_id,
            title=title,
            message=message,
            color=color,
            radius=radius,
            progress=progress,
        )

    @classmethod
    def get_instance(cls) -> 'MultiverseWindow':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = MultiverseWindow()
        return cls._instance


def get_multiverse_instance() -> Optional[MultiverseWindow]:
    """Get the multiverse window instance if it exists"""
    return MultiverseWindow._instance


# =============================================================================
# VOICE TOOLS
# =============================================================================

def show_multiverse(params: Dict[str, Any]) -> str:
    """
    Show the multiverse canvas window.

    Voice triggers:
    - "Show the multiverse"
    - "Open the canvas"
    - "Show my projects"
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = MultiverseWindow.get_instance()
    window.show()
    window.raise_()
    window.activateWindow()

    bubble_count = len(window.multiverse_scene.bubbles)
    particle_count = len(window.multiverse_scene.particles)

    return f"Showing the multiverse with {bubble_count} project bubbles and {particle_count} floating ideas."


def hide_multiverse(params: Dict[str, Any]) -> str:
    """
    Hide the multiverse canvas window.

    Voice triggers:
    - "Hide the multiverse"
    - "Close the canvas"
    """
    window = get_multiverse_instance()
    if window:
        window.hide()
        return "Multiverse hidden."
    return "Multiverse is not open."


def navigate_to_project(params: Dict[str, Any]) -> str:
    """
    Navigate into a project's universe (zoom into bubble).

    Voice triggers:
    - "Go to project X"
    - "Open project X"
    - "Enter the X universe"

    Args:
        name: Project name (fuzzy match)
    """
    name = params.get("name", "").strip()
    if not name:
        return "Which project would you like to enter?"

    window = get_multiverse_instance()
    if not window:
        return "Multiverse is not open. Say 'show the multiverse' first."

    # Find project by name
    project = ProjectsRepository().get_by_name(name)
    if not project:
        return f"I couldn't find a project called '{name}'."

    if project.id not in window.multiverse_scene.bubbles:
        return f"Project '{name}' doesn't have a bubble yet."

    window.enter_project(project.id)
    content_count = len([
        n for n in CanvasRepository().list_nodes()
        if n.linked_project_id == project.id
    ])

    return f"Entering '{project.name}'. It contains {content_count} items."


def show_all_projects(params: Dict[str, Any]) -> str:
    """
    Return to multiverse view showing all projects.

    Voice triggers:
    - "Show all projects"
    - "Go back to multiverse"
    - "Zoom out"
    """
    window = get_multiverse_instance()
    if not window:
        return "Multiverse is not open."

    if window.view_mode == "multiverse":
        bubble_count = len(window.multiverse_scene.bubbles)
        return f"You're already viewing the multiverse with {bubble_count} project bubbles."

    window.exit_to_multiverse()
    return "Returning to multiverse view."


def list_bubbles(params: Dict[str, Any]) -> str:
    """
    List all project bubbles in the multiverse.

    Voice triggers:
    - "What bubbles do I have?"
    - "List my universes"
    - "What projects are in the multiverse?"
    """
    projects = ProjectsRepository().list(limit=20)

    if not projects:
        return "No project bubbles yet. Create a project to see it as a bubble."

    result = f"You have {len(projects)} project bubble(s):\n"
    for i, p in enumerate(projects, 1):
        status_icon = {"active": "+", "paused": "~", "completed": "*", "archived": "-"}.get(p.status, " ")
        result += f"  {i}. [{status_icon}] {p.name} ({p.progress:.0f}%)\n"

    return result.strip()


def list_orphan_ideas(params: Dict[str, Any]) -> str:
    """
    List ideas floating in the void (not assigned to projects).

    Voice triggers:
    - "What ideas are floating around?"
    - "Show orphan ideas"
    - "List floating particles"
    """
    ideas_repo = IdeasRepository()
    canvas_repo = CanvasRepository()

    all_ideas = ideas_repo.list(limit=50)
    all_nodes = canvas_repo.list_nodes()

    # Find ideas not linked to any project
    linked_idea_ids = set()
    for node in all_nodes:
        if node.linked_idea_id and node.linked_project_id:
            linked_idea_ids.add(node.linked_idea_id)

    orphans = [
        idea for idea in all_ideas
        if idea.promoted_to_project_id is None and idea.id not in linked_idea_ids
    ]

    if not orphans:
        return "No orphan ideas. All your ideas are assigned to projects."

    result = f"You have {len(orphans)} idea(s) floating in the void:\n"
    for i, idea in enumerate(orphans[:10], 1):
        result += f"  {i}. {idea.title}\n"

    if len(orphans) > 10:
        result += f"  ... and {len(orphans) - 10} more"

    return result.strip()


def assign_idea_to_project(params: Dict[str, Any]) -> str:
    """
    Assign an orphan idea to a project (pull particle into bubble).

    Voice triggers:
    - "Add idea X to project Y"
    - "Put idea X in project Y"
    - "Assign idea X to project Y"

    Args:
        idea_title: Name/title of the idea
        project_name: Name of the project
    """
    idea_title = params.get("idea_title", "").strip()
    project_name = params.get("project_name", "").strip()

    if not idea_title:
        return "Which idea would you like to assign?"
    if not project_name:
        return "Which project should I add it to?"

    # Find idea and project
    idea = IdeasRepository().get_by_title(idea_title)
    if not idea:
        return f"Couldn't find idea '{idea_title}'."

    project = ProjectsRepository().get_by_name(project_name)
    if not project:
        return f"Couldn't find project '{project_name}'."

    # Create canvas node linking idea to project
    canvas_repo = CanvasRepository()
    node = canvas_repo.create_node(
        node_type="idea",
        title=idea.title,
        content=idea.description,
        x=0, y=0,  # Will be auto-positioned
        linked_idea_id=idea.id,
        linked_project_id=project.id,
    )

    # Refresh multiverse if open
    window = get_multiverse_instance()
    if window:
        window.refresh_from_database()

    return f"Assigned '{idea.title}' to project '{project.name}'. The particle is now inside the bubble."


def refresh_multiverse(params: Dict[str, Any]) -> str:
    """
    Refresh the multiverse from database.

    Voice triggers:
    - "Refresh the multiverse"
    - "Update the canvas"
    """
    window = get_multiverse_instance()
    if window:
        window.refresh_from_database()
        return "Multiverse refreshed."
    return "Multiverse is not open."


def create_bubble(params: Dict[str, Any]) -> str:
    """
    Create a new bubble in the multiverse.

    Voice triggers:
    - "Create a bubble called X"
    - "Add a new universe called X"
    - "Make a bubble for X"

    Args:
        title: Name/title for the bubble
        message: Optional message to display inside
    """
    title = params.get("title", "").strip()
    message = params.get("message", "")

    if not title:
        return "What should I call this bubble?"

    window = get_multiverse_instance()
    if not window:
        return "Multiverse is not open. Say 'show the multiverse' first."

    # Generate unique ID
    import uuid
    bubble_id = f"bubble_{uuid.uuid4().hex[:8]}"

    # Remove welcome bubble if it exists
    if "welcome" in window.multiverse_scene.bubbles:
        window.multiverse_scene.remove_bubble("welcome")

    # Add the new bubble
    window.add_bubble(
        bubble_id=bubble_id,
        title=title,
        message=message,
        color=BUBBLE_COLORS['active'],
        radius=BUBBLE_BASE_RADIUS,
    )

    bubble_count = len(window.multiverse_scene.bubbles)
    return f"Created bubble '{title}'. You now have {bubble_count} bubble(s) in the multiverse."


# Tool registry
MULTIVERSE_TOOLS = {
    "show_multiverse": show_multiverse,
    "hide_multiverse": hide_multiverse,
    "navigate_to_project": navigate_to_project,
    "show_all_projects": show_all_projects,
    "list_bubbles": list_bubbles,
    "list_orphan_ideas": list_orphan_ideas,
    "assign_idea_to_project": assign_idea_to_project,
    "refresh_multiverse": refresh_multiverse,
    "create_bubble": create_bubble,
}


def register_multiverse_tools(tools_manager) -> None:
    """Register all multiverse tools with the ClientToolsManager"""
    for tool_name, tool_func in MULTIVERSE_TOOLS.items():
        tools_manager.client_tools.register(tool_name, tool_func)
        print(f"  - {tool_name}")


# =============================================================================
# MAIN (for testing)
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MultiverseWindow.get_instance()
    window.show()

    print("Multiverse Canvas - Ego Perspective View")
    print(f"  Teardrop bubbles: {len(window.multiverse_scene.bubbles)}")
    print(f"  Particles: {len(window.multiverse_scene.particles)}")
    print()
    print("Controls:")
    print("  - Click bubble: Enter project")
    print("  - Mouse wheel: Zoom (limited)")
    print("  - Hover: Hand cursor on bubbles")

    sys.exit(app.exec_())
