"""
Cosmic Canvas - Voice-First Infinite Canvas with Dark Space Theme

A PyQt5 canvas for visualizing ideas, projects, and notes with:
- Dark cosmic background with twinkling stars
- Auto-layout grid (no manual positioning needed)
- Voice-controlled via ElevenLabs agent tools
- Multiple canvas islands in infinite space
- Project State criteria tracking
"""

import sys
import numpy as np
from typing import Optional, List, Dict, Any
from PyQt5.QtWidgets import (
    QApplication, QWidget, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsEllipseItem, QVBoxLayout, QLabel
)
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient,
    QRadialGradient, QPainterPath, QTransform
)

# Import data layer
sys.path.insert(0, '.')
from data import (
    CanvasNode, CanvasEdge, Idea, Project,
    CanvasRepository, IdeasRepository, ProjectsRepository
)


# =============================================================================
# CONSTANTS
# =============================================================================

# Colors
BACKGROUND_COLOR = QColor(10, 10, 18)  # Near-black with blue tint #0A0A12
STAR_COLOR_RANGE = (180, 240)  # HSV hue range for stars

# Node colors by type (HSV: hue, saturation%, value%)
NODE_COLORS = {
    'idea': (200, 60, 90),      # Blue
    'project': (120, 60, 90),   # Green
    'note': (45, 60, 90),       # Yellow
    'image': (280, 60, 90),     # Purple
    'link': (0, 60, 90),        # Red
    'figma': (340, 60, 90),     # Pink
}

# Layout
GRID_CELL_WIDTH = 280
GRID_CELL_HEIGHT = 180
GRID_COLUMNS = 4
GRID_PADDING = 40
NODE_WIDTH = 240
NODE_HEIGHT = 140
NODE_CORNER_RADIUS = 12

# Animation
STAR_COUNT = 800
ANIMATION_FPS = 30


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def hsv_to_rgb(h: float, s: float, v: float) -> tuple:
    """Convert HSV (0-360, 0-100, 0-100) to RGB (0-255, 0-255, 0-255)"""
    s = s / 100.0
    v = v / 100.0
    h = h / 60.0

    c = v * s
    x = c * (1 - abs((h % 2) - 1))
    m = v - c

    if h < 1:
        r, g, b = c, x, 0
    elif h < 2:
        r, g, b = x, c, 0
    elif h < 3:
        r, g, b = 0, c, x
    elif h < 4:
        r, g, b = 0, x, c
    elif h < 5:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def get_node_color(node_type: str, alpha: int = 200) -> QColor:
    """Get QColor for a node type"""
    if node_type in NODE_COLORS:
        h, s, v = NODE_COLORS[node_type]
        r, g, b = hsv_to_rgb(h, s, v)
        return QColor(r, g, b, alpha)
    return QColor(100, 100, 100, alpha)


# =============================================================================
# CANVAS NODE ITEM
# =============================================================================

