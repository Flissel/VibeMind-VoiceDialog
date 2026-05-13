"""BrainOpenFangBridge — routes via Brain, executes via OpenFang, rewards on result.

Phase -1 in IntentOrchestrator: activated only when Brain has graduated
(brain_shadow._active == True, i.e. 95% routing accuracy).

Flow:
1. ContextAssembler gathers VibeMind workspace state
2. Brain /api/cortex/route receives enriched user_text + context → routing decision
3. Space mapped to OpenFang agent via SPACE_AGENT_MAP
4. OpenFang /api/agents/{id}/message receives context-enriched message
5. Brain /api/cortex/route/reward receives success/failure feedback
6. OrchestrationResult returned to voice pipeline

Graceful degradation:
- Brain down → return None → HybridRouter handles
- OpenFang down → return None → SyncExecutor handles
- Timeout > 1.5s → quick ack + background execution
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import aiohttp

from swarm.orchestrator.result_formatter import OrchestrationResult
from swarm.routing.context_assembler import ContextAssembler, WorkspaceContext
from swarm.routing.space_agent_registry import RoutingRecipe, SpaceAgentRegistry

logger = logging.getLogger(__name__)

# Legacy fallback map — used when registry YAML absent or VIBEMIND_ROUTING_REGISTRY=off.
# New routing is driven by config/space_agent_registry.yml.
LEGACY_SPACE_AGENT_MAP: Dict[str, str] = {
    "ideas": "vibemind",
    "bubbles": "vibemind",
    "coding": "brain-coder",
    "desktop": "vibemind",
    "research": "vibemind",
    "n8n": "vibemind",
    "schedule": "vibemind",
    "roarboot": "rowboat-knowledge",
    "agentfarm": "vibemind",
    "video": "vibemind",
    "flowzen": "vibemind",
    "mirofish": "vibemind",
    "minibook": "vibemind",
}

# Kept as alias for backwards-compat with any external import.
SPACE_AGENT_MAP = LEGACY_SPACE_AGENT_MAP


class BrainOpenFangBridge:
    """Routes intents via Brain and executes via OpenFang agents."""

    def __init__(
        self,
        brain_url: str = "http://localhost:5000",
        openfang_url: str = "http://localhost:4200",
        space_agent_map: Optional[Dict[str, str]] = None,
        voice_timeout_s: float = 1.5,
        min_confidence: float = 0.0,
    ):
        self._brain_url = brain_url.rstrip("/")
        self._openfang_url = openfang_url.rstrip("/")
        self._space_map = space_agent_map or LEGACY_SPACE_AGENT_MAP
        self._voice_timeout = voice_timeout_s
        self._min_confidence = min_confidence
        self._assembler = ContextAssembler()
        self._agent_cache: Dict[str, str] = {}  # agent_name → agent_id
        self._available = True
        self._registry = SpaceAgentRegistry.load_or_legacy(legacy=self._space_map)
        self._registry_mode = os.getenv("VIBEMIND_ROUTING_REGISTRY", "shadow").lower()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self,
        intent_text: str,
        context: Any = None,
        pre_classification: str = "",
    ) -> Optional[OrchestrationResult]:
        """Full pipeline: context → Brain route → OpenFang execute → reward.

        Returns OrchestrationResult on success, None to fall through to
        HybridRouter/SyncExecutor.
        """
        if not self._available:
            return None

        start = time.perf_counter()

        # 1. Assemble workspace context (~5ms)
        try:
            workspace_ctx = await self._assembler.assemble_async(intent_text)
        except Exception as e:
            logger.debug(f"[BrainBridge] Context assembly failed: {e}")
            workspace_ctx = WorkspaceContext()

        # 2. Route via Brain (~100ms, 500ms timeout)
        brain_prefix = ContextAssembler.to_brain_prefix(workspace_ctx)
        enriched_text = f"{brain_prefix} {intent_text}".strip()
        context_dict = ContextAssembler.to_brain_context_dict(workspace_ctx)

        brain_result = await self._route_via_brain(enriched_text, pre_classification, context_dict)
        if not brain_result:
            return None
        if brain_result["confidence"] < self._min_confidence:
            logger.debug(
                f"[BrainBridge] Low confidence {brain_result['confidence']:.0%}, "
                f"falling through"
            )
            return None

        space = brain_result["space"]
        routing_id = brain_result.get("routing_id", "")

        # 3. Map space → OpenFang agent (via registry; legacy dict when OFF)
        recipe = None
        if self._registry_mode != "off":
            recipe = self._registry.lookup(space, pre_classification)
            if recipe is None:
                recipe = self._registry.fallback(space)

            # Shadow mode: log divergence but still execute via registry
            if self._registry_mode == "shadow":
                legacy_agent = self._space_map.get(space, "")
                if recipe.agent != legacy_agent:
                    logger.info(
                        f"[BrainBridge.shadow] divergence space={space} "
                        f"legacy={legacy_agent} registry={recipe.agent}"
                    )

        agent_name = recipe.agent if recipe else self._space_map.get(space)
        if not agent_name:
            logger.warning(f"[BrainBridge] No agent mapped for space '{space}'")
            return None

        agent_id = await self._ensure_agent(agent_name)
        if not agent_id:
            return None

        # 4. Build structured JSON envelope (schema: vibemind.intent.v1)
        if recipe and not recipe.is_fallback:
            context_fields = recipe.context_fields or None
            context_json = ContextAssembler.to_json_context(workspace_ctx, context_fields)
            envelope = {
                "schema": "vibemind.intent.v1",
                "event_type": pre_classification,
                "space": space,
                "preferred_tool": recipe.tool_hint,
                "required_params": recipe.required_params,
                "mcp_scope": recipe.mcp_scope,
                "context": context_json,
                "user_text": intent_text,
            }
            message = json.dumps(envelope, ensure_ascii=False)
        else:
            # Fallback path — legacy markdown block for unknown/generic agents
            context_block = ContextAssembler.to_openfang_block(workspace_ctx)
            message = f"{context_block}\n\n{intent_text}"

        tool_hint = recipe.tool_hint if recipe else ""
        logger.info(
            f"[BrainBridge] Routed \"{intent_text[:50]}...\" "
            f"-> {space} ({brain_result['confidence']:.0%}) "
            f"-> {agent_name} [tool={tool_hint or '-'}]"
        )

        # 5. Execute with voice timeout
        try:
            response_text = await asyncio.wait_for(
                self._send_to_openfang(agent_id, message),
                timeout=self._voice_timeout,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            logger.info(f"[BrainBridge] {agent_name} responded in {latency_ms:.0f}ms")

            # 6. Reward Brain (fire-and-forget)
            asyncio.create_task(self._reward_brain(routing_id, success=True))

            return OrchestrationResult(
                job_id=routing_id or f"brain-{space}",
                event_type=pre_classification or f"brain.{space}",
                stream=space,
                response_hint=response_text,
                is_conversational=False,
            )

        except asyncio.TimeoutError:
            logger.info(
                f"[BrainBridge] {agent_name} timeout after {self._voice_timeout}s, "
                f"continuing in background"
            )
            # Background execution
            asyncio.create_task(
                self._background_execute(agent_id, message, routing_id, space, pre_classification)
            )
            return OrchestrationResult(
                job_id=routing_id or f"brain-{space}",
                event_type=pre_classification or f"brain.{space}",
                stream=space,
                response_hint="Ich arbeite daran...",
                is_conversational=False,
            )

        except Exception as e:
            logger.warning(f"[BrainBridge] OpenFang execution failed: {e}")
            asyncio.create_task(self._reward_brain(routing_id, success=False))
            return None

    # ------------------------------------------------------------------
    # Brain communication
    # ------------------------------------------------------------------

    async def _route_via_brain(
        self,
        user_text: str,
        event_type: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """POST /api/cortex/route with enriched payload."""
        try:
            timeout = aiohttp.ClientTimeout(total=0.5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {
                    "user_text": user_text,
                    "event_type": event_type,
                }
                if context:
                    payload["context"] = context

                async with session.post(
                    f"{self._brain_url}/api/cortex/route",
                    json=payload,
                ) as resp:
                    if resp.status != 200:
                        logger.debug(f"[BrainBridge] Brain route returned {resp.status}")
                        return None
                    data = await resp.json()
                    return {
                        "space": data.get("primary_space", ""),
                        "confidence": data.get("confidence", 0),
                        "routing_id": data.get("routing_id", ""),
                    }
        except aiohttp.ClientError:
            self._available = False
            asyncio.get_event_loop().call_later(30, self._re_enable)
            logger.warning("[BrainBridge] Brain unavailable, disabling for 30s")
            return None
        except Exception as e:
            logger.debug(f"[BrainBridge] Brain route failed: {e}")
            return None

    async def _reward_brain(self, routing_id: str, success: bool) -> None:
        """POST /api/cortex/route/reward (fire-and-forget)."""
        if not routing_id:
            return
        try:
            timeout = aiohttp.ClientTimeout(total=1.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                await session.post(
                    f"{self._brain_url}/api/cortex/route/reward",
                    json={"routing_id": routing_id, "success": success},
                )
        except Exception as e:
            logger.debug(f"[BrainBridge] Reward failed (non-critical): {e}")

    # ------------------------------------------------------------------
    # OpenFang communication
    # ------------------------------------------------------------------

    async def ensure_agent(self, agent_name: str) -> Optional[str]:
        """Public: ensure an OpenFang agent is running, returns agent_id.

        Usable standalone from Phase 0 (HybridRouter direct-exec) when
        USE_OPENFANG_DIRECT is enabled, without needing the full Phase -1
        Brain-bridge flow.
        """
        return await self._ensure_agent(agent_name)

    async def send_to_agent(self, agent_id: str, message: str) -> str:
        """Public: send a message to an OpenFang agent, return the response.

        Mirrors execute() but without the Brain routing / reward steps, so
        callers that already know which tool/agent to use can short-circuit.
        """
        return await self._send_to_openfang(agent_id, message)

    def space_to_agent(self, space: str) -> Optional[str]:
        """Public: look up which OpenFang agent handles a given VibeMind space."""
        return self._space_map.get(space)

    async def _ensure_agent(self, agent_name: str) -> Optional[str]:
        """Ensure an OpenFang agent is running. Returns agent_id or None."""
        # Check cache first
        if agent_name in self._agent_cache:
            return self._agent_cache[agent_name]

        try:
            timeout = aiohttp.ClientTimeout(total=0.3)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # List agents to find by name
                async with session.get(f"{self._openfang_url}/api/agents") as resp:
                    if resp.status != 200:
                        return None
                    agents = await resp.json()

                # Find existing agent by name
                for agent in agents:
                    if agent.get("name") == agent_name:
                        agent_id = agent.get("id", "")
                        self._agent_cache[agent_name] = agent_id
                        return agent_id

                # Agent doesn't exist — spawn it
                async with session.post(
                    f"{self._openfang_url}/api/agents",
                    json={"name": agent_name},
                ) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        agent_id = data.get("id", "")
                        self._agent_cache[agent_name] = agent_id
                        logger.info(f"[BrainBridge] Spawned OpenFang agent: {agent_name} ({agent_id})")
                        return agent_id
                    else:
                        logger.warning(f"[BrainBridge] Failed to spawn {agent_name}: {resp.status}")
                        return None

        except Exception as e:
            logger.debug(f"[BrainBridge] Agent ensure failed for {agent_name}: {e}")
            return None

    async def _send_to_openfang(self, agent_id: str, message: str) -> str:
        """POST /api/agents/{id}/message → response text."""
        timeout = aiohttp.ClientTimeout(total=10.0)  # Outer timeout managed by caller
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self._openfang_url}/api/agents/{agent_id}/message",
                json={"message": message},
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"OpenFang returned {resp.status}")
                data = await resp.json()
                # Extract response text from OpenFang's response format
                if isinstance(data, dict):
                    return (
                        data.get("response", "")
                        or data.get("message", "")
                        or data.get("text", "")
                        or str(data)
                    )
                return str(data)

    # ------------------------------------------------------------------
    # Background execution (for voice timeout cases)
    # ------------------------------------------------------------------

    async def _background_execute(
        self,
        agent_id: str,
        message: str,
        routing_id: str,
        space: str,
        event_type: str,
    ) -> None:
        """Continue OpenFang execution in background after voice timeout."""
        try:
            response_text = await self._send_to_openfang(agent_id, message)
            logger.info(f"[BrainBridge] Background: {space} completed")
            await self._reward_brain(routing_id, success=True)

            # Notify voice pipeline of background completion
            try:
                from tools.workspace_tools import _broadcast_to_electron
                _broadcast_to_electron({
                    "type": "brain_bridge_result",
                    "space": space,
                    "event_type": event_type,
                    "response": response_text,
                    "routing_id": routing_id,
                })
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"[BrainBridge] Background execution failed: {e}")
            await self._reward_brain(routing_id, success=False)

    # ------------------------------------------------------------------
    # Availability management
    # ------------------------------------------------------------------

    def _re_enable(self) -> None:
        """Re-enable after backoff (called via call_later)."""
        self._available = True
        logger.info("[BrainBridge] Re-enabled after backoff")
