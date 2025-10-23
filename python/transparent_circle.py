"""
Transparent window with circular starfield - desktop visible behind
"""

import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit
from PyQt5.QtCore import QTimer, Qt, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont
from audio_analyzer import AudioAnalyzer, AudioFeatures
import sounddevice as sd


class TransparentCircleVisual(QWidget):
    """Circular visual with transparent window"""

    def __init__(self):
        super().__init__()

        # Window setup
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Size and position - make taller for chat input
        screen = QApplication.primaryScreen().geometry()
        circle_size = min(screen.width(), screen.height()) - 100
        window_height = circle_size + 120  # Extra space for chat input
        self.setGeometry(
            (screen.width() - circle_size) // 2,
            (screen.height() - window_height) // 2,
            circle_size, window_height
        )

        # Circle parameters
        self.center_x = circle_size / 2
        self.center_y = circle_size / 2
        self.radius = circle_size / 2.6  # Smaller to add padding

        # Audio
        self.audio_analyzer = AudioAnalyzer(sample_rate=44100)
        self.audio_buffer = np.zeros(2048, dtype=np.float32)
        self.audio_stream = None
        self.current_audio = AudioFeatures(
            amplitude=0.0, bass=0.0, mid=0.0, treble=0.0,
            spectrum=[0.0] * 64, beat_detected=0.0
        )

        # Visual state
        self.demo_time = 0.0
        self.phase = 0.0
        self.hue_offset = 0.0

        # Text animation - DISABLED
        # self.messages = []
        # self.current_message_index = 0
        # self.message_alpha = 0.0
        # self.message_timer = 0.0

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
        self.chat_input.setPlaceholderText("Type here...")
        self.chat_input.setFont(QFont("Arial", 10))  # Smaller font (was 12)
        self.chat_input.setMaximumHeight(32)  # Smaller (was 40)
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
        self._position_chat_input()

        # Animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_visual)
        self.timer.start(33)  # 30 FPS

        print("[READY] Transparent circle visual")
        print("Press ESC to exit, SPACE for mic")
        print("Left-click and drag to move")
        print("Mouse wheel or Arrow Up/Down to resize")

    def _position_chat_input(self):
        """Position chat input below the circle"""
        margin = 40  # Larger margins (was 20)
        input_width = self.width() - (margin * 2)
        chat_y = int(self.center_y + self.radius + 50)  # 50px from circle (was 30)

        # Hide chat if window is too small (chat would be cut off)
        if self.width() < 300 or chat_y + self.chat_input.maximumHeight() + margin > self.height():
            self.chat_input.hide()
        else:
            self.chat_input.show()
            self.chat_input.setGeometry(
                margin,
                chat_y,
                input_width,
                self.chat_input.maximumHeight()
            )

    def _on_text_changed(self):
        """Auto-expand chat input based on content"""
        doc_height = self.chat_input.document().size().height()
        new_height = min(150, max(32, int(doc_height + 16)))  # Smaller range
        self.chat_input.setMaximumHeight(new_height)
        self._position_chat_input()

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
        """Demo audio"""
        amplitude = 0.5 + 0.4 * np.sin(t * 1.2)
        bass = 0.6 + 0.4 * np.sin(t * 0.8)
        mid = 0.7 + 0.3 * np.sin(t * 1.5)
        treble = 0.5 + 0.4 * np.sin(t * 2.5)
        beat = 1.0 if (t % 0.6) < 0.06 else 0.0
        spectrum = [0.6 + 0.4 * np.sin(t * 1.2 + i * 0.15) for i in range(64)]

        return AudioFeatures(
            amplitude=float(np.clip(amplitude, 0, 1)),
            bass=float(np.clip(bass, 0, 1)),
            mid=float(np.clip(mid, 0, 1)),
            treble=float(np.clip(treble, 0, 1)),
            spectrum=spectrum, beat_detected=beat
        )

    def update_visual(self):
        """Update animation"""
        # Audio
        if self.audio_stream and len(self.audio_buffer) > 0:
            self.current_audio = self.audio_analyzer.analyze(self.audio_buffer)
        else:
            self.demo_time += 0.033
            self.current_audio = self._generate_demo_audio(self.demo_time)

        audio = self.current_audio

        # Update phase
        self.phase += audio.amplitude * 0.05 + 0.01
        self.hue_offset += audio.amplitude * 0.5

        # Text animation - DISABLED
        # (removed)

        # Update particles
        for p in self.particles:
            # Movement
            speed_mult = 1.0 + audio.amplitude * 0.05 * p['depth']
            p['x'] += p['vx'] * speed_mult
            p['y'] += p['vy'] * speed_mult

            # Bounce at boundary
            r = np.sqrt(p['x']**2 + p['y']**2)
            if r > 0.92:
                theta = np.arctan2(p['y'], p['x'])
                p['x'] = 0.92 * np.cos(theta)
                p['y'] = 0.92 * np.sin(theta)

                # Random bounce
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

        # Draw black circle background
        painter.setBrush(QBrush(QColor(0, 0, 0, 255)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(
            QPointF(self.center_x, self.center_y),
            self.radius, self.radius
        )

        # Draw moiré rings
        for i in range(1, self.num_rings + 1):
            base_radius = (i / self.num_rings) * self.radius
            pulse = audio.bass * 0.01 * self.radius * np.sin(self.phase + i * 0.3)
            ring_radius = base_radius + pulse

            hue = int((i * 8 + self.hue_offset + audio.mid * 150) % 360)
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
            # Fade effect
            p['fade_phase'] += p['fade_speed']
            phase_normalized = (p['fade_phase'] % (2 * np.pi)) / (2 * np.pi)

            if phase_normalized < 0.25:
                local_phase = phase_normalized / 0.25
                fade_alpha = np.sin(local_phase * np.pi)
            else:
                fade_alpha = 0.0

            if fade_alpha < 0.01:
                continue

            # Position
            px = self.center_x + p['x'] * self.radius
            py = self.center_y + p['y'] * self.radius

            # Color
            freq_idx = int(len(self.particles)) % len(audio.spectrum)
            freq_val = audio.spectrum[freq_idx]

            hue_shift = (audio.bass * 10 + audio.mid * 20 + audio.treble * 30)
            final_hue = int((p['hue'] + hue_shift * 0.1) % 360)

            base_brightness = 0.8 + audio.amplitude * 0.05 + freq_val * 0.05
            brightness = base_brightness * fade_alpha

            color = self._hsv_to_rgb(final_hue, 0.2, brightness)
            alpha = int(fade_alpha * 255)

            # Draw star
            size = p['base_size'] * (0.8 + p['depth'] * 0.4) * fade_alpha
            painter.setBrush(QBrush(QColor(color[0], color[1], color[2], alpha)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(px, py), size/2, size/2)

        # Draw boundary
        boundary_hue = int((self.hue_offset + audio.mid * 100) % 360)
        boundary_color = self._hsv_to_rgb(boundary_hue, 0.7, 0.8)
        alpha = int((0.4 + audio.amplitude * 0.02) * 255)

        pen = QPen(QColor(boundary_color[0], boundary_color[1], boundary_color[2], alpha))
        pen.setWidthF(2 + audio.beat_detected * 0.3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(
            QPointF(self.center_x, self.center_y),
            self.radius * 0.98, self.radius * 0.98
        )

        # Text drawing - DISABLED
        # (removed)

        # Draw resize indicator in bottom-right corner
        corner_size = 50
        painter.setPen(QPen(QColor(100, 100, 100, 100)))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(
            int(self.width() - corner_size), int(self.height()),
            int(self.width()), int(self.height() - corner_size)
        )
        painter.drawLine(
            int(self.width() - corner_size + 10), int(self.height()),
            int(self.width()), int(self.height() - corner_size + 10)
        )
        painter.drawLine(
            int(self.width() - corner_size + 20), int(self.height()),
            int(self.width()), int(self.height() - corner_size + 20)
        )

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

    def keyPressEvent(self, event):
        """Handle keyboard"""
        if event.key() == Qt.Key_Escape or event.key() == Qt.Key_Q:
            self.close()
        elif event.key() == Qt.Key_Space:
            if self.audio_stream is None:
                self._start_audio()
            else:
                self._stop_audio()
        elif event.key() == Qt.Key_Up:
            # Arrow up - make larger
            new_size = max(200, min(1500, self.width() + 30))
            new_height = new_size + 120  # Extra space for chat
            self.resize(new_size, new_height)
            self.center_x = new_size / 2
            self.center_y = new_size / 2
            self.radius = new_size / 2.6
            self._position_chat_input()
        elif event.key() == Qt.Key_Down:
            # Arrow down - make smaller
            new_size = max(200, min(1500, self.width() - 30))
            new_height = new_size + 120  # Extra space for chat
            self.resize(new_size, new_height)
            self.center_x = new_size / 2
            self.center_y = new_size / 2
            self.radius = new_size / 2.6
            self._position_chat_input()

    def _start_audio(self):
        """Start mic"""
        try:
            self.audio_stream = sd.InputStream(
                channels=1, samplerate=44100, blocksize=2048,
                callback=self._audio_callback
            )
            self.audio_stream.start()
            print("[MIC] Active")
        except Exception as e:
            print(f"[ERROR] {e}")

    def _stop_audio(self):
        """Stop mic"""
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
            print("[MIC] Stopped")

    def _audio_callback(self, indata, frames, time_info, status):
        """Audio callback"""
        self.audio_buffer = indata[:, 0].copy()

    def mousePressEvent(self, event):
        """Handle mouse press"""
        from PyQt5.QtCore import Qt

        if event.button() == Qt.LeftButton:
            # Start dragging
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.RightButton:
            # Check if near corner for resizing
            corner_size = 50
            if (event.x() > self.width() - corner_size and
                event.y() > self.height() - corner_size):
                self.resizing = True
                self.resize_corner = event.globalPos()
                event.accept()

    def mouseMoveEvent(self, event):
        """Handle mouse move"""
        if self.dragging and self.drag_position:
            # Move window
            self.move(event.globalPos() - self.drag_position)
            event.accept()
        elif self.resizing and self.resize_corner:
            # Resize window
            delta = event.globalPos() - self.resize_corner
            new_size = max(200, self.width() + delta.x())
            new_height = new_size + 120  # Extra space for chat
            self.resize(new_size, new_height)

            # Update center and radius
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
        # Get scroll delta (positive = zoom in, negative = zoom out)
        delta = event.angleDelta().y()

        # Resize based on scroll direction
        size_change = 20 if delta > 0 else -20
        new_size = max(200, min(1500, self.width() + size_change))
        new_height = new_size + 120  # Extra space for chat

        # Resize window
        self.resize(new_size, new_height)

        # Update center and radius
        self.center_x = new_size / 2
        self.center_y = new_size / 2
        self.radius = new_size / 2.6

        self._position_chat_input()
        event.accept()

    def closeEvent(self, event):
        """Cleanup"""
        if self.audio_stream:
            self._stop_audio()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = TransparentCircleVisual()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