class CanvasNodeItem(QGraphicsItem):
    """
    Visual representation of a canvas node.

    Displays:
    - Rounded rectangle background with type-specific color
    - Title text
    - Score badge for ideas
    - Progress bar for projects
    """

    def __init__(self, node_data: CanvasNode, linked_data: Any = None):
        super().__init__()
        self.node_data = node_data
        self.linked_data = linked_data  # Idea or Project object

        # Enable interactions
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setAcceptHoverEvents(True)

        # Visual state
        self._hovered = False
        self._width = NODE_WIDTH
        self._height = NODE_HEIGHT

        # Position from data
        self.setPos(node_data.x, node_data.y)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._width, self._height)

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        # Get node color
        base_color = get_node_color(self.node_data.node_type)

        # Hover/selection glow
        if self._hovered or self.isSelected():
            glow_color = QColor(base_color)
            glow_color.setAlpha(60)
            painter.setBrush(QBrush(glow_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(
                QRectF(-8, -8, self._width + 16, self._height + 16),
                NODE_CORNER_RADIUS + 4, NODE_CORNER_RADIUS + 4
            )

        # Background gradient
        gradient = QLinearGradient(0, 0, 0, self._height)
        gradient.setColorAt(0, QColor(base_color.red(), base_color.green(), base_color.blue(), 220))
        gradient.setColorAt(1, QColor(base_color.red() // 2, base_color.green() // 2, base_color.blue() // 2, 200))

        painter.setBrush(QBrush(gradient))

        # Border
        border_color = QColor(255, 255, 255, 80)
        if self.isSelected():
            border_color = QColor(255, 255, 255, 200)
        painter.setPen(QPen(border_color, 2))

        # Draw rounded rect
        painter.drawRoundedRect(
            QRectF(0, 0, self._width, self._height),
            NODE_CORNER_RADIUS, NODE_CORNER_RADIUS
        )

        # Draw content
        self._draw_content(painter)

    def _draw_content(self, painter: QPainter):
        """Draw node content based on type"""
        # Title
        title = self.node_data.title or "Untitled"
        if len(title) > 30:
            title = title[:27] + "..."

        painter.setPen(QPen(QColor(255, 255, 255, 240)))
        painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
        painter.drawText(QRectF(12, 10, self._width - 24, 24), Qt.AlignLeft, title)

        # Type badge
        type_text = self.node_data.node_type.upper()
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QPen(QColor(255, 255, 255, 150)))
        painter.drawText(QRectF(12, 36, self._width - 24, 16), Qt.AlignLeft, type_text)

        # Content based on type
        if self.node_data.node_type == 'idea' and self.linked_data:
            self._draw_idea_content(painter)
        elif self.node_data.node_type == 'project' and self.linked_data:
            self._draw_project_content(painter)
        elif self.node_data.content:
            self._draw_text_content(painter)

    def _draw_idea_content(self, painter: QPainter):
        """Draw idea-specific content (score badge, tags)"""
        idea = self.linked_data

        # Score badge
        score = idea.score if hasattr(idea, 'score') else 0
        score_color = QColor(255, 100, 100) if score < 50 else (
            QColor(255, 200, 100) if score < 70 else QColor(100, 255, 100)
        )

        # Draw score circle
        painter.setBrush(QBrush(score_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(self._width - 50, 60, 38, 38))

        # Score text
        painter.setPen(QPen(QColor(0, 0, 0)))
        painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
        painter.drawText(QRectF(self._width - 50, 60, 38, 38), Qt.AlignCenter, f"{int(score)}")

        # Status
        status = idea.status if hasattr(idea, 'status') else 'raw'
        painter.setPen(QPen(QColor(255, 255, 255, 180)))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(12, 60, 120, 20), Qt.AlignLeft, f"Status: {status}")

        # Tags (if any)
        if hasattr(idea, 'tags') and idea.tags:
            tags_text = ", ".join(idea.tags[:3])
            if len(idea.tags) > 3:
                tags_text += "..."
            painter.setPen(QPen(QColor(200, 200, 255, 180)))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(12, self._height - 30, self._width - 24, 20), Qt.AlignLeft, tags_text)

    def _draw_project_content(self, painter: QPainter):
        """Draw project-specific content (progress bar, status)"""
        project = self.linked_data

        # Progress bar background
        bar_x = 12
        bar_y = 70
        bar_width = self._width - 24
        bar_height = 12

        painter.setBrush(QBrush(QColor(50, 50, 50, 200)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_width, bar_height), 6, 6)

        # Progress bar fill
        progress = project.progress if hasattr(project, 'progress') else 0
        fill_width = (progress / 100.0) * bar_width

        progress_color = QColor(100, 200, 100, 220)
        painter.setBrush(QBrush(progress_color))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, fill_width, bar_height), 6, 6)

        # Progress text
        painter.setPen(QPen(QColor(255, 255, 255, 200)))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(bar_x, bar_y + 16, bar_width, 20), Qt.AlignCenter, f"{int(progress)}% complete")

        # Status
        status = project.status if hasattr(project, 'status') else 'active'
        painter.drawText(QRectF(12, self._height - 30, self._width - 24, 20), Qt.AlignLeft, f"Status: {status}")

    def _draw_text_content(self, painter: QPainter):
        """Draw text content for notes"""
        content = self.node_data.content or ""
        if len(content) > 100:
            content = content[:97] + "..."

        painter.setPen(QPen(QColor(220, 220, 220, 200)))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(
            QRectF(12, 55, self._width - 24, self._height - 65),
            Qt.AlignLeft | Qt.TextWordWrap,
            content
        )

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)


# =============================================================================
# CANVAS EDGE ITEM
# =============================================================================

