"""
Knowledge Worker - AutoGen gRPC Agent

This worker provides knowledge retrieval and processing capabilities:
- URL fetching and content extraction
- Web search
- Document summarization
- Semantic search (future)

Triggered by ElevenLabs agents through client tools → AutoGen bridge → gRPC host.

Usage:
    python workers/knowledge_worker.py
    # Connects to gRPC host at localhost:50051
    # Press Ctrl+C to stop
"""

import asyncio
import logging
import signal
import sys
from dataclasses import dataclass
from typing import Optional

import requests
from autogen_core import MessageContext, RoutedAgent, default_subscription, message_handler
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('knowledge_worker.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


# Message Types
@dataclass
class URLRequest:
    """Request to fetch and process a URL."""
    url: str
    summary_length: str = "medium"  # "brief", "medium", "detailed"
    user_context: Optional[str] = None


@dataclass
class URLResponse:
    """Response containing processed URL content."""
    url: str
    title: str
    content: str
    summary: str
    word_count: int
    success: bool
    error: Optional[str] = None


@dataclass
class WebSearchRequest:
    """Request to perform web search."""
    query: str
    max_results: int = 5


@dataclass
class WebSearchResponse:
    """Response containing search results."""
    query: str
    results: list
    success: bool
    error: Optional[str] = None


@default_subscription
class KnowledgeWorker(RoutedAgent):
    """
    AutoGen agent specialized in knowledge retrieval and processing.

    Capabilities:
    - Fetch and parse web URLs
    - Extract text from HTML
    - Generate summaries of different lengths
    - Web search (placeholder for future implementation)
    """

    def __init__(self):
        super().__init__("Knowledge Worker Agent")
        logger.info("KnowledgeWorker initialized")

    @message_handler
    async def handle_url_request(self, message: URLRequest, ctx: MessageContext) -> URLResponse:
        """
        Handle URL fetching and processing requests.

        Args:
            message: URLRequest with URL and preferences
            ctx: Message context

        Returns:
            URLResponse with processed content
        """
        logger.info(f"Processing URL request: {message.url}")

        try:
            # Fetch URL content
            response = await asyncio.to_thread(
                requests.get,
                message.url,
                timeout=30,
                headers={'User-Agent': 'Mozilla/5.0 (VibeMind Knowledge Worker)'}
            )
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title = soup.title.string if soup.title else "No title"

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            content = '\n'.join(chunk for chunk in chunks if chunk)

            # Generate summary based on length preference
            summary = self._generate_summary(content, message.summary_length)

            word_count = len(content.split())

            logger.info(f"✓ Successfully processed {message.url} ({word_count} words)")

            return URLResponse(
                url=message.url,
                title=title,
                content=content,
                summary=summary,
                word_count=word_count,
                success=True
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching URL {message.url}: {e}")
            return URLResponse(
                url=message.url,
                title="Error",
                content="",
                summary="",
                word_count=0,
                success=False,
                error=f"Failed to fetch URL: {str(e)}"
            )

        except Exception as e:
            logger.error(f"Error processing URL {message.url}: {e}", exc_info=True)
            return URLResponse(
                url=message.url,
                title="Error",
                content="",
                summary="",
                word_count=0,
                success=False,
                error=f"Processing error: {str(e)}"
            )

    @message_handler
    async def handle_web_search(self, message: WebSearchRequest, ctx: MessageContext) -> WebSearchResponse:
        """
        Handle web search requests.

        Note: This is a placeholder. Implement with actual search API (e.g., Bing, Google, DuckDuckGo).

        Args:
            message: WebSearchRequest with query
            ctx: Message context

        Returns:
            WebSearchResponse with results
        """
        logger.info(f"Web search request: {message.query}")

        # Placeholder implementation
        return WebSearchResponse(
            query=message.query,
            results=[],
            success=False,
            error="Web search not yet implemented. Add search API integration."
        )

    def _generate_summary(self, content: str, length: str) -> str:
        """
        Generate a summary of the content.

        Args:
            content: Full text content
            length: "brief", "medium", or "detailed"

        Returns:
            Summary text
        """
        # Simple extractive summary - take first N sentences
        sentences = [s.strip() for s in content.split('.') if s.strip()]

        if length == "brief":
            num_sentences = min(3, len(sentences))
        elif length == "detailed":
            num_sentences = min(10, len(sentences))
        else:  # medium
            num_sentences = min(5, len(sentences))

        summary_sentences = sentences[:num_sentences]
        summary = '. '.join(summary_sentences)

        if summary and not summary.endswith('.'):
            summary += '.'

        return summary


# Global runtime instance
_runtime_instance: Optional[GrpcWorkerAgentRuntime] = None
_shutdown_event = asyncio.Event()


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    logger.info("Shutdown signal received")
    _shutdown_event.set()


async def main():
    """Main entry point for the knowledge worker."""
    global _runtime_instance

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        logger.info("Starting Knowledge Worker...")
        logger.info("Connecting to gRPC host at localhost:50051")

        # Create runtime and connect to host
        _runtime_instance = GrpcWorkerAgentRuntime(host_address="localhost:50051")
        await _runtime_instance.start()

        logger.info("✓ Connected to gRPC host")

        # Register KnowledgeWorker agent
        await KnowledgeWorker.register(
            _runtime_instance,
            "knowledge_worker",
            lambda: KnowledgeWorker()
        )

        logger.info("✓ KnowledgeWorker registered and ready")
        logger.info("Press Ctrl+C to stop")

        # Wait for shutdown signal
        await _shutdown_event.wait()

    except Exception as e:
        logger.error(f"Knowledge worker error: {e}", exc_info=True)
    finally:
        if _runtime_instance:
            logger.info("Stopping Knowledge Worker...")
            await _runtime_instance.stop()
            logger.info("✓ Knowledge Worker stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
