"""
Audio-reactive visual with circular window and moiré pattern
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle
from audio_analyzer import AudioAnalyzer, AudioFeatures
import sounddevice as sd


class CircularMoireVisual:
    """Circular audio-reactive visual with moiré pattern"""

    def __init__(self):
        # Audio setup
        self.audio_analyzer = AudioAnalyzer(sample_rate=44100)
        self.audio_buffer = np.zeros(2048, dtype=np.float32)
        self.audio_stream = None

        # Audio features
        self.current_audio = AudioFeatures(
            amplitude=0.0, bass=0.0, mid=0.0, treble=0.0,
            spectrum=[0.0] * 64, beat_detected=0.0
        )

        # Visual state
        self.demo_time = 0.0
        self.phase = 0.0
        self.hue_offset = 0.0

        # Create figure with black background
        self.fig = plt.figure(figsize=(10, 10), facecolor='black')
        self.ax = self.fig.add_subplot(111, facecolor='black')
        self.ax.set_xlim(-1.2, 1.2)
        self.ax.set_ylim(-1.2, 1.2)
        self.ax.set_aspect('equal')
        self.ax.axis('off')

        # Create grid for moiré pattern
        self.setup_moire_grid()

        # Create particles in circular pattern
        self.num_particles = 200
        self.particles = self.init_circular_particles()

        # Title
        self.title = self.fig.text(
            0.5, 0.95, 'Audio-Reactive Moire\nPress SPACE for mic',
            color='cyan', ha='center', va='top', fontsize=14, weight='bold'
        )

        # Circular boundary
        self.boundary = Circle((0, 0), 1.0, fill=False,
                              edgecolor='cyan', linewidth=2, alpha=0.5)
        self.ax.add_patch(self.boundary)

        # Keyboard
        self.fig.canvas.mpl_connect('key_press_event', self._on_key)

        print("[OK] Circular Moire Visual initialized!")

    def setup_moire_grid(self):
        """Create moiré pattern grid"""
        # Radial lines for moiré effect
        self.num_rings = 30
        self.num_rays = 60

        self.rings = []
        self.rays = []

        # Concentric circles
        for i in range(1, self.num_rings + 1):
            radius = i / self.num_rings
            circle = Circle((0, 0), radius, fill=False,
                          edgecolor='white', linewidth=0.5, alpha=0.3)
            self.ax.add_patch(circle)
            self.rings.append(circle)

        # Radial rays
        theta = np.linspace(0, 2 * np.pi, self.num_rays, endpoint=False)
        for t in theta:
            x = [0, np.cos(t)]
            y = [0, np.sin(t)]
            line, = self.ax.plot(x, y, 'w-', linewidth=0.5, alpha=0.2)
            self.rays.append(line)

    def init_circular_particles(self):
        """Initialize particles in circular arrangement"""
        particles = []

        for i in range(self.num_particles):
            # Random radius and angle
            r = np.random.rand() * 0.9
            theta = np.random.rand() * 2 * np.pi

            x = r * np.cos(theta)
            y = r * np.sin(theta)

            # Velocity perpendicular to radius (circular motion)
            vx = -np.sin(theta) * 0.02
            vy = np.cos(theta) * 0.02

            particles.append({
                'x': x, 'y': y, 'vx': vx, 'vy': vy,
                'hue': np.random.rand() * 360,
                'size': np.random.uniform(20, 60)
            })

        # Create scatter plot
        positions = np.array([[p['x'], p['y']] for p in particles])
        colors = [self._hsv_to_rgb(p['hue'], 0.8, 0.8) for p in particles]
        sizes = [p['size'] for p in particles]

        self.scatter = self.ax.scatter(
            positions[:, 0], positions[:, 1],
            s=sizes, c=colors, alpha=0.7, edgecolors='white', linewidths=0.5
        )

        return particles

    def _on_key(self, event):
        """Handle keyboard input"""
        if event.key == ' ':
            if self.audio_stream is None:
                self.start_audio()
            else:
                self.stop_audio()
        elif event.key == 'escape':
            plt.close(self.fig)

    def start_audio(self):
        """Start microphone"""
        try:
            self.audio_stream = sd.InputStream(
                channels=1, samplerate=44100, blocksize=2048,
                callback=self._audio_callback
            )
            self.audio_stream.start()
            self.title.set_text('Audio-Reactive Moire\n[MIC ACTIVE]')
            self.title.set_color('lime')
            print("[MIC] Microphone active!")
        except Exception as e:
            print(f"[ERROR] Audio error: {e}")
            self.title.set_text(f'Audio Error\n{e}')

    def stop_audio(self):
        """Stop audio"""
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
            self.title.set_text('Audio-Reactive Moire\nPress SPACE for mic')
            self.title.set_color('cyan')
            print("[MIC] Microphone stopped")

    def _audio_callback(self, indata, frames, time_info, status):
        """Audio callback"""
        if status:
            print(f"Audio: {status}")
        self.audio_buffer = indata[:, 0].copy()

    def _generate_demo_audio(self, t):
        """Generate demo audio"""
        amplitude = 0.4 + 0.3 * np.sin(t * 1.5)
        bass = 0.5 + 0.4 * np.sin(t * 1.0)
        mid = 0.6 + 0.3 * np.sin(t * 2.0)
        treble = 0.4 + 0.35 * np.sin(t * 3.0)
        beat = 1.0 if (t % 0.5) < 0.05 else 0.0
        spectrum = [0.5 + 0.4 * np.sin(t * 1.5 + i * 0.1) for i in range(64)]

        return AudioFeatures(
            amplitude=float(np.clip(amplitude, 0, 1)),
            bass=float(np.clip(bass, 0, 1)),
            mid=float(np.clip(mid, 0, 1)),
            treble=float(np.clip(treble, 0, 1)),
            spectrum=spectrum, beat_detected=beat
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

        return (r + m, g + m, b + m)

    def update(self, frame):
        """Update animation"""
        dt = 0.016  # ~60 FPS

        # Get audio
        if self.audio_stream and len(self.audio_buffer) > 0:
            self.current_audio = self.audio_analyzer.analyze(self.audio_buffer)
        else:
            self.demo_time += dt
            self.current_audio = self._generate_demo_audio(self.demo_time)

        audio = self.current_audio

        # Update phase for moiré pattern
        self.phase += audio.amplitude * 0.5 + 0.1
        self.hue_offset += audio.amplitude * 3.0

        # Animate moiré rings
        for i, ring in enumerate(self.rings):
            # Pulse radius with audio
            base_radius = (i + 1) / self.num_rings
            pulse = audio.bass * 0.1 * np.sin(self.phase + i * 0.2)
            new_radius = base_radius + pulse

            # Color based on audio
            hue = (i * 10 + self.hue_offset + audio.mid * 120) % 360
            color = self._hsv_to_rgb(hue, 0.6 + audio.beat_detected * 0.4, 0.7)

            ring.set_radius(new_radius)
            ring.set_edgecolor(color)
            ring.set_alpha(0.3 + audio.amplitude * 0.3)

        # Animate rays (rotating moiré effect)
        ray_rotation = self.phase * 0.1
        for i, line in enumerate(self.rays):
            theta = (i / self.num_rays) * 2 * np.pi + ray_rotation

            # Audio-reactive length
            length = 0.9 + audio.treble * 0.1
            x = [0, length * np.cos(theta)]
            y = [0, length * np.sin(theta)]
            line.set_data(x, y)

            # Color
            hue = (i * 5 + self.hue_offset + audio.treble * 180) % 360
            color = self._hsv_to_rgb(hue, 0.7, 0.6)
            line.set_color(color)
            line.set_alpha(0.2 + audio.amplitude * 0.2)

        # Update particles
        positions = []
        colors = []
        sizes = []

        for i, p in enumerate(self.particles):
            # Rotate particles
            speed_mult = 1.0 + audio.amplitude * 2.0
            p['x'] += p['vx'] * speed_mult
            p['y'] += p['vy'] * speed_mult

            # Keep in circle
            r = np.sqrt(p['x']**2 + p['y']**2)
            if r > 0.95:
                # Bounce back
                theta = np.arctan2(p['y'], p['x'])
                p['x'] = 0.95 * np.cos(theta)
                p['y'] = 0.95 * np.sin(theta)
                p['vx'] = -p['vx']
                p['vy'] = -p['vy']

            # Audio-reactive color
            freq_idx = i % len(audio.spectrum)
            freq_val = audio.spectrum[freq_idx]

            hue_shift = (audio.bass * 60 + audio.mid * 120 + audio.treble * 240)
            final_hue = (p['hue'] + self.hue_offset + hue_shift + freq_val * 60) % 360

            color = self._hsv_to_rgb(
                final_hue,
                0.7 + audio.beat_detected * 0.3,
                0.6 + audio.amplitude * 0.4
            )

            # Size pulses
            size = p['size'] * (1.0 + audio.beat_detected * 0.8 + freq_val * 0.3)

            positions.append([p['x'], p['y']])
            colors.append(color)
            sizes.append(size)

        # Update scatter
        self.scatter.set_offsets(np.array(positions))
        self.scatter.set_facecolors(colors)
        self.scatter.set_sizes(sizes)

        # Update boundary color
        boundary_hue = (self.hue_offset + audio.mid * 180) % 360
        boundary_color = self._hsv_to_rgb(boundary_hue, 0.8, 0.8)
        self.boundary.set_edgecolor(boundary_color)
        self.boundary.set_linewidth(2 + audio.beat_detected * 3)

        return [self.scatter, self.boundary, *self.rings, *self.rays]

    def run(self):
        """Start visualization"""
        print("\n" + "="*60)
        print("CIRCULAR MOIRE AUDIO-REACTIVE VISUAL")
        print("="*60)
        print("\nControls:")
        print("  SPACE - Toggle microphone")
        print("  ESC   - Exit")
        print("\n[DEMO] Starting in DEMO mode...")
        print("  Press SPACE to use your microphone!\n")

        anim = animation.FuncAnimation(
            self.fig, self.update,
            interval=16, blit=False, cache_frame_data=False
        )

        plt.show()

        if self.audio_stream:
            self.stop_audio()


def main():
    try:
        visual = CircularMoireVisual()
        visual.run()
    except KeyboardInterrupt:
        print("\n[EXIT] Exiting...")
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