class CanvasEdgeItem(QGraphicsItem):
    """Visual representation of an edge between nodes"""

    EDGE_COLORS = {
        'default': QColor(150, 150, 150, 150),
        'dependency': QColor(255, 153, 0, 180),
        'reference': QColor(0, 153, 255, 180),
        'flow': QColor(0, 255, 153, 180),
    }

    def __init__(self, from_node: CanvasNodeItem, to_node: CanvasNodeItem, edge_type: str = 'default'):
        super().__init__()
        self.from_node = from_node
        self.to_node = to_node
        self.edge_type = edge_type
        self.setZValue(-1)  # Behind nodes

    def boundingRect(self) -> QRectF:
        p1 = self.from_node.scenePos() + QPointF(NODE_WIDTH / 2, NODE_HEIGHT / 2)
        p2 = self.to_node.scenePos() + QPointF(NODE_WIDTH / 2, NODE_HEIGHT / 2)
        return QRectF(p1, p2).normalized().adjusted(-10, -10, 10, 10)

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        # Get connection points (center of nodes)
        p1 = self.from_node.scenePos() + QPointF(NODE_WIDTH / 2, NODE_HEIGHT / 2)
        p2 = self.to_node.scenePos() + QPointF(NODE_WIDTH / 2, NODE_HEIGHT / 2)

        # Get edge color
        color = self.EDGE_COLORS.get(self.edge_type, self.EDGE_COLORS['default'])

        # Draw line
        pen = QPen(color, 2)
        if self.edge_type == 'dependency':
            pen.setStyle(Qt.DashLine)
        elif self.edge_type == 'reference':
            pen.setStyle(Qt.DotLine)

        painter.setPen(pen)
        painter.drawLine(p1, p2)

        # Draw arrow for flow edges
        if self.edge_type == 'flow':
            self._draw_arrow(painter, p1, p2, color)

    def _draw_arrow(self, painter: QPainter, p1: QPointF, p2: QPointF, color: QColor):
        """Draw arrow head at p2"""
        import math

        angle = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
        arrow_size = 12

        # Arrow points
        arrow_p1 = QPointF(
            p2.x() - arrow_size * math.cos(angle - math.pi / 6),
            p2.y() - arrow_size * math.sin(angle - math.pi / 6)
        )
        arrow_p2 = QPointF(
            p2.x() - arrow_size * math.cos(angle + math.pi / 6),
            p2.y() - arrow_size * math.sin(angle + math.pi / 6)
        )

        painter.setBrush(QBrush(color))
        path = QPainterPath()
        path.moveTo(p2)
        path.lineTo(arrow_p1)
        path.lineTo(arrow_p2)
        path.closeSubpath()
        painter.drawPath(path)


# =============================================================================
# STARFIELD BACKGROUND
# =============================================================================

class StarfieldBackground:
    """
    Twinkling star background for cosmic canvas.
    Uses same patterns as voice_dialog_visual.py
    """

    def __init__(self, scene_rect: QRectF, num_stars: int = STAR_COUNT):
        self.scene_rect = scene_rect
        self.stars = self._init_stars(num_stars)
        self.time = 0.0

    def _init_stars(self, num_stars: int) -> List[Dict]:
        """Initialize star particles"""
        stars = []
        for _ in range(num_stars):
            stars.append({
                'x': np.random.uniform(self.scene_rect.left(), self.scene_rect.right()),
                'y': np.random.uniform(self.scene_rect.top(), self.scene_rect.bottom()),
                'hue': np.random.uniform(*STAR_COLOR_RANGE),
                'base_size': np.random.uniform(1, 4),
                'fade_phase': np.random.uniform(0, np.pi * 2),
                'fade_speed': np.random.uniform(0.02, 0.05),
                'brightness': np.random.uniform(0.4, 1.0),
            })
        return stars

    def update(self, dt: float = 0.033):
        """Update star animation"""
        self.time += dt
        for star in self.stars:
            star['fade_phase'] += star['fade_speed']

    def draw(self, painter: QPainter, visible_rect: QRectF):
        """Draw visible stars"""
        painter.setRenderHint(QPainter.Antialiasing)

        for star in self.stars:
            # Check if star is in visible area (with margin)
            if not visible_rect.adjusted(-50, -50, 50, 50).contains(star['x'], star['y']):
                continue

            # Calculate twinkle alpha
            phase_normalized = (star['fade_phase'] % (np.pi * 2)) / (np.pi * 2)

            if phase_normalized < 0.25:
                fade_alpha = np.sin(phase_normalized / 0.25 * np.pi)
            else:
                fade_alpha = 0.0

            if fade_alpha < 0.05:
                continue

            # Get star color
            r, g, b = hsv_to_rgb(star['hue'], 40, star['brightness'] * 100)
            alpha = int(fade_alpha * 255 * star['brightness'])

            color = QColor(r, g, b, alpha)
            size = star['base_size'] * (0.5 + fade_alpha * 0.5)

            # Draw star
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(
                QPointF(star['x'], star['y']),
                size, size
            )


# =============================================================================
# COSMIC CANVAS SCENE
# =============================================================================

