"""
ToolOrchestrator - Sonnet-based agentic tool orchestration.

Replaces the simple IntentClassifier with a reasoning model that can
execute multiple tools in sequence (batch processing).

Architecture:
    User Request → Sonnet (with tool definitions)
                        ↓
                 tool_calls: [{name, args}, ...]
                        ↓
                 Tool Executor (sequential/parallel)
                        ↓
                 Results aggregation
                        ↓
                 Summary for voice output
"""

import json
import logging
import os
import uuid
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field

from llm_config import token_kwargs

from swarm.orchestrator.tool_definitions import (
    get_all_tools,
    TOOL_TO_EVENT_TYPE,
)
from swarm.orchestrator.system_context_store import get_system_context_store
from swarm.orchestrator.notification_queue import get_notification_queue

logger = logging.getLogger(__name__)


# System prompt for the orchestrator
ORCHESTRATOR_SYSTEM_PROMPT = """Du bist der VibeMind Orchestrator - das Gehirn des Systems.

## Deine Aufgabe
Analysiere User-Anfragen und fuehre die passenden Tools aus.
Du kannst MEHRERE Tools in einer Anfrage aufrufen (Batch Processing).

## VibeMind Konzepte
- **Spaces/Bubbles**: Container fuer Ideen (wie Ordner/Workspaces)
- **Ideas/Notizen**: Inhalte innerhalb von Spaces
- **Multiverse**: Die Uebersicht aller Spaces
- **Desktop**: Automatisierung des Windows-Desktops
- **Code Generation**: Erstellt Projekte aus Beschreibungen

## Regeln
1. Extrahiere EXAKT die Woerter/Namen die der User sagt
2. Bei komplexen Anfragen: Mehrere Tools in logischer Reihenfolge
3. Bei Unklarheit: Nutze conversation_clarify um nachzufragen
4. Kombiniere verwandte Aktionen sinnvoll

## Beispiele fuer Multi-Step

User: "Erstelle einen Space Projekt und eine Idee Brainstorm darin"
→ bubble_create(title="Projekt")
→ bubble_enter(bubble_name="Projekt")
→ idea_create(title="Brainstorm", content="Brainstorm")

User: "Loesche alle Testdaten"
→ bubble_delete(bubble_name="Test") [wenn vorhanden]

User: "Verbinde Katze mit Hund"
→ idea_connect(idea1="Katze", idea2="Hund")

## Wichtig
- Antworte NUR mit Tool-Aufrufen, kein zusaetzlicher Text
- Wenn keine Aktion passt, nutze conversation_clarify
- Bei Greetings (Hallo, Hi): Kein Tool noetig, lass es leer
"""


@dataclass
class ToolCall:
    """A single tool call from the orchestrator."""
    name: str
    arguments: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class ToolResult:
    """Result of a single tool execution."""
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None


@dataclass
class OrchestrationResult:
    """Complete result of tool orchestration."""
    tool_calls: List[ToolCall]
    results: List[ToolResult]
    summary: str
    job_id: str = field(default_factory=lambda: f"batch-{str(uuid.uuid4())[:8]}")
    error: Optional[str] = None


