"""
IPC Authentication Tests
Tests for token-based IPC authentication system
"""

import sys
import os
import tempfile
import secrets
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ipc_auth import IPCAuthManager, TOKEN_SIZE_BYTES, generate_token


def test_token_generation():
    """Test cryptographically secure token generation"""
    print("\n[Test 1] Token Generation")

    # Generate token
    token = generate_token()

    # Verify size
    assert len(token) == TOKEN_SIZE_BYTES, f"Expected {TOKEN_SIZE_BYTES} bytes, got {len(token)}"

    # Verify randomness (two tokens should not be the same)
    token2 = generate_token()
    assert token != token2, "Two random tokens should not match"

    print("  [OK] Token generation works correctly")
    return True


def test_token_storage_and_loading():
    """Test token storage and loading"""
    print("\n[Test 2] Token Storage and Loading")

    # Use temp directory
    temp_dir = Path(tempfile.gettempdir()) / "test_ipc_auth"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Create manager
        auth = IPCAuthManager(token_dir=temp_dir)

        # Generate and store token
        original_token = auth.generate_and_store_token()
        assert original_token is not None, "Token generation failed"
        assert len(original_token) == TOKEN_SIZE_BYTES, "Invalid token size"

        # Load token
        loaded_token = auth.load_token()
        assert loaded_token is not None, "Token loading failed"
        assert loaded_token == original_token, "Loaded token doesn't match original"

        print("  [OK] Token storage and loading works correctly")
        return True

    finally:
        # Cleanup
        if auth.token_file.exists():
            auth.token_file.unlink()
        if temp_dir.exists():
            try:
                temp_dir.rmdir()
            except:
                pass


def test_token_validation():
    """Test token validation (constant-time comparison)"""
    print("\n[Test 3] Token Validation")

    # Use temp directory
    temp_dir = Path(tempfile.gettempdir()) / "test_ipc_auth"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Create manager and generate token
        auth = IPCAuthManager(token_dir=temp_dir)
        original_token = auth.generate_and_store_token()
        assert original_token is not None, "Token generation failed"

        # Test valid token
        is_valid = auth.validate_token(original_token)
        assert is_valid == True, "Valid token was rejected"

        # Test invalid token
        invalid_token = secrets.token_bytes(TOKEN_SIZE_BYTES)
        is_valid = auth.validate_token(invalid_token)
        assert is_valid == False, "Invalid token was accepted"

        # Test wrong size token
        wrong_size_token = secrets.token_bytes(16)  # Half size
        is_valid = auth.validate_token(wrong_size_token)
        assert is_valid == False, "Wrong size token was accepted"

        print("  [OK] Token validation works correctly")
        return True

    finally:
        # Cleanup
        if auth.token_file.exists():
            auth.token_file.unlink()
        if temp_dir.exists():
            try:
                temp_dir.rmdir()
            except:
                pass


def test_token_deletion():
    """Test token deletion"""
    print("\n[Test 4] Token Deletion")

    # Use temp directory
    temp_dir = Path(tempfile.gettempdir()) / "test_ipc_auth"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Create manager and generate token
        auth = IPCAuthManager(token_dir=temp_dir)
        token = auth.generate_and_store_token()
        assert token is not None, "Token generation failed"

        # Verify token file exists
        assert auth.token_file.exists(), "Token file not created"

        # Delete token
        success = auth.delete_token()
        assert success == True, "Token deletion failed"

        # Verify token file deleted
        assert not auth.token_file.exists(), "Token file still exists after deletion"

        # Try to load deleted token
        loaded_token = auth.load_token()
        assert loaded_token is None, "Deleted token can still be loaded"

        print("  [OK] Token deletion works correctly")
        return True

    finally:
        # Cleanup
        if auth.token_file.exists():
            auth.token_file.unlink()
        if temp_dir.exists():
            try:
                temp_dir.rmdir()
            except:
                pass


def test_service_client_integration():
    """Test service-client integration with auth"""
    print("\n[Test 5] Service-Client Integration")

    # Use temp directory
    temp_dir = Path(tempfile.gettempdir()) / "test_ipc_auth"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Service side: generate and store token
        service_auth = IPCAuthManager(token_dir=temp_dir)
        service_token = service_auth.generate_and_store_token()
        assert service_token is not None, "Service token generation failed"

        # Client side: load token
        client_auth = IPCAuthManager(token_dir=temp_dir)
        client_token = client_auth.load_token()
        assert client_token is not None, "Client token loading failed"

        # Verify tokens match
        assert client_token == service_token, "Client and service tokens don't match"

        # Service validates client token
        is_valid = service_auth.validate_token(client_token)
        assert is_valid == True, "Service rejected valid client token"

        print("  [OK] Service-client integration works correctly")
        return True

    finally:
        # Cleanup
        if service_auth.token_file.exists():
            service_auth.token_file.unlink()
        if temp_dir.exists():
            try:
                temp_dir.rmdir()
            except:
                pass


def test_unauthorized_client():
    """Test unauthorized client (no token)"""
    print("\n[Test 6] Unauthorized Client Detection")

    # Use temp directory
    temp_dir = Path(tempfile.gettempdir()) / "test_ipc_auth"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Service side: generate token (but don't share)
        service_auth = IPCAuthManager(token_dir=temp_dir)
        service_token = service_auth.generate_and_store_token()
        assert service_token is not None, "Service token generation failed"

        # Unauthorized client: tries to use random token
        unauthorized_token = secrets.token_bytes(TOKEN_SIZE_BYTES)

        # Service should reject unauthorized token
        is_valid = service_auth.validate_token(unauthorized_token)
        assert is_valid == False, "Service accepted unauthorized token"

        print("  [OK] Unauthorized clients are properly rejected")
        return True

    finally:
        # Cleanup
        if service_auth.token_file.exists():
            service_auth.token_file.unlink()
        if temp_dir.exists():
            try:
                temp_dir.rmdir()
            except:
                pass


def main():
    """Run all IPC authentication tests"""
    print("\n" + "="*70)
    print("  IPC AUTHENTICATION TESTS")
    print("="*70)

    tests = [
        ("Token Generation", test_token_generation),
        ("Token Storage/Loading", test_token_storage_and_loading),
        ("Token Validation", test_token_validation),
        ("Token Deletion", test_token_deletion),
        ("Service-Client Integration", test_service_client_integration),
        ("Unauthorized Client Detection", test_unauthorized_client)
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"  [FAIL] {test_name}")
                failed += 1
        except Exception as e:
            print(f"  [FAIL] {test_name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"  Total tests: {len(tests)}")
    print(f"  Passed: {passed}/{len(tests)}")
    print(f"  Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n  [OK] All IPC authentication tests passed!")
        print("="*70 + "\n")
        return 0
    else:
        print(f"\n  [FAIL] {failed} test(s) failed")
        print("="*70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
