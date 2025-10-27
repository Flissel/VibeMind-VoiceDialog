"""
AutoGen Bridge - Connect ElevenLabs Client Tools to AutoGen Workers

This module provides functions that ElevenLabs agents can call as client tools.
These functions bridge to AutoGen gRPC workers for complex processing.

Flow:
    ElevenLabs Agent → Client Tool (this file) → gRPC Runtime → AutoGen Worker → Response

Usage in Client Tool JSON:
    {
      "type": "client",
      "name": "fetch_url_knowledge",
      "description": "Fetch and process knowledge from a URL using AutoGen worker",
      ...
    }

The function `fetch_url_knowledge()` in this file will be called by ElevenLabs,
which then sends a request to the KnowledgeWorker via gRPC.
"""

import asyncio
import logging
from typing import Optional

from autogen_core import AgentId
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime

# Import message types from knowledge worker
import sys
from pathlib import Path

# Add workers to path
workers_path = Path(__file__).parent.parent / "workers"
sys.path.insert(0, str(workers_path))

from knowledge_worker import URLRequest, URLResponse, WebSearchRequest, WebSearchResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoGenBridge:
    """
    Bridge between ElevenLabs client tools and AutoGen gRPC workers.

    This class maintains a persistent connection to the gRPC host and
    forwards requests to appropriate workers.
    """

    def __init__(self, host_address: str = "localhost:50051"):
        """
        Initialize the bridge.

        Args:
            host_address: gRPC host address
        """
        self.host_address = host_address
        self.runtime: Optional[GrpcWorkerAgentRuntime] = None
        self._initialized = False

    async def initialize(self):
        """Connect to gRPC host."""
        if self._initialized:
            return

        try:
            logger.info(f"Connecting AutoGen bridge to {self.host_address}")
            self.runtime = GrpcWorkerAgentRuntime(host_address=self.host_address)
            await self.runtime.start()
            self._initialized = True
            logger.info("✓ AutoGen bridge connected")
        except Exception as e:
            logger.error(f"Failed to connect AutoGen bridge: {e}")
            raise

    async def shutdown(self):
        """Disconnect from gRPC host."""
        if self.runtime and self._initialized:
            await self.runtime.stop()
            self._initialized = False
            logger.info("✓ AutoGen bridge disconnected")

    async def fetch_url(self, url: str, summary_length: str = "medium") -> URLResponse:
        """
        Fetch and process a URL using KnowledgeWorker.

        Args:
            url: URL to fetch
            summary_length: "brief", "medium", or "detailed"

        Returns:
            URLResponse with processed content
        """
        if not self._initialized:
            await self.initialize()

        try:
            logger.info(f"Sending URL request to KnowledgeWorker: {url}")

            # Create request
            request = URLRequest(url=url, summary_length=summary_length)

            # Send to knowledge worker
            worker_id = AgentId("knowledge_worker", "default")
            response = await self.runtime.send_message(request, worker_id)

            logger.info(f"✓ Received response from KnowledgeWorker")
            return response

        except Exception as e:
            logger.error(f"Error in fetch_url: {e}", exc_info=True)
            return URLResponse(
                url=url,
                title="Error",
                content="",
                summary="",
                word_count=0,
                success=False,
                error=f"Bridge error: {str(e)}"
            )

    async def search_web(self, query: str, max_results: int = 5) -> WebSearchResponse:
        """
        Perform web search using KnowledgeWorker.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            WebSearchResponse with results
        """
        if not self._initialized:
            await self.initialize()

        try:
            logger.info(f"Sending search request to KnowledgeWorker: {query}")

            request = WebSearchRequest(query=query, max_results=max_results)
            worker_id = AgentId("knowledge_worker", "default")
            response = await self.runtime.send_message(request, worker_id)

            return response

        except Exception as e:
            logger.error(f"Error in search_web: {e}", exc_info=True)
            return WebSearchResponse(
                query=query,
                results=[],
                success=False,
                error=f"Bridge error: {str(e)}"
            )


# Global bridge instance
_bridge_instance: Optional[AutoGenBridge] = None


def get_bridge() -> AutoGenBridge:
    """Get or create the global bridge instance."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = AutoGenBridge()
    return _bridge_instance


# === Client Tool Functions (Called by ElevenLabs) ===

def fetch_url_knowledge(url: str, summary_length: str = "medium") -> str:
    """
    Fetch and process knowledge from a URL.

    This function is called by ElevenLabs agents as a client tool.
    It connects to the AutoGen Knowledge Worker via gRPC.

    Args:
        url: URL to fetch and process
        summary_length: "brief", "medium", or "detailed"

    Returns:
        str: Human-readable summary for the agent to speak
    """
    try:
        # Get bridge and run async operation
        bridge = get_bridge()
        response = asyncio.run(bridge.fetch_url(url, summary_length))

        if response.success:
            return (
                f"I've fetched knowledge from {url}. "
                f"The page is titled '{response.title}' and contains {response.word_count} words. "
                f"Here's a {summary_length} summary: {response.summary}"
            )
        else:
            return f"I encountered an error fetching {url}: {response.error}"

    except Exception as e:
        logger.error(f"Error in fetch_url_knowledge: {e}", exc_info=True)
        return f"I encountered an error processing the URL: {str(e)}"


def search_web_knowledge(query: str, max_results: int = 5) -> str:
    """
    Search the web using AutoGen Knowledge Worker.

    This function is called by ElevenLabs agents as a client tool.

    Args:
        query: Search query
        max_results: Maximum number of results

    Returns:
        str: Human-readable search results for the agent to speak
    """
    try:
        bridge = get_bridge()
        response = asyncio.run(bridge.search_web(query, max_results))

        if response.success:
            if not response.results:
                return f"I searched for '{query}' but found no results."

            result_text = f"I found {len(response.results)} results for '{query}': "
            for i, result in enumerate(response.results[:3], 1):
                result_text += f"{i}. {result.get('title', 'Untitled')} "

            return result_text
        else:
            return f"Search failed: {response.error}"

    except Exception as e:
        logger.error(f"Error in search_web_knowledge: {e}", exc_info=True)
        return f"I encountered an error searching: {str(e)}"


# Export functions for client tools
__all__ = [
    "fetch_url_knowledge",
    "search_web_knowledge",
    "AutoGenBridge",
    "get_bridge"
]
