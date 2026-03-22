"""
Flowzen Brain Bridge — Sends 30-min summaries to Brain/Tahlamus.

If Brain is available (BRAIN_SERVER_URL), POST to /api/knowledge/feed.
Otherwise, use local LLM to generate the cognitive decision.

The bridge converts Rose's situation summary into a Brain-compatible signal
and processes the response back into a Rose-compatible decision.
"""

import logging
import os
from typing import Any, Callable, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

BRAIN_DECISION_PROMPT = """Du bist der kognitive Entscheider im VibeMind Brain/Tahlamus System.

Du erhaelst eine 30-Minuten-Zusammenfassung vom Blaue-Rose-Aktivitaetstracker.
Entscheide basierend auf neurowissenschaftlichen Prinzipien:

1. "suggest_task" — Wenn der User produktiv sein koennte (gute Tageszeit, nicht ueberlastet)
2. "suggest_rest" — Wenn Ermuedungszeichen erkennbar sind (lange Inaktivitaet, Nachtzeit, hohe Frequenz gefolgt von Abbruch)
3. "do_nothing" — Im Zweifel: nicht stoeren (DEFAULT)

Antworte NUR mit einem JSON-Objekt:
{
    "action": "suggest_task" | "suggest_rest" | "do_nothing",
    "reasoning": "1-2 Saetze warum",
    "category": "deep_work|creative|admin|social|rest" (nur bei suggest_task)
}"""


class FlowzenBrainBridge:
    """Bridge between Blaue Rose and Brain/Tahlamus."""

    def __init__(self):
        self._brain_url = os.getenv("BRAIN_SERVER_URL", "http://localhost:5000")
        self._brain_available: Optional[bool] = None
        self._rose_callback: Optional[Callable] = None

    def set_rose_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback to send Brain decisions back to Rose."""
        self._rose_callback = callback

    async def process_summary(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a 30-min summary from the ActivityTracker.

        Try Brain first, fall back to local LLM.
        Returns decision dict: {action, reasoning, category?}
        """
        decision = await self._try_brain(summary)

        if decision is None:
            decision = await self._local_decision(summary)

        if self._rose_callback and decision:
            try:
                self._rose_callback(decision)
            except Exception as e:
                logger.warning(f"FlowzenBrain: rose callback failed: {e}")

        return decision

    async def _try_brain(self, summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Try sending summary to Brain microservice."""
        if self._brain_available is False:
            return None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Feed summary as knowledge entry
                payload = {
                    "source": "flowzen_activity_tracker",
                    "content": (
                        f"30-Min Activity Summary: {summary.get('intent_count', 0)} intents, "
                        f"time: {summary.get('time_window', 'unknown')}, "
                        f"types: {summary.get('event_types', {})}"
                    ),
                    "tags": ["flowzen", "circadian", summary.get("time_window", "")],
                    "metadata": summary,
                }

                resp = await client.post(
                    f"{self._brain_url}/api/knowledge/feed",
                    json=payload,
                )

                if resp.status_code == 200:
                    self._brain_available = True
                    data = resp.json()
                    # Brain returns evaluation — parse into decision
                    return self._parse_brain_response(data, summary)
                else:
                    logger.debug(f"FlowzenBrain: Brain returned {resp.status_code}")
                    return None

        except (httpx.ConnectError, httpx.TimeoutException):
            if self._brain_available is None:
                logger.info("FlowzenBrain: Brain not reachable, using local LLM fallback")
            self._brain_available = False
            return None
        except Exception as e:
            logger.debug(f"FlowzenBrain: Brain error: {e}")
            return None

    def _parse_brain_response(self, brain_data: dict, summary: dict) -> Dict[str, Any]:
        """Parse Brain's response into a Rose-compatible decision."""
        # Brain's knowledge feed returns acknowledgment
        # Use the summary data + Brain's state to decide
        intent_count = summary.get("intent_count", 0)
        minutes_idle = summary.get("minutes_since_last_activity", -1)
        time_window = summary.get("time_window", "")

        if minutes_idle > 20 and time_window in ("evening", "night"):
            return {"action": "suggest_rest", "reasoning": "Laengere Inaktivitaet am Abend"}
        elif intent_count > 10:
            return {"action": "suggest_rest", "reasoning": "Hohe Aktivitaet — Pause empfohlen"}
        elif intent_count == 0 and minutes_idle > 15:
            return {
                "action": "suggest_task",
                "reasoning": "Inaktivitaet erkannt — Aufgabenempfehlung",
                "category": summary.get("circadian_matrix", {}).get("calm", "admin"),
            }
        else:
            return {"action": "do_nothing", "reasoning": "Alles normal"}

    async def _local_decision(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Use local LLM to generate Brain decision when Brain is unavailable."""
        import json as json_module

        try:
            from llm_config import get_model, get_async_client

            client = get_async_client("flowzen_reasoning")
            model = get_model("flowzen_reasoning")

            summary_text = (
                f"Zeit: {summary.get('time_window', '?')} ({summary.get('hour', '?')}:00)\n"
                f"Intents in 30 Min: {summary.get('intent_count', 0)}\n"
                f"Event-Typen: {summary.get('event_types', {})}\n"
                f"Minuten seit letzter Aktivitaet: {summary.get('minutes_since_last_activity', -1)}\n"
                f"LLM Reasoning: {summary.get('llm_reasoning', 'n/a')}"
            )

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": BRAIN_DECISION_PROMPT},
                    {"role": "user", "content": summary_text},
                ],
                max_completion_tokens=150,
                temperature=0.3,
            )

            text = response.choices[0].message.content.strip()
            # Parse JSON from response
            if text.startswith("{"):
                return json_module.loads(text)
            # Try to extract JSON from markdown code blocks
            if "```" in text:
                json_str = text.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                return json_module.loads(json_str.strip())

            return {"action": "do_nothing", "reasoning": text[:100]}

        except Exception as e:
            logger.debug(f"FlowzenBrain: local LLM decision failed: {e}")
            # Hardcoded fallback: rule-based
            return self._rule_based_fallback(summary)

    def _rule_based_fallback(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Last-resort rule-based decision when everything else fails."""
        minutes_idle = summary.get("minutes_since_last_activity", -1)
        time_window = summary.get("time_window", "")
        intent_count = summary.get("intent_count", 0)

        if time_window in ("night",) or (time_window == "evening" and minutes_idle > 15):
            return {"action": "suggest_rest", "reasoning": "Spaete Stunde — Pause empfohlen"}
        elif minutes_idle > 20 and intent_count == 0:
            return {
                "action": "suggest_task",
                "reasoning": "Laengere Inaktivitaet",
                "category": "admin",
            }
        return {"action": "do_nothing", "reasoning": "Alles normal"}


_bridge: Optional[FlowzenBrainBridge] = None


def get_brain_bridge() -> FlowzenBrainBridge:
    global _bridge
    if _bridge is None:
        _bridge = FlowzenBrainBridge()
    return _bridge
