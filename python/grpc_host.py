"""
AutoGen gRPC Host Service

This service acts as a central coordinator for AutoGen worker agents.
It enables distributed execution of complex tasks triggered by ElevenLabs agents.

Architecture:
    ElevenLabs Agent (voice) → Client Tool → AutoGen Bridge → gRPC Host → Workers

Workers connect to this host and register their capabilities.
Client tools send RPC requests through the host to appropriate workers.

Usage:
    python grpc_host.py
    # Starts host on localhost:50051
    # Press Ctrl+C to stop
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntimeHost

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('grpc_host.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class AutoGenGrpcHost:
    """
    Manages the gRPC host service for AutoGen distributed workers.

    The host provides:
    - Agent registration and discovery
    - Message routing between workers
    - Pub/sub topic management
    - Connection management
    """

    def __init__(self, address: str = "localhost:50051"):
        """
        Initialize the gRPC host.

        Args:
            address: Network address to bind (default: "localhost:50051")
        """
        self.address = address
        self.host: Optional[GrpcWorkerAgentRuntimeHost] = None
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the gRPC host service."""
        try:
            logger.info(f"Starting AutoGen gRPC host on {self.address}")

            self.host = GrpcWorkerAgentRuntimeHost(address=self.address)
            self.host.start()

            logger.info(f"✓ gRPC host successfully started on {self.address}")
            logger.info("Waiting for worker connections...")
            logger.info("Press Ctrl+C to stop")

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except Exception as e:
            logger.error(f"Failed to start gRPC host: {e}", exc_info=True)
            raise

    async def stop(self):
        """Stop the gRPC host service."""
        if self.host:
            logger.info("Stopping gRPC host...")
            try:
                await self.host.stop()
                logger.info("✓ gRPC host stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping gRPC host: {e}", exc_info=True)

    def signal_shutdown(self):
        """Signal the host to shutdown."""
        logger.info("Shutdown signal received")
        self._shutdown_event.set()


# Global host instance
_host_instance: Optional[AutoGenGrpcHost] = None


def handle_signal(signum, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM)."""
    if _host_instance:
        _host_instance.signal_shutdown()


async def main():
    """Main entry point for the gRPC host service."""
    global _host_instance

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Create and start host
    _host_instance = AutoGenGrpcHost(address="localhost:50051")

    try:
        await _host_instance.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Host error: {e}", exc_info=True)
    finally:
        await _host_instance.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
