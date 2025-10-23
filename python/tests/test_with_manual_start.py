"""
Test IPC with manually started MoireTracker
This lets us see MoireTracker's console output for debugging
"""

import time
from tools.moire_client import MoireTrackerClient

print("=" * 60)
print("MANUAL START TEST")
print("=" * 60)
print()
print("STEP 1: Start MoireTracker manually in another terminal:")
print("  cd C:\\Users\\User\\Desktop\\Moire\\build\\Release")
print("  MoireTracker.exe")
print()
print("STEP 2: Wait for desktop scan to complete (~5 seconds)")
print()
print("STEP 3: Press Enter here to connect...")
input()

print("\nConnecting to MoireTracker...")
client = MoireTrackerClient()
if not client.connect():
    print("[FAIL] Connection failed")
    exit(1)

print("[OK] Connected!")

print("\nSending GET_MOUSE_POS command...")
time.sleep(0.5)  # Small delay

pos = client.get_mouse_position()
if pos:
    print(f"\n[SUCCESS] Mouse position received!")
    print(f"  Position: ({pos.x}, {pos.y})")
    print(f"  Confidence: {pos.confidence}")
    print(f"  Timestamp: {pos.timestamp_ms}")
else:
    print("\n[FAIL] No response")

print("\nCleaning up...")
client.disconnect()
print("Done. You can close MoireTracker now.")
