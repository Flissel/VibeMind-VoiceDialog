"""
Quick test of integrated health endpoints
Auto-exits after demonstrating functionality
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / 'python'))

from health_server import HealthServer
from integrated_health import IntegratedHealthProvider
from tools.moire_service import MoireTrackerService
from tools.moire_client import MoireTrackerClient


def main():
    print("\n" + "="*70)
    print("  HEALTH ENDPOINTS - INTEGRATION TEST")
    print("="*70)

    # Setup components
    print("\n[1] Initializing components...")
    service = MoireTrackerService()
    client = MoireTrackerClient()

    # Check if running
    if not service.is_running():
        print("  [INFO] MoireTracker not running, starting...")
        if not service.start():
            print("  [WARN] Could not start (will show unhealthy state)")
    else:
        print("  [OK] MoireTracker already running")

    # Connect client
    print("\n[2] Connecting client...")
    if client.connect():
        print("  [OK] Client connected")
    else:
        print("  [WARN] Client not connected (will show unhealthy state)")

    # Create health provider
    print("\n[3] Creating integrated health provider...")
    health_provider = IntegratedHealthProvider(service, client, "1.0.0-test")
    health = health_provider.get_health()

    print(f"  [OK] Health provider created")
    print(f"    - Overall status: {health['overall_status']}")
    print(f"    - Components: {len(health['checks'])}")
    print(f"    - Metrics: {len(health['metrics'])}")

    # Start health server
    print("\n[4] Starting health server on port 8090...")
    health_server = HealthServer(port=8090)
    health_server.set_health_provider(health_provider.get_health)
    health_server.start()
    time.sleep(1)  # Give server time to start

    print("  [OK] Health server started")

    # Test endpoints
    print("\n[5] Testing endpoints...")

    import urllib.request
    import json

    endpoints_tested = 0
    endpoints_passed = 0

    test_cases = [
        ("/health", "Health check"),
        ("/health/ready", "Readiness check"),
        ("/health/live", "Liveness check"),
        ("/metrics", "Metrics")
    ]

    for path, name in test_cases:
        endpoints_tested += 1
        try:
            url = health_server.get_url(path)
            response = urllib.request.urlopen(url, timeout=5)
            data = json.loads(response.read().decode('utf-8'))
            print(f"  [OK] {name:20s} - Status {response.status}")
            endpoints_passed += 1
        except urllib.error.HTTPError as e:
            # 503 is expected for ready check if not ready
            if path == "/health/ready" and e.code == 503:
                print(f"  [OK] {name:20s} - Status 503 (not ready)")
                endpoints_passed += 1
            else:
                print(f"  [FAIL] {name:20s} - HTTP {e.code}")
        except Exception as e:
            print(f"  [FAIL] {name:20s} - {e}")

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"  Endpoints tested: {endpoints_tested}")
    print(f"  Endpoints passed: {endpoints_passed}/{endpoints_tested}")

    if endpoints_passed == endpoints_tested:
        print("\n  [OK] All health endpoints operational!")
    else:
        print("\n  [WARN] Some endpoints failed")

    # Show URLs
    print("\n[Available Endpoints]")
    for path, name in test_cases:
        print(f"  - {health_server.get_url(path)}")

    # Cleanup
    print("\n[6] Cleanup...")
    health_server.stop()
    client.disconnect()
    print("  [OK] Shutdown complete")

    print("\n" + "="*70)
    print("  Integration test complete!")
    print("="*70 + "\n")

    return 0 if endpoints_passed == endpoints_tested else 1


if __name__ == "__main__":
    sys.exit(main())
