"""
Summarization Worker - AutoGen gRPC Agent

This worker provides AI-powered summarization of idea content using OpenAI GPT-4.1.
Part of the multi-agent summarization pipeline:
1. SummarizationWorker (GPT-4.1) - Creates initial summary
2. RewriteWorker (Gemini) - Rewrites with larger context

Triggered by voice agents through client tools → AutoGen bridge → gRPC host.

Usage:
    python workers/summarization_worker.py
    # Connects to gRPC host at localhost:50051
"""

import asyncio
import logging
import os
import signal
import sys
from dataclasses import dataclass
from typing import Optional

from autogen_core import MessageContext, RoutedAgent, default_subscription, message_handler
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime

# Try to import OpenAI
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('summarization_worker.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


# Message Types
@dataclass
class SummarizationRequest:
    """Request to summarize content."""
    content: str
    title: Optional[str] = None
    context: Optional[str] = None  # Additional context about the idea
    max_tokens: int = 500


@dataclass
class SummarizationResponse:
    """Response containing the summary."""
    summary: str
    original_length: int
    summary_length: int
    success: bool
    error: Optional[str] = None


@default_subscription
class SummarizationWorker(RoutedAgent):
    """
    AutoGen agent specialized in content summarization using GPT-4.1.

    This worker:
    - Receives raw content from ideas/notes
    - Uses OpenAI GPT-4.1 to generate concise summaries
    - Returns structured summary for further processing
    """

    def __init__(self):
        super().__init__("Summarization Worker Agent")
        self.openai_client = None
        self.model = os.getenv("OPENAI_SUMMARIZATION_MODEL", "gpt-4o-mini")
        
        if HAS_OPENAI:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
                logger.info(f"SummarizationWorker initialized with model: {self.model}")
            else:
                logger.warning("OPENAI_API_KEY not set - summarization will fail")
        else:
            logger.warning("OpenAI package not installed")

    @message_handler
    async def handle_summarization_request(
        self, message: SummarizationRequest, ctx: MessageContext
    ) -> SummarizationResponse:
        """
        Handle content summarization requests.

        Args:
            message: SummarizationRequest with content to summarize
            ctx: Message context

        Returns:
            SummarizationResponse with generated summary
        """
        logger.info(f"Processing summarization request (content length: {len(message.content)})")

        if not self.openai_client:
            return SummarizationResponse(
                summary="",
                original_length=len(message.content),
                summary_length=0,
                success=False,
                error="OpenAI client not configured. Set OPENAI_API_KEY."
            )

        try:
            # Build the prompt
            system_prompt = """You are a concise summarization assistant. 
Your task is to create clear, informative summaries of ideas and notes.
Focus on:
- Key concepts and main points
- Important details and insights
- Actionable items if present
Keep the summary focused and avoid redundancy."""

            user_prompt = f"""Summarize the following content:

Title: {message.title or 'Untitled'}

Content:
{message.content}

{f'Additional context: {message.context}' if message.context else ''}

Provide a clear, concise summary that captures the essence of this idea."""

            # Call OpenAI API
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=message.max_tokens,
                temperature=0.5
            )

            summary = response.choices[0].message.content.strip()

            logger.info(f"✓ Generated summary ({len(summary)} chars from {len(message.content)} chars)")

            return SummarizationResponse(
                summary=summary,
                original_length=len(message.content),
                summary_length=len(summary),
                success=True
            )

        except Exception as e:
            logger.error(f"Error in summarization: {e}", exc_info=True)
            return SummarizationResponse(
                summary="",
                original_length=len(message.content),
                summary_length=0,
                success=False,
                error=f"Summarization failed: {str(e)}"
            )


# Global runtime instance
_runtime_instance: Optional[GrpcWorkerAgentRuntime] = None
_shutdown_event = asyncio.Event()


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    logger.info("Shutdown signal received")
    _shutdown_event.set()


async def main():
    """Main entry point for the summarization worker."""
    global _runtime_instance

    # Load .env
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded .env from {env_path}")
    except ImportError:
        pass

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        logger.info("Starting Summarization Worker...")
        logger.info("Connecting to gRPC host at localhost:50051")

        # Create runtime and connect to host
        _runtime_instance = GrpcWorkerAgentRuntime(host_address="localhost:50051")
        await _runtime_instance.start()

        logger.info("✓ Connected to gRPC host")

        # Register SummarizationWorker agent
        await SummarizationWorker.register(
            _runtime_instance,
            "summarization_worker",
            lambda: SummarizationWorker()
        )

        logger.info("✓ SummarizationWorker registered and ready")
        logger.info("Press Ctrl+C to stop")

        # Wait for shutdown signal
        await _shutdown_event.wait()

    except Exception as e:
        logger.error(f"Summarization worker error: {e}", exc_info=True)
    finally:
        if _runtime_instance:
            logger.info("Stopping Summarization Worker...")
            await _runtime_instance.stop()
            logger.info("✓ Summarization Worker stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)