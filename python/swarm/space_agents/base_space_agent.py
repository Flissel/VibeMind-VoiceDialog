"""
BaseSpaceAgent — Abstract base for space-specific LLM tool-calling agents.

Each Space gets its own agent with domain-specific tools exposed as
OpenAI-compatible function calling definitions. The agent runs an
agentic loop: LLM → tool_calls → execute → feed results → repeat.

Pattern reuses:
- tool_orchestrator.py → Client setup, execute pattern
- base_listener.py → async via ThreadPoolExecutor
"""

import asyncio
import concurrent.futures
import json
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod

from llm_config import get_model, token_kwargs
from typing import Dict, Any, List, Optional, Callable

from .models import (
    SpaceAgentContext,
    SpaceAgentResult,
    SpaceToolCall,
    SpaceToolResult,
)

logger = logging.getLogger(__name__)


class BaseSpaceAgent(ABC):
    """LLM agent with native tool calling for a specific Space."""

    def __init__(self, model: str = None, max_turns: int = 5):
        self.model = model or get_model("space_agent")
        self._max_turns = max_turns
        self._client = None
        self._tools: List[Dict[str, Any]] = []
        self._executors: Dict[str, Callable] = {}
        self._load_tools()
        logger.info(
            f"[SpaceAgent:{self.space_name}] Initialized with "
            f"{len(self._tools)} tools (model: {self.model})"
        )

    @property
    @abstractmethod
    def space_name(self) -> str:
        """Space identifier, e.g. 'ideas', 'coding', 'desktop'."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Domain-specific system prompt for the agent."""
        ...

    @abstractmethod
    def _load_tools(self):
        """Register tool JSON schemas and executor functions."""
        ...

    def _build_system_prompt(self, context: SpaceAgentContext) -> str:
        """Inject runtime context into system prompt."""
        prompt = self.system_prompt

        # Replace context placeholders
        bubble_info = context.current_bubble or "Multiverse (kein Space betreten)"
        prompt = prompt.replace("{current_bubble}", bubble_info)
        prompt = prompt.replace("{idea_count}", str(context.idea_count))

        # Add conversation history
        if context.conversation_history:
            last_msgs = context.conversation_history[-5:]
            history_str = "\n".join(
                f"- {m.get('role', '?')}: {m.get('text', m.get('content', ''))}"
                for m in last_msgs
            )
            prompt = prompt.replace("{conversation_history}", history_str)
        else:
            prompt = prompt.replace("{conversation_history}", "(keine)")

        return prompt

    @property
    def client(self):
        """Lazy-load OpenRouter client."""
        if self._client is None:
            from openai import OpenAI
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY not set")
            self._client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=15.0,
            )
        return self._client

    async def execute(
        self, user_input: str, context: SpaceAgentContext
    ) -> SpaceAgentResult:
        """
        Agentic loop: LLM → tool_calls → execute → feed back → repeat.

        Returns SpaceAgentResult with all tool calls, results, and summary.
        """
        start = time.perf_counter()

        messages = [
            {"role": "system", "content": self._build_system_prompt(context)},
            {"role": "user", "content": user_input},
        ]

        all_tool_calls: List[SpaceToolCall] = []
        all_results: List[SpaceToolResult] = []
        final_text = ""
        turns = 0

        for turn in range(self._max_turns):
            turns += 1
            response = await self._call_llm(messages)
            message = response.choices[0].message

            # If LLM returned text (no tool calls), we're done
            if not message.tool_calls:
                final_text = message.content or ""
                break

            # Process tool calls
            # Build assistant message with all tool calls for this turn
            assistant_msg = {
                "role": "assistant",
                "content": message.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
            messages.append(assistant_msg)

            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                tool_call = SpaceToolCall(
                    name=tc.function.name,
                    arguments=args,
                    id=tc.id or str(uuid.uuid4())[:8],
                )
                all_tool_calls.append(tool_call)

                # Execute
                result = self._execute_tool(tc.function.name, args)
                all_results.append(result)

                result_content = (
                    str(result.result) if result.success
                    else f"ERROR: {result.error}"
                )

                # Feed result back to LLM
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_content,
                })

            # If this was the last allowed turn, force a summary
            if turn == self._max_turns - 1:
                final_text = self._generate_summary(all_results)

        # If we finished the loop with tool calls but no final text,
        # make one more LLM call to get the summary
        if not final_text and all_results:
            try:
                summary_response = await self._call_llm(messages)
                final_text = summary_response.choices[0].message.content or ""
            except Exception:
                final_text = self._generate_summary(all_results)

        elapsed = (time.perf_counter() - start) * 1000

        # Log
        tool_names = [tc.name for tc in all_tool_calls]
        logger.info(
            f"[SpaceAgent:{self.space_name}] {turns} turns, "
            f"tools={tool_names}, {elapsed:.0f}ms"
        )

        return SpaceAgentResult(
            tool_calls=all_tool_calls,
            results=all_results,
            summary=final_text,
            total_latency_ms=elapsed,
            turns=turns,
        )

    async def _call_llm(self, messages: List[Dict]) -> Any:
        """Call LLM via OpenRouter in thread pool (non-blocking)."""
        def _sync_call():
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self._tools,
                tool_choice="auto",
                temperature=0.1,
                **token_kwargs(self.model, 1500),
            )

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(pool, _sync_call)

    def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> SpaceToolResult:
        """Execute a tool by name and return result."""
        executor = self._executors.get(name)
        if not executor:
            logger.warning(f"[SpaceAgent:{self.space_name}] No executor: {name}")
            return SpaceToolResult(
                tool_name=name,
                success=False,
                error=f"Tool '{name}' not available",
            )

        try:
            result = executor(arguments)
            logger.debug(f"[SpaceAgent:{self.space_name}] {name} → {str(result)[:100]}")
            return SpaceToolResult(
                tool_name=name,
                success=True,
                result=result,
            )
        except Exception as e:
            logger.error(f"[SpaceAgent:{self.space_name}] {name} failed: {e}")
            return SpaceToolResult(
                tool_name=name,
                success=False,
                error=str(e),
            )

    def _generate_summary(self, results: List[SpaceToolResult]) -> str:
        """Fallback summary when LLM doesn't provide one."""
        if not results:
            return "Erledigt."

        messages = []
        for r in results:
            if r.success and r.result:
                if isinstance(r.result, str):
                    messages.append(r.result)
                elif isinstance(r.result, dict) and "message" in r.result:
                    messages.append(r.result["message"])
            elif r.error:
                messages.append(f"Fehler bei {r.tool_name}: {r.error}")

        return " ".join(messages) if messages else "Erledigt."
