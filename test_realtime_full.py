"""
Minimal OpenAI Realtime API test - full pipeline:
Microphone → WebSocket → Response → Speaker

Run: python test_realtime_full.py
Speak into microphone, wait for response.
Press Ctrl+C to stop.
"""
import asyncio
import base64
import json
import os
import sys
import queue
import time
import numpy as np

# Fix Windows console encoding for German umlauts
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load .env
with open('.env') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

SAMPLE_RATE = 24000
BLOCK_SIZE = 2400  # 100ms

audio_queue = queue.Queue(maxsize=200)
playback_buffer = []
playback_lock = asyncio.Lock()


def mic_callback(indata, frames, time_info, status):
    """Sounddevice input callback - runs in separate thread."""
    if status:
        print(f"  [MIC STATUS] {status}", flush=True)
    audio_bytes = indata.tobytes()
    b64 = base64.b64encode(audio_bytes).decode("utf-8")
    try:
        audio_queue.put_nowait(b64)
    except queue.Full:
        pass


def speaker_callback(outdata, frames, time_info, status):
    """Sounddevice output callback - runs in separate thread."""
    if playback_buffer:
        chunk = playback_buffer.pop(0)
        if len(chunk) >= frames:
            outdata[:, 0] = chunk[:frames]
        else:
            outdata[:frames, 0] = 0
            outdata[:len(chunk), 0] = chunk
    else:
        outdata.fill(0)


async def main():
    import sounddevice as sd
    from openai import AsyncOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")
    voice = os.getenv("OPENAI_REALTIME_VOICE", "alloy")

    print(f"=== OpenAI Realtime API Full Test ===")
    print(f"Model: {model}")
    print(f"Voice: {voice}")
    print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
    print(f"Sample Rate: {SAMPLE_RATE}Hz")
    print()

    # List audio devices
    print("Audio devices:")
    devices = sd.query_devices()
    default_input = sd.default.device[0]
    default_output = sd.default.device[1]
    print(f"  Input:  [{default_input}] {devices[default_input]['name']}")
    print(f"  Output: [{default_output}] {devices[default_output]['name']}")
    print()

    # Connect to OpenAI Realtime
    print("[1/4] Connecting to OpenAI Realtime API...")
    client = AsyncOpenAI(api_key=api_key)

    async with client.realtime.connect(model=model) as connection:
        print("[2/4] Connected! Configuring session...")

        # Configure session (GA API schema - openai SDK v2.0.0+)
        await connection.session.update(session={
            "type": "realtime",
            "output_modalities": ["audio"],
            "instructions": "Du bist Rachel, eine freundliche Assistentin. Antworte kurz und freundlich auf Deutsch.",
            "audio": {
                "input": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": SAMPLE_RATE,
                    },
                    "transcription": {
                        "model": "whisper-1",
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                        "create_response": True,
                        "interrupt_response": True,
                    },
                },
                "output": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": SAMPLE_RATE,
                    },
                    "voice": voice,
                },
            },
            "tools": [],
            "tool_choice": "auto",
        })
        print("[3/4] Session configured!")

        # Start audio streams
        print("[4/4] Starting audio streams...")
        input_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=BLOCK_SIZE,
            callback=mic_callback,
        )
        output_stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=BLOCK_SIZE,
            callback=speaker_callback,
        )
        input_stream.start()
        output_stream.start()

        print()
        print("=" * 50)
        print("READY! Speak into your microphone...")
        print("Press Ctrl+C to stop.")
        print("=" * 50)
        print()

        chunks_sent = 0
        last_log = time.time()
        agent_transcript = ""

        # Start audio sending task
        async def send_audio():
            nonlocal chunks_sent, last_log
            while True:
                try:
                    b64 = audio_queue.get_nowait()
                    await connection.input_audio_buffer.append(audio=b64)
                    chunks_sent += 1
                    now = time.time()
                    if now - last_log > 3.0:
                        print(f"  [AUDIO] {chunks_sent} chunks sent to OpenAI", flush=True)
                        last_log = now
                except queue.Empty:
                    await asyncio.sleep(0.02)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"  [ERROR] Audio send: {e}", flush=True)
                    await asyncio.sleep(0.1)

        send_task = asyncio.create_task(send_audio())

        # Process events
        try:
            async for event in connection:
                etype = event.type

                if etype == "session.created":
                    print("  [EVENT] Session created", flush=True)
                elif etype == "session.updated":
                    print("  [EVENT] Session updated", flush=True)

                elif etype == "input_audio_buffer.speech_started":
                    print("  [VAD] >>> Speech STARTED <<<", flush=True)
                    playback_buffer.clear()

                elif etype == "input_audio_buffer.speech_stopped":
                    print("  [VAD] >>> Speech STOPPED <<<", flush=True)

                elif etype in ("conversation.item.input_audio_transcription.completed",
                               "conversation.item.input_audio_transcription.delta"):
                    transcript = getattr(event, "transcript", "")
                    if transcript:
                        print(f"  [USER] {transcript}", flush=True)

                elif etype in ("response.output_audio.delta", "response.audio.delta"):
                    if hasattr(event, "delta") and event.delta:
                        audio_bytes = base64.b64decode(event.delta)
                        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
                        playback_buffer.append(audio_array)

                elif etype in ("response.output_audio_transcript.delta", "response.audio_transcript.delta"):
                    if hasattr(event, "delta"):
                        agent_transcript += event.delta

                elif etype in ("response.output_audio_transcript.done", "response.audio_transcript.done"):
                    if agent_transcript.strip():
                        print(f"  [RACHEL] {agent_transcript.strip()}", flush=True)
                    agent_transcript = ""

                elif etype == "response.done":
                    print("  [EVENT] Response complete", flush=True)

                elif etype == "error":
                    error_msg = getattr(event, "error", {})
                    if isinstance(error_msg, dict):
                        print(f"  [ERROR] {error_msg.get('message', error_msg)}", flush=True)
                    else:
                        print(f"  [ERROR] {error_msg}", flush=True)

                elif etype in ("rate_limits.updated",
                               "input_audio_buffer.committed",
                               "conversation.item.added",
                               "conversation.item.done",
                               "response.output_item.added",
                               "response.output_item.done",
                               "response.content_part.added",
                               "response.content_part.done",
                               "response.output_audio.done",
                               "response.created"):
                    pass  # Ignore GA info events

                else:
                    print(f"  [EVENT] {etype}", flush=True)

        except KeyboardInterrupt:
            print("\n\nStopping...")
        finally:
            send_task.cancel()
            input_stream.stop()
            input_stream.close()
            output_stream.stop()
            output_stream.close()
            print("Done!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye!")
