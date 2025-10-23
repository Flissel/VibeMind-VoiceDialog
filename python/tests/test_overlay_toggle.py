"""Test overlay toggle persistence"""
from tools.moire_service import MoireTrackerService
from tools.moire_client import MoireTrackerClient
import time

s = MoireTrackerService()
s.start()

c = MoireTrackerClient()
c.connect()

print("\n=== Testing Overlay Toggle ===\n")

print("1. Setting ACTIVE (overlay should appear and stay visible)...")
if c.set_active():
    print("   [OK] SET_ACTIVE command succeeded")
else:
    print("   [FAIL] SET_ACTIVE command failed")

print("\n   >>> Check your screen - moiré overlay should be VISIBLE <<<")
print("   >>> Waiting 3 seconds... <<<\n")
time.sleep(3)

print("2. Setting STANDBY (overlay should disappear)...")
if c.set_standby():
    print("   [OK] SET_STANDBY command succeeded")
else:
    print("   [FAIL] SET_STANDBY command failed")

print("\n   >>> Check your screen - moiré overlay should be HIDDEN <<<")
print("   >>> Waiting 2 seconds... <<<\n")
time.sleep(2)

print("3. Setting ACTIVE again...")
if c.set_active():
    print("   [OK] SET_ACTIVE command succeeded")
else:
    print("   [FAIL] SET_ACTIVE command failed")

print("\n   >>> Check your screen - moiré overlay should be VISIBLE again <<<")
print("   >>> Waiting 3 seconds... <<<\n")
time.sleep(3)

print("4. Setting STANDBY to clean up...")
c.set_standby()

print("\n=== Test Complete ===")
print("If the overlay appeared and stayed visible during steps 1 and 3,")
print("and disappeared during steps 2 and 4, the fix is working!")

c.disconnect()
s.stop()