class ToolOrchestrator:
    """
    Sonnet-based tool orchestrator with batch processing.

    Uses Claude's native tool calling to:
    1. Understand complex user requests
    2. Plan multiple tool calls
    3. Execute in sequence
    4. Summarize results for voice output
    """

    def __init__(
        self,
        model: str = None,
        use_tool_orchestrator: bool = None
    ):
        """
        Initialize the orchestrator.

        Args:
            model: Model to use (default: anthropic/claude-sonnet-4)
            use_tool_orchestrator: Override env var USE_TOOL_ORCHESTRATOR
        """
        from llm_config import get_model
        self.model = model or get_model("tool_orchestrator")
        self._client = None
        self._tools = get_all_tools()
        self._executors: Dict[str, Callable] = {}

        # Check if enabled
        if use_tool_orchestrator is not None:
            self._enabled = use_tool_orchestrator
        else:
            self._enabled = os.getenv("USE_TOOL_ORCHESTRATOR", "false").lower() == "true"

        if self._enabled:
            self._load_executors()
            logger.info(f"ToolOrchestrator initialized with {len(self._tools)} tools (model: {self.model})")
        else:
            logger.info("ToolOrchestrator disabled (USE_TOOL_ORCHESTRATOR=false)")

    @property
    def enabled(self) -> bool:
        """Check if orchestrator is enabled."""
        return self._enabled

    @property
    def client(self):
        """Get or create OpenAI-compatible client."""
        if self._client is None:
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENROUTER_API_KEY")
                if not api_key:
                    raise ValueError("OPENROUTER_API_KEY not set")

                self._client = OpenAI(
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1"
                )
                logger.info(f"ToolOrchestrator client created for {self.model}")
            except Exception as e:
                logger.error(f"Failed to create orchestrator client: {e}")
                raise

        return self._client

    def _load_executors(self):
        """Load tool executor functions from tool modules."""
        # === BUBBLE TOOLS ===
        try:
            from tools.bubble_tools import (
                list_bubbles, create_bubble, enter_bubble,
                exit_bubble, delete_bubble, get_bubble_stats,
                score_bubble, promote_bubble
            )
            from tools.idea_tools import get_current_space

            self._executors.update({
                "bubble_list": list_bubbles,
                "bubble_create": create_bubble,
                "bubble_enter": enter_bubble,
                "bubble_exit": exit_bubble,
                "bubble_delete": delete_bubble,
                "bubble_stats": get_bubble_stats,
                "bubble_score": score_bubble,
                "bubble_promote": promote_bubble,
                "bubble_current": get_current_space,
            })
            logger.debug("Loaded bubble tools")
        except ImportError as e:
            logger.warning(f"Could not load bubble tools: {e}")

        # === IDEA TOOLS ===
        try:
            from tools.idea_tools import (
                create_idea, list_ideas, find_idea, delete_idea,
                update_idea, connect_ideas, add_image
            )
            self._executors.update({
                "idea_list": list_ideas,
                "idea_create": create_idea,
                "idea_find": find_idea,
                "idea_update": update_idea,
                "idea_delete": delete_idea,
                "idea_connect": connect_ideas,
                "idea_add_image": add_image,
            })
            logger.debug("Loaded idea tools")
        except ImportError as e:
            logger.warning(f"Could not load idea tools: {e}")

        # === CODING TOOLS ===
        try:
            from spaces.coding.tools.coding_tools import (
                generate_code, get_generation_status, start_preview,
                stop_preview, list_generated_projects, cancel_generation
            )
            self._executors.update({
                "code_generate": generate_code,
                "code_status": get_generation_status,
                "code_preview_start": start_preview,
                "code_preview_stop": stop_preview,
                "code_list": list_generated_projects,
                "code_cancel": cancel_generation,
            })
            logger.debug("Loaded coding tools")
        except ImportError as e:
            logger.warning(f"Could not load coding tools: {e}")

        # === DESKTOP TOOLS (with sync wrappers) ===
        try:
            from spaces.desktop.tools.desktop_tools import (
                execute_desktop_task, click_element, type_text,
                press_key, take_screenshot, scroll_screen
            )
            import asyncio
            import concurrent.futures

            def _run_async(coro):
                """Run async function synchronously."""
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(asyncio.run, coro)
                            return future.result()
                    return loop.run_until_complete(coro)
                except RuntimeError:
                    return asyncio.run(coro)

            def _format_desktop_result(result):
                if isinstance(result, dict):
                    if result.get("success"):
                        return result.get("message", "Done.")
                    else:
                        return f"Error: {result.get('error', 'Unknown')}"
                return str(result)

            def desktop_task_sync(params):
                goal = params.get("goal", "") or params.get("description", "")
                if not goal:
                    return "What should I do on the desktop?"
                result = _run_async(execute_desktop_task(goal))
                return _format_desktop_result(result)

            def click_sync(params):
                desc = params.get("element_description", "") or params.get("description", "")
                if not desc:
                    return "Which element?"
                result = _run_async(click_element(desc))
                return _format_desktop_result(result)

            def type_sync(params):
                text = params.get("text", "")
                if not text:
                    return "What to type?"
                result = _run_async(type_text(text))
                return _format_desktop_result(result)

            def press_key_sync(params):
                key = params.get("key", "")
                if not key:
                    return "Which key?"
                result = _run_async(press_key(key))
                return _format_desktop_result(result)

            def screenshot_sync(params):
                result = _run_async(take_screenshot())
                return _format_desktop_result(result)

            def scroll_sync(params):
                direction = params.get("direction", "down")
                amount = params.get("amount", 3)
                result = _run_async(scroll_screen(direction, amount))
                return _format_desktop_result(result)

            self._executors.update({
                "desktop_task": desktop_task_sync,
                "desktop_open_app": desktop_task_sync,
                "desktop_click": click_sync,
                "desktop_type": type_sync,
                "desktop_press_key": press_key_sync,
                "desktop_screenshot": screenshot_sync,
                "desktop_scroll": scroll_sync,
            })
            logger.debug("Loaded desktop tools")
        except ImportError as e:
            logger.warning(f"Could not load desktop tools: {e}")

        # === CONVERSATION TOOL ===
        def clarify(params):
            question = params.get("question", "Can you explain that in more detail?")
            return question

        self._executors["conversation_clarify"] = clarify

        logger.info(f"Loaded {len(self._executors)} tool executors")

    def process_sync(self, user_request: str) -> OrchestrationResult:
        """
        Synchronous processing of user request.

        Args:
            user_request: Natural language from user

        Returns:
            OrchestrationResult with tool calls, results, and summary
        """
        if not self._enabled:
            return OrchestrationResult(
                tool_calls=[],
                results=[],
                summary="ToolOrchestrator is disabled.",
                error="Orchestrator disabled"
            )

        try:
            # 1. Call Sonnet with tools
            logger.info(f"Processing request: {user_request[:50]}...")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_request}
                ],
                tools=self._tools,
                tool_choice="auto",
                temperature=0.1,
                **token_kwargs(self.model, 1000),
            )

            message = response.choices[0].message

            # 2. Extract tool calls
            tool_calls = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append(ToolCall(
                        name=tc.function.name,
                        arguments=args,
                        id=tc.id or str(uuid.uuid4())[:8]
                    ))
                    logger.info(f"Tool call: {tc.function.name}({args})")

            # 3. Execute tools
            results = self._execute_tools(tool_calls)

            # 4. Generate summary
            summary = self._generate_summary(user_request, results)

            return OrchestrationResult(
                tool_calls=tool_calls,
                results=results,
                summary=summary
            )

        except Exception as e:
            logger.error(f"Orchestration error: {e}")
            return OrchestrationResult(
                tool_calls=[],
                results=[],
                summary=f"There was a problem: {str(e)}",
                error=str(e)
            )

    async def process(self, user_request: str) -> OrchestrationResult:
        """Async wrapper for process_sync."""
        return self.process_sync(user_request)

    def _execute_tools(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """Execute tool calls sequentially and push results to context stores."""
        results = []

        # Get context stores for pushing results
        context_store = get_system_context_store()
        notification_queue = get_notification_queue()

        for tc in tool_calls:
            executor = self._executors.get(tc.name)

            if not executor:
                logger.warning(f"No executor for tool: {tc.name}")
                results.append(ToolResult(
                    tool_name=tc.name,
                    success=False,
                    result=None,
                    error=f"Tool {tc.name} not available"
                ))
                continue

            try:
                result = executor(tc.arguments)
                results.append(ToolResult(
                    tool_name=tc.name,
                    success=True,
                    result=result
                ))
                logger.info(f"Tool {tc.name} executed: {str(result)[:100]}...")

                # Phase 8B: Push successful results to context stores
                # This enables Rachel to remember what just happened
                event_type = tc.name.replace("_", ".")
                result_str = str(result) if result else "Done"

                # 1. Push to SystemContextStore (for relevance-based queries)
                context_store.store(
                    event_type=event_type,
                    result=result_str,
                    metadata={"tool_args": tc.arguments}
                )
                logger.debug(f"Pushed to SystemContextStore: {event_type}")

                # 2. Push to NotificationQueue (for immediate feedback)
                notification_queue.add_notification(
                    job_id=tc.id,
                    event_type=event_type,
                    result=result_str,
                    metadata={"tool_args": tc.arguments}
                )
                logger.debug(f"Pushed to NotificationQueue: {event_type}")

            except Exception as e:
                logger.error(f"Tool {tc.name} failed: {e}")
                results.append(ToolResult(
                    tool_name=tc.name,
                    success=False,
                    result=None,
                    error=str(e)
                ))

        return results

    def _generate_summary(self, request: str, results: List[ToolResult]) -> str:
        """Generate natural language summary of results."""
        if not results:
            # No tools called - might be a greeting or unclear request
            return "How can I help you?"

        # Collect successful results
        success_messages = []
        error_messages = []

        for r in results:
            if r.success and r.result:
                # Use the tool result directly if it's a string
                if isinstance(r.result, str):
                    success_messages.append(r.result)
                elif isinstance(r.result, dict) and "message" in r.result:
                    success_messages.append(r.result["message"])
                else:
                    success_messages.append(f"{r.tool_name} successful")
            elif r.error:
                error_messages.append(r.error)

        # Build response
        if success_messages and not error_messages:
            if len(success_messages) == 1:
                return success_messages[0]
            return " ".join(success_messages)

        if error_messages and not success_messages:
            return f"Error: {'; '.join(error_messages)}"

        if success_messages and error_messages:
            return f"{' '.join(success_messages)} (But: {'; '.join(error_messages)})"

        return "Done."


# Singleton
_tool_orchestrator: Optional[ToolOrchestrator] = None


def get_tool_orchestrator() -> ToolOrchestrator:
    """Get or create ToolOrchestrator singleton."""
    global _tool_orchestrator
    if _tool_orchestrator is None:
        _tool_orchestrator = ToolOrchestrator()
    return _tool_orchestrator


__all__ = [
    "ToolOrchestrator",
    "ToolCall",
    "ToolResult",
    "OrchestrationResult",
    "get_tool_orchestrator",
    "ORCHESTRATOR_SYSTEM_PROMPT",
]
