"""
Audio analyzer for extracting features to drive visual effects
"""

import numpy as np
import librosa
from dataclasses import dataclass
from typing import List


@dataclass
class AudioFeatures:
    """Audio features extracted from input"""
    amplitude: float
    bass: float
    mid: float
    treble: float
    spectrum: List[float]
    beat_detected: float


class AudioAnalyzer:
    """
    Real-time audio analysis for visual feedback
    """

    def __init__(self, sample_rate=22050, hop_length=512):
        self.sample_rate = sample_rate
        self.hop_length = hop_length

        # Beat detection state
        self.onset_strength_history = []
        self.beat_threshold = 0.5

    def analyze(self, audio_chunk: np.ndarray) -> AudioFeatures:
        """
        Analyze audio chunk and extract features for visualization

        Args:
            audio_chunk: Audio samples (mono, float32)

        Returns:
            AudioFeatures object with extracted features
        """

        # Ensure audio is float32
        audio_chunk = audio_chunk.astype(np.float32)

        # Handle stereo → mono conversion
        if len(audio_chunk.shape) > 1:
            audio_chunk = np.mean(audio_chunk, axis=1)

        # Overall amplitude (RMS)
        amplitude = np.sqrt(np.mean(audio_chunk ** 2))
        amplitude = float(np.clip(amplitude, 0.0, 1.0))

        # Frequency spectrum (FFT)
        spectrum = np.abs(np.fft.rfft(audio_chunk))
        spectrum = spectrum / (np.max(spectrum) + 1e-6)  # Normalize

        # Frequency bands (customize based on audio characteristics)
        num_bins = len(spectrum)
        bass_end = max(1, int(num_bins * 0.1))        # 0-10%
        mid_end = max(bass_end + 1, int(num_bins * 0.5))   # 10-50%

        bass = float(np.mean(spectrum[:bass_end]))
        mid = float(np.mean(spectrum[bass_end:mid_end]))
        treble = float(np.mean(spectrum[mid_end:]))

        # Beat detection (simple onset strength)
        beat_detected = self._detect_beat(audio_chunk)

        # Downsample spectrum to 64 bins for visualization
        spectrum_64 = self._resample_spectrum(spectrum, 64)

        return AudioFeatures(
            amplitude=amplitude,
            bass=bass,
            mid=mid,
            treble=treble,
            spectrum=spectrum_64.tolist(),
            beat_detected=beat_detected
        )

    def _detect_beat(self, audio_chunk: np.ndarray) -> float:
        """
        Simple beat detection using onset strength

        Returns:
            1.0 if beat detected, 0.0 otherwise
        """
        try:
            onset_env = librosa.onset.onset_strength(
                y=audio_chunk,
                sr=self.sample_rate,
                hop_length=self.hop_length
            )

            # Check if onset strength exceeds threshold
            max_onset = np.max(onset_env) if len(onset_env) > 0 else 0.0

            # Simple threshold-based beat detection
            if max_onset > self.beat_threshold:
                return 1.0

        except Exception as e:
            # Fallback if librosa fails
            pass

        return 0.0

    def _resample_spectrum(self, spectrum: np.ndarray, target_bins: int) -> np.ndarray:
        """
        Resample spectrum to target number of bins

        Args:
            spectrum: Input spectrum
            target_bins: Desired number of bins

        Returns:
            Resampled spectrum
        """
        if len(spectrum) <= target_bins:
            # Pad with zeros
            return np.pad(spectrum, (0, target_bins - len(spectrum)))

        # Downsample by averaging bins
        bin_size = len(spectrum) / target_bins
        resampled = np.zeros(target_bins)

        for i in range(target_bins):
            start_idx = int(i * bin_size)
            end_idx = int((i + 1) * bin_size)
            resampled[i] = np.mean(spectrum[start_idx:end_idx])

        return resampled
