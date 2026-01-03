"""
Clean circular audio-reactive visual - fullscreen, no GUI elements
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle
from audio_analyzer import AudioAnalyzer, AudioFeatures
import sounddevice as sd


class CircularVisual:
    """Pure circular visual - no GUI chrome"""

    def __init__(self, fullscreen=True):
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

        # Create figure - FULLSCREEN, TRANSPARENT background
        self.fig = plt.figure(figsize=(12, 12), facecolor='none')

        if fullscreen:
            manager = plt.get_current_fig_manager()
            try:
                manager.full_screen_toggle()  # Try fullscreen
            except:
                try:
                    manager.window.state('zoomed')  # Try maximize on Windows
                except:
                    pass

        # Remove ALL margins and chrome, transparent outside circle
        self.ax = self.fig.add_axes([0, 0, 1, 1], facecolor='none')
        self.ax.set_xlim(-1.3, 1.3)
        self.ax.set_ylim(-1.3, 1.3)
        self.ax.set_aspect('equal')
        self.ax.axis('off')

        # Add black circle as background (only circle visible, rest transparent)
        self.bg_circle = Circle((0, 0), 1.0, fill=True,
                               facecolor='black', edgecolor='none', zorder=0)
        self.ax.add_patch(self.bg_circle)

        # Moire grid
        self.num_rings = 40
        self.num_rays = 80
        self.rings = []
        self.rays = []

        # Concentric circles - much more subtle
        for i in range(1, self.num_rings + 1):
            radius = i / self.num_rings
            circle = Circle((0, 0), radius, fill=False,
                          edgecolor='white', linewidth=0.5, alpha=0.15)
            self.ax.add_patch(circle)
            self.rings.append(circle)

        # Radial rays - much more subtle
        theta = np.linspace(0, 2 * np.pi, self.num_rays, endpoint=False)
        for t in theta:
            x = [0, np.cos(t)]
            y = [0, np.sin(t)]
            line, = self.ax.plot(x, y, 'w-', linewidth=0.4, alpha=0.1)
            self.rays.append(line)

        # Particles (like distant stars)
        self.num_particles = 500
        self.particles = self._init_particles()

        # Outer boundary - more subtle
        self.boundary = Circle((0, 0), 0.98, fill=False,
                              edgecolor='cyan', linewidth=2, alpha=0.4)
        self.ax.add_patch(self.boundary)

        # Keyboard
        self.fig.canvas.mpl_connect('key_press_event', self._on_key)

        print("[READY] Circular visual - Press SPACE for mic, ESC to exit")

    def _init_particles(self):
        """Initialize particles like distant stars"""
        particles = []
        for i in range(self.num_particles):
            r = np.random.rand() * 0.9
            theta = np.random.rand() * 2 * np.pi
            x = r * np.cos(theta)
            y = r * np.sin(theta)

            # Extremely slow drift for stars
            vx = -np.sin(theta) * 0.0002
            vy = np.cos(theta) * 0.0002

            # Stars: tiny, bright points
            particles.append({
                'x': x, 'y': y, 'vx': vx, 'vy': vy,
                'hue': np.random.rand() * 360,
                'base_size': np.random.uniform(1, 6),  # Small like stars
                'twinkle_phase': np.random.rand() * np.pi * 2,
                'depth': np.random.rand(),  # Depth for parallax
                'fade_phase': np.random.rand() * np.pi * 2,  # For fade in/out
                'fade_speed': np.random.uniform(0.01, 0.03)  # Random fade speed
            })

        positions = np.array([[p['x'], p['y']] for p in particles])
        colors = [self._hsv_to_rgb(p['hue'], 0.4, 1.0) for p in particles]  # Less saturated
        sizes = [p['base_size'] for p in particles]

        self.scatter = self.ax.scatter(
            positions[:, 0], positions[:, 1],
            s=sizes, c=colors, alpha=0.9,
            edgecolors='none', marker='*'  # Star marker!
        )
        return particles

    def _on_key(self, event):
        """Keyboard"""
        if event.key == ' ':
            if self.audio_stream is None:
                self._start_audio()
            else:
                self._stop_audio()
        elif event.key == 'escape' or event.key == 'q':
            plt.close(self.fig)

    def _start_audio(self):
        """Start mic"""
        try:
            self.audio_stream = sd.InputStream(
                channels=1, samplerate=44100, blocksize=2048,
                callback=self._audio_callback
            )
            self.audio_stream.start()
            print("[MIC] Microphone ACTIVE - speak or play music!")
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
        dt = 0.033

        # Audio
        if self.audio_stream and len(self.audio_buffer) > 0:
            self.current_audio = self.audio_analyzer.analyze(self.audio_buffer)
        else:
            self.demo_time += dt
            self.current_audio = self._generate_demo_audio(self.demo_time)

        audio = self.current_audio

        # Phase - ultra slow
        self.phase += audio.amplitude * 0.05 + 0.01
        self.hue_offset += audio.amplitude * 0.5

        # Animate rings - ultra gentle pulse
        for i, ring in enumerate(self.rings):
            base_radius = (i + 1) / self.num_rings
            pulse = audio.bass * 0.01 * np.sin(self.phase + i * 0.3)
            new_radius = base_radius + pulse

            hue = (i * 8 + self.hue_offset + audio.mid * 150) % 360
            color = self._hsv_to_rgb(hue, 0.7 + audio.beat_detected * 0.3, 0.8)

            ring.set_radius(new_radius)
            ring.set_edgecolor(color)
            ring.set_alpha(0.15 + audio.amplitude * 0.05)
            ring.set_linewidth(0.5 + audio.beat_detected * 0.1)

        # Animate rays - ultra slow rotation
        ray_rotation = self.phase * 0.01
        for i, line in enumerate(self.rays):
            theta = (i / self.num_rays) * 2 * np.pi + ray_rotation
            length = 0.95 + audio.treble * 0.02
            x = [0, length * np.cos(theta)]
            y = [0, length * np.sin(theta)]
            line.set_data(x, y)

            hue = (i * 4 + self.hue_offset + audio.treble * 200) % 360
            color = self._hsv_to_rgb(hue, 0.8, 0.7)
            line.set_color(color)
            line.set_alpha(0.1 + audio.amplitude * 0.04)
            line.set_linewidth(0.4 + audio.beat_detected * 0.08)

        # Update star particles
        positions = []
        colors = []
        sizes = []

        for i, p in enumerate(self.particles):
            # Stars drift very slowly, minimal parallax to reduce shaking
            speed_mult = 1.0 + audio.amplitude * 0.05 * p['depth']
            p['x'] += p['vx'] * speed_mult
            p['y'] += p['vy'] * speed_mult

            # Bounce back at random angle when hitting outer circle
            r = np.sqrt(p['x']**2 + p['y']**2)
            if r > 0.92:
                # Position star at the boundary
                theta = np.arctan2(p['y'], p['x'])
                p['x'] = 0.92 * np.cos(theta)
                p['y'] = 0.92 * np.sin(theta)

                # Bounce back at random angle (toward center)
                random_angle = np.random.rand() * 2 * np.pi
                speed = np.sqrt(p['vx']**2 + p['vy']**2)
                # Bias direction toward center
                dx = -p['x'] * 0.5 + np.cos(random_angle) * 0.5
                dy = -p['y'] * 0.5 + np.sin(random_angle) * 0.5
                length = np.sqrt(dx**2 + dy**2)
                p['vx'] = (dx / length) * speed
                p['vy'] = (dy / length) * speed

            # Star color - subtle, like distant stars
            freq_idx = i % len(audio.spectrum)
            freq_val = audio.spectrum[freq_idx]

            # Stars have natural colors (bluish-white, yellowish-white)
            hue_shift = (audio.bass * 10 + audio.mid * 20 + audio.treble * 30)
            final_hue = (p['hue'] + hue_shift * 0.1) % 360

            # Smooth random fade in/out (visible 25%, transparent 75%)
            p['fade_phase'] += p['fade_speed']
            # Normalize phase to 0-1 range
            phase_normalized = (p['fade_phase'] % (2 * np.pi)) / (2 * np.pi)

            if phase_normalized < 0.25:
                # Visible for 25% - smooth fade in and out
                local_phase = phase_normalized / 0.25  # 0 to 1 within visible period
                fade_alpha = np.sin(local_phase * np.pi)  # Smooth bell curve
            else:
                # Transparent for 75% of the time
                fade_alpha = 0.0

            # Reduce brightness variation and apply fade
            base_brightness = 0.8 + audio.amplitude * 0.05 + freq_val * 0.05
            brightness = base_brightness * fade_alpha  # Fade to black smoothly

            # Very low saturation
            saturation = 0.2 + freq_val * 0.1

            color = self._hsv_to_rgb(final_hue, saturation, brightness)

            # Remove twinkling - just use fade effect
            # Star size - constant, no twinkle
            size = p['base_size'] * (0.8 + p['depth'] * 0.4) * fade_alpha

            positions.append([p['x'], p['y']])
            colors.append(color)
            sizes.append(size)

        self.scatter.set_offsets(np.array(positions))
        self.scatter.set_facecolors(colors)
        self.scatter.set_sizes(sizes)

        # Boundary - subtle changes
        boundary_hue = (self.hue_offset + audio.mid * 100) % 360
        boundary_color = self._hsv_to_rgb(boundary_hue, 0.7, 0.8)
        self.boundary.set_edgecolor(boundary_color)
        self.boundary.set_linewidth(2 + audio.beat_detected * 0.3)
        self.boundary.set_alpha(0.4 + audio.amplitude * 0.02)

        return [self.scatter, self.boundary, *self.rings, *self.rays]

    def run(self):
        """Start"""
        print("\n" + "="*60)
        print("CIRCULAR MOIRE VISUAL - FULLSCREEN")
        print("="*60)
        print("\nSPACE - Toggle mic | ESC/Q - Exit")
        print("\n[RUNNING] Demo mode active...")
        print("Press SPACE to use your microphone!\n")

        # Enable transparency
        self.fig.patch.set_alpha(0.0)
        self.ax.patch.set_alpha(0.0)

        anim = animation.FuncAnimation(
            self.fig, self.update,
            interval=33, blit=False, cache_frame_data=False
        )

        plt.show()

        if self.audio_stream:
            self._stop_audio()


def main():
    try:
        visual = CircularVisual(fullscreen=True)
        visual.run()
    except KeyboardInterrupt:
        print("\n[EXIT]")
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
