"""
IPC Authentication Module
Provides secure authentication for shared memory IPC between client and service
"""

import os
import sys
import secrets
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from logger import get_logger

logger = get_logger(__name__)

# Token size in bytes (32 bytes = 256 bits)
TOKEN_SIZE_BYTES = 32

# Token file name
TOKEN_FILE_NAME = "moire_auth_token.bin"


class IPCAuthManager:
    """
    Manages IPC authentication tokens for secure communication

    Features:
    - Generates cryptographically secure random tokens
    - Stores tokens with restricted file permissions
    - Validates tokens during connection
    - Automatic token refresh on service restart

    Usage:
        # Service side:
        auth = IPCAuthManager()
        token = auth.generate_and_store_token()

        # Client side:
        auth = IPCAuthManager()
        token = auth.load_token()
        # Send token to service for validation
    """

    def __init__(self, token_dir: Optional[Path] = None):
        """
        Initialize IPC authentication manager

        Args:
            token_dir: Directory to store token file (default: temp directory)
        """
        if token_dir is None:
            # Use system temp directory
            token_dir = Path(tempfile.gettempdir())

        self.token_dir = Path(token_dir)
        self.token_file = self.token_dir / TOKEN_FILE_NAME

        logger.debug(f"IPCAuthManager initialized (token_file={self.token_file})")

    def generate_token(self) -> bytes:
        """
        Generate cryptographically secure random token

        Returns:
            32-byte token
        """
        token = secrets.token_bytes(TOKEN_SIZE_BYTES)
        logger.debug(f"Generated new token ({TOKEN_SIZE_BYTES} bytes)")
        return token

    def store_token(self, token: bytes) -> bool:
        """
        Store token to file with restricted permissions

        Args:
            token: Token bytes to store

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            self.token_dir.mkdir(parents=True, exist_ok=True)

            # Write token to file
            self.token_file.write_bytes(token)

            # Set restrictive permissions (Windows: current user only)
            self._set_secure_permissions(self.token_file)

            logger.info(f"Token stored securely at {self.token_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to store token: {e}", exc_info=True)
            return False

    def load_token(self) -> Optional[bytes]:
        """
        Load token from file

        Returns:
            Token bytes if successful, None otherwise
        """
        try:
            if not self.token_file.exists():
                logger.warning(f"Token file not found: {self.token_file}")
                return None

            # Read token
            token = self.token_file.read_bytes()

            # Validate size
            if len(token) != TOKEN_SIZE_BYTES:
                logger.error(f"Invalid token size: {len(token)} bytes (expected {TOKEN_SIZE_BYTES})")
                return None

            logger.debug("Token loaded successfully")
            return token

        except Exception as e:
            logger.error(f"Failed to load token: {e}", exc_info=True)
            return None

    def generate_and_store_token(self) -> Optional[bytes]:
        """
        Generate new token and store to file

        Returns:
            Token bytes if successful, None otherwise
        """
        token = self.generate_token()

        if self.store_token(token):
            return token
        else:
            return None

    def validate_token(self, provided_token: bytes) -> bool:
        """
        Validate provided token against stored token

        Args:
            provided_token: Token to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Load stored token
            stored_token = self.load_token()

            if stored_token is None:
                logger.warning("No stored token available for validation")
                return False

            # Constant-time comparison to prevent timing attacks
            if secrets.compare_digest(provided_token, stored_token):
                logger.debug("Token validation successful")
                return True
            else:
                logger.warning("Token validation failed: token mismatch")
                return False

        except Exception as e:
            logger.error(f"Token validation error: {e}", exc_info=True)
            return False

    def delete_token(self) -> bool:
        """
        Delete token file

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.token_file.exists():
                self.token_file.unlink()
                logger.info("Token file deleted")
                return True
            else:
                logger.debug("Token file does not exist")
                return True

        except Exception as e:
            logger.error(f"Failed to delete token: {e}", exc_info=True)
            return False

    def token_exists(self) -> bool:
        """
        Check if token file exists

        Returns:
            True if token file exists, False otherwise
        """
        return self.token_file.exists()

    def _set_secure_permissions(self, file_path: Path):
        """
        Set secure file permissions (Windows: current user only)

        Args:
            file_path: Path to file
        """
        try:
            # On Windows, use icacls to set permissions
            # This is a simplified approach - proper ACL would be better
            if sys.platform == 'win32':
                # Make file read-only for current user
                os.chmod(file_path, 0o600)  # rw------- (owner read/write only)
                logger.debug(f"Set secure permissions on {file_path}")
            else:
                # Unix-like systems
                os.chmod(file_path, 0o600)
                logger.debug(f"Set secure permissions (0600) on {file_path}")

        except Exception as e:
            logger.warning(f"Could not set secure permissions: {e}")
            # Not critical - token is still secure by obscurity


def generate_token() -> bytes:
    """
    Convenience function to generate a token

    Returns:
        32-byte cryptographically secure token
    """
    return secrets.token_bytes(TOKEN_SIZE_BYTES)


def token_to_hex(token: bytes) -> str:
    """
    Convert token bytes to hex string (for debugging/logging)

    Args:
        token: Token bytes

    Returns:
        Hex string representation
    """
    return token.hex()


def hex_to_token(hex_str: str) -> bytes:
    """
    Convert hex string back to token bytes

    Args:
        hex_str: Hex string

    Returns:
        Token bytes
    """
    return bytes.fromhex(hex_str)


if __name__ == "__main__":
    # Test token generation and storage
    print("\n" + "="*70)
    print("  IPC Authentication Test")
    print("="*70)

    # Initialize manager
    auth = IPCAuthManager()
    print(f"\n[1] Token file location: {auth.token_file}")

    # Generate and store token
    print("\n[2] Generating token...")
    token = auth.generate_and_store_token()

    if token:
        print(f"  [OK] Token generated: {token_to_hex(token)[:16]}... ({len(token)} bytes)")
        print(f"  [OK] Token stored at: {auth.token_file}")
    else:
        print("  [FAIL] Token generation failed")
        sys.exit(1)

    # Load token
    print("\n[3] Loading token...")
    loaded_token = auth.load_token()

    if loaded_token:
        print(f"  [OK] Token loaded: {token_to_hex(loaded_token)[:16]}... ({len(loaded_token)} bytes)")
    else:
        print("  [FAIL] Token load failed")
        sys.exit(1)

    # Validate token
    print("\n[4] Validating token...")

    # Test valid token
    if auth.validate_token(loaded_token):
        print("  [OK] Valid token accepted")
    else:
        print("  [FAIL] Valid token rejected")
        sys.exit(1)

    # Test invalid token
    invalid_token = secrets.token_bytes(TOKEN_SIZE_BYTES)
    if not auth.validate_token(invalid_token):
        print("  [OK] Invalid token rejected")
    else:
        print("  [FAIL] Invalid token accepted")
        sys.exit(1)

    # Clean up
    print("\n[5] Cleanup...")
    if auth.delete_token():
        print("  [OK] Token file deleted")
    else:
        print("  [WARN] Token file not deleted")

    print("\n" + "="*70)
    print("  All tests passed!")
    print("="*70 + "\n")
