"""
Cloud LLM client via OpenRouter.

OpenRouter provides unified access to Claude, GPT, and other models
with a single API key and OpenAI-compatible interface.
"""

import os
import logging
from pathlib import Path
from typing import Optional

from llm_config import get_model, get_api_key, get_base_url

# Load .env file if present
try:
    from dotenv import load_dotenv
    # Look for .env in project root
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, rely on environment

logger = logging.getLogger(__name__)

# Default model - Claude Sonnet 4 via OpenRouter
DEFAULT_MODEL = get_model("orchestrator")


class CloudModelClient:
    """Wrapper for OpenRouter LLM access."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize OpenRouter client.

        Args:
            model: OpenRouter model ID (default: anthropic/claude-sonnet-4)
            api_key: OpenRouter API key (default: from OPENROUTER_API_KEY env var)
        """
        self.model = model or get_model("orchestrator")
        self.api_key = api_key or get_api_key("orchestrator") or os.getenv("OPENROUTER_API_KEY")
        self.base_url = get_base_url("orchestrator") or "https://openrouter.ai/api/v1"
        self._client = None

        if not self.api_key:
            raise ValueError("No API key configured for orchestrator role (check llm_models.yml or OPENROUTER_API_KEY)")

        logger.info(f"CloudModelClient configured: model={self.model}")

    @property
    def client(self):
        """Lazy-load the AutoGen client."""
        if self._client is None:
            from autogen_ext.models.openai import OpenAIChatCompletionClient

            self._client = OpenAIChatCompletionClient(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                model_info={
                    "family": "claude",  # Required by AutoGen 0.4.7+
                    "vision": True,
                    "function_calling": True,
                    "json_output": True,
                    "structured_output": True,  # Future-proofing
                }
            )
            logger.info(f"Connected to OpenRouter: {self.model}")

        return self._client


# Singleton instance
_cloud_client: Optional[CloudModelClient] = None


def get_cloud_client(model: Optional[str] = None) -> CloudModelClient:
    """
    Get or create the singleton CloudModelClient.

    Args:
        model: Optional model override

    Returns:
        CloudModelClient instance
    """
    global _cloud_client

    if _cloud_client is None:
        _cloud_client = CloudModelClient(model=model)

    return _cloud_client


def get_model_client():
    """
    Get the AutoGen-compatible model client.

    Returns:
        OpenAIChatCompletionClient configured for OpenRouter
    """
    return get_cloud_client().client


__all__ = [
    "CloudModelClient",
    "get_cloud_client",
    "get_model_client",
    "DEFAULT_MODEL",
]
