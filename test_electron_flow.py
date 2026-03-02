"""
Test: Simulate exactly how electron_backend.py starts voice.

This mimics the real flow:
1. asyncio.run(main()) with ProactorEventLoop on Windows
2. Message queue processing loop
3. asyncio.create_task(start_voice()) triggered by message
4. Voice session connect + start

Run: python test_electron_flow.py
"""
import asyncio
import sys
import os
import time
import threading

# Fix Windows console encoding
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

# Add python/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))


async def test_voice_start():
    """Simulate what _start_voice_openai_realtime does."""
    from voice.openai_realtime import OpenAIRealtimeVoiceSession

    print(f"[TEST] Creating OpenAIRealtimeVoiceSession...", flush=True)
    session = OpenAIRealtimeVoiceSession(
        api_key=os.getenv("OPENAI_API_KEY"),
        system_prompt="Du bist Rachel, eine freundliche Assistentin. Antworte kurz und freundlich auf Deutsch.",
        on_tool_call=lambda cid, name, args: "OK",
        on_user_transcript=lambda t: print(f"  [USER] {t}", flush=True),
        on_agent_transcript=lambda t: print(f"  [RACHEL] {t}", flush=True),
    )

    print(f"[TEST] Calling session.connect()...", flush=True)
    await session.connect()
    print(f"[TEST] Connected! Calling session.start()...", flush=True)
    await session.start()
    print(f"[TEST] Voice session ACTIVE! Speak into mic for 15 seconds...", flush=True)

    # Let it run for 15 seconds
    await asyncio.sleep(15)

    print(f"[TEST] Disconnecting...", flush=True)
    await session.disconnect()
    print(f"[TEST] Done!", flush=True)


async def main():
    """Simulate electron_backend.py main loop with message queue."""
    print("=== Simulating Electron Backend Voice Start ===", flush=True)
    print(f"Python: {sys.version}", flush=True)
    print(f"Event loop: {type(asyncio.get_event_loop()).__name__}", flush=True)
    print(flush=True)

    # Simulate the message queue pattern from electron_backend.py
    message_queue = asyncio.Queue()

    loop = asyncio.get_event_loop()

    # Simulate stdin reader thread putting a message
    def fake_stdin_reader():
        time.sleep(0.5)  # Small delay like real startup
        asyncio.run_coroutine_threadsafe(
            message_queue.put({"type": "start_voice"}),
            loop
        )

    reader_thread = threading.Thread(target=fake_stdin_reader, daemon=True)
    reader_thread.start()

    # Main message processing loop (exactly like electron_backend.py)
    print("[MAIN] Waiting for messages...", flush=True)
    timeout_counter = 0
    while True:
        try:
            message = await asyncio.wait_for(message_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            timeout_counter += 1
            if timeout_counter > 20:
                print("[MAIN] Timeout - exiting", flush=True)
                break
            continue

        msg_type = message.get("type")
        print(f"[MAIN] Got message: {msg_type}", flush=True)

        if msg_type == "start_voice":
            # This is exactly what electron_backend.py does
            task = asyncio.create_task(test_voice_start())
            print(f"[MAIN] Created task: {task}", flush=True)
            # Continue processing messages (don't await the task!)

        elif msg_type == "quit":
            break


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye!")
