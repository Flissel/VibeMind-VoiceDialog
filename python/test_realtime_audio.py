"""
Standalone test: OpenAI Realtime API audio output test.
Tests session config + greeting + audio playback.
Run: .venv312\Scripts\python.exe test_realtime_audio.py
"""
import asyncio
import os
import sys
import time
import base64
import numpy as np

# Add parent to path for llm_config import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_config import get_model

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def log(msg):
    elapsed = time.time() - _t0
    print(f"[{elapsed:7.2f}s] {msg}", flush=True)

_t0 = time.time()

async def test_audio():
    log("=== OpenAI Realtime Audio Test ===")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        log("ERROR: OPENAI_API_KEY not set")
        return

    log(f"API key: {api_key[:8]}...{api_key[-4:]}")

    # 1. Connect
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key)

    log("Connecting to OpenAI Realtime...")
    connection_manager = client.realtime.connect(
        model=get_model("voice"),
        websocket_connection_options={"open_timeout": 15, "close_timeout": 5},
    )
    connection = await connection_manager.__aenter__()
    log("WebSocket connected!")

    # 2. Send session.update with CORRECT format
    session_config = {
        "type": "realtime",
        "output_modalities": ["audio"],
        "instructions": "Du bist Rachel, eine freundliche deutsche Assistentin. Antworte kurz.",
        "audio": {
            "input": {
                "format": {"type": "audio/pcm", "rate": 24000},
                "transcription": {"model": get_model("transcription")},
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
                "format": {"type": "audio/pcm", "rate": 24000},
                "voice": "alloy",
            },
        },
    }

    log(f"Sending session.update: {list(session_config.keys())}")
    await connection.session.update(session=session_config)
    log("session.update sent!")

    # 3. Wait for session events
    audio_chunks = []
    transcript_parts = []
    events_seen = []

    async def process_events():
        async for event in connection:
            etype = event.type
            events_seen.append(etype)

            if etype == "session.created":
                log(f"EVENT: session.created")
            elif etype == "session.updated":
                log(f"EVENT: session.updated OK")
            elif etype == "response.created":
                log(f"EVENT: response.created")
            elif etype in ("response.audio.delta", "response.output_audio.delta"):
                delta = getattr(event, "delta", "")
                if delta:
                    audio_chunks.append(delta)
                    if len(audio_chunks) == 1:
                        log(f"EVENT: FIRST audio delta! ({len(delta)} chars)")
                    elif len(audio_chunks) % 50 == 0:
                        log(f"EVENT: audio delta #{len(audio_chunks)}")
            elif etype in ("response.audio_transcript.delta", "response.output_audio_transcript.delta"):
                delta = getattr(event, "delta", "")
                transcript_parts.append(delta)
            elif etype in ("response.audio_transcript.done", "response.output_audio_transcript.done"):
                transcript = "".join(transcript_parts)
                log(f"EVENT: transcript done: '{transcript}'")
                transcript_parts.clear()
            elif etype in ("response.audio.done", "response.output_audio.done"):
                log(f"EVENT: audio done (total chunks: {len(audio_chunks)})")
            elif etype == "response.done":
                log(f"EVENT: response.done OK")
                return  # Done!
            elif etype == "error":
                error_msg = getattr(event, "error", {})
                log(f"EVENT: ERROR: {error_msg}")
                return
            else:
                if len(events_seen) <= 5:
                    log(f"EVENT: {etype}")

    # Start event processing in background
    event_task = asyncio.create_task(process_events())

    # 4. Wait a moment for session.updated, then trigger greeting
    await asyncio.sleep(0.5)
    log("Triggering greeting via response.create...")
    await connection.response.create(
        response={
            "instructions": "Sag kurz Hallo! Sag: Hey, ich bin Rachel.",
        }
    )
    log("response.create sent!")

    # 5. Wait for response to complete (max 15s)
    try:
        await asyncio.wait_for(event_task, timeout=15.0)
    except asyncio.TimeoutError:
        log(f"TIMEOUT after 15s. Events seen: {events_seen}")

    # 6. Results
    log(f"\n=== RESULTS ===")
    log(f"Events seen: {len(events_seen)}")
    log(f"Unique event types: {sorted(set(events_seen))}")
    log(f"Audio chunks: {len(audio_chunks)}")
    if audio_chunks:
        total_bytes = sum(len(base64.b64decode(c)) for c in audio_chunks)
        duration_s = total_bytes / (24000 * 2)  # 24kHz, 16-bit
        log(f"Audio duration: {duration_s:.2f}s ({total_bytes} bytes)")

        # Try to play audio
        try:
            import sounddevice as sd
            all_audio = b"".join(base64.b64decode(c) for c in audio_chunks)
            audio_array = np.frombuffer(all_audio, dtype=np.int16).astype(np.float32) / 32768.0
            log(f"Playing audio ({duration_s:.1f}s)...")
            sd.play(audio_array, samplerate=24000)
            sd.wait()
            log("Audio playback complete!")
        except Exception as e:
            log(f"Playback error: {e}")
    else:
        log("NO AUDIO RECEIVED!")

    # Cleanup
    try:
        await connection_manager.__aexit__(None, None, None)
    except:
        pass
    log("Done.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(test_audio())
