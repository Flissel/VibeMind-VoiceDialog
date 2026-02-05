"""
BaseBroadcastAgent - Foundation for fan-out broadcast agents.

Each agent independently evaluates responsibility and either
executes actions or profiles user behavior.

Migrates core functionality from BaseBackendAgent:
- Parameter normalization (PARAM_MAPPING)
- Transcript-based parameter extraction
- Context reference resolution

Subclasses must define:
- name: Agent identifier
- domain_prefixes: Set of event_type prefixes this agent handles
- profiling_perspective: Description for user profiling
- EVENT_TO_TOOL: Dict mapping event_type → tool function name
- PARAM_MAPPING: Dict mapping event_type → {classifier_param: tool_param}
- _load_tools(): Returns dict mapping tool names to functions
"""

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Set, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm.broadcast.dispatcher import IntentPayload

logger = logging.getLogger(__name__)


@dataclass
class ResponsibilityEvaluation:
    """Result of evaluating whether this agent is responsible."""
    is_responsible: bool
    confidence: float  # 0.0 - 1.0
    reasoning: str = ""
    domain_perspective: str = ""


class BaseBroadcastAgent(ABC):
    """
    Abstract base for agents participating in fan-out broadcast.

    Combines:
    - Responsibility evaluation (rule-based prefix matching)
    - Tool execution (migrated from BaseBackendAgent)
    - User profiling (new: via MemorySubAgent)
    - Context tracking (new: via ContextSubAgent)
    """

    # Subclasses must define these:
    EVENT_TO_TOOL: Dict[str, str] = {}
    PARAM_MAPPING: Dict[str, Dict[str, str]] = {}

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._memory_sub_agent = None
        self._context_sub_agent = None
        self._tools_loaded = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent identifier."""
        pass

    @property
    @abstractmethod
    def domain_prefixes(self) -> Set[str]:
        """Event type prefixes this agent handles (e.g., {'idea.', 'bubble.'})."""
        pass

    @property
    @abstractmethod
    def profiling_perspective(self) -> str:
        """Description of this agent's perspective for user profiling."""
        pass

    @property
    def tools(self) -> Dict[str, Callable]:
        """Lazy-load tools."""
        if not self._tools_loaded:
            self._tools = self._load_tools()
            self._tools_loaded = True
        return self._tools

    def set_memory_sub_agent(self, agent):
        """Set the memory sub-agent for user profiling."""
        self._memory_sub_agent = agent

    def set_context_sub_agent(self, agent):
        """Set the context sub-agent for transcript tracking."""
        self._context_sub_agent = agent

    # =========================================================================
    # Responsibility Evaluation
    # =========================================================================

    async def evaluate_responsibility(
        self, intent: "IntentPayload"
    ) -> ResponsibilityEvaluation:
        """
        Evaluate if this agent is responsible for the given intent.

        Fast rule-based check using domain_prefixes.
        Override for more sophisticated evaluation.
        """
        event_type = intent.event_type

        for prefix in self.domain_prefixes:
            if event_type.startswith(prefix):
                return ResponsibilityEvaluation(
                    is_responsible=True,
                    confidence=1.0,
                    reasoning=f"Event '{event_type}' matches prefix '{prefix}'",
                    domain_perspective=self.profiling_perspective,
                )

        return ResponsibilityEvaluation(
            is_responsible=False,
            confidence=0.0,
            reasoning=f"Event '{event_type}' not in {self.domain_prefixes}",
            domain_perspective=self.profiling_perspective,
        )

    # =========================================================================
    # Tool Execution (migrated from BaseBackendAgent._handle_event)
    # =========================================================================

    async def execute(self, intent: "IntentPayload") -> str:
        """
        Execute the intent using this agent's tools.

        Replaces BaseBackendAgent._handle_event() with:
        1. Parameter normalization
        2. Context reference resolution
        3. Transcript-based fallback extraction
        4. Tool execution
        5. Context sub-agent notification

        Args:
            intent: The classified intent to execute

        Returns:
            Result string from tool execution
        """
        event_type = intent.event_type
        payload = dict(intent.payload)  # Copy to avoid mutation

        # Get tool name
        tool_name = self.EVENT_TO_TOOL.get(event_type)
        if not tool_name:
            return f"Unbekannter Event-Typ: {event_type}"

        tool = self.tools.get(tool_name)
        if not tool:
            return f"Tool nicht gefunden: {tool_name}"

        # Remove internal fields from payload
        tool_params = {
            k: v for k, v in payload.items()
            if k not in (
                "job_id", "user_id", "session_id", "priority",
                "bubble_context", "metadata", "_user_input",
                "_conversation_history",
            )
        }

        # Extract user_input and conversation_history
        user_input = payload.get("_user_input", "") or intent.user_input
        conversation_history = (
            payload.get("_conversation_history", []) or intent.conversation_history
        )

        # Step 1: Normalize parameter names
        tool_params = self._normalize_params(event_type, tool_params)

        # Step 2: Resolve contextual references from conversation history
        if conversation_history:
            context_resolved = self._resolve_context_references(
                event_type, user_input, tool_params, conversation_history
            )
            for key, value in context_resolved.items():
                if key not in tool_params or not tool_params.get(key):
                    tool_params[key] = value
                    logger.info(
                        f"{self.name}: Resolved '{key}' from conversation context"
                    )

        # Step 3: Fallback - extract missing params from transcript
        if user_input:
            extracted = self._extract_params_from_transcript(event_type, user_input)
            for key, value in extracted.items():
                if key not in tool_params or not tool_params.get(key):
                    tool_params[key] = value
                    logger.info(
                        f"{self.name}: Filled '{key}' from transcript"
                    )

        # Step 4: Execute tool
        logger.info(
            f"{self.name}: Executing {tool_name} for {event_type} "
            f"with params: {list(tool_params.keys())}"
        )

        result = tool(**tool_params)
        if asyncio.iscoroutine(result):
            result = await result

        # Step 5: Notify context sub-agent
        if self._context_sub_agent:
            try:
                await self._context_sub_agent.record_execution(intent, result)
            except Exception as e:
                logger.debug(f"{self.name}: Context recording failed: {e}")

        logger.info(f"{self.name}: Completed {event_type}")
        return result

    # =========================================================================
    # User Profiling (new capability)
    # =========================================================================

    async def profile_user(
        self, intent: "IntentPayload"
    ) -> Optional[Dict[str, Any]]:
        """
        Profile user behavior from this agent's domain perspective.

        Called when this agent is NOT responsible for the intent.
        Analyzes the intent and stores behavioral observations to Supermemory.

        Returns:
            Profiling insight dict, or None if nothing noteworthy.
        """
        if self._memory_sub_agent:
            return await self._memory_sub_agent.analyze_intent(
                intent=intent,
                perspective=self.profiling_perspective,
            )
        return None

    # =========================================================================
    # Parameter Normalization (migrated from BaseBackendAgent)
    # =========================================================================

    def _normalize_params(
        self, event_type: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Normalize parameter names for a given event type.

        Maps classifier output names to tool expected names using PARAM_MAPPING.
        Also handles "_inject" key for fixed parameter injection.

        Migrated 1:1 from BaseBackendAgent._normalize_params.
        """
        mapping = self.PARAM_MAPPING.get(event_type, {})
        if not mapping:
            return params

        normalized = {}
        for key, value in params.items():
            new_key = mapping.get(key, key)
            if new_key not in normalized:
                normalized[new_key] = value
            elif key not in mapping:
                normalized[key] = value

        # Handle _inject for fixed parameter injection
        inject_params = mapping.get("_inject", {})
        if inject_params:
            for inject_key, inject_value in inject_params.items():
                if inject_key not in normalized:
                    normalized[inject_key] = inject_value
                    logger.debug(
                        f"Injected param for {event_type}: {inject_key}={inject_value}"
                    )

        logger.debug(f"Normalized params for {event_type}: {params} -> {normalized}")
        return normalized

    # =========================================================================
    # Transcript Parameter Extraction (migrated from BaseBackendAgent)
    # =========================================================================

    def _extract_params_from_transcript(
        self, event_type: str, user_input: str
    ) -> Dict[str, Any]:
        """
        Extract missing parameters from user transcript using regex.

        Fallback when the LLM doesn't extract parameters properly.
        Migrated from BaseBackendAgent._extract_params_from_transcript.
        """
        if not user_input:
            return {}

        extracted = {}

        if event_type == "bubble.enter":
            patterns = [
                r"(?:space|bubble|bereich)\s+['\"]?([^'\"]+?)['\"]?\s*$",
                r"(?:space|bubble|bereich)\s+['\"]?([^'\"]+?)['\"]?(?:\s+und|\s+dann|\.|$)",
                r"(?:in|zu|nach)\s+(?:den?\s+)?(?:space|bubble)?\s*['\"]?([A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df][A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df0-9\s-]+)",
                r"navigiere?\s+(?:in|zu|nach)?\s*['\"]?([A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df][A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df0-9\s-]+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    name = re.sub(
                        r'\s+(und|dann|rein|hinein)$', '', name, flags=re.IGNORECASE
                    )
                    if name and len(name) > 1:
                        extracted["bubble_name"] = name
                        break

        elif event_type == "idea.create":
            patterns = [
                r"(?:idee|note|notiz)\s+['\"]?([^'\"]+?)['\"]?\s*$",
                r"erstelle\s+(?:eine?\s+)?(?:idee|note|notiz)?\s*['\"]?(.+?)(?:\s+(?:mit|und|im)|$)",
                r"(?:neue?|erstelle)\s+(?:idee|note|notiz)\s+['\"]?(.+?)['\"]?(?:\s|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    title = match.group(1).strip()
                    if title and len(title) > 1:
                        extracted["title"] = title
                        break

        elif event_type == "idea.find":
            patterns = [
                r"(?:suche?|finde?)\s+(?:nach\s+)?['\"]?(.+?)['\"]?(?:\s|$)",
                r"(?:zeig|list)e?\s+(?:mir\s+)?(?:idee|note)?\s*['\"]?(.+?)['\"]?(?:\s|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    query = match.group(1).strip()
                    if query and len(query) > 1:
                        extracted["query"] = query
                        break

        elif event_type == "idea.connect":
            patterns = [
                r"(?:verbinde|verlinke|connect)\s+['\"]?(.+?)['\"]?\s+(?:mit|und|with|to)\s+['\"]?(.+?)['\"]?(?:\s|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    extracted["idea1"] = match.group(1).strip()
                    extracted["idea2"] = match.group(2).strip()
                    break

        if extracted:
            logger.info(f"{self.name}: Extracted params from transcript: {extracted}")

        return extracted

    # =========================================================================
    # Context Reference Resolution (migrated from BaseBackendAgent)
    # =========================================================================

    def _resolve_context_references(
        self,
        event_type: str,
        user_input: str,
        tool_params: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Resolve contextual references (alle, die, das, sie) from conversation history.

        Migrated from BaseBackendAgent._resolve_context_references.
        """
        resolved = {}
        user_input_lower = user_input.lower() if user_input else ""

        context_keywords = [
            "alle", "die", "das", "sie", "es", "diese", "jene", "davon"
        ]
        has_context_reference = any(kw in user_input_lower for kw in context_keywords)

        if not has_context_reference:
            return resolved

        if event_type in ["bubble.delete", "idea.delete", "bubble.list"]:
            for msg in reversed(conversation_history):
                if msg.get("speaker") in ["rachel", "assistant", "agent"]:
                    text = msg.get("text", "")
                    text_lower = text.lower()

                    list_indicators = [
                        "hier sind", "du hast", "folgende",
                        "diese bubbles", "diese spaces",
                    ]
                    if any(ind in text_lower for ind in list_indicators):
                        names = re.findall(
                            r'(?:^|\n)\s*[-\u2022\u25cf\d.)\]]\s*'
                            r'([A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df]'
                            r'[A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df0-9\s-]+?)'
                            r'(?:\s*[-\u2013:(\n]|$)',
                            text,
                        )
                        if names:
                            cleaned = [
                                n.strip() for n in names
                                if n.strip() and len(n.strip()) > 1
                            ]
                            if cleaned and "alle" in user_input_lower:
                                resolved["_targets"] = cleaned
                                resolved["_target_type"] = "all"
                                logger.info(
                                    f"{self.name}: Resolved 'alle' to "
                                    f"{len(cleaned)} items: {cleaned}"
                                )
                                break

                        # "Marketing, Sales und Ideas"
                        comma_pattern = (
                            r'([A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df]'
                            r'[A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df0-9-]+'
                            r'(?:\s*,\s*[A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df]'
                            r'[A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df0-9-]+)+'
                            r'(?:\s+und\s+[A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df]'
                            r'[A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df0-9-]+)?)'
                        )
                        comma_match = re.search(comma_pattern, text)
                        if comma_match:
                            items = re.split(
                                r'\s*,\s*|\s+und\s+', comma_match.group(1)
                            )
                            cleaned = [
                                n.strip() for n in items
                                if n.strip() and len(n.strip()) > 1
                            ]
                            if cleaned:
                                resolved["_targets"] = cleaned
                                resolved["_target_type"] = "all"
                                logger.info(
                                    f"{self.name}: Resolved 'alle' from "
                                    f"comma list to: {cleaned}"
                                )
                                break

        elif event_type == "bubble.enter":
            for msg in reversed(conversation_history):
                text = msg.get("text", "")
                mentions = re.findall(
                    r'(?:space|bubble|bereich)\s+["\']?'
                    r'([A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df]'
                    r'[A-Za-z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df0-9\s-]+)',
                    text,
                    re.IGNORECASE,
                )
                if mentions:
                    resolved["bubble_name"] = mentions[-1].strip()
                    logger.info(
                        f"{self.name}: Resolved context reference "
                        f"to bubble: {resolved['bubble_name']}"
                    )
                    break

        return resolved

    # =========================================================================
    # Abstract: Tool Loading
    # =========================================================================

    @abstractmethod
    def _load_tools(self) -> Dict[str, Callable]:
        """
        Load tools for this agent.

        Returns:
            Dict mapping tool function names to callable functions
        """
        pass


__all__ = ["BaseBroadcastAgent", "ResponsibilityEvaluation"]
