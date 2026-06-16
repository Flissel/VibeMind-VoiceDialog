"""BrainMultihopBridge — Phase -2 capability-routed bridge.

Routes voice intents through Brain's /api/multihop/execute → CapabilityRouter
→ MCPExecutor / OpenFangExecutor (whatever the matched capability's
execution_target specifies). For our prototype usage, "erstelle einen
openfang agent für X" matches the `openfang_agent_create` capability whose
target is `mcp:openfang-agents:openfang_agent_spawn_from_template`, so Brain
fans out to the openfang-agents stdio MCP server (registered in .mcp.json)
which wraps POST :4200/api/agents — same path Claude Code uses.

Distinct from `BrainOpenFangBridge` (Phase -1, cortex/route → Space-Router)
on purpose: that one picks a *space* and dispatches to a pre-existing
OpenFang agent. This one drives the *CapabilityRouter*, which is what our
new `openfang_agent_create` registry entry actually feeds.

Wired in `IntentOrchestrator` as Phase -2, called *before* Phase -1. On
no-cap-match / brain-down / timeout, return None → existing Phase -1 takes
over (and through it the HybridRouter), preserving the default behavior
bit-for-bit when VOICE_BRAIN_MULTIHOP=false.

Activation: env `VOICE_BRAIN_MULTIHOP=true`. Default off.

Graceful degradation:
- Brain down       → mark unavailable, 30s backoff, fall through
- Timeout >6s      → fall through
- HTTP non-2xx     → fall through
- `ok: false`      → fall through (no cap matched, planner returned no plan)
- empty final_text → try executed-hop summary, else fall through
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import aiohttp

from swarm.orchestrator.result_formatter import OrchestrationResult

logger = logging.getLogger(__name__)


class BrainMultihopBridge:
    """Phase -2 voice→brain→cap bridge. POSTs to /api/multihop/execute."""

    def __init__(
        self,
        brain_url: str = "http://localhost:5000",
        request_timeout_s: float = 6.0,
        backoff_seconds: float = 30.0,
    ):
        # cortex's 0.5s timeout is too tight here: multihop may invoke
        # the final_synthesizer LLM, plus the MCPExecutor stdio roundtrip.
        # 6s covers a typical OpenFang spawn (~5s) + overhead. Above that
        # we'd rather fall through than block voice.
        self._brain_url = brain_url.rstrip("/")
        self._request_timeout = request_timeout_s
        self._backoff = backoff_seconds
        self._available = True

    # ------------------------------------------------------------------
    # Public API — matches BrainOpenFangBridge.execute() signature so the
    # orchestrator can hold both bridges side-by-side.
    # ------------------------------------------------------------------

    async def execute(
        self,
        intent_text: str,
        context: Any = None,                # v1: not forwarded; multihop builds its own state
        pre_classification: str = "",       # ignored — CapabilityRouter does its own matching
    ) -> Optional[OrchestrationResult]:
        """POST /api/multihop/execute with the raw intent text.

        Returns OrchestrationResult only when Brain reports ok=true AND a
        non-empty final_text (or a synthesizable executed-hop summary).
        Returns None in every other case so Phase -1 / HybridRouter run.
        Never raises.
        """
        if not self._available:
            return None

        text = (intent_text or "").strip()
        if not text:
            return None

        data = await self._post_multihop(text)
        if data is None:
            return None

        # CapabilityRouter found nothing OR planner gave up. The Brain side
        # signals this with ok=false (introspection.py:2392). Quiet fall-through.
        if not data.get("ok"):
            return None

        final_text = (data.get("final_text") or "").strip()
        executed = data.get("executed") or {}
        if not final_text and executed:
            final_text = self._summarize_executed(executed)
        if not final_text:
            # Nothing for voice to say. Treat as no-result, fall through.
            return None

        # state may carry the matched capability name (final_space etc.) —
        # useful for the job_id so memory + telemetry can correlate.
        state = data.get("state") or {}
        cap = state.get("capability") or state.get("matched_capability") or ""
        job_id = data.get("plan_id") or (f"brain-multihop:{cap}" if cap else "brain-multihop")

        logger.info(
            f"[MultihopBridge] match \"{text[:60]}...\" "
            f"-> cap={cap or '(unknown)'} hops={len(executed)} "
            f"len(final_text)={len(final_text)}"
        )

        return OrchestrationResult(
            job_id=job_id,
            event_type="brain.multihop",
            stream="brain",
            response_hint=final_text,
            is_conversational=False,
        )

    # ------------------------------------------------------------------
    # Brain communication
    # ------------------------------------------------------------------

    async def _post_multihop(self, intent_text: str) -> Optional[Dict[str, Any]]:
        """POST /api/multihop/execute, return parsed JSON or None on any failure."""
        try:
            timeout = aiohttp.ClientTimeout(total=self._request_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self._brain_url}/api/multihop/execute",
                    json={"intent": intent_text},
                ) as resp:
                    if resp.status != 200:
                        logger.debug(
                            f"[MultihopBridge] brain returned {resp.status}, fall-through"
                        )
                        return None
                    return await resp.json()
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            # Connection refused, DNS fail, OR timeout — Brain is effectively
            # unavailable. On Windows, a refused-connect to a non-listening
            # port surfaces as TimeoutError (aiohttp keeps retrying the
            # connect for the full request_timeout), so both need the same
            # backoff treatment — otherwise every voice utterance would burn
            # the full 6s waiting for a Brain that won't answer.
            # Same 30s backoff pattern as BrainOpenFangBridge.
            self._available = False
            try:
                asyncio.get_event_loop().call_later(self._backoff, self._re_enable)
            except RuntimeError:
                # No running loop (rare; e.g. called outside async ctx).
                # Mark unavailable; next event-loop tick may recover.
                pass
            kind = "timeout" if isinstance(e, asyncio.TimeoutError) else f"unreachable ({e})"
            logger.warning(
                f"[MultihopBridge] brain {kind} after {self._request_timeout}s, "
                f"disabled {self._backoff}s"
            )
            return None
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[MultihopBridge] unexpected error: {e}")
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize_executed(executed: Dict[str, Any]) -> str:
        """Build a 1-line voice-friendly summary from the hops dict.

        Used only when Brain's `final_synthesizer` produced no text
        (e.g. syn is None in introspection.py:2404). Better than silence,
        worse than a real synthesizer — caller code prefers final_text.
        """
        if not executed:
            return ""
        # `executed` is {hop_0: {capability, ok, result}, hop_1: ...}
        parts = []
        for key in sorted(executed.keys()):
            hop = executed.get(key) or {}
            if not isinstance(hop, dict):
                continue
            cap = hop.get("capability") or hop.get("name") or "?"
            ok = hop.get("ok", False)
            parts.append(f"{cap}={'ok' if ok else 'fail'}")
        if not parts:
            return ""
        return f"executed {len(parts)} hop(s): " + ", ".join(parts)

    def _re_enable(self) -> None:
        """Re-enable bridge after backoff window expires."""
        self._available = True
        logger.info("[MultihopBridge] re-enabled after backoff")
