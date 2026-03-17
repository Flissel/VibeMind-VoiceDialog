"""
Audio Manager for OpenAI Realtime API

Handles microphone capture and audio playback using sounddevice.
Audio format: PCM 16-bit, 24kHz, mono (as required by OpenAI Realtime API).

Features:
- Microphone input stream with callback
- Audio playback with buffer management
- Base64 encoding for WebSocket transport
- Graceful start/stop with resource cleanup
"""

import base64
import concurrent.futures
import logging
import threading
import numpy as np
import sounddevice as sd
from typing import Optional, Callable
from collections import deque

logger = logging.getLogger(__name__)

# OpenAI Realtime audio requirements
SAMPLE_RATE = 24000
CHANNELS = 1
DTYPE = np.int16
BLOCK_SIZE = 2400  # 100ms chunks at 24kHz (2400 samples)


class AudioManager:
    """
    Manages microphone capture and audio playback for OpenAI Realtime.

    Audio is captured as PCM 16-bit 24kHz mono and encoded to base64
    for transmission over WebSocket. Received audio (also PCM16 24kHz)
    is decoded from base64 and played through speakers.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        block_size: int = BLOCK_SIZE,
        on_audio_chunk: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize AudioManager.

        Args:
            sample_rate: Audio sample rate (must be 24000 for OpenAI Realtime)
            channels: Number of audio channels (must be 1 for mono)
            block_size: Samples per audio chunk
            on_audio_chunk: Callback receiving base64-encoded audio chunks
        """
        self._sample_rate = sample_rate
        self._channels = channels
        self._block_size = block_size
        self._on_audio_chunk = on_audio_chunk

        # Streams (lazy import sounddevice)
        self._input_stream = None
        self._output_stream = None
        self._is_capturing = False
        self._is_playing = False

        # Playback buffer
        self._playback_buffer: deque = deque()
        self._playback_lock = threading.Lock()

        # Audio level monitoring (for client-side silence detection)
        self._last_rms: float = 0.0

        logger.info(
            f"AudioManager initialized: {sample_rate}Hz, {channels}ch, "
            f"block_size={block_size}"
        )

    def _create_input_stream(self) -> None:
        """Create and start input stream (runs in thread pool for timeout support)."""
        try:
            default_input = sd.query_devices(kind="input")
            logger.debug(
                f"[AudioManager] Default input device: "
                f"'{default_input['name']}' (index={default_input['index']}, "
                f"channels={default_input['max_input_channels']}, "
                f"rate={default_input['default_samplerate']})"
            )
        except Exception as dev_err:
            logger.debug(f"[AudioManager] Could not query input device: {dev_err}")

        self._input_stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="int16",
            blocksize=self._block_size,
            callback=self._input_callback,
        )
        self._input_stream.start()

    def start_capture(self) -> None:
        """Start microphone capture. Audio chunks are sent via on_audio_chunk callback."""
        if self._is_capturing:
            logger.warning("Already capturing audio")
            return

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._create_input_stream)
                future.result(timeout=15)
            self._is_capturing = True
            logger.info("Microphone capture started")

        except concurrent.futures.TimeoutError:
            logger.error("Audio capture init timed out (15s) — PortAudio hung")
            raise RuntimeError("Audio device init timed out")
        except Exception as e:
            logger.error(f"Failed to start microphone capture: {e}")
            raise

    def stop_capture(self) -> None:
        """Stop microphone capture."""
        if not self._is_capturing:
            return

        try:
            if self._input_stream:
                self._input_stream.stop()
                self._input_stream.close()
                self._input_stream = None
            self._is_capturing = False
            logger.info("Microphone capture stopped")

        except Exception as e:
            logger.error(f"Error stopping microphone capture: {e}")

    def _create_output_stream(self) -> None:
        """Create and start output stream (runs in thread pool for timeout support)."""
        self._output_stream = sd.OutputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="int16",
            blocksize=self._block_size,
            callback=self._output_callback,
        )
        self._output_stream.start()

    def start_playback(self) -> None:
        """Start audio playback stream."""
        if self._is_playing:
            return

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._create_output_stream)
                future.result(timeout=15)
            self._is_playing = True
            logger.info("Audio playback started")

        except concurrent.futures.TimeoutError:
            logger.error("Audio playback init timed out (15s) — PortAudio hung")
            raise RuntimeError("Audio device init timed out")
        except Exception as e:
            logger.error(f"Failed to start audio playback: {e}")
            raise

    def stop_playback(self) -> None:
        """Stop audio playback stream."""
        if not self._is_playing:
            return

        try:
            if self._output_stream:
                self._output_stream.stop()
                self._output_stream.close()
                self._output_stream = None
            self._is_playing = False
            self.clear_playback_buffer()
            logger.info("Audio playback stopped")

        except Exception as e:
            logger.error(f"Error stopping audio playback: {e}")

    def enqueue_audio(self, base64_audio: str) -> None:
        """
        Add base64-encoded audio chunk to playback buffer.

        Args:
            base64_audio: Base64-encoded PCM 16-bit audio
        """
        try:
            audio_bytes = base64.b64decode(base64_audio)
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)

            with self._playback_lock:
                self._playback_buffer.append(audio_array)

        except Exception as e:
            logger.error(f"Error enqueuing audio: {e}")

    def clear_playback_buffer(self) -> None:
        """Clear all pending audio from playback buffer."""
        with self._playback_lock:
            self._playback_buffer.clear()
        logger.debug("Playback buffer cleared")

    def _input_callback(self, indata, frames, time_info, status):
        """
        Sounddevice input callback - called for each audio chunk.

        Encodes audio as base64, computes RMS level, and sends via callback.
        """
        if status:
            logger.warning(f"Audio input status: {status}")

        if self._on_audio_chunk and self._is_capturing:
            # Compute RMS level for silence detection
            rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
            self._last_rms = rms

            # Convert numpy array to bytes, then base64
            audio_bytes = indata.tobytes()
            base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
            self._on_audio_chunk(base64_audio)

    def _output_callback(self, outdata, frames, time_info, status):
        """
        Sounddevice output callback - called to fill speaker buffer.

        Reads from playback buffer, fills with silence if buffer is empty.
        """
        if status:
            logger.warning(f"Audio output status: {status}")

        samples_needed = frames
        output_chunks = []
        samples_collected = 0

        with self._playback_lock:
            while samples_collected < samples_needed and self._playback_buffer:
                chunk = self._playback_buffer[0]
                remaining = samples_needed - samples_collected

                if len(chunk) <= remaining:
                    # Use entire chunk
                    output_chunks.append(chunk)
                    samples_collected += len(chunk)
                    self._playback_buffer.popleft()
                else:
                    # Use partial chunk, keep remainder
                    output_chunks.append(chunk[:remaining])
                    self._playback_buffer[0] = chunk[remaining:]
                    samples_collected += remaining

        if output_chunks:
            audio = np.concatenate(output_chunks)
            # Pad with silence if we didn't get enough samples
            if len(audio) < samples_needed:
                padding = np.zeros(samples_needed - len(audio), dtype=np.int16)
                audio = np.concatenate([audio, padding])
            outdata[:, 0] = audio[:samples_needed]
        else:
            # Silence
            outdata.fill(0)

    def set_audio_callback(self, callback: Callable[[str], None]) -> None:
        """Set the callback for audio chunks from microphone."""
        self._on_audio_chunk = callback

    @property
    def is_capturing(self) -> bool:
        """Whether microphone is active."""
        return self._is_capturing

    @property
    def is_playing(self) -> bool:
        """Whether playback is active."""
        return self._is_playing

    @property
    def playback_buffer_size(self) -> int:
        """Number of audio chunks in playback buffer."""
        return len(self._playback_buffer)

    @property
    def last_rms(self) -> float:
        """Last measured RMS audio level from microphone (0-32768 for int16)."""
        return self._last_rms

    def cleanup(self) -> None:
        """Release all audio resources."""
        self.stop_capture()
        self.stop_playback()
        logger.info("AudioManager cleaned up")

    def __del__(self):
        """Ensure cleanup on garbage collection."""
        try:
            self.cleanup()
        except Exception:
            pass