class CosmicCanvasScene(QGraphicsScene):
    """
    QGraphicsScene with starfield background and node management.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set large scene rect for infinite canvas feel
        self.setSceneRect(-5000, -5000, 10000, 10000)
        self.setBackgroundBrush(QBrush(BACKGROUND_COLOR))

        # Initialize starfield
        self.starfield = StarfieldBackground(self.sceneRect())

        # Node tracking
        self.node_items: Dict[str, CanvasNodeItem] = {}
        self.edge_items: List[CanvasEdgeItem] = []

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draw cosmic background with stars"""
        # Fill background
        painter.fillRect(rect, BACKGROUND_COLOR)

        # Draw stars
        self.starfield.draw(painter, rect)

    def update_animation(self):
        """Called by timer to update starfield"""
        self.starfield.update()
        self.invalidate(self.sceneRect(), QGraphicsScene.BackgroundLayer)


# =============================================================================
# COSMIC CANVAS VIEW
# =============================================================================

class CosmicCanvasView(QGraphicsView):
    """
    QGraphicsView with pan/zoom and animation timer.
    """

    def __init__(self, scene: CosmicCanvasScene, parent=None):
        super().__init__(scene, parent)

        # View settings
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # Zoom state
        self._zoom = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 3.0

    def wheelEvent(self, event):
        """Handle zoom with mouse wheel"""
        zoom_factor = 1.15

        if event.angleDelta().y() > 0:
            # Zoom in
            if self._zoom < self._max_zoom:
                self._zoom *= zoom_factor
                self.scale(zoom_factor, zoom_factor)
        else:
            # Zoom out
            if self._zoom > self._min_zoom:
                self._zoom /= zoom_factor
                self.scale(1 / zoom_factor, 1 / zoom_factor)


# =============================================================================
# COSMIC CANVAS WINDOW
# =============================================================================

class CosmicCanvasWindow(QWidget):
    """
    Main window for the Cosmic Canvas.

    Voice-first design:
    - Opens via voice command "show canvas"
    - Nodes added via voice commands
    - Auto-layout manages positioning
    """

    # Singleton instance
    _instance = None

    # Signals
    canvas_updated = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Window setup
        self.setWindowTitle("Vibemind Cosmic Canvas")
        self.setMinimumSize(800, 600)

        # Create scene and view
        self.scene = CosmicCanvasScene()
        self.view = CosmicCanvasView(self.scene)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        # Data repositories
        self.canvas_repo = CanvasRepository()
        self.ideas_repo = IdeasRepository()
        self.projects_repo = ProjectsRepository()

        # Animation timer
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._on_animation_tick)
        self.animation_timer.start(int(1000 / ANIMATION_FPS))

        # Load existing data
        self.refresh_from_database()

        # Center view
        self.view.centerOn(0, 0)

    @classmethod
    def get_instance(cls) -> 'CosmicCanvasWindow':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = CosmicCanvasWindow()
        return cls._instance

    def _on_animation_tick(self):
        """Update animation each frame"""
        self.scene.update_animation()

    def refresh_from_database(self):
        """Load nodes and edges from database"""
        # Clear existing items
        for item in self.scene.node_items.values():
            self.scene.removeItem(item)
        for item in self.scene.edge_items:
            self.scene.removeItem(item)

        self.scene.node_items.clear()
        self.scene.edge_items.clear()

        # Load nodes
        nodes = self.canvas_repo.list_nodes(limit=500)

        for i, node in enumerate(nodes):
            # Auto-position if not set
            if node.x == 0 and node.y == 0:
                node.x, node.y = self._auto_position(i)
                # Update in database
                self.canvas_repo.update_node(node)

            # Get linked data
            linked_data = None
            if node.linked_idea_id:
                linked_data = self.ideas_repo.get(node.linked_idea_id)
            elif node.linked_project_id:
                linked_data = self.projects_repo.get(node.linked_project_id)

            # Create visual item
            item = CanvasNodeItem(node, linked_data)
            self.scene.addItem(item)
            self.scene.node_items[node.id] = item

        # Load edges
        edges = self.canvas_repo.list_edges(limit=500)

        for edge in edges:
            from_item = self.scene.node_items.get(edge.from_node_id)
            to_item = self.scene.node_items.get(edge.to_node_id)

            if from_item and to_item:
                edge_item = CanvasEdgeItem(from_item, to_item, edge.edge_type)
                self.scene.addItem(edge_item)
                self.scene.edge_items.append(edge_item)

        self.canvas_updated.emit()

    def _auto_position(self, index: int) -> tuple:
        """Calculate auto-layout position for a node"""
        col = index % GRID_COLUMNS
        row = index // GRID_COLUMNS

        x = col * GRID_CELL_WIDTH + GRID_PADDING
        y = row * GRID_CELL_HEIGHT + GRID_PADDING

        return x, y

    def add_node(self, node_type: str, title: str, content: str = "",
                 linked_idea_id: str = None, linked_project_id: str = None) -> CanvasNode:
        """Add a new node to the canvas"""
        # Calculate position
        index = len(self.scene.node_items)
        x, y = self._auto_position(index)

        # Create in database
        node = self.canvas_repo.create_node(
            node_type=node_type,
            title=title,
            content=content,
            x=x, y=y,
            linked_idea_id=linked_idea_id,
            linked_project_id=linked_project_id,
        )

        # Get linked data
        linked_data = None
        if linked_idea_id:
            linked_data = self.ideas_repo.get(linked_idea_id)
        elif linked_project_id:
            linked_data = self.projects_repo.get(linked_project_id)

        # Create visual item
        item = CanvasNodeItem(node, linked_data)
        self.scene.addItem(item)
        self.scene.node_items[node.id] = item

        self.canvas_updated.emit()
        return node

    def auto_arrange(self):
        """Re-arrange all nodes using auto-layout"""
        nodes = list(self.scene.node_items.values())

        for i, item in enumerate(nodes):
            x, y = self._auto_position(i)
            item.setPos(x, y)

            # Update in database
            item.node_data.x = x
            item.node_data.y = y
            self.canvas_repo.update_node(item.node_data)

        self.canvas_updated.emit()

    def focus_on_node(self, node_id: str):
        """Center view on a specific node"""
        if node_id in self.scene.node_items:
            item = self.scene.node_items[node_id]
            self.view.centerOn(item)

    def closeEvent(self, event):
        """Handle window close - just hide, don't destroy"""
        self.hide()
        event.ignore()


