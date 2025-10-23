"""Quick scan test"""
from tools.moire_service import MoireTrackerService
from tools.moire_client import MoireTrackerClient
import traceback

s = MoireTrackerService()
s.start()

c = MoireTrackerClient()
c.connect()

print("\nScanning...")
try:
    elems = c.scan_desktop()
    print(f"\n[SUCCESS] Found {len(elems)} elements")
    if elems:
        print("\nFirst 5:")
        for e in elems[:5]:
            print(f"  - {e.text} at ({e.x:.0f}, {e.y:.0f})")
except Exception as ex:
    print(f"\n[ERROR] {ex}")
    traceback.print_exc()

s.stop()
