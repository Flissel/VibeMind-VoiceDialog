"""
Phase 1 Refactoring Regression Tests
Tests that the cross-platform IPC abstraction works correctly
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.ipc_factory import create_ipc_backend, is_windows, is_linux, is_macos, get_platform_info
from tools.moire_client import MoireTrackerClient


def test_platform_detection():
    """Test platform detection functions"""
    print("Testing platform detection...")

    info = get_platform_info()
    assert 'system' in info
    assert 'python_version' in info

    # At least one platform should be detected
    assert is_windows() or is_linux() or is_macos()

    print(f"  [OK] Platform: {info['system']}")
    print("  [OK] Platform detection working")


def test_backend_creation():
    """Test IPC backend can be created"""
    print("\nTesting backend creation...")

    backend = create_ipc_backend()
    assert backend is not None
    assert hasattr(backend, 'connect')
    assert hasattr(backend, 'disconnect')
    assert hasattr(backend, 'send_command')
    assert hasattr(backend, 'receive_response')
    assert hasattr(backend, 'is_connected')
    assert hasattr(backend, 'get_backend_name')

    backend_name = backend.get_backend_name()
    print(f"  [OK] Backend created: {backend_name}")
    print("  [OK] All required methods present")


def test_client_initialization():
    """Test MoireTrackerClient initializes with factory"""
    print("\nTesting client initialization...")

    client = MoireTrackerClient()

    # Verify client has IPC backend
    assert hasattr(client, 'ipc')
    assert client.ipc is not None

    # Verify backend is correct type
    backend_name = client.ipc.get_backend_name()
    assert backend_name in ['Windows Shared Memory', 'Unix Domain Socket']

    print(f"  [OK] Client initialized with: {backend_name}")
    print("  [OK] IPC backend properly injected")


def test_api_compatibility():
    """Test all existing client APIs still exist"""
    print("\nTesting API compatibility...")

    client = MoireTrackerClient()

    # Public APIs that must exist
    required_methods = [
        'connect', 'disconnect', 'reconnect',
        'get_mouse_position', 'scan_desktop', 'find_element',
        'set_active', 'set_standby',
        'is_healthy', 'is_authorized', 'get_health_metrics'
    ]

    for method in required_methods:
        assert hasattr(client, method), f"Missing method: {method}"
        assert callable(getattr(client, method)), f"Not callable: {method}"

    print(f"  [OK] All {len(required_methods)} required methods present")
    print("  [OK] API backward compatible")


def test_circuit_breaker_preserved():
    """Test circuit breaker features still exist"""
    print("\nTesting circuit breaker preservation...")

    client = MoireTrackerClient()

    # Circuit breaker attributes
    assert hasattr(client, 'circuit_state')
    assert hasattr(client, 'failure_count')
    assert hasattr(client, 'failure_threshold')

    # Circuit breaker methods
    assert hasattr(client, '_record_success')
    assert hasattr(client, '_record_failure')
    assert hasattr(client, '_check_circuit')

    print("  [OK] Circuit breaker state preserved")
    print("  [OK] Circuit breaker methods intact")


def test_health_monitoring_preserved():
    """Test health monitoring features still exist"""
    print("\nTesting health monitoring preservation...")

    client = MoireTrackerClient()

    # Health metrics attributes
    assert hasattr(client, 'total_requests')
    assert hasattr(client, 'failed_requests')
    assert hasattr(client, 'total_reconnects')

    # Health methods
    metrics = client.get_health_metrics()
    assert 'connected' in metrics
    assert 'circuit_state' in metrics
    assert 'total_requests' in metrics
    assert 'error_rate_percent' in metrics

    print("  [OK] Health metrics preserved")
    print("  [OK] Health monitoring intact")


def test_retry_logic_preserved():
    """Test retry configuration still exists"""
    print("\nTesting retry logic preservation...")

    client = MoireTrackerClient(max_retries=5, timeout_ms=10000)

    assert client.max_retries == 5
    assert client.timeout_ms == 10000

    print("  [OK] Retry configuration preserved")
    print("  [OK] Timeout configuration preserved")


def test_no_windows_specific_code_in_client():
    """Verify no Windows-specific code remains in client"""
    print("\nTesting platform-agnostic code...")

    import inspect
    from tools import moire_client

    source = inspect.getsource(moire_client.MoireTrackerClient)

    # These should NOT appear in the refactored client
    forbidden_patterns = [
        'mmap.mmap',
        'tagname=',
        'CMD_MEMORY_NAME',
        'RESP_MEMORY_NAME',
        'MOUSE_MEMORY_NAME'
    ]

    for pattern in forbidden_patterns:
        assert pattern not in source, f"Found Windows-specific code: {pattern}"

    print("  [OK] No Windows-specific imports")
    print("  [OK] No direct mmap usage")
    print("  [OK] No memory region names")
    print("  [OK] Client is platform-agnostic")


def main():
    """Run all regression tests"""
    print("=" * 60)
    print("Phase 1 Refactoring Regression Tests")
    print("=" * 60)

    tests = [
        test_platform_detection,
        test_backend_creation,
        test_client_initialization,
        test_api_compatibility,
        test_circuit_breaker_preserved,
        test_health_monitoring_preserved,
        test_retry_logic_preserved,
        test_no_windows_specific_code_in_client
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n  [FAIL] FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n  [ERROR] ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n[SUCCESS] ALL TESTS PASSED - Phase 1 refactoring successful!")
        return 0
    else:
        print(f"\n[FAILED] {failed} TEST(S) FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
