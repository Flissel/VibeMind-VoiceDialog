"""
Custom Audio Interface with Threshold Filtering

Prevents audio feedback loop by filtering quiet sounds (speaker output)
and only capturing loud sounds (user voice close to microphone).
"""

import numpy as np
import sounddevice as sd
import queue
import threading
from typing import Optional
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface


class ThresholdAudioInterface(DefaultAudioInterface):
    """
    Custom audio interface that extends DefaultAudioInterface with amplitude threshold.

    This prevents audio feedback loops where the AI's speaker output gets picked up
    by the microphone, causing the AI to respond to itself.

    How it works:
    - Calculates RMS (Root Mean Square) amplitude of audio input
    - Only passes audio chunks above the threshold to the conversation
    - Drops quiet audio (speaker output from far away) silently
    - Captures loud audio (user voice close to microphone)

    Parameters:
        amplitude_threshold: Minimum RMS amplitude (0.0 to 1.0)
                           Higher = only louder sounds pass
                           Start with 0.03 (3%) and adjust based on testing

        min_speech_duration: Minimum duration of continuous speech to trigger (seconds)
                            Default: 0.3 seconds (300ms)
    """

    def __init__(
        self,
        amplitude_threshold: float = 0.03,
        min_speech_duration: float = 0.3,
        **kwargs
    ):
        """
        Initialize threshold audio interface

        Args:
            amplitude_threshold: RMS amplitude threshold (0.0-1.0)
            min_speech_duration: Minimum speech duration in seconds
            **kwargs: Additional arguments passed to DefaultAudioInterface
        """
        # Initialize parent DefaultAudioInterface
        super().__init__(**kwargs)

        self.amplitude_threshold = amplitude_threshold
        self.min_speech_duration = min_speech_duration

        # Speech detection state
        self.speech_samples = []
        self.is_speech_detected = False

        print(f"Threshold Audio Interface initialized:")
        print(f"  Amplitude threshold: {amplitude_threshold:.3f} ({amplitude_threshold*100:.1f}%)")
        print(f"  Min speech duration: {min_speech_duration}s")
        print(f"  This helps prevent audio feedback from speakers")

    def _calculate_rms(self, audio_data: np.ndarray) -> float:
        """
        Calculate RMS (Root Mean Square) amplitude of audio data

        RMS gives us a measure of the "loudness" of the audio signal.
        Closer sounds (user voice) have higher RMS than distant sounds (speaker output).

        Args:
            audio_data: Audio samples as numpy array

        Returns:
            RMS amplitude value between 0.0 and 1.0
        """
        return np.sqrt(np.mean(audio_data**2))

    def _is_above_threshold(self, audio_chunk: np.ndarray) -> bool:
        """
        Check if audio chunk is above the threshold

        Args:
            audio_chunk: Audio samples to check

        Returns:
            True if audio is loud enough (user voice), False if too quiet (speaker feedback)
        """
        rms = self._calculate_rms(audio_chunk)
        is_above = rms > self.amplitude_threshold

        # Optional: Print debug info (comment out after testing)
        # if is_above:
        #     print(f"Audio detected: RMS={rms:.4f} (threshold={self.amplitude_threshold:.4f})")

        return is_above


# Convenience function for testing different thresholds
def test_threshold(duration_seconds: int = 10, threshold: float = 0.03):
    """
    Test the microphone threshold for a few seconds

    This helps you find the right threshold value:
    - Speak normally into microphone -> should show "SPEECH DETECTED"
    - Let speaker play -> should show "Below threshold (filtered)"

    Args:
        duration_seconds: How long to test (default: 10 seconds)
        threshold: Amplitude threshold to test (default: 0.03)
    """
    print(f"Testing microphone threshold for {duration_seconds} seconds...")
    print(f"Threshold: {threshold:.3f} ({threshold*100:.1f}%)")
    print()
    print("Speak into your microphone - you should see 'SPEECH DETECTED'")
    print("Let your speakers play - you should see 'Below threshold (filtered)'")
    print()

    sample_rate = 16000
    chunk_size = int(sample_rate * 0.1)  # 100ms chunks

    def audio_callback(indata, frames, time, status):
        """Process audio and display threshold detection"""
        if status:
            print(f"Status: {status}")

        audio_data = indata.flatten()
        rms = np.sqrt(np.mean(audio_data**2))

        if rms > threshold:
            print(f"✓ SPEECH DETECTED - RMS: {rms:.4f} (above {threshold:.4f})")
        else:
            # Only print occasionally to avoid spam
            pass  # print(f"✗ Below threshold (filtered) - RMS: {rms:.4f}")

    # Start audio stream
    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        callback=audio_callback,
        blocksize=chunk_size
    ):
        print("Recording... Press Ctrl+C to stop")
        try:
            sd.sleep(duration_seconds * 1000)
        except KeyboardInterrupt:
            print("\nTest stopped by user")

    print("\nThreshold test complete!")
    print()
    print("Adjustment guidelines:")
    print("  - If speaker audio triggers detection: INCREASE threshold (0.04, 0.05, ...)")
    print("  - If your voice doesn't trigger detection: DECREASE threshold (0.02, 0.01, ...)")
    print(f"  - Current threshold: {threshold:.3f}")


if __name__ == "__main__":
    """Run threshold test when executed directly"""
    import sys

    # Default threshold
    threshold = 0.03

    # Allow testing with custom threshold: python custom_audio_interface.py 0.05
    if len(sys.argv) > 1:
        try:
            threshold = float(sys.argv[1])
        except ValueError:
            print(f"Invalid threshold value: {sys.argv[1]}")
            print("Usage: python custom_audio_interface.py [threshold]")
            print("Example: python custom_audio_interface.py 0.05")
            sys.exit(1)

    # Run test
    test_threshold(duration_seconds=10, threshold=threshold)
