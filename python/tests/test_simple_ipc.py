"""
Simple IPC test - just test mouse position
"""

import time
from tools.moire_client import MoireTrackerClient

print("Starting MoireTracker manually...")
print("Please run: C:\\Users\\User\\Desktop\\Moire\\build\\Release\\MoireTracker.exe")
print("Press Enter when MoireTracker is running...")
input()

print("\nConnecting to MoireTracker...")
client = MoireTrackerClient()
if not client.connect():
    print("[FAIL] Could not connect")
    exit(1)

print("[OK] Connected!")

print("\nTesting GET_MOUSE_POS command...")
time.sleep(1)  # Give server time to start command processing

pos = client.get_mouse_position()
if pos:
    print(f"[OK] Got mouse position: ({pos.x}, {pos.y})")
    print(f"  Confidence: {pos.confidence}")
    print(f"  Timestamp: {pos.timestamp_ms}")
else:
    print("[FAIL] No response received")
    print("  Check if MoireTracker command processing thread is running")

client.disconnect()
print("\nTest complete")
