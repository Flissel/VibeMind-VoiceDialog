"""
Test: Simulate Electron starting/stopping/restarting voice in Python backend.
Verifies that stop->start cycle produces exactly 1 voice_stopped message.
Run: .venv312\Scripts\python.exe test_electron_voice.py
"""
import subprocess
import sys
import time
import threading
import os
import json

# Counters for voice_stopped / voice_started messages
voice_stopped_count = 0
voice_started_count = 0
stdout_lines = []


def main():
    global voice_stopped_count, voice_started_count

    python_exe = os.path.join(os.path.dirname(__file__), "..", ".venv312", "Scripts", "python.exe")
    backend_script = os.path.join(os.path.dirname(__file__), "electron_backend.py")

    print(f"Starting backend: {python_exe} {backend_script}")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [python_exe, backend_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(__file__),
        env=env,
    )

    # Read stderr in background thread
    def read_stderr():
        for line in proc.stderr:
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                print(f"[STDERR] {text}", flush=True)

    # Read stdout in background thread — count voice_stopped/voice_started
    def read_stdout():
        global voice_stopped_count, voice_started_count
        for line in proc.stdout:
            text = line.decode("utf-8", errors="replace").rstrip()
            if not text:
                continue
            stdout_lines.append(text)
            try:
                msg = json.loads(text)
                msg_type = msg.get("type", "")
                if msg_type == "voice_stopped":
                    voice_stopped_count += 1
                    print(f"[STDOUT] {text}  <<< voice_stopped #{voice_stopped_count}", flush=True)
                elif msg_type == "voice_started":
                    voice_started_count += 1
                    print(f"[STDOUT] {text}  <<< voice_started #{voice_started_count}", flush=True)
                elif msg_type in ("agent_response", "user_transcript"):
                    print(f"[STDOUT] {text}", flush=True)
                else:
                    # Suppress noisy messages (roarboot, automation_ui, etc.)
                    pass
            except json.JSONDecodeError:
                print(f"[STDOUT] {text}", flush=True)

    t_err = threading.Thread(target=read_stderr, daemon=True)
    t_out = threading.Thread(target=read_stdout, daemon=True)
    t_err.start()
    t_out.start()

    # Wait for python_ready
    print("Waiting 3s for backend to initialize...")
    time.sleep(3)

    def send(msg_dict):
        data = json.dumps(msg_dict) + "\n"
        proc.stdin.write(data.encode())
        proc.stdin.flush()

    # === Phase 1: Start voice, wait for greeting ===
    # PortAudio on Windows can hold the GIL for 30+ seconds via CFFI ABI
    # mode during Pa_OpenStream(). Wait 45s to cover worst case.
    print("\n=== Phase 1: start_voice ===")
    voice_stopped_count = 0
    voice_started_count = 0
    send({"type": "start_voice"})

    print("Waiting 45s for greeting (PortAudio init can take 35s)...")
    time.sleep(45)

    # === Phase 2: Stop voice ===
    print(f"\n=== Phase 2: stop_voice (started={voice_started_count}, stopped={voice_stopped_count}) ===")
    send({"type": "stop_voice"})
    # Wait long enough for stop to complete (audio cleanup may block on GIL)
    time.sleep(5)
    print(f"After stop: voice_stopped={voice_stopped_count}")

    # === Phase 3: Restart voice (the problematic case) ===
    print(f"\n=== Phase 3: start_voice again (stopped so far={voice_stopped_count}) ===")
    send({"type": "start_voice"})
    print("Waiting 45s for second greeting...")
    time.sleep(45)

    # === Phase 4: Final stop ===
    print(f"\n=== Phase 4: final stop_voice (started={voice_started_count}, stopped={voice_stopped_count}) ===")
    send({"type": "stop_voice"})
    time.sleep(5)

    # === Results ===
    print("\n" + "=" * 60)
    print(f"RESULTS:")
    print(f"  voice_started messages: {voice_started_count}")
    print(f"  voice_stopped messages: {voice_stopped_count}")
    print(f"  Expected: 2x started, 2x stopped")
    if voice_started_count == 2 and voice_stopped_count == 2:
        print("  STATUS: PASS")
    else:
        print(f"  STATUS: FAIL (got {voice_started_count} started, {voice_stopped_count} stopped)")
    print("=" * 60)

    # Cleanup
    print("\nTerminating backend...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    print("Done.")


if __name__ == "__main__":
    main()
