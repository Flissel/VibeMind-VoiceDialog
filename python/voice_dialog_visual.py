"""
Voice Dialog Visual - Fully integrated multi-agent voice assistant with audio-reactive visuals

Features:
- Voice input (speech-to-text)
- Multi-agent system with handoffs
- TTS output that drives visual animation
- Transparent circular starfield interface
"""

import sys
import asyncio
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QTextEdit
from PyQt5.QtCore import QTimer, Qt, QPointF, QEvent
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont
from audio_analyzer import AudioAnalyzer, AudioFeatures
from voice_bridge import get_voice_bridge


def safe_print(text: str):
    """
    Safely print text, handling Unicode characters that Windows console can't encode
    Strips emoji and special Unicode characters to prevent UnicodeEncodeError
    """
    try:
        # Try to encode with console encoding
        text.encode(sys.stdout.encoding or 'utf-8')
        print(text)
    except (UnicodeEncodeError, AttributeError):
        # Fallback: encode to ASCII, replacing problematic characters
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print(safe_text)


class VoiceDialogVisual(QWidget):
    """Complete voice dialog system with visual interface"""

    def __init__(self):
        super().__init__()

        # Window setup
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Size and position
        screen = QApplication.primaryScreen().geometry()
        circle_size = int((min(screen.width(), screen.height()) - 100) * 0.67)  # 33% smaller
        window_height = circle_size + 120
        self.setGeometry(
            (screen.width() - circle_size) // 2,
            (screen.height() - window_height) // 2,
            circle_size, window_height
        )

        # Circle parameters
        self.center_x = circle_size / 2
        self.center_y = circle_size / 2
        self.radius = circle_size / 2.6

        # Audio analyzer
        self.audio_analyzer = AudioAnalyzer(sample_rate=44100)
        self.audio_buffer = np.zeros(2048, dtype=np.float32)
        self.current_audio = AudioFeatures(
            amplitude=0.0, bass=0.0, mid=0.0, treble=0.0,
            spectrum=[0.0] * 64, beat_detected=0.0
        )

        # Voice bridge (will be initialized async)
        self.voice_bridge = None
        self.agent_status = "idle"  # idle, listening, thinking, speaking
        self.active_agent = "general"  # Current active agent: general, desktop, research, code
        self.agent_message = "Ready"  # Status message to display

        # Auto-start setting (loaded from config)
        from config import get_config
        self.auto_start_enabled = get_config().moire_tracker.auto_start

        # Visual state
        self.demo_time = 0.0
        self.phase = 0.0
        self.hue_offset = 0.0

        # Agent-specific colors (H, S, V)
        # Phase 1: Color-code circle by active agent
        self.agent_colors = {
            # Status-based colors
            "idle": (180, 0.7, 0.8),        # Cyan
            "listening": (120, 0.8, 0.9),   # Green
            "thinking": (270, 0.7, 0.8),    # Purple
            "speaking": (30, 0.9, 0.9),     # Orange
            # Agent-based colors (Phase 1)
            "general": (200, 0.6, 0.8),     # Blue - General/Orchestrator
            "desktop": (120, 0.8, 0.9),     # Green - Desktop Agent
            "research": (0, 0.8, 0.9),      # Red - Research Agent
            "code": (280, 0.8, 0.9),        # Purple - Code Agent
            "devops": (30, 0.9, 0.9),       # Orange - DevOps/System
        }

        # Agent display names (Phase 1)
        self.agent_names = {
            "general": "General Chat",
            "desktop": "Desktop Agent",
            "research": "Research Agent",
            "code": "Code Agent",
            "devops": "DevOps Monitor"
        }

        # Phase 2: Circle menu state
        self.menu_visible = False
        self.menu_pinned = False

        # Phase 3: Context-specific actions
        self.desktop_elements_cache = []  # Cached desktop elements for overlay
        self.overlay_visible = False  # Desktop element overlay visibility

        # Store button areas for click detection
        self.button1_rect = None
        self.button2_rect = None
        self.pin_button_rect = None

        # Phase 4: Power user mode locking
        self.locked_mode = None  # None, "desktop", "code", "devops"
        self.settings_menu_visible = False

        # Moiré pattern
        self.num_rings = 40
        self.num_rays = 80

        # Particles
        self.particles = self._init_particles()

        # Mouse interaction
        self.dragging = False
        self.resizing = False
        self.drag_position = None
        self.resize_corner = None

        # Chat input
        self.chat_input = QTextEdit(self)
        self.chat_input.setPlaceholderText("Type or press V for voice...")
        self.chat_input.setFont(QFont("Arial", 10))
        self.chat_input.setMaximumHeight(32)
        self.chat_input.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0, 0, 0, 150);
                color: white;
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 6px;
                padding: 6px;
            }
        """)
        self.chat_input.textChanged.connect(self._on_text_changed)
        self.chat_input.installEventFilter(self)  # Intercept Enter key
        self.chat_input.setFocus()  # Give chat focus on startup
        self._position_chat_input()

        # Animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_visual)
        self.timer.start(33)  # 30 FPS

        # Initialize voice bridge asynchronously (will be set up after event loop starts)
        self.voice_bridge_ready = False

        # Schedule voice bridge initialization after event loop is running
        QTimer.singleShot(100, lambda: asyncio.ensure_future(self._init_voice_bridge()))

        print("[VOICE DIALOG] Ready!")
        print("Controls:")
        print("  V - Voice input (speak)")
        print("  Enter - Send text")
        print("  Click circle - Open status menu (Phase 2)")
        print("  ESC - Exit")
        print("  Mouse wheel/Arrow keys - Resize")
        print(f"\nPhase 1: [OK] Smart visual feedback (color-coded agents)")
        print(f"Phase 2: [OK] Circle menu with system status")
        print(f"Auto-start: {'ENABLED' if self.auto_start_enabled else 'DISABLED'}")

    async def _init_voice_bridge(self):
        """Initialize voice bridge asynchronously"""
        try:
            print("[VOICE DIALOG] Initializing voice bridge...")
            self.voice_bridge = await get_voice_bridge()

            # Connect callbacks
            self.voice_bridge.set_audio_callback(self._on_tts_audio)
            self.voice_bridge.set_text_callback(self._on_speech_recognized)
            self.voice_bridge.set_response_callback(self._on_agent_response)

            # Set agent status callbacks
            if self.voice_bridge.orchestrator:
                self.voice_bridge.orchestrator.set_status_callback(self._on_agent_status)

            self.voice_bridge_ready = True
            print("[VOICE DIALOG] Voice bridge ready!")
        except Exception as e:
            print(f"[VOICE DIALOG] Voice bridge error: {e}")
            self.voice_bridge_ready = False

    def _on_tts_audio(self, audio_chunk: np.ndarray):
        """
        Callback when TTS audio is generated
        This audio drives the visual animation!
        """
        if len(audio_chunk) == 2048:  # Match our buffer size
            self.audio_buffer = audio_chunk
            # Audio will be processed in next update cycle

    def _on_speech_recognized(self, text: str):
        """Callback when speech is recognized"""
        safe_print(f"[VOICE DIALOG] Recognized: {text}")
        # Could display in chat or status area

    def _on_agent_response(self, response: str):
        """Callback when agent responds"""
        safe_print(f"[VOICE DIALOG] Agent: {response[:100]}...")
        # Don't display in chat input - it causes the input to hide
        # Just log to console for now
        # TODO: Add a proper chat history display area

    def _on_agent_status(self, status: str, message: str, agent: str = None):
        """
        Callback for agent status updates
        Phase 1: Track active agent for color-coding
        """
        self.agent_status = status
        self.agent_message = message

        # Phase 1: Update active agent if provided
        if agent:
            if agent.lower() in self.agent_colors:
                self.active_agent = agent.lower()
            print(f"[VOICE DIALOG] Agent: {agent} | Status: {status} - {message}")
        else:
            print(f"[VOICE DIALOG] Status: {status} - {message}")

    def _position_chat_input(self):
        """Position chat input below circle"""
        margin = 40
        input_width = self.width() - (margin * 2)
        chat_y = int(self.center_y + self.radius + 50)

        if self.width() < 300 or chat_y + self.chat_input.maximumHeight() + margin > self.height():
            self.chat_input.hide()
        else:
            self.chat_input.show()
            self.chat_input.setGeometry(
                margin, chat_y, input_width,
                self.chat_input.maximumHeight()
            )

    def _on_text_changed(self):
        """Auto-expand chat input"""
        doc_height = self.chat_input.document().size().height()
        new_height = min(150, max(32, int(doc_height + 16)))
        self.chat_input.setMaximumHeight(new_height)
        self._position_chat_input()

    def _on_return_pressed(self):
        """Handle Enter key in chat"""
        text = self.chat_input.toPlainText().strip()
        print(f"[GUI DEBUG] _on_return_pressed called")
        print(f"[GUI DEBUG] Input text: '{text}'")
        print(f"[GUI DEBUG] Bridge ready: {self.voice_bridge is not None}")
        print(f"[GUI DEBUG] Chat input has focus: {self.chat_input.hasFocus()}")
        safe_print(f"[VOICE DIALOG] Enter pressed. Text: '{text}', Bridge ready: {self.voice_bridge is not None}")
        if text and self.voice_bridge:
            self.chat_input.clear()
            self.chat_input.setFocus()  # Restore focus after clearing
            print(f"[GUI DEBUG] Focus restored: {self.chat_input.hasFocus()}")
            safe_print(f"[VOICE DIALOG] Sending to agents: {text}")
            # Process text input through voice bridge
            asyncio.ensure_future(self.voice_bridge.process_voice_input(text))
        elif text and not self.voice_bridge:
            print("[VOICE DIALOG] Voice bridge not ready yet, please wait...")
        else:
            print(f"[GUI DEBUG] Message not sent: text={bool(text)}, bridge={self.voice_bridge is not None}")

    def _init_particles(self):
        """Initialize star particles"""
        particles = []
        for i in range(500):
            r = np.random.rand() * 0.9
            theta = np.random.rand() * 2 * np.pi

            particles.append({
                'x': r * np.cos(theta),
                'y': r * np.sin(theta),
                'vx': -np.sin(theta) * 0.0002,
                'vy': np.cos(theta) * 0.0002,
                'hue': np.random.rand() * 360,
                'base_size': np.random.uniform(2, 6),
                'fade_phase': np.random.rand() * np.pi * 2,
                'fade_speed': np.random.uniform(0.01, 0.03),
                'depth': np.random.rand()
            })
        return particles

    def _generate_demo_audio(self, t):
        """Demo audio when not speaking"""
        amplitude = 0.3 + 0.2 * np.sin(t * 1.2)
        bass = 0.4 + 0.3 * np.sin(t * 0.8)
        mid = 0.5 + 0.2 * np.sin(t * 1.5)
        treble = 0.3 + 0.25 * np.sin(t * 2.5)
        beat = 1.0 if (t % 0.6) < 0.06 else 0.0
        spectrum = [0.4 + 0.3 * np.sin(t * 1.2 + i * 0.15) for i in range(64)]

        return AudioFeatures(
            amplitude=float(np.clip(amplitude, 0, 1)),
            bass=float(np.clip(bass, 0, 1)),
            mid=float(np.clip(mid, 0, 1)),
            treble=float(np.clip(treble, 0, 1)),
            spectrum=spectrum, beat_detected=beat
        )

    def update_visual(self):
        """Update animation"""
        # Process audio
        if self.voice_bridge and self.voice_bridge.speaking and len(self.audio_buffer) > 0:
            # Agent is speaking! Use TTS audio
            self.current_audio = self.audio_analyzer.analyze(self.audio_buffer)
        else:
            # Demo mode
            self.demo_time += 0.033
            self.current_audio = self._generate_demo_audio(self.demo_time)

        audio = self.current_audio

        # Update phase
        self.phase += audio.amplitude * 0.05 + 0.01
        self.hue_offset += audio.amplitude * 0.5

        # Update particles
        for p in self.particles:
            speed_mult = 1.0 + audio.amplitude * 0.05 * p['depth']
            p['x'] += p['vx'] * speed_mult
            p['y'] += p['vy'] * speed_mult

            # Bounce at boundary
            r = np.sqrt(p['x']**2 + p['y']**2)
            if r > 0.92:
                theta = np.arctan2(p['y'], p['x'])
                p['x'] = 0.92 * np.cos(theta)
                p['y'] = 0.92 * np.sin(theta)

                random_angle = np.random.rand() * 2 * np.pi
                speed = np.sqrt(p['vx']**2 + p['vy']**2)
                dx = -p['x'] * 0.5 + np.cos(random_angle) * 0.5
                dy = -p['y'] * 0.5 + np.sin(random_angle) * 0.5
                length = np.sqrt(dx**2 + dy**2)
                p['vx'] = (dx / length) * speed
                p['vy'] = (dy / length) * speed

        self.update()

    def paintEvent(self, event):
        """Paint the visual"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        audio = self.current_audio

        # Phase 1: Get color based on active agent (not just status)
        # Priority: active_agent color > status color > idle
        if self.active_agent in self.agent_colors:
            agent_hue, agent_sat, agent_val = self.agent_colors[self.active_agent]
        elif self.agent_status in self.agent_colors:
            agent_hue, agent_sat, agent_val = self.agent_colors[self.agent_status]
        else:
            agent_hue, agent_sat, agent_val = self.agent_colors["idle"]

        # Draw black circle background
        painter.setBrush(QBrush(QColor(0, 0, 0, 255)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(
            QPointF(self.center_x, self.center_y),
            self.radius, self.radius
        )

        # Draw moiré rings with agent color influence
        for i in range(1, self.num_rings + 1):
            base_radius = (i / self.num_rings) * self.radius
            pulse = audio.bass * 0.01 * self.radius * np.sin(self.phase + i * 0.3)
            ring_radius = base_radius + pulse

            # Mix base hue with agent hue
            hue = int((i * 8 + self.hue_offset + audio.mid * 150 + agent_hue * 0.3) % 360)
            color = self._hsv_to_rgb(hue, 0.7, 0.8)
            alpha = int((0.15 + audio.amplitude * 0.05) * 255)

            pen = QPen(QColor(color[0], color[1], color[2], alpha))
            pen.setWidthF(0.5 + audio.beat_detected * 0.1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(
                QPointF(self.center_x, self.center_y),
                ring_radius, ring_radius
            )

        # Draw rays
        ray_rotation = self.phase * 0.01
        for i in range(self.num_rays):
            theta = (i / self.num_rays) * 2 * np.pi + ray_rotation
            length = (0.95 + audio.treble * 0.02) * self.radius

            x = self.center_x + length * np.cos(theta)
            y = self.center_y + length * np.sin(theta)

            hue = int((i * 4 + self.hue_offset + audio.treble * 200) % 360)
            color = self._hsv_to_rgb(hue, 0.8, 0.7)
            alpha = int((0.1 + audio.amplitude * 0.04) * 255)

            pen = QPen(QColor(color[0], color[1], color[2], alpha))
            pen.setWidthF(0.4 + audio.beat_detected * 0.08)
            painter.setPen(pen)
            painter.drawLine(
                QPointF(self.center_x, self.center_y),
                QPointF(x, y)
            )

        # Draw stars
        for p in self.particles:
            p['fade_phase'] += p['fade_speed']
            phase_normalized = (p['fade_phase'] % (2 * np.pi)) / (2 * np.pi)

            if phase_normalized < 0.25:
                local_phase = phase_normalized / 0.25
                fade_alpha = np.sin(local_phase * np.pi)
            else:
                fade_alpha = 0.0

            if fade_alpha < 0.01:
                continue

            px = self.center_x + p['x'] * self.radius
            py = self.center_y + p['y'] * self.radius

            freq_idx = int(len(self.particles)) % len(audio.spectrum)
            freq_val = audio.spectrum[freq_idx]

            hue_shift = (audio.bass * 10 + audio.mid * 20 + audio.treble * 30)
            final_hue = int((p['hue'] + hue_shift * 0.1) % 360)

            base_brightness = 0.8 + audio.amplitude * 0.05 + freq_val * 0.05
            brightness = base_brightness * fade_alpha

            color = self._hsv_to_rgb(final_hue, 0.2, brightness)
            alpha = int(fade_alpha * 255)

            size = p['base_size'] * (0.8 + p['depth'] * 0.4) * fade_alpha
            painter.setBrush(QBrush(QColor(color[0], color[1], color[2], alpha)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(px, py), size/2, size/2)

        # Draw boundary with agent color
        boundary_hue = int((agent_hue + audio.mid * 100) % 360)
        boundary_color = self._hsv_to_rgb(boundary_hue, agent_sat, agent_val)
        alpha = int((0.4 + audio.amplitude * 0.02) * 255)

        pen = QPen(QColor(boundary_color[0], boundary_color[1], boundary_color[2], alpha))
        pen.setWidthF(2 + audio.beat_detected * 0.3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(
            QPointF(self.center_x, self.center_y),
            self.radius * 0.98, self.radius * 0.98
        )

        # Draw auto-start indicator at center
        if self.auto_start_enabled:
            # Draw green checkmark/dot
            painter.setBrush(QBrush(QColor(0, 255, 100, 180)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(self.center_x, self.center_y), 8, 8)
        else:
            # Draw gray dot
            painter.setBrush(QBrush(QColor(100, 100, 100, 100)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(self.center_x, self.center_y), 6, 6)

        # Phase 1: Draw agent name and status at bottom
        agent_name = self.agent_names.get(self.active_agent, "Unknown Agent")
        agent_text = f"{agent_name}"
        if self.agent_message and self.agent_message != "Ready":
            agent_text += f"\n{self.agent_message}"

        # Draw semi-transparent background for text
        text_font = QFont("Arial", 11, QFont.Bold)
        painter.setFont(text_font)
        text_rect = painter.boundingRect(0, 0, self.width(), 100, Qt.AlignCenter, agent_text)
        text_y = int(self.center_y + self.radius + 10)
        text_rect.moveCenter(QPointF(self.center_x, text_y).toPoint())

        # Draw background
        bg_rect = text_rect.adjusted(-10, -5, 10, 5)
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bg_rect, 8, 8)

        # Draw text with agent color
        text_color = self._hsv_to_rgb(agent_hue, agent_sat, agent_val)
        painter.setPen(QPen(QColor(text_color[0], text_color[1], text_color[2], 230)))
        painter.drawText(text_rect, Qt.AlignCenter, agent_text)

        # Phase 2: Draw status menu if visible
        if self.menu_visible:
            self._draw_status_menu(painter, agent_hue, agent_sat, agent_val)

        # Phase 3: Draw desktop element overlay if visible
        if self.overlay_visible and self.desktop_elements_cache:
            self._draw_desktop_overlay(painter)

        # Phase 4: Draw settings menu if visible
        if self.settings_menu_visible:
            self._draw_settings_menu(painter, agent_hue, agent_sat, agent_val)

        # Draw resize indicator
        corner_size = 50
        painter.setPen(QPen(QColor(100, 100, 100, 100)))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(
            int(self.width() - corner_size), int(self.height()),
            int(self.width()), int(self.height() - corner_size)
        )

    def _draw_status_menu(self, painter, agent_hue, agent_sat, agent_val):
        """
        Phase 2: Draw status menu popup
        Shows: active agent, system health, quick actions
        """
        # Menu dimensions
        menu_width = 280
        menu_height = 200
        menu_x = int(self.center_x - menu_width / 2)
        menu_y = int(self.center_y - menu_height / 2)

        # Draw menu background
        painter.setBrush(QBrush(QColor(20, 20, 20, 240)))
        painter.setPen(QPen(QColor(60, 60, 60, 200), 2))
        painter.drawRoundedRect(menu_x, menu_y, menu_width, menu_height, 12, 12)

        # Draw header with agent color
        header_height = 40
        agent_color_rgb = self._hsv_to_rgb(agent_hue, agent_sat, agent_val)
        painter.setBrush(QBrush(QColor(agent_color_rgb[0], agent_color_rgb[1], agent_color_rgb[2], 100)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(menu_x, menu_y, menu_width, header_height, 12, 12)

        # Draw agent icon (colored circle)
        icon_size = 20
        icon_x = menu_x + 15
        icon_y = menu_y + 10
        painter.setBrush(QBrush(QColor(agent_color_rgb[0], agent_color_rgb[1], agent_color_rgb[2], 220)))
        painter.drawEllipse(icon_x, icon_y, icon_size, icon_size)

        # Draw agent name in header
        painter.setPen(QPen(QColor(255, 255, 255, 255)))
        header_font = QFont("Arial", 11, QFont.Bold)
        painter.setFont(header_font)
        agent_name = self.agent_names.get(self.active_agent, "Unknown")
        painter.drawText(menu_x + 45, menu_y + 25, agent_name)

        # Content area
        content_y = menu_y + header_height + 15
        content_font = QFont("Arial", 9)
        painter.setFont(content_font)

        # System health section
        painter.setPen(QPen(QColor(180, 180, 180, 255)))
        painter.drawText(menu_x + 15, content_y, "System Status:")

        content_y += 18
        # Check MoireTracker status - check orchestrator's desktop agent
        moire_connected = False
        if self.voice_bridge and hasattr(self.voice_bridge, 'orchestrator'):
            orchestrator = self.voice_bridge.orchestrator
            if hasattr(orchestrator, 'desktop_agent'):
                desktop_agent = orchestrator.desktop_agent
                if hasattr(desktop_agent, 'moire_client') and desktop_agent.moire_client:
                    moire_connected = desktop_agent.moire_client.connected

        moire_status = "[OK] Running" if moire_connected else "[!] Not Connected"
        moire_color = QColor(100, 255, 100, 255) if moire_connected else QColor(255, 200, 100, 255)
        painter.setPen(QPen(moire_color))
        painter.drawText(menu_x + 25, content_y, f"MoireTracker: {moire_status}")

        content_y += 18
        # Show element count if connected
        if moire_connected:
            painter.setPen(QPen(QColor(200, 200, 200, 255)))
            element_count = len(self.desktop_elements_cache) if self.desktop_elements_cache else 0
            painter.drawText(menu_x + 25, content_y, f"Elements detected: {element_count}")

        # Phase 3: Agent-specific quick actions
        content_y += 30
        painter.setPen(QPen(QColor(180, 180, 180, 255)))

        # Different actions based on active agent
        if self.active_agent == "desktop":
            painter.drawText(menu_x + 15, content_y, "Desktop Actions:")
        elif self.active_agent == "code":
            painter.drawText(menu_x + 15, content_y, "Code Actions:")
        elif self.active_agent == "devops":
            painter.drawText(menu_x + 15, content_y, "DevOps Actions:")
        else:
            painter.drawText(menu_x + 15, content_y, "Quick Actions:")

        # Draw action buttons
        button_y = content_y + 10
        button_height = 28
        button_width = (menu_width - 50) // 2

        # Phase 3: Context-specific button labels
        if self.active_agent == "desktop":
            button1_text = "Show Overlay"
            button2_text = "Rescan"
        elif self.active_agent == "code":
            button1_text = "File Context"
            button2_text = "Explain"
        elif self.active_agent == "devops":
            button1_text = "Health Check"
            button2_text = "Logs"
        else:
            button1_text = "Settings"
            button2_text = "Help"

        # Button 1 (left)
        button1_x = menu_x + 15
        painter.setBrush(QBrush(QColor(40, 40, 40, 200)))
        painter.setPen(QPen(QColor(80, 80, 80, 200), 1))
        painter.drawRoundedRect(button1_x, button_y, button_width, button_height, 6, 6)
        painter.setPen(QPen(QColor(200, 200, 200, 255)))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(button1_x, button_y, button_width, button_height, Qt.AlignCenter, button1_text)

        # Store button 1 rect for click detection (Phase 3)
        self.button1_rect = (button1_x, button_y, button_width, button_height)

        # Button 2 (right)
        button2_x = button1_x + button_width + 10
        painter.setBrush(QBrush(QColor(40, 40, 40, 200)))
        painter.setPen(QPen(QColor(80, 80, 80, 200), 1))
        painter.drawRoundedRect(button2_x, button_y, button_width, button_height, 6, 6)
        painter.setPen(QPen(QColor(200, 200, 200, 255)))
        painter.drawText(button2_x, button_y, button_width, button_height, Qt.AlignCenter, button2_text)

        # Store button 2 rect for click detection (Phase 3)
        self.button2_rect = (button2_x, button_y, button_width, button_height)

        # Pin button (bottom right)
        pin_text = "[*] Pinned" if self.menu_pinned else "[ ] Pin"
        pin_color = QColor(100, 255, 100, 255) if self.menu_pinned else QColor(150, 150, 150, 255)
        painter.setPen(QPen(pin_color))
        painter.setFont(QFont("Arial", 8))
        pin_x = menu_x + menu_width - 70
        pin_y = menu_y + menu_height - 10
        painter.drawText(pin_x, pin_y, pin_text)

        # Store pin button rect for click detection (Phase 2)
        self.pin_button_rect = (pin_x, pin_y - 10, 70, 20)

    def _draw_desktop_overlay(self, painter):
        """
        Phase 3: Draw desktop element overlay
        Shows rectangles over detected desktop elements
        """
        # Draw semi-transparent info box
        info_x = 10
        info_y = 10
        info_width = 200
        info_height = 60

        painter.setBrush(QBrush(QColor(0, 0, 0, 200)))
        painter.setPen(QPen(QColor(100, 255, 100, 255), 2))
        painter.drawRoundedRect(info_x, info_y, info_width, info_height, 8, 8)

        # Draw info text
        painter.setPen(QPen(QColor(100, 255, 100, 255)))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(info_x + 10, info_y + 20, "Desktop Overlay")
        painter.setFont(QFont("Arial", 9))
        painter.setPen(QPen(QColor(200, 200, 200, 255)))
        painter.drawText(info_x + 10, info_y + 38, f"{len(self.desktop_elements_cache)} elements")
        painter.drawText(info_x + 10, info_y + 52, "Click to hide")

        # Note: Desktop elements are at absolute screen coordinates
        # This window is also at screen coordinates, so we need to adjust
        # Get window position
        window_pos = self.pos()

        # Draw element rectangles (simplified - just show count for now)
        # Full overlay implementation would require a separate transparent overlay window
        painter.setPen(QPen(QColor(150, 150, 150, 180)))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(info_x + 10, info_y + info_height + 15,
                        "(Full overlay requires screen-space window)")

    def _draw_settings_menu(self, painter, agent_hue, agent_sat, agent_val):
        """
        Phase 4: Draw settings menu for power users
        Shows mode locking options and advanced settings
        """
        # Menu dimensions
        menu_width = 300
        menu_height = 250
        menu_x = int(self.center_x - menu_width / 2)
        menu_y = int(self.center_y - menu_height / 2)

        # Draw menu background
        painter.setBrush(QBrush(QColor(20, 20, 20, 250)))
        painter.setPen(QPen(QColor(80, 80, 80, 255), 2))
        painter.drawRoundedRect(menu_x, menu_y, menu_width, menu_height, 12, 12)

        # Draw header
        header_height = 40
        agent_color_rgb = self._hsv_to_rgb(agent_hue, agent_sat, agent_val)
        painter.setBrush(QBrush(QColor(agent_color_rgb[0], agent_color_rgb[1], agent_color_rgb[2], 100)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(menu_x, menu_y, menu_width, header_height, 12, 12)

        # Draw settings icon
        icon_size = 20
        icon_x = menu_x + 15
        icon_y = menu_y + 10
        painter.setBrush(QBrush(QColor(agent_color_rgb[0], agent_color_rgb[1], agent_color_rgb[2], 220)))
        painter.drawEllipse(icon_x, icon_y, icon_size, icon_size)

        # Draw header text
        painter.setPen(QPen(QColor(255, 255, 255, 255)))
        header_font = QFont("Arial", 11, QFont.Bold)
        painter.setFont(header_font)
        painter.drawText(menu_x + 45, menu_y + 25, "Settings")

        # Content area
        content_y = menu_y + header_height + 20
        content_font = QFont("Arial", 9)
        painter.setFont(content_font)

        # Mode locking section
        painter.setPen(QPen(QColor(200, 200, 200, 255)))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(menu_x + 15, content_y, "Mode Locking (Power Users)")

        content_y += 25
        painter.setFont(QFont("Arial", 9))
        painter.setPen(QPen(QColor(180, 180, 180, 255)))

        # Mode lock options
        modes = [
            ("desktop", "Lock to Desktop Mode"),
            ("code", "Lock to Code Mode"),
            ("devops", "Lock to DevOps Mode")
        ]

        for mode_key, mode_name in modes:
            # Draw checkbox
            checkbox_x = menu_x + 25
            checkbox_size = 14

            painter.setBrush(QBrush(QColor(40, 40, 40, 255)))
            painter.setPen(QPen(QColor(100, 100, 100, 255), 1))
            painter.drawRect(checkbox_x, content_y - 12, checkbox_size, checkbox_size)

            # Draw checkmark if locked
            if self.locked_mode == mode_key:
                painter.setPen(QPen(QColor(100, 255, 100, 255), 2))
                painter.drawLine(checkbox_x + 2, content_y - 6, checkbox_x + 5, content_y - 3)
                painter.drawLine(checkbox_x + 5, content_y - 3, checkbox_x + 12, content_y - 10)

            # Draw label
            label_color = QColor(100, 255, 100, 255) if self.locked_mode == mode_key else QColor(180, 180, 180, 255)
            painter.setPen(QPen(label_color))
            painter.drawText(checkbox_x + 22, content_y, mode_name)

            content_y += 25

        # Unlock button
        content_y += 10
        if self.locked_mode:
            unlock_button_x = menu_x + 25
            unlock_button_width = 120
            unlock_button_height = 28

            painter.setBrush(QBrush(QColor(60, 40, 40, 255)))
            painter.setPen(QPen(QColor(255, 100, 100, 255), 1))
            painter.drawRoundedRect(unlock_button_x, content_y - 15, unlock_button_width, unlock_button_height, 6, 6)

            painter.setPen(QPen(QColor(255, 150, 150, 255)))
            painter.drawText(unlock_button_x, content_y - 15, unlock_button_width, unlock_button_height, Qt.AlignCenter, "Unlock Mode")

        # Close button
        close_x = menu_x + menu_width - 60
        close_y = menu_y + menu_height - 35
        close_width = 50
        close_height = 25

        painter.setBrush(QBrush(QColor(40, 40, 40, 255)))
        painter.setPen(QPen(QColor(100, 100, 100, 255), 1))
        painter.drawRoundedRect(close_x, close_y, close_width, close_height, 6, 6)

        painter.setPen(QPen(QColor(200, 200, 200, 255)))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(close_x, close_y, close_width, close_height, Qt.AlignCenter, "Close")

    def _hsv_to_rgb(self, h, s, v):
        """HSV to RGB"""
        h = h / 60.0
        c = v * s
        x = c * (1 - abs((h % 2) - 1))
        m = v - c

        if h < 1: r, g, b = c, x, 0
        elif h < 2: r, g, b = x, c, 0
        elif h < 3: r, g, b = 0, c, x
        elif h < 4: r, g, b = 0, x, c
        elif h < 5: r, g, b = x, 0, c
        else: r, g, b = c, 0, x

        return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))

    def eventFilter(self, obj, event):
        """Filter events to intercept Enter key in chat input"""
        if obj == self.chat_input and event.type() == QEvent.KeyPress:
            print(f"[GUI DEBUG] Key pressed in chat: {event.key()}")
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                print(f"[GUI DEBUG] Enter key detected, modifiers: {event.modifiers()}")
                # Only handle Enter without Shift (Shift+Enter = newline)
                if not event.modifiers() & Qt.ShiftModifier:
                    print(f"[GUI DEBUG] Calling _on_return_pressed()")
                    self._on_return_pressed()
                    return True  # Event handled, don't propagate
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        """Handle keyboard"""
        if event.key() == Qt.Key_Escape or event.key() == Qt.Key_Q:
            self.close()
        elif event.key() == Qt.Key_V:
            # Voice input!
            if self.voice_bridge:
                asyncio.ensure_future(self.voice_bridge.process_voice_input())
        elif event.key() == Qt.Key_Up:
            new_size = max(200, min(1500, self.width() + 30))
            new_height = new_size + 120
            self.resize(new_size, new_height)
            self.center_x = new_size / 2
            self.center_y = new_size / 2
            self.radius = new_size / 2.6
            self._position_chat_input()
        elif event.key() == Qt.Key_Down:
            new_size = max(200, min(1500, self.width() - 30))
            new_height = new_size + 120
            self.resize(new_size, new_height)
            self.center_x = new_size / 2
            self.center_y = new_size / 2
            self.radius = new_size / 2.6
            self._position_chat_input()

    def mousePressEvent(self, event):
        """Handle mouse press"""
        if event.button() == Qt.LeftButton:
            x, y = event.x(), event.y()

            # Phase 4: Check if click is on settings menu (if visible)
            if self.settings_menu_visible:
                self._handle_settings_menu_click(x, y)
                event.accept()
                return

            # Phase 3: Check if click is on menu buttons (if menu is visible)
            if self.menu_visible:
                # Check pin button
                if self.pin_button_rect:
                    px, py, pw, ph = self.pin_button_rect
                    if px <= x <= px + pw and py <= y <= py + ph:
                        self.menu_pinned = not self.menu_pinned
                        print(f"[MENU] Menu pinned: {self.menu_pinned}")
                        event.accept()
                        return

                # Check action button 1
                if self.button1_rect:
                    bx, by, bw, bh = self.button1_rect
                    if bx <= x <= bx + bw and by <= y <= by + bh:
                        self._handle_button1_action()
                        event.accept()
                        return

                # Check action button 2
                if self.button2_rect:
                    bx, by, bw, bh = self.button2_rect
                    if bx <= x <= bx + bw and by <= y <= by + bh:
                        self._handle_button2_action()
                        event.accept()
                        return

            # Check if click is inside the circle
            dx = event.x() - self.center_x
            dy = event.y() - self.center_y
            distance = np.sqrt(dx**2 + dy**2)

            if distance <= self.radius:
                # Phase 2: Click inside circle - toggle status menu
                self.menu_visible = not self.menu_visible
                print(f"[MENU] Status menu: {'visible' if self.menu_visible else 'hidden'}")
                event.accept()
                return

            # Click outside circle - start dragging or close menus
            if self.menu_visible and not self.menu_pinned:
                self.menu_visible = False
            if self.settings_menu_visible:
                self.settings_menu_visible = False
            if self.overlay_visible:
                self.overlay_visible = False  # Hide overlay on click
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            # Phase 4: Check if click is on settings menu items (if menu is visible)
            if self.settings_menu_visible:
                x, y = event.x(), event.y()
                self._handle_settings_menu_click(x, y)
                event.accept()
                return

            # Check if right-click is inside the circle
            dx = event.x() - self.center_x
            dy = event.y() - self.center_y
            distance = np.sqrt(dx**2 + dy**2)

            if distance <= self.radius:
                # Phase 4: Right-click inside circle - show settings menu
                self.settings_menu_visible = not self.settings_menu_visible
                print(f"[MENU] Settings menu: {'visible' if self.settings_menu_visible else 'hidden'}")
                event.accept()
                return

            # Right-click on resize corner
            corner_size = 50
            if (event.x() > self.width() - corner_size and
                event.y() > self.height() - corner_size):
                self.resizing = True
                self.resize_corner = event.globalPos()
                event.accept()

    def mouseMoveEvent(self, event):
        """Handle mouse move"""
        if self.dragging and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
        elif self.resizing and self.resize_corner:
            delta = event.globalPos() - self.resize_corner
            new_size = max(200, self.width() + delta.x())
            new_height = new_size + 120
            self.resize(new_size, new_height)

            self.center_x = new_size / 2
            self.center_y = new_size / 2
            self.radius = new_size / 2.6

            self.resize_corner = event.globalPos()
            self._position_chat_input()
            event.accept()

    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self.dragging = False
        self.resizing = False
        self.drag_position = None
        self.resize_corner = None
        event.accept()

    def wheelEvent(self, event):
        """Handle mouse wheel for resizing"""
        delta = event.angleDelta().y()
        size_change = 20 if delta > 0 else -20
        new_size = max(200, min(1500, self.width() + size_change))
        new_height = new_size + 120

        self.resize(new_size, new_height)
        self.center_x = new_size / 2
        self.center_y = new_size / 2
        self.radius = new_size / 2.6

        self._position_chat_input()
        event.accept()

    def _handle_button1_action(self):
        """
        Phase 3: Handle button 1 click - context-specific action
        """
        if self.active_agent == "desktop":
            # Show desktop element overlay
            self._action_show_overlay()
        elif self.active_agent == "code":
            # Show file context
            self._action_file_context()
        elif self.active_agent == "devops":
            # Run health check
            self._action_health_check()
        else:
            # General settings
            self._action_settings()

    def _handle_button2_action(self):
        """
        Phase 3: Handle button 2 click - context-specific action
        """
        if self.active_agent == "desktop":
            # Rescan desktop
            self._action_rescan_desktop()
        elif self.active_agent == "code":
            # Explain code
            self._action_explain_code()
        elif self.active_agent == "devops":
            # Show logs
            self._action_show_logs()
        else:
            # General help
            self._action_help()

    # Phase 3: Action implementations
    def _action_show_overlay(self):
        """Show desktop element overlay"""
        print("[ACTION] Show Overlay")
        # Get desktop agent's moire_client
        moire_client = None
        if self.voice_bridge and hasattr(self.voice_bridge, 'orchestrator'):
            orchestrator = self.voice_bridge.orchestrator
            if hasattr(orchestrator, 'desktop_agent'):
                desktop_agent = orchestrator.desktop_agent
                if hasattr(desktop_agent, 'moire_client'):
                    moire_client = desktop_agent.moire_client

        if moire_client:
            # Get desktop elements from MoireTracker
            self.desktop_elements_cache = moire_client.scan_desktop()
            if self.desktop_elements_cache:
                self.overlay_visible = True
                print(f"[OVERLAY] Showing {len(self.desktop_elements_cache)} elements")
                self.update()  # Trigger repaint
            else:
                print("[OVERLAY] No elements found")
        else:
            print("[OVERLAY] MoireTracker not connected")

    def _action_rescan_desktop(self):
        """Rescan desktop elements"""
        print("[ACTION] Rescan Desktop")
        # Get desktop agent's moire_client
        moire_client = None
        if self.voice_bridge and hasattr(self.voice_bridge, 'orchestrator'):
            orchestrator = self.voice_bridge.orchestrator
            if hasattr(orchestrator, 'desktop_agent'):
                desktop_agent = orchestrator.desktop_agent
                if hasattr(desktop_agent, 'moire_client'):
                    moire_client = desktop_agent.moire_client

        if moire_client:
            # Force rescan
            self.desktop_elements_cache = moire_client.scan_desktop()
            if self.desktop_elements_cache:
                print(f"[RESCAN] Found {len(self.desktop_elements_cache)} elements")
                if self.overlay_visible:
                    self.update()  # Update overlay
            else:
                print("[RESCAN] No elements found")
        else:
            print("[RESCAN] MoireTracker not connected")

    def _action_file_context(self):
        """Show file context (placeholder)"""
        print("[ACTION] File Context - Not yet implemented")

    def _action_explain_code(self):
        """Explain code (placeholder)"""
        print("[ACTION] Explain Code - Not yet implemented")

    def _action_health_check(self):
        """Run health check (placeholder)"""
        print("[ACTION] Health Check - Not yet implemented")

    def _action_show_logs(self):
        """Show logs (placeholder)"""
        print("[ACTION] Show Logs - Not yet implemented")

    def _action_settings(self):
        """Open settings menu"""
        print("[ACTION] Settings")
        self.settings_menu_visible = True
        self.update()

    def _action_help(self):
        """Show help information"""
        print("[ACTION] Help")
        print("Voice Dialog Help:")
        print("  - Click circle: Toggle status menu")
        print("  - Right-click circle: Settings")
        print("  - Speak or type to interact")
        print("  - Click colored circle to toggle auto-start")

    def _handle_settings_menu_click(self, x, y):
        """
        Phase 4: Handle clicks on settings menu items
        """
        # Calculate menu bounds
        menu_width = 300
        menu_height = 250
        menu_x = int(self.center_x - menu_width / 2)
        menu_y = int(self.center_y - menu_height / 2)
        header_height = 40

        # Check close button
        close_x = menu_x + menu_width - 60
        close_y = menu_y + menu_height - 35
        close_width = 50
        close_height = 25

        if close_x <= x <= close_x + close_width and close_y <= y <= close_y + close_height:
            self.settings_menu_visible = False
            print("[SETTINGS] Menu closed")
            self.update()
            return

        # Check unlock button (if locked)
        if self.locked_mode:
            unlock_button_x = menu_x + 25
            unlock_button_y = menu_y + header_height + 20 + 25 + 75 + 10 - 15
            unlock_button_width = 120
            unlock_button_height = 28

            if (unlock_button_x <= x <= unlock_button_x + unlock_button_width and
                unlock_button_y <= y <= unlock_button_y + unlock_button_height):
                print(f"[SETTINGS] Unlocked from {self.locked_mode} mode")
                self.locked_mode = None
                self.update()
                return

        # Check mode lock checkboxes
        content_y = menu_y + header_height + 20 + 25
        modes = [
            ("desktop", "Desktop Mode"),
            ("code", "Code Mode"),
            ("devops", "DevOps Mode")
        ]

        for mode_key, mode_name in modes:
            checkbox_x = menu_x + 25
            checkbox_y = content_y - 12
            checkbox_size = 14

            # Check if click is in checkbox row (checkbox + label area)
            label_width = 200
            row_height = 20
            if (checkbox_x <= x <= checkbox_x + label_width and
                checkbox_y <= y <= checkbox_y + row_height):
                # Toggle mode lock
                if self.locked_mode == mode_key:
                    self.locked_mode = None
                    print(f"[SETTINGS] Unlocked {mode_name}")
                else:
                    self.locked_mode = mode_key
                    print(f"[SETTINGS] Locked to {mode_name}")
                self.update()
                return

            content_y += 25

    def _toggle_auto_start(self):
        """Toggle auto-start setting and save to .env"""
        self.auto_start_enabled = not self.auto_start_enabled

        # Update .env file
        import os
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')

        try:
            # Read current .env
            lines = []
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()

            # Update or add AUTO_START_MOIRE setting
            found = False
            for i, line in enumerate(lines):
                if line.strip().startswith('AUTO_START_MOIRE='):
                    lines[i] = f"AUTO_START_MOIRE={'true' if self.auto_start_enabled else 'false'}\n"
                    found = True
                    break

            if not found:
                lines.append(f"\n# Auto-start MoireTracker on launch\nAUTO_START_MOIRE={'true' if self.auto_start_enabled else 'false'}\n")

            # Write back
            with open(env_path, 'w') as f:
                f.writelines(lines)

            status = "ENABLED" if self.auto_start_enabled else "DISABLED"
            print(f"[SETTINGS] Auto-start {status} - restart app to apply")
            print(f"[SETTINGS] Saved to {env_path}")

        except Exception as e:
            print(f"[SETTINGS] Error saving auto-start setting: {e}")

    def closeEvent(self, event):
        """Cleanup"""
        if self.voice_bridge:
            asyncio.ensure_future(self.voice_bridge.shutdown())
        event.accept()


def main():
    # Load environment variables from .env file
    from dotenv import load_dotenv
    import os

    # Load .env from project root (one level up from python/)
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"[VOICE DIALOG] Loaded .env from: {env_path}")
    else:
        load_dotenv()  # Try default .env location
        print("[VOICE DIALOG] Using environment variables")

    app = QApplication(sys.argv)

    # Set up async event loop integration
    import qasync
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = VoiceDialogVisual()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[EXIT]")
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
