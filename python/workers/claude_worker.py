"""
Claude Worker - Step-Based Desktop Automation Agent

Uses Claude Opus 4.5 via OpenRouter to execute desktop automation tasks.
Listens to the TaskQueue for tasks seeded by ElevenLabs voice agents.

Key Features:
- Step-based execution (plan → execute → verify)
- Task interruption check every 3 steps
- MCP tools for desktop automation (click, type, OCR)
- Progress reporting back to TaskQueue

Architecture:
    ElevenLabs → seed_task() → TaskQueue → ClaudeWorker → MCP Tools

Usage:
    python -m workers.claude_worker
"""

import asyncio
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/claude_worker.log', mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import components
try:
    from tools.worker_queue import (
        get_task_queue, TaskQueue, WorkerTask, TaskPriority,
        get_report_queue, StepReport
    )
except ImportError:
    logger.error("worker_queue not found. Run from python directory.")
    sys.exit(1)

try:
    from workers.mcp_tools_adapter import (
        execute_tool,
        get_tools_for_llm,
        get_status as get_tools_status
    )
except ImportError:
    logger.error("mcp_tools_adapter not found")
    sys.exit(1)

try:
    from moire.core.openrouter_client import get_openrouter_client, OpenRouterClient
except ImportError:
    logger.warning("OpenRouter client not found, using direct API calls")
    get_openrouter_client = None


# =============================================================================
# CONFIGURATION
# =============================================================================

# Claude Opus 4.5 via OpenRouter
WORKER_MODEL = "anthropic/claude-opus-4-5-20251101"

# System prompt for the worker
WORKER_SYSTEM_PROMPT = """You are a desktop automation worker. You execute tasks step by step using MCP tools.

## Your Capabilities
You can control the desktop using these tools:
- scan_desktop: See what's on screen (use this FIRST for any task)
- find_element: Find a specific UI element by text
- click: Click at coordinates
- type_text: Type text at cursor
- press_key: Press keyboard keys (enter, ctrl+c, etc.)
- scroll: Scroll up/down
- wait: Wait for UI to update

## Execution Rules
1. ALWAYS scan_desktop first to understand the current state
2. Find elements before clicking (use find_element or scan_desktop)
3. Verify actions worked before proceeding
4. Report progress after each step
5. If something fails, explain what happened

## Response Format
For each step, respond with JSON:
{
    "thought": "What I'm about to do and why",
    "tool": "tool_name",
    "params": {"param1": "value1"},
    "verify": "How I'll verify this worked"
}

When the task is complete:
{
    "status": "completed",
    "summary": "What was accomplished",
    "result": {"any": "relevant data"}
}

If the task fails:
{
    "status": "failed",
    "error": "What went wrong",
    "suggestion": "What the user could try instead"
}"""


@dataclass
class ExecutionStep:
    """A single step in task execution."""
    step_number: int
    thought: str
    tool: str
    params: Dict[str, Any]
    verify: str = ""
    result: Optional[Dict[str, Any]] = None
    success: bool = False
    error: Optional[str] = None


@dataclass
class ExecutionPlan:
    """Plan for executing a task."""
    task_id: str
    goal: str
    steps: List[ExecutionStep] = field(default_factory=list)
    current_step: int = 0
    status: str = "planning"  # planning, executing, completed, failed


# =============================================================================
# CLAUDE WORKER
# =============================================================================

