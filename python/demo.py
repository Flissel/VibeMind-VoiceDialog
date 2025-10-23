"""
Demo application for audio-reactive visual simulation
"""

import sys
import time
import numpy as np
import glfw
from audio_analyzer import AudioAnalyzer, AudioFeatures
import sounddevice as sd

# Import C++ module (will be built by CMake)
try:
    import visual_sim_core
except ImportError:
    print("ERROR: visual_sim_core not found. Please build the C++ module first.")
    print("Run: mkdir build && cd build && cmake .. && cmake --build .")
    sys.exit(1)


class AudioReactiveVisualDemo:
    """Demo application showing audio-reactive visuals"""

    def __init__(self, width=800, height=600, num_particles=200):
        self.width = width
        self.height = height
        self.num_particles = num_particles

        # Initialize GLFW
        if not glfw.init():
            raise RuntimeError("Failed to initialize GLFW")

        # Create window
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

        self.window = glfw.create_window(width, height, "Voice Dialog Visuals", None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("Failed to create GLFW window")

        glfw.make_context_current(self.window)
        glfw.swap_interval(1)  # VSync

        # Create simulation
        self.simulation = visual_sim_core.AudioReactiveSimulation(num_particles)

        # Initialize simulation
        if not self.simulation.initialize(width, height):
            raise RuntimeError("Failed to initialize simulation")

        self.simulation.set_fisheye_strength(0.6)

        # Audio analyzer
        self.audio_analyzer = AudioAnalyzer(sample_rate=44100)

        # Audio stream
        self.audio_stream = None
        self.audio_buffer = np.zeros(2048, dtype=np.float32)

        # Timing
        self.last_time = time.time()

        # Callbacks
        glfw.set_framebuffer_size_callback(self.window, self._on_resize)
        glfw.set_key_callback(self.window, self._on_key)

    def _on_resize(self, window, width, height):
        """Handle window resize"""
        self.width = width
        self.height = height
        self.simulation.set_window_size(width, height)

    def _on_key(self, window, key, scancode, action, mods):
        """Handle keyboard input"""
        if action == glfw.PRESS:
            if key == glfw.KEY_ESCAPE:
                glfw.set_window_should_close(window, True)
            elif key == glfw.KEY_SPACE:
                # Toggle audio input
                if self.audio_stream is None:
                    self.start_audio_input()
                else:
                    self.stop_audio_input()
            elif key == glfw.KEY_UP:
                # Increase fisheye
                self.simulation.set_fisheye_strength(0.8)
            elif key == glfw.KEY_DOWN:
                # Decrease fisheye
                self.simulation.set_fisheye_strength(0.3)

    def start_audio_input(self):
        """Start capturing audio from microphone"""
        try:
            self.audio_stream = sd.InputStream(
                channels=1,
                samplerate=44100,
                blocksize=2048,
                callback=self._audio_callback
            )
            self.audio_stream.start()
            print("Audio input started. Speak or play music!")
        except Exception as e:
            print(f"Failed to start audio input: {e}")

    def stop_audio_input(self):
        """Stop audio input"""
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
            print("Audio input stopped")

    def _audio_callback(self, indata, frames, time_info, status):
        """Audio input callback"""
        if status:
            print(f"Audio status: {status}")

        # Copy audio data
        self.audio_buffer = indata[:, 0].copy()

    def run(self):
        """Main application loop"""
        print("=== Audio-Reactive Visual Demo ===")
        print("Controls:")
        print("  SPACE    - Toggle audio input")
        print("  UP/DOWN  - Adjust fisheye strength")
        print("  ESC      - Quit")
        print()
        print("Starting in demo mode (no audio input)")
        print("Press SPACE to enable microphone input")
        print()

        # Demo mode: generate fake audio data
        demo_time = 0.0

        while not glfw.window_should_close(self.window):
            # Calculate delta time
            current_time = time.time()
            delta_time = current_time - self.last_time
            self.last_time = current_time

            # Get audio features
            if self.audio_stream is not None and len(self.audio_buffer) > 0:
                # Real audio from microphone
                features = self.audio_analyzer.analyze(self.audio_buffer)
            else:
                # Demo mode: generate fake audio data
                demo_time += delta_time
                features = self._generate_demo_audio(demo_time)

            # Convert Python features to C++ struct
            cpp_features = visual_sim_core.AudioFeatures()
            cpp_features.amplitude = features.amplitude
            cpp_features.bass = features.bass
            cpp_features.mid = features.mid
            cpp_features.treble = features.treble
            cpp_features.spectrum = features.spectrum
            cpp_features.beat_detected = features.beat_detected

            # Update simulation with audio
            self.simulation.update_audio(cpp_features)

            # Update simulation
            self.simulation.update(delta_time)

            # Render
            self.simulation.render()

            # Swap buffers and poll events
            glfw.swap_buffers(self.window)
            glfw.poll_events()

        # Cleanup
        self.cleanup()

    def _generate_demo_audio(self, t: float) -> AudioFeatures:
        """Generate fake audio data for demo mode"""
        # Simulated audio with sine waves
        amplitude = 0.3 + 0.2 * np.sin(t * 2.0)
        bass = 0.4 + 0.3 * np.sin(t * 1.5)
        mid = 0.5 + 0.2 * np.sin(t * 2.5)
        treble = 0.3 + 0.25 * np.sin(t * 3.0)

        # Beat every 0.5 seconds
        beat_detected = 1.0 if (t % 0.5) < 0.05 else 0.0

        # Generate spectrum
        spectrum = [0.5 + 0.3 * np.sin(t * 2.0 + i * 0.1) for i in range(64)]

        return AudioFeatures(
            amplitude=float(np.clip(amplitude, 0, 1)),
            bass=float(np.clip(bass, 0, 1)),
            mid=float(np.clip(mid, 0, 1)),
            treble=float(np.clip(treble, 0, 1)),
            spectrum=spectrum,
            beat_detected=beat_detected
        )

    def cleanup(self):
        """Cleanup resources"""
        if self.audio_stream:
            self.stop_audio_input()

        self.simulation.cleanup()
        glfw.terminate()


def main():
    """Entry point"""
    try:
        demo = AudioReactiveVisualDemo(width=1024, height=768, num_particles=300)
        demo.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
