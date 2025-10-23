"""
Test Health Check HTTP Server
Validates all health endpoints and monitoring integration
"""

import sys
import time
import json
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from health_server import HealthServer, HealthStatus
from logger import get_logger

logger = get_logger(__name__)


def test_server_lifecycle():
    """Test server start/stop lifecycle"""
    print("\n" + "="*60)
    print("TEST 1: Server Lifecycle")
    print("="*60)

    try:
        server = HealthServer(port=8081)
        print("[OK] Server created on port 8081")

        # Start server
        server.start()
        time.sleep(0.5)  # Give server time to start

        if not server.is_running():
            print("[FAIL] Server not running after start()")
            return False

        print("[OK] Server started successfully")
        print(f"  - URL: {server.get_url()}")

        # Stop server
        server.stop()
        time.sleep(0.5)  # Give server time to stop

        if server.is_running():
            print("[FAIL] Server still running after stop()")
            return False

        print("[OK] Server stopped successfully")
        return True

    except Exception as e:
        print(f"[FAIL] Server lifecycle test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_health_endpoint():
    """Test /health endpoint"""
    print("\n" + "="*60)
    print("TEST 2: /health Endpoint")
    print("="*60)

    server = None
    try:
        # Setup health provider
        def health_provider():
            return {
                'overall_status': HealthStatus.HEALTHY,
                'version': '1.0.0-test',
                'checks': {
                    'test_component': {
                        'status': 'ok',
                        'value': 42
                    }
                }
            }

        server = HealthServer(port=8082)
        server.set_health_provider(health_provider)
        server.start()
        time.sleep(0.5)

        # Make request
        url = server.get_url('/health')
        print(f"[Testing] GET {url}")

        response = urlopen(url, timeout=5)
        data = json.loads(response.read().decode('utf-8'))

        print("[OK] /health endpoint responded")
        print(f"  - Status code: {response.status}")
        print(f"  - Status: {data.get('status')}")
        print(f"  - Version: {data.get('version')}")
        print(f"  - Uptime: {data.get('uptime_seconds')}s")
        print(f"  - Checks: {len(data.get('checks', {}))} components")

        # Validate response
        if data.get('status') != HealthStatus.HEALTHY:
            print(f"[FAIL] Expected status 'healthy', got '{data.get('status')}'")
            return False

        if 'timestamp' not in data:
            print("[FAIL] Missing timestamp in response")
            return False

        if 'uptime_seconds' not in data:
            print("[FAIL] Missing uptime_seconds in response")
            return False

        print("[OK] Response structure valid")
        return True

    except Exception as e:
        print(f"[FAIL] /health endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if server:
            server.stop()


def test_ready_endpoint():
    """Test /health/ready endpoint"""
    print("\n" + "="*60)
    print("TEST 3: /health/ready Endpoint")
    print("="*60)

    server = None
    try:
        # Test READY state
        def ready_provider():
            return {
                'overall_status': HealthStatus.HEALTHY,
                'checks': {
                    'moire_tracker': {'connected': True},
                    'moire_client': {
                        'connected': True,
                        'circuit_state': 'closed'
                    }
                }
            }

        server = HealthServer(port=8083)
        server.set_health_provider(ready_provider)
        server.start()
        time.sleep(0.5)

        # Test ready state
        url = server.get_url('/health/ready')
        print(f"[Testing] GET {url} (should be ready)")

        response = urlopen(url, timeout=5)
        data = json.loads(response.read().decode('utf-8'))

        print("[OK] /health/ready endpoint responded")
        print(f"  - Status code: {response.status}")
        print(f"  - Ready: {data.get('ready')}")
        print(f"  - Checks: {data.get('checks')}")

        if not data.get('ready'):
            print("[FAIL] Service should be ready")
            return False

        if response.status != 200:
            print(f"[FAIL] Expected status 200, got {response.status}")
            return False

        print("[OK] Readiness check passed (ready=True)")

        # Test NOT READY state
        def not_ready_provider():
            return {
                'overall_status': HealthStatus.DEGRADED,
                'checks': {
                    'moire_tracker': {'connected': False},
                    'moire_client': {
                        'connected': False,
                        'circuit_state': 'open'
                    }
                }
            }

        server.set_health_provider(not_ready_provider)
        time.sleep(0.1)

        print(f"\n[Testing] GET {url} (should NOT be ready)")

        try:
            response = urlopen(url, timeout=5)
            data = json.loads(response.read().decode('utf-8'))
            print(f"[FAIL] Expected 503 status, got {response.status}")
            return False
        except HTTPError as e:
            if e.code == 503:
                data = json.loads(e.read().decode('utf-8'))
                print(f"[OK] Correctly returned 503 (service not ready)")
                print(f"  - Ready: {data.get('ready')}")
                if data.get('ready'):
                    print("[FAIL] Ready should be False")
                    return False
            else:
                print(f"[FAIL] Expected 503, got {e.code}")
                return False

        return True

    except Exception as e:
        print(f"[FAIL] /health/ready endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if server:
            server.stop()


def test_live_endpoint():
    """Test /health/live endpoint"""
    print("\n" + "="*60)
    print("TEST 4: /health/live Endpoint")
    print("="*60)

    server = None
    try:
        server = HealthServer(port=8084)
        server.start()
        time.sleep(0.5)

        url = server.get_url('/health/live')
        print(f"[Testing] GET {url}")

        response = urlopen(url, timeout=5)
        data = json.loads(response.read().decode('utf-8'))

        print("[OK] /health/live endpoint responded")
        print(f"  - Status code: {response.status}")
        print(f"  - Alive: {data.get('alive')}")
        print(f"  - Uptime: {data.get('uptime_seconds')}s")

        # Liveness should always return 200 if process is running
        if response.status != 200:
            print(f"[FAIL] Expected status 200, got {response.status}")
            return False

        if not data.get('alive'):
            print("[FAIL] Service should be alive")
            return False

        print("[OK] Liveness check passed (alive=True)")
        return True

    except Exception as e:
        print(f"[FAIL] /health/live endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if server:
            server.stop()


def test_metrics_endpoint():
    """Test /metrics endpoint"""
    print("\n" + "="*60)
    print("TEST 5: /metrics Endpoint")
    print("="*60)

    server = None
    try:
        def metrics_provider():
            return {
                'overall_status': HealthStatus.HEALTHY,
                'version': '1.0.0-test',
                'metrics': {
                    'total_requests': 1000,
                    'failed_requests': 10,
                    'error_rate_percent': 1.0,
                    'avg_response_time_ms': 25.5
                }
            }

        server = HealthServer(port=8085)
        server.set_health_provider(metrics_provider)
        server.start()
        time.sleep(0.5)

        url = server.get_url('/metrics')
        print(f"[Testing] GET {url}")

        response = urlopen(url, timeout=5)
        data = json.loads(response.read().decode('utf-8'))

        print("[OK] /metrics endpoint responded")
        print(f"  - Status code: {response.status}")
        print(f"  - Metrics available: {len(data.get('metrics', {}))}")

        metrics = data.get('metrics', {})
        print("\n[Metrics Data]")
        for key, value in metrics.items():
            print(f"  - {key}: {value}")

        # Validate metrics structure
        if 'timestamp' not in data:
            print("[FAIL] Missing timestamp in response")
            return False

        if 'metrics' not in data:
            print("[FAIL] Missing metrics in response")
            return False

        print("\n[OK] Metrics structure valid")
        return True

    except Exception as e:
        print(f"[FAIL] /metrics endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if server:
            server.stop()


def test_404_handling():
    """Test 404 for unknown endpoints"""
    print("\n" + "="*60)
    print("TEST 6: 404 Handling")
    print("="*60)

    server = None
    try:
        server = HealthServer(port=8086)
        server.start()
        time.sleep(0.5)

        url = "http://127.0.0.1:8086/unknown-endpoint"
        print(f"[Testing] GET {url}")

        try:
            response = urlopen(url, timeout=5)
            print(f"[FAIL] Expected 404, got {response.status}")
            return False
        except HTTPError as e:
            if e.code == 404:
                data = json.loads(e.read().decode('utf-8'))
                print("[OK] Correctly returned 404")
                print(f"  - Error: {data.get('error')}")
                print(f"  - Available endpoints: {len(data.get('available_endpoints', []))}")

                if 'available_endpoints' not in data:
                    print("[FAIL] Missing available_endpoints in 404 response")
                    return False

                print("[OK] 404 response structure valid")
                return True
            else:
                print(f"[FAIL] Expected 404, got {e.code}")
                return False

    except Exception as e:
        print(f"[FAIL] 404 handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if server:
            server.stop()


def main():
    """Run all health server tests"""
    print("\n" + "="*80)
    print(" "*20 + "HEALTH SERVER TESTS")
    print("="*80)

    results = {
        'Server Lifecycle': test_server_lifecycle(),
        '/health Endpoint': test_health_endpoint(),
        '/health/ready Endpoint': test_ready_endpoint(),
        '/health/live Endpoint': test_live_endpoint(),
        '/metrics Endpoint': test_metrics_endpoint(),
        '404 Handling': test_404_handling()
    }

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "[OK] PASS" if passed_test else "[FAIL] FAIL"
        print(f"  {test_name:25s} {status}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n[OK] All health server tests passed!")
        print("\nEndpoints validated:")
        print("  - GET /health       - Overall health status")
        print("  - GET /health/ready - Readiness for traffic")
        print("  - GET /health/live  - Process liveness")
        print("  - GET /metrics      - Detailed metrics")
        print("  - 404 handling      - Unknown endpoints")
        return 0
    else:
        print("\n[FAIL] Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
