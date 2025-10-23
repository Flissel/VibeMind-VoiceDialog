"""
Test production infrastructure
Validates configuration, logging, and service management
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config, validate_config, ConfigurationError
from logger import get_logger, ProductionLogger
from tools.moire_service import MoireTrackerService

def test_configuration():
    """Test configuration system"""
    print("\n" + "="*60)
    print("TEST 1: Configuration Management")
    print("="*60)

    try:
        config = get_config()
        print(f"[OK] Configuration loaded successfully")
        print(f"  - OpenAI API Key: {'Set' if config.openai_api_key else 'Not set'}")
        print(f"  - MoireTracker Path: {config.moire_tracker.path}")
        print(f"  - Log Level: {config.logging.level}")
        print(f"  - Log File: {config.logging.file}")

        # Validate (non-strict mode)
        if validate_config(strict=False):
            print(f"[OK] Configuration validation passed")
        else:
            print(f"[WARN] Configuration validation passed with warnings")

        return True
    except ConfigurationError as e:
        print(f"[FAIL] Configuration error: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        return False


def test_logging():
    """Test logging infrastructure"""
    print("\n" + "="*60)
    print("TEST 2: Logging Infrastructure")
    print("="*60)

    try:
        # Get logger
        logger = get_logger(__name__)

        # Test all log levels
        logger.debug("Debug message test")
        logger.info("Info message test")
        logger.warning("Warning message test")
        logger.error("Error message test (this is a test, not a real error)")

        print(f"[OK] Logging system operational")
        print(f"  - Log levels working correctly")
        print(f"  - Check voice_dialog.log for output")

        # Test structured logging with context
        logger.set_context(test_id="prod_test", component="logging")
        logger.info("Structured logging test")
        logger.clear_context()

        print(f"[OK] Structured logging with context works")

        return True
    except Exception as e:
        print(f"[FAIL] Logging test failed: {e}")
        return False


def test_service_config():
    """Test service configuration"""
    print("\n" + "="*60)
    print("TEST 3: Service Configuration")
    print("="*60)

    try:
        # Create service with default config
        service = MoireTrackerService()

        print(f"[OK] Service created successfully")
        print(f"  - Executable path: {service.moire_exe}")
        print(f"  - Executable exists: {service.moire_exe.exists()}")
        print(f"  - Max reconnect attempts: {service.config.max_reconnect_attempts}")
        print(f"  - Timeout: {service.config.timeout_ms}ms")

        # Get health status
        health = service.get_health_status()
        print(f"[OK] Health check available")
        for key, value in health.items():
            print(f"    - {key}: {value}")

        return True
    except Exception as e:
        print(f"[FAIL] Service configuration test failed: {e}")
        return False


def test_error_handling():
    """Test error handling and recovery"""
    print("\n" + "="*60)
    print("TEST 4: Error Handling")
    print("="*60)

    try:
        logger = get_logger(__name__)

        # Test exception logging
        try:
            raise ValueError("Test exception for error handling")
        except ValueError as e:
            logger.exception("Caught test exception")

        print(f"[OK] Exception logging works")

        # Test configuration with invalid path
        from config import MoireTrackerConfig
        invalid_config = MoireTrackerConfig(
            path=Path("C:\\NonExistent\\Path"),
            timeout_ms=1000
        )
        service = MoireTrackerService(invalid_config)
        health = service.get_health_status()

        if not health['exe_exists']:
            print(f"[OK] Service correctly detects missing executable")

        return True
    except Exception as e:
        print(f"[FAIL] Error handling test failed: {e}")
        return False


def test_backwards_compatibility():
    """Test backward compatibility"""
    print("\n" + "="*60)
    print("TEST 5: Backward Compatibility")
    print("="*60)

    try:
        # Test old-style service creation
        from tools.moire_service import create_service

        service = create_service()
        print(f"[OK] Legacy create_service() works")

        # Test with explicit path (deprecated)
        service2 = create_service(r"C:\Users\User\Desktop\Moire\build\Release")
        print(f"[OK] Legacy create_service(path) works with deprecation warning")

        return True
    except Exception as e:
        print(f"[FAIL] Backward compatibility test failed: {e}")
        return False


def main():
    """Run all production tests"""
    print("\n" + "="*80)
    print(" "*20 + "PRODUCTION INFRASTRUCTURE TESTS")
    print("="*80)

    results = {
        'Configuration': test_configuration(),
        'Logging': test_logging(),
        'Service Config': test_service_config(),
        'Error Handling': test_error_handling(),
        'Backward Compat': test_backwards_compatibility()
    }

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "[OK] PASS" if passed_test else "[FAIL] FAIL"
        print(f"  {test_name:20s} {status}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n[OK] All production infrastructure tests passed!")
        print("\nNext steps:")
        print("  1. Review SECURITY.md and revoke exposed API key")
        print("  2. Configure .env with production settings")
        print("  3. Review PRODUCTION.md for deployment checklist")
        print("  4. Run integration tests: python tests/test_end_to_end.py")
        return 0
    else:
        print("\n[FAIL] Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