# =============================================================================
# VOICE TOOL FUNCTIONS
# =============================================================================

def get_canvas_instance() -> Optional[CosmicCanvasWindow]:
    """Get the canvas window instance (creates if needed)"""
    try:
        # Check if QApplication exists
        app = QApplication.instance()
        if app is None:
            return None
        return CosmicCanvasWindow.get_instance()
    except Exception:
        return None


def show_canvas(params: Dict[str, Any]) -> str:
    """
    Voice tool: Open/focus the cosmic canvas window.

    Usage: "Show my canvas"
    """
    canvas = get_canvas_instance()
    if canvas:
        canvas.show()
        canvas.raise_()
        canvas.activateWindow()
        return "Canvas is now visible."
    return "Canvas is not available. Make sure the UI is running."


def hide_canvas(params: Dict[str, Any]) -> str:
    """
    Voice tool: Hide the cosmic canvas window.

    Usage: "Hide the canvas"
    """
    canvas = get_canvas_instance()
    if canvas:
        canvas.hide()
        return "Canvas hidden."
    return "Canvas is not available."


def auto_arrange_canvas(params: Dict[str, Any]) -> str:
    """
    Voice tool: Re-arrange all nodes using auto-layout.

    Usage: "Arrange the canvas"
    """
    canvas = get_canvas_instance()
    if canvas:
        canvas.auto_arrange()
        return "Canvas nodes have been arranged."
    return "Canvas is not available."


def refresh_canvas(params: Dict[str, Any]) -> str:
    """
    Voice tool: Refresh canvas from database.

    Usage: "Refresh the canvas"
    """
    canvas = get_canvas_instance()
    if canvas:
        canvas.refresh_from_database()
        return "Canvas refreshed from database."
    return "Canvas is not available."


# Canvas tools registry
CANVAS_TOOLS = {
    "show_canvas": show_canvas,
    "hide_canvas": hide_canvas,
    "auto_arrange_canvas": auto_arrange_canvas,
    "refresh_canvas": refresh_canvas,
}


def register_canvas_tools(tools_manager) -> None:
    """Register canvas tools with ClientToolsManager"""
    for tool_name, tool_func in CANVAS_TOOLS.items():
        tools_manager.client_tools.register(tool_name, tool_func)
        print(f"  - {tool_name}")


# =============================================================================
# MAIN (for standalone testing)
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Create and show canvas
    canvas = CosmicCanvasWindow.get_instance()
    canvas.show()

    # Add some test nodes
    canvas.add_node("idea", "Voice-controlled workspace", "Build a desktop app for ideas")
    canvas.add_node("project", "Vibemind MVP", "First version of the workspace")
    canvas.add_node("note", "Design thoughts", "Dark theme with stars, cosmic feel")
    canvas.add_node("idea", "AI orchestration layer", "Connect multiple LLMs")

    sys.exit(app.exec_())
