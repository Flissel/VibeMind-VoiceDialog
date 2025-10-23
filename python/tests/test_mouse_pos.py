"""Test GET_MOUSE_POS with running MoireTracker"""
from tools.moire_client import MoireTrackerClient
import time

print("Connecting to MoireTracker...")
client = MoireTrackerClient()

if not client.connect():
    print("[FAIL] Connection failed")
    exit(1)

print("[OK] Connected!")
time.sleep(1)

print("\nTesting GET_MOUSE_POS...")
pos = client.get_mouse_position()

if pos:
    print(f"\n[SUCCESS] Mouse position received!")
    print(f"  Position: ({pos.x:.2f}, {pos.y:.2f})")
    print(f"  Confidence: {pos.confidence:.4f}")
    print(f"  Timestamp: {pos.timestamp_ms}")
else:
    print("\n[FAIL] No response")

client.disconnect()
print("\nDone")
