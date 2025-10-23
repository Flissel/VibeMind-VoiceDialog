"""Debug scan parsing"""
from tools.moire_service import MoireTrackerService
from tools.moire_client import MoireTrackerClient

s = MoireTrackerService()
if not s.is_running():
    s.start()

c = MoireTrackerClient()
c.connect()

print("\nScanning...")
elems = c.scan_desktop()

print(f"\n[SUCCESS] Found {len(elems)} elements\n")

# Show all elements with details
for i, e in enumerate(elems):
    if e.text or e.x != 0 or e.y != 0:  # Only show non-empty elements
        # Handle Unicode characters that can't be printed
        try:
            text_display = e.text[:40].ljust(40)
            print(f"{i+1:3d}. '{text_display}' at ({e.x:6.1f}, {e.y:6.1f}) conf={e.confidence:.2f}")
        except UnicodeEncodeError:
            # Replace unprintable chars with ?
            text_safe = e.text[:40].encode('ascii', errors='replace').decode('ascii').ljust(40)
            print(f"{i+1:3d}. '{text_safe}' at ({e.x:6.1f}, {e.y:6.1f}) conf={e.confidence:.2f}")

s.stop()
