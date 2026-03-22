"""
Rewrite Worker - AutoGen gRPC Agent

This worker provides AI-powered summary rewriting using Google Gemini 1.5 Pro.
Part of the multi-agent summarization pipeline:
1. SummarizationWorker (GPT-4.1) - Creates initial summary
2. RewriteWorker (Gemini) - Rewrites with larger context

Gemini is used for its large context window (1M+ tokens) which allows
incorporating more context during the rewrite phase.

Triggered by voice agents through client tools → AutoGen bridge → gRPC host.

Usage:
    python workers/rewrite_worker.py
    # Connects to gRPC host at localhost:50051
    
Environment:
    GOOGLE_API_KEY - Google AI API key for Gemini
"""

import asyncio
import logging
import os
import signal
import sys
from dataclasses import dataclass
from typing import Optional, List

from llm_config import get_model

from autogen_core import MessageContext, RoutedAgent, default_subscription, message_handler
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rewrite_worker.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


# Message Types
@dataclass
class RewriteRequest:
    """Request to rewrite/improve a summary."""
    initial_summary: str
    original_content: Optional[str] = None  # Full original content for context
    title: Optional[str] = None
    style: str = "concise"  # "concise", "detailed", "actionable", "creative"
    additional_context: Optional[str] = None


@dataclass
class RewriteResponse:
    """Response containing the rewritten summary."""
    rewritten_summary: str
    style_applied: str
    success: bool
    error: Optional[str] = None


@default_subscription
class RewriteWorker(RoutedAgent):
    """
    AutoGen agent specialized in summary rewriting using Google Gemini.

    This worker:
    - Receives initial summaries from SummarizationWorker
    - Uses Gemini's large context window for contextual understanding
    - Rewrites summaries with improved clarity and style
    """

    def __init__(self):
        super().__init__("Rewrite Worker Agent")
        self.model = None
        self.model_name = get_model("rewrite_worker")
        
        if HAS_GEMINI:
            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(self.model_name)
                logger.info(f"RewriteWorker initialized with model: {self.model_name}")
            else:
                logger.warning("GOOGLE_API_KEY not set - rewrite will fail")
        else:
            logger.warning("google-generativeai package not installed. Install with: pip install google-generativeai")

    @message_handler
    async def handle_rewrite_request(
        self, message: RewriteRequest, ctx: MessageContext
    ) -> RewriteResponse:
        """
        Handle summary rewrite requests.

        Args:
            message: RewriteRequest with summary to rewrite
            ctx: Message context

        Returns:
            RewriteResponse with rewritten summary
        """
        logger.info(f"Processing rewrite request (style: {message.style})")

        if not self.model:
            return RewriteResponse(
                rewritten_summary=message.initial_summary,  # Return original as fallback
                style_applied=message.style,
                success=False,
                error="Gemini not configured. Set GOOGLE_API_KEY and install google-generativeai."
            )

        try:
            # Build style instructions
            style_instructions = {
                "concise": "Make it shorter and more direct. Remove unnecessary words.",
                "detailed": "Expand on key points with more explanation and examples.",
                "actionable": "Focus on actionable takeaways and next steps.",
                "creative": "Use more engaging language and metaphors while keeping accuracy."
            }
            
            style_guide = style_instructions.get(message.style, style_instructions["concise"])

            # Build the prompt with all available context
            prompt_parts = [
                f"You are a skilled editor improving summaries of ideas and notes.",
                f"\nTask: Rewrite the following summary to be better quality.",
                f"\nStyle guidance: {style_guide}",
                f"\n\n--- SUMMARY TO REWRITE ---",
                f"\n{message.initial_summary}",
            ],

            if message.title:
                prompt_parts.append(f"\n\n--- TITLE ---\n{message.title}")

            if message.original_content:
                prompt_parts.append(f"\n\n--- ORIGINAL SOURCE CONTENT ---\n{message.original_content[:5000]}")  # Limit to 5k chars
            
            if message.additional_context:
                prompt_parts.append(f"\n\n--- ADDITIONAL CONTEXT ---\n{message.additional_context}")

            prompt_parts.append("\n\n--- YOUR REWRITTEN SUMMARY ---\nProvide only the improved summary, no explanations:")

            full_prompt = "".join(prompt_parts)

            # Call Gemini API
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt
            )

            rewritten = response.text.strip()

            logger.info(f"✓ Rewritten summary ({len(message.initial_summary)} -> {len(rewritten)} chars)")

            return RewriteResponse(
                rewritten_summary=rewritten,
                style_applied=message.style,
                success=True
            )

        except Exception as e:
            logger.error(f"Error in rewrite: {e}", exc_info=True)
            return RewriteResponse(
                rewritten_summary=message.initial_summary,  # Return original as fallback
                style_applied=message.style,
                success=False,
                error=f"Rewrite failed: {str(e)}"
            )


# Global runtime instance
_runtime_instance: Optional[GrpcWorkerAgentRuntime] = None
_shutdown_event = asyncio.Event()


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    logger.info("Shutdown signal received")
    _shutdown_event.set()


async def main():
    """Main entry point for the rewrite worker."""
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
        logger.info("Starting Rewrite Worker...")
        logger.info("Connecting to gRPC host at localhost:50051")

        # Create runtime and connect to host
        _runtime_instance = GrpcWorkerAgentRuntime(host_address="localhost:50051")
        await _runtime_instance.start()

        logger.info("✓ Connected to gRPC host")

        # Register RewriteWorker agent
        await RewriteWorker.register(
            _runtime_instance,
            "rewrite_worker",
            lambda: RewriteWorker()
        )

        logger.info("✓ RewriteWorker registered and ready")
        logger.info("Press Ctrl+C to stop")

        # Wait for shutdown signal
        await _shutdown_event.wait()

    except Exception as e:
        logger.error(f"Rewrite worker error: {e}", exc_info=True)
    finally:
        if _runtime_instance:
            logger.info("Stopping Rewrite Worker...")
            await _runtime_instance.stop()
            logger.info("✓ Rewrite Worker stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)