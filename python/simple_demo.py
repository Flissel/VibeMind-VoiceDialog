"""
Simple Python-only demo showing audio-reactive visuals
(No C++ compilation required)

This demo uses matplotlib to visualize audio-reactive particle system
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from audio_analyzer import AudioAnalyzer, AudioFeatures
import sounddevice as sd
from dataclasses import dataclass
from typing import List


@dataclass
class Particle:
    """Simple particle for visualization"""
    x: float
    y: float
    vx: float
    vy: float
    hue: float
    size: float


class AudioReactiveDemo:
    """Audio-reactive particle demo using matplotlib"""

    def __init__(self, num_particles=200):
        self.num_particles = num_particles
        self.particles = self._init_particles()

        # Audio
        self.audio_analyzer = AudioAnalyzer(sample_rate=44100)
        self.audio_buffer = np.zeros(2048, dtype=np.float32)
        self.audio_stream = None

        # Audio features
        self.current_audio = AudioFeatures(
            amplitude=0.0,
            bass=0.0,
            mid=0.0,
            treble=0.0,
            spectrum=[0.0] * 64,
            beat_detected=0.0
        )

        # Visual state
        self.hue_offset = 0.0
        self.demo_time = 0.0

        # Setup plot
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)
        self.ax.set_facecolor('black')
        self.fig.patch.set_facecolor('black')
        self.ax.set_aspect('equal')
        self.ax.axis('off')

        # Scatter plot for particles
        self.scatter = self.ax.scatter([], [], s=[], c=[], alpha=0.8)

        # Title
        self.title = self.ax.text(
            0.5, 0.95, 'Audio-Reactive Visuals\nPress Space to enable mic',
            color='white', ha='center', va='top',
            transform=self.ax.transAxes, fontsize=12
        )

        # Connect keyboard
        self.fig.canvas.mpl_connect('key_press_event', self._on_key)

    def _init_particles(self) -> List[Particle]:
        """Initialize random particles"""
        particles = []
        for i in range(self.num_particles):
            particles.append(Particle(
                x=np.random.rand(),
                y=np.random.rand(),
                vx=np.random.uniform(-0.01, 0.01),
                vy=np.random.uniform(-0.01, 0.01),
                hue=np.random.rand() * 360,
                size=np.random.uniform(5, 15)
            ))
        return particles

    def _on_key(self, event):
        """Handle keyboard input"""
        if event.key == ' ':
            # Toggle audio
            if self.audio_stream is None:
                self.start_audio()
            else:
                self.stop_audio()
        elif event.key == 'escape':
            plt.close(self.fig)

    def start_audio(self):
        """Start microphone input"""
        try:
            self.audio_stream = sd.InputStream(
                channels=1,
                samplerate=44100,
                blocksize=2048,
                callback=self._audio_callback
            )
            self.audio_stream.start()
            self.title.set_text('Audio-Reactive Visuals\n🎤 Microphone Active (Space to stop)')
            print("Microphone started!")
        except Exception as e:
            print(f"Failed to start audio: {e}")
            self.title.set_text(f'Audio-Reactive Visuals\n❌ Mic error: {e}')

    def stop_audio(self):
        """Stop audio input"""
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
            self.title.set_text('Audio-Reactive Visuals\nPress Space to enable mic')
            print("Microphone stopped")

    def _audio_callback(self, indata, frames, time_info, status):
        """Audio input callback"""
        if status:
            print(f"Audio status: {status}")
        self.audio_buffer = indata[:, 0].copy()

    def _update_particles(self, dt=0.016):
        """Update particle positions and colors"""

        # Get audio features
        if self.audio_stream and len(self.audio_buffer) > 0:
            self.current_audio = self.audio_analyzer.analyze(self.audio_buffer)
        else:
            # Demo mode with fake audio
            self.demo_time += dt
            self.current_audio = self._generate_demo_audio(self.demo_time)

        audio = self.current_audio

        # Update hue offset
        self.hue_offset += audio.amplitude * 5.0

        # Update each particle
        positions = []
        colors = []
        sizes = []

        for i, p in enumerate(self.particles):
            # Update position
            speed_mult = 1.0 + audio.amplitude * 2.0
            p.x += p.vx * speed_mult
            p.y += p.vy * speed_mult

            # Wrap around
            if p.x < 0: p.x += 1
            if p.x > 1: p.x -= 1
            if p.y < 0: p.y += 1
            if p.y > 1: p.y -= 1

            # Audio-reactive color
            hue_shift = (audio.bass * 60 + audio.mid * 120 + audio.treble * 180)
            final_hue = (p.hue + self.hue_offset + hue_shift) % 360

            # HSV to RGB
            c = self._hsv_to_rgb(final_hue, 0.8 + audio.beat_detected * 0.2, 0.6 + audio.amplitude * 0.4)

            # Size pulses with beats
            size = p.size * (1.0 + audio.beat_detected * 0.5)

            positions.append([p.x, p.y])
            colors.append(c)
            sizes.append(size ** 2)  # matplotlib uses area

        return np.array(positions), colors, sizes

    def _hsv_to_rgb(self, h, s, v):
        """Convert HSV to RGB"""
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

        return (r + m, g + m, b + m)

    def _generate_demo_audio(self, t):
        """Generate fake audio for demo mode"""
        amplitude = 0.3 + 0.2 * np.sin(t * 2.0)
        bass = 0.4 + 0.3 * np.sin(t * 1.5)
        mid = 0.5 + 0.2 * np.sin(t * 2.5)
        treble = 0.3 + 0.25 * np.sin(t * 3.0)
        beat_detected = 1.0 if (t % 0.5) < 0.05 else 0.0
        spectrum = [0.5 + 0.3 * np.sin(t * 2.0 + i * 0.1) for i in range(64)]

        return AudioFeatures(
            amplitude=float(np.clip(amplitude, 0, 1)),
            bass=float(np.clip(bass, 0, 1)),
            mid=float(np.clip(mid, 0, 1)),
            treble=float(np.clip(treble, 0, 1)),
            spectrum=spectrum,
            beat_detected=beat_detected
        )

    def _animate(self, frame):
        """Animation update function"""
        positions, colors, sizes = self._update_particles()

        self.scatter.set_offsets(positions)
        self.scatter.set_facecolors(colors)
        self.scatter.set_sizes(sizes)

        return self.scatter, self.title

    def run(self):
        """Start the visualization"""
        print("=" * 50)
        print("Audio-Reactive Visual Demo (Python-only version)")
        print("=" * 50)
        print("\nControls:")
        print("  SPACE - Toggle microphone input")
        print("  ESC   - Quit")
        print("\nStarting in demo mode...")
        print("The particles will respond to simulated audio.")
        print("Press SPACE to use your microphone!\n")

        anim = animation.FuncAnimation(
            self.fig, self._animate,
            interval=16,  # ~60 FPS
            blit=True,
            cache_frame_data=False
        )

        plt.show()

        # Cleanup
        if self.audio_stream:
            self.stop_audio()


def main():
    """Entry point"""
    try:
        demo = AudioReactiveDemo(num_particles=300)
        demo.run()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
