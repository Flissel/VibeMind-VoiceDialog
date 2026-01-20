"""
Ollama Model Client for VibeMind Swarm

Provides a configured OllamaChatCompletionClient for local LLM inference.
Uses llama3.1 (8B) by default, configurable via environment variables.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default configuration
# Using llama3.1:8b for better function calling support
# Requires ~8GB VRAM. Use qwen2.5:3b for lower RAM systems via OLLAMA_MODEL env var.
DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_HOST = "http://localhost:11434"

# Global client instance (singleton pattern)
_ollama_client: Optional["OllamaModelClient"] = None


class OllamaModelClient:
    """
    Wrapper around AutoGen's OllamaChatCompletionClient.

    Provides:
    - Lazy initialization
    - Environment-based configuration
    - Fallback to OpenAI-compatible endpoint
    - Connection health checking
    """

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
    ):
        """
        Initialize Ollama client.

        Args:
            model: Model name (default: llama3.1 or OLLAMA_MODEL env var)
            host: Ollama server URL (default: localhost:11434 or OLLAMA_HOST env var)
        """
        self.model = (model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)).strip()
        self.host = (host or os.getenv("OLLAMA_HOST", DEFAULT_HOST)).strip()
        self._client = None
        self._is_connected = False

        logger.info(f"OllamaModelClient configured: model={self.model}, host={self.host}")

    def _create_client(self):
        """Create the underlying AutoGen client."""
        try:
            from autogen_ext.models.ollama import OllamaChatCompletionClient

            self._client = OllamaChatCompletionClient(
                model=self.model,
                host=self.host,
            )
            self._is_connected = True
            logger.info(f"Connected to Ollama: {self.model} at {self.host}")
            return self._client

        except ImportError:
            logger.warning("autogen_ext.models.ollama not available, trying OpenAI-compatible endpoint")
            return self._create_openai_compatible_client()
        except Exception as e:
            logger.error(f"Failed to create Ollama client: {e}")
            return self._create_openai_compatible_client()

    def _create_openai_compatible_client(self):
        """
        Fallback: Use OpenAI-compatible endpoint.

        Ollama provides an OpenAI-compatible API at /v1/
        """
        try:
            from autogen_ext.models.openai import OpenAIChatCompletionClient
            from autogen_core.models import ModelInfo

            # Ollama's OpenAI-compatible endpoint
            base_url = f"{self.host}/v1"

            self._client = OpenAIChatCompletionClient(
                model=self.model,
                base_url=base_url,
                api_key="ollama",  # Ollama doesn't need a real key
                model_info=ModelInfo(
                    vision=False,
                    function_calling=True,
                    json_output=True,
                    family="llama",
                    structured_output=False,
                ),
            )
            self._is_connected = True
            logger.info(f"Connected to Ollama via OpenAI-compatible API: {base_url}")
            return self._client

        except Exception as e:
            logger.error(f"Failed to create OpenAI-compatible client: {e}")
            self._is_connected = False
            raise RuntimeError(f"Cannot connect to Ollama at {self.host}: {e}")

    @property
    def client(self):
        """Get the underlying AutoGen client (lazy initialization)."""
        if self._client is None:
            self._create_client()
        return self._client

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._is_connected

    async def health_check(self) -> bool:
        """
        Check if Ollama server is reachable.

        Returns:
            bool: True if server responds, False otherwise
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.host}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    logger.info(f"Ollama health check OK. Available models: {models}")
                    return True
                return False
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    async def close(self):
        """Close the client connection."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning(f"Error closing Ollama client: {e}")
            finally:
                self._client = None
                self._is_connected = False


def get_ollama_client(
    model: Optional[str] = None,
    host: Optional[str] = None,
) -> OllamaModelClient:
    """
    Get or create the global Ollama client instance.

    Args:
        model: Model name (optional, uses env var or default)
        host: Ollama server URL (optional, uses env var or default)

    Returns:
        OllamaModelClient instance
    """
    global _ollama_client

    if _ollama_client is None:
        _ollama_client = OllamaModelClient(model=model, host=host)

    return _ollama_client


def reset_ollama_client():
    """Reset the global client (for testing)."""
    global _ollama_client
    _ollama_client = None


__all__ = [
    "OllamaModelClient",
    "get_ollama_client",
    "reset_ollama_client",
    "DEFAULT_MODEL",
    "DEFAULT_HOST",
]