class ClaudeWorker:
    """
    Claude Opus 4.5 worker for desktop automation.

    Executes tasks from the TaskQueue using MCP tools.
    """

    def __init__(self, model: str = WORKER_MODEL):
        self.model = model
        self.queue = get_task_queue()
        self.client: Optional[OpenRouterClient] = None
        self.running = False
        self.current_task: Optional[WorkerTask] = None
        self.steps_since_check = 0
        self.check_interval = 3  # Check for new tasks every N steps

        # Try to get OpenRouter client
        if get_openrouter_client:
            try:
                self.client = get_openrouter_client()
            except Exception as e:
                logger.warning(f"OpenRouter client init failed: {e}")

    async def start(self):
        """Start the worker loop."""
        self.running = True
        logger.info("Claude Worker starting...")
        logger.info(f"Model: {self.model}")
        logger.info(f"Tools available: {get_tools_status()}")

        while self.running:
            try:
                # Get next task from queue
                task = await self.queue.get_next_task(timeout=2.0)

                if task:
                    logger.info(f"Picked up task: {task.id} - {task.description[:50]}...")
                    await self.execute_task(task)
                else:
                    # No task, just wait
                    await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                logger.info("Worker cancelled")
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info("Claude Worker stopped")

    async def stop(self):
        """Stop the worker."""
        self.running = False
        if self.client:
            await self.client.close()

    async def execute_task(self, task: WorkerTask):
        """
        Execute a task step by step.

        Args:
            task: WorkerTask to execute
        """
        self.current_task = task
        self.steps_since_check = 0

        # Step buffer for reports (collect 3 steps before pushing report)
        step_buffer: List[Dict[str, Any]] = []
        report_number = 0
        report_queue = get_report_queue()

        # Update task status
        self.queue.update_task(
            task.id,
            status="planning",
            progress_message="Analyzing task..."
        )

        try:
            # Build conversation with Claude
            messages = [
                {"role": "system", "content": WORKER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Task: {task.description}\n\nBegin by scanning the desktop to understand the current state."}
            ]

            step_count = 0
            max_steps = 20  # Safety limit

            while step_count < max_steps:
                # Check for higher priority task and push report every 3 steps
                if self.steps_since_check >= self.check_interval:
                    # Push report for the last 3 steps
                    if step_buffer:
                        report_number += 1
                        report = StepReport(
                            task_id=task.id,
                            report_number=report_number,
                            steps_completed=step_count,
                            steps=step_buffer.copy(),
                            summary=self._generate_summary(step_buffer),
                            is_final=False
                        )
                        report_queue.push_report(report)
                        logger.info(f"Report #{report_number} pushed: {report.summary[:50]}...")
                        step_buffer.clear()

                    # Check for higher priority task
                    if self.queue.has_higher_priority_task(task.priority):
                        logger.info(f"Higher priority task waiting, pausing {task.id}")
                        self.queue.update_task(
                            task.id,
                            status="queued",
                            progress_message="Paused for higher priority task"
                        )
                        return
                    self.steps_since_check = 0

                # Get next action from Claude
                response = await self._call_claude(messages)

                if not response:
                    self.queue.update_task(
                        task.id,
                        status="failed",
                        error="Failed to get response from Claude"
                    )
                    return

                # Parse the response
                action = self._parse_action(response)

                if action.get("status") == "completed":
                    # Push final report with remaining steps
                    if step_buffer:
                        report_number += 1
                        report = StepReport(
                            task_id=task.id,
                            report_number=report_number,
                            steps_completed=step_count,
                            steps=step_buffer.copy(),
                            summary=action.get("summary", "Task completed"),
                            is_final=True
                        )
                        report_queue.push_report(report)

                    # Task completed
                    self.queue.update_task(
                        task.id,
                        status="completed",
                        progress_message=action.get("summary", "Task completed"),
                        result=action.get("result", {})
                    )
                    logger.info(f"Task {task.id} completed: {action.get('summary')}")
                    return

                elif action.get("status") == "failed":
                    # Push report before failing
                    if step_buffer:
                        report_number += 1
                        report = StepReport(
                            task_id=task.id,
                            report_number=report_number,
                            steps_completed=step_count,
                            steps=step_buffer.copy(),
                            summary=f"Failed: {action.get('error', 'Unknown error')[:100]}",
                            is_final=True
                        )
                        report_queue.push_report(report)

                    # Task failed
                    self.queue.update_task(
                        task.id,
                        status="failed",
                        error=action.get("error", "Unknown error")
                    )
                    logger.error(f"Task {task.id} failed: {action.get('error')}")
                    return

                elif "tool" in action:
                    # Execute tool
                    step_count += 1
                    self.steps_since_check += 1

                    tool_name = action["tool"]
                    tool_params = action.get("params", {})
                    thought = action.get("thought", "")

                    # Update progress
                    self.queue.update_task(
                        task.id,
                        status="executing",
                        current_step=step_count,
                        progress_message=f"{thought[:50]}..."
                    )

                    logger.info(f"Step {step_count}: {tool_name} - {thought[:50]}")

                    # Execute the tool
                    result = await execute_tool(tool_name, tool_params)

                    # Add to step buffer for report
                    step_buffer.append({
                        "step": step_count,
                        "tool": tool_name,
                        "thought": thought,
                        "success": result.get("success", False)
                    })

                    # Add result to conversation
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": f"Tool result:\n{json.dumps(result, indent=2)}\n\nContinue with the next step, or report completion/failure."
                    })

                else:
                    # Unexpected response format
                    logger.warning(f"Unexpected response format: {response[:100]}")
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": "Please respond with a tool action or completion status in JSON format."
                    })

            # Hit step limit
            self.queue.update_task(
                task.id,
                status="failed",
                error=f"Task exceeded maximum steps ({max_steps})"
            )

        except Exception as e:
            logger.error(f"Task execution error: {e}", exc_info=True)
            self.queue.update_task(
                task.id,
                status="failed",
                error=str(e)
            )

        finally:
            self.current_task = None

    def _generate_summary(self, steps: List[Dict[str, Any]]) -> str:
        """
        Generate a natural language summary of executed steps.

        Args:
            steps: List of step dicts with tool/thought/success

        Returns:
            Human-readable summary
        """
        if not steps:
            return "No steps executed yet"

        # Build summary from thoughts and tools
        parts = []
        for step in steps:
            tool = step.get("tool", "unknown")
            thought = step.get("thought", "")
            success = step.get("success", False)

            # Use thought if available, otherwise describe tool
            if thought:
                parts.append(thought[:50])
            else:
                status = "done" if success else "attempted"
                parts.append(f"{tool} {status}")

        return "; ".join(parts)

    async def _call_claude(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """
        Call Claude via OpenRouter.

        Args:
            messages: Conversation messages

        Returns:
            Claude's response text or None on error
        """
        if self.client:
            try:
                response = await self.client.chat(
                    messages=messages,
                    model=self.model,
                    temperature=0.2,
                    max_tokens=2048
                )
                return response.content
            except Exception as e:
                logger.error(f"OpenRouter client error: {e}")

        # Fallback to direct API call
        return await self._call_openrouter_direct(messages)

    async def _call_openrouter_direct(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Direct API call to OpenRouter."""
        import os
        import aiohttp

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.error("OPENROUTER_API_KEY not set")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://vibemind.local",
                        "X-Title": "VibeMind Claude Worker"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.2,
                        "max_tokens": 2048
                    }
                ) as response:
                    if response.status != 200:
                        error = await response.text()
                        logger.error(f"OpenRouter API error {response.status}: {error}")
                        return None

                    data = await response.json()
                    return data["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Direct API call error: {e}")
            return None

    def _parse_action(self, response: str) -> Dict[str, Any]:
        """
        Parse Claude's response to extract action.

        Args:
            response: Claude's response text

        Returns:
            Parsed action dict
        """
        # Try to extract JSON from response
        try:
            # Look for JSON in code blocks
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            else:
                # Try parsing the whole response as JSON
                return json.loads(response.strip())

        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract key info
            response_lower = response.lower()

            if "completed" in response_lower or "done" in response_lower:
                return {"status": "completed", "summary": response[:200]}
            elif "failed" in response_lower or "error" in response_lower:
                return {"status": "failed", "error": response[:200]}
            else:
                # Return as-is for retry
                return {"raw_response": response}


# =============================================================================
# MAIN
# =============================================================================

_worker: Optional[ClaudeWorker] = None
_shutdown_event = asyncio.Event()


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    logger.info("Shutdown signal received")
    _shutdown_event.set()


async def main():
    """Main entry point."""
    global _worker

    # Ensure logs directory exists
    import os
    os.makedirs("logs", exist_ok=True)

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        logger.info("=" * 60)
        logger.info("Claude Worker Starting")
        logger.info("=" * 60)

        # Create worker
        _worker = ClaudeWorker()

        # Start worker in background
        worker_task = asyncio.create_task(_worker.start())

        # Wait for shutdown
        await _shutdown_event.wait()

        # Stop worker
        await _worker.stop()
        worker_task.cancel()

        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Claude Worker shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Fatal: {e}", exc_info=True)
        sys.exit(1)
