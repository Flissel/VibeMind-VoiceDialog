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
- Brain down       → mark unavailable, 30s backoff; the sentence gets "nicht erreichbar" (a hint)
- No connection within CONNECT_TIMEOUT_S → like Brain down
- Answer too slow  → the sentence gets "nicht rechtzeitig" (a hint); no backoff, the next
                     sentence goes to the Brain again (it works serially: 16 s, 33 s happen)
- In the backoff   → the sentence is not sent; it gets "nicht erreichbar" (a hint)
- HTTP non-2xx     → fall through
- `ok: false`      → fall through (no cap matched, planner returned no plan)
- empty final_text → try executed-hop summary, else fall through
"""

from __future__ import annotations

import asyncio
import re
import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

from swarm.orchestrator.result_formatter import OrchestrationResult

logger = logging.getLogger(__name__)

# Event types of a multihop result: the plan ran, a tool refused or failed, the Brain asks back.
EVENT_DONE = "brain.multihop"
EVENT_FAILED = "brain.multihop.failed"
EVENT_QUESTION = "brain.multihop.question"
UNREACHABLE_TEXT = ("Das Gehirn ist gerade nicht erreichbar. Versuch es in ein, zwei Minuten noch einmal; "
                    "geändert habe ich nichts.")
# The request went out but no answer came in time: the Brain may have acted, so no promise.
# The Brain must take the connection within this time; a slow answer is no reason to stop sending.
CONNECT_TIMEOUT_S = 5.0
# What _post_multihop returns when the Brain took the request but gave no answer in time.
_TIMED_OUT = object()
TIMEOUT_TEXT = "Das Gehirn hat nicht rechtzeitig geantwortet. Ob sich etwas geändert hat, weiß ich nicht – sieh bitte nach."
EVENT_HINT = "brain.multihop.hint"  # a hint of the Brain ("keine Spalten"): information, not a failure

# A sentence a person typed into a chat field of the app (electron-app/chat-input.js sets
# eingabe "getippt" in the main process). The field alone does not count for the Brain: the
# app proves it for exactly this sentence with a signature over time and text, made with a
# key shared with the Brain. The key is read here only, never passed on and never logged.
TYPED = "getippt"
HEADER_TYPED = "X-Vibemind-Eingabe"
KEY_NAME = "VIBEMIND_EINGABE_SCHLUESSEL"
KEY_MIN_LENGTH = 32


def eingabe_zeichen(schluessel: str, satz: str, zeit: int) -> str:
    """Signature for exactly this sentence at exactly this time: "<zeit>.<hmac-sha256 hex>".

    Same as eingabe_zeichen() in brain/the_brain/core/desktop_tagesrest.py of the Brain.
    """
    import hashlib
    import hmac

    stoff = f"{int(zeit)}\n{satz}".encode("utf-8")
    return f"{int(zeit)}." + hmac.new(schluessel.encode("utf-8"), stoff, hashlib.sha256).hexdigest()


def typed_request(
    intent_text: str,
    ui_context: Optional[Dict[str, Any]],
    *,
    environ: Optional[Dict[str, str]] = None,
    now: Optional[float] = None,
) -> "tuple[Optional[Dict[str, Any]], Dict[str, str]]":
    """Context and headers for the request to the Brain.

    eingabe "getippt" goes on, with its signature in the header, only when the app marked the
    sentence as typed AND the key is there. Without the key neither field nor header go; any
    other value of eingabe is dropped. The context of the caller is not changed in place.
    """
    import time

    if not isinstance(ui_context, dict) or not ui_context:
        return None, {}
    context = dict(ui_context)
    marked = context.pop("eingabe", None) == TYPED
    headers: Dict[str, str] = {}
    if marked:
        key = (os.environ if environ is None else environ).get(KEY_NAME) or ""
        sentence = (intent_text or "").strip()
        if len(key) >= KEY_MIN_LENGTH and sentence:
            zeit = int(time.time() if now is None else now)
            headers[HEADER_TYPED] = eingabe_zeichen(key, sentence, zeit)
            context["eingabe"] = TYPED
    return (context or None), headers


TRACE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
PLAIN_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")
PLAIN_SPACE = re.compile(r"^[a-z0-9_]{1,32}$")


def ziel_of(value: Any) -> Optional[Dict[str, Any]]:
    """Where the result of an answer lies: {space, bubble_id, node_id} or None.

    The Brain names it in the answer of /api/multihop/execute (and in plan_completed and
    /stand). Only plain ids pass; node_id may be None (a bubble as a whole, e.g. rated).
    A space alone (no bubble_id, e.g. {"space": "desktop"}) is a ziel too: the app goes to
    that space. A bubble_id that is there but not plain drops the whole ziel.
    A promoted project (Software Design) adds a plain projekt_id: the app opens its wizard.
    """
    if not isinstance(value, dict):
        return None
    ziel = _ziel_place(value)
    if ziel is None:
        return None
    projekt = value.get("projekt_id")
    if isinstance(projekt, int) and not isinstance(projekt, bool):
        projekt = str(projekt)
    if isinstance(projekt, str) and PLAIN_ID.match(projekt):
        ziel["projekt_id"] = projekt
    return ziel


def _ziel_place(value: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The place of a ziel: {space, bubble_id, node_id} or None (see ziel_of)."""
    space = value.get("space")
    bubble = value.get("bubble_id")
    node = value.get("node_id")
    if not isinstance(space, str) or not PLAIN_SPACE.match(space):
        return None
    if bubble is None or bubble == "":
        return {"space": space, "bubble_id": None, "node_id": None}
    if isinstance(bubble, int) and not isinstance(bubble, bool):
        bubble = str(bubble)
    if not isinstance(bubble, str) or not PLAIN_ID.match(bubble):
        return None
    if isinstance(node, int) and not isinstance(node, bool):
        node = str(node)
    if node is not None and (not isinstance(node, str) or not PLAIN_ID.match(node)):
        node = None
    return {"space": space, "bubble_id": bubble, "node_id": node}


def trace_of(
    ui_context: Optional[Dict[str, Any]],
) -> "tuple[str, Optional[Dict[str, Any]]]":
    """The trace id of the sentence (set by the app per sentence) and the context without it.

    Only a plain id passes; anything else is dropped. The caller's context is not changed in place.
    """
    if not isinstance(ui_context, dict) or "trace_id" not in ui_context:
        return "", ui_context
    context = dict(ui_context)
    value = context.pop("trace_id")
    trace = value if isinstance(value, str) and TRACE_ID.match(value) else ""
    return trace, (context or None)


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
        #
        # Env-tunable (VOICE_BRAIN_MULTIHOP_TIMEOUT_S): this is the WORST-CASE
        # latency a voice turn pays when multihop MISSES (no cap / no plan) —
        # it waits this long, then falls through to the old fast path. Lower
        # it (e.g. 2.5) to cap that tail at the cost of cutting off slow
        # legitimate multihop runs (an OpenFang spawn can need ~5s). Read at
        # instantiation, AFTER electron_backend has loaded the .env files.
        _env_timeout = os.getenv("VOICE_BRAIN_MULTIHOP_TIMEOUT_S")
        try:
            self._request_timeout = float(_env_timeout) if _env_timeout else request_timeout_s
        except ValueError:
            logger.warning(
                f"[MultihopBridge] bad VOICE_BRAIN_MULTIHOP_TIMEOUT_S={_env_timeout!r}, "
                f"using {request_timeout_s}s"
            )
            self._request_timeout = request_timeout_s
        self._brain_url = brain_url.rstrip("/")
        self._backoff = backoff_seconds
        self._available = True
        # Why the Brain is off: "unreachable" (no connection). Only that starts the backoff; the
        # sentence is answered here, the old path did not know it ("nicht ganz verstanden").
        self._down = ""

    # ------------------------------------------------------------------
    # Public API — matches BrainOpenFangBridge.execute() signature so the
    # orchestrator can hold both bridges side-by-side.
    # ------------------------------------------------------------------

    async def execute(
        self,
        intent_text: str,
        context: Any = None,                # v1: not forwarded; multihop builds its own state
        pre_classification: str = "",       # ignored — CapabilityRouter does its own matching
        ui_context: Optional[Dict[str, Any]] = None,  # what is on screen in the app; sent on as given
    ) -> Optional[OrchestrationResult]:
        """POST /api/multihop/execute with the raw intent text.

        Returns OrchestrationResult whenever the Brain has a sentence (final_text, or for
        ok=true an accepted order or a synthesizable executed-hop summary). Returns None
        only without any sentence, so Phase -1 / HybridRouter run.
        Never raises.
        """
        if not self._available:
            # in the backoff the sentence is never sent: nothing changed
            return self._unreachable(UNREACHABLE_TEXT)

        text = (intent_text or "").strip()
        if not text:
            return None

        if isinstance(ui_context, dict) and ui_context:
            data = await self._post_multihop(text, ui_context)
        else:
            data = await self._post_multihop(text)
        if data is _TIMED_OUT:
            return self._unreachable(TIMEOUT_TEXT)
        if data is None:
            # No connection: the old path did not know the sentence either and answered
            # "nicht verstanden" (measured 2026-11-23 during a restart of the Brain).
            if not self._available:
                return self._unreachable(UNREACHABLE_TEXT)
            return None

        ok = bool(data.get("ok"))
        final_text = (data.get("final_text") or "").strip()
        executed = data.get("executed") or {}
        # Not understood (verstanden=false) is a question back as well: the Brain names examples
        # from the space on screen in final_text. Its raw original (`fehler`) is never passed on.
        question = bool(data.get("rueckfrage")) or data.get("verstanden") is False
        hint = not question and data.get("hinweis") is True
        # A proposal for a changed card (`vorschlag`): the app shows it with two answers.
        proposal = None if question else self._proposal(data)

        # ok=false has two meanings. CapabilityRouter found nothing, or the planner
        # gave up: nothing to say, quiet fall-through (introspection.py:2392). But the
        # Brain also answers ok=false when it DID act and a tool refused or failed, and
        # when it asks back (rueckfrage=true); then final_text is its sentence for the
        # user. Dropping that sentence made the old path answer "I did not understand
        # you" while the tool had plainly said what was wrong. Every sentence of the Brain
        # is shown: also one with only a way (`weg`, e.g. "lesen-fehlt") and no other mark
        # (Lauf 19: "Welche Agenten gibt es in Rowboat?" went to the old path that way).
        if not ok and not final_text:
            return None
        if not ok and not (question or hint or proposal is not None or executed):
            # nothing done, no failure of a tool: the Brain's sentence, calmly, as a question back
            question = True

        # MH-5 (Phase 0): feed the REAL per-hop truth-verdict back as a
        # reward, keyed on the top-level plan_id (MH-5a response contract).
        # outcome_gate ANDs {ok, validator_verdict} across hops: True/False
        # reward, None (unverified / empty executed) rewards NOTHING — never
        # a fabricated positive. Fires even when voice has no final_text:
        # the hop ground truth exists independently of the synthesizer.
        try:
            from swarm.routing import outcome_gate as _og
            _plan_id = data.get("plan_id") or ""
            _sig = _og.contract_pass_from_executed(executed)
            if _plan_id and _sig is not None:
                asyncio.create_task(self._reward_multihop(_plan_id, _sig))
        except Exception as e:  # noqa: BLE001 — reward must never break voice
            logger.debug(f"[MultihopBridge] reward gating skipped: {e}")

        # An order the Brain took and a model works on (ok true, pending true, status
        # "angenommen"): its result comes later at the card. Never a failure.
        accepted, targets = self._accepted(data, executed)
        if not final_text and accepted:
            final_text = "Auftrag angenommen"
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

        # `error` stays empty on purpose: the orchestrator falls through to the old path
        # on a result with `error`, and the Brain's own sentence would be lost again.
        # The outcome travels in the event type (see clawport_handlers).
        if ok or accepted or proposal is not None:
            event_type = EVENT_DONE
        elif question:
            event_type = EVENT_QUESTION
        elif hint:
            event_type = EVENT_HINT
        else:
            event_type = EVENT_FAILED

        tool_result = {"pending": True, "status": "angenommen", "targets": targets,
                       "orders": self._orders(data, executed)} if accepted else None
        if proposal is not None:
            tool_result = {**(tool_result or {}), "vorschlag": proposal}
        # The place of the result: the app goes there, into the bubble, and marks the card.
        ziel = ziel_of(data.get("ziel"))
        if ziel is not None:
            tool_result = {**(tool_result or {}), "ziel": ziel}
        return OrchestrationResult(
            job_id=job_id,
            event_type=event_type,
            stream="brain",
            response_hint=final_text,
            is_conversational=False,
            tool_result=tool_result,
        )

    @staticmethod
    def _unreachable(text: str) -> OrchestrationResult:
        """No answer of the Brain (no connection, or none in time): said plainly, calmly (a hint,
        not a failure). No plan id: the app knows of no plan of the Brain for it."""
        return OrchestrationResult(
            job_id="brain-multihop:unreachable",
            event_type=EVENT_HINT,
            stream="brain",
            response_hint=text,
            is_conversational=False,
            tool_result=None,
        )

    @staticmethod
    def _proposal(data: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """The proposal in an answer of the Brain: {} for `vorschlag: true`, else only the card
        id (`karte`) and its title (`titel`); None without a proposal. Nothing else passes."""
        found = data.get("vorschlag")
        if found is True:
            return {}
        if not isinstance(found, dict):
            return None
        proposal: Dict[str, str] = {}
        for key in ("karte", "titel"):
            value = found.get(key)
            if isinstance(value, str) and value.strip():
                proposal[key] = value.strip()[:200]
        return proposal

    # ------------------------------------------------------------------
    # Brain communication
    # ------------------------------------------------------------------

    async def _post_multihop(
        self, intent_text: str, ui_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """POST /api/multihop/execute, return parsed JSON or None on any failure.

        `ui_context` is what the app has on screen (open bubble, visible cards; built in
        electron-app/renderer/ideas-chat.js). It goes into the body as `context`, next to
        `intent`; how names are resolved from it is the Brain's business. Only `eingabe` is
        checked here: it stays only with its signature in the header (typed_request).
        """
        body: Dict[str, Any] = {"intent": intent_text}
        # The trace of the sentence goes beside intent, not in the context: the Brain puts it on
        # every event of the run and on its answer (task-navigation.js passes it on to the app).
        trace, ui_context = trace_of(ui_context)
        if trace:
            body["trace_id"] = trace
        # A typed sentence carries its signature in the header (typed_request); never logged.
        context, headers = typed_request(intent_text, ui_context)
        if context:
            body["context"] = context
        try:
            timeout = aiohttp.ClientTimeout(total=self._request_timeout,
                                            sock_connect=min(CONNECT_TIMEOUT_S, self._request_timeout))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self._brain_url}/api/multihop/execute",
                    json=body,
                    headers=headers or None,
                ) as resp:
                    if resp.status != 200:
                        logger.debug(
                            f"[MultihopBridge] brain returned {resp.status}, fall-through"
                        )
                        return None
                    return await resp.json()
        except asyncio.TimeoutError as e:
            if not isinstance(e, aiohttp.ServerTimeoutError):
                # The Brain took the request but did not answer within the limit. It works
                # serially and may still be busy: no backoff, the next sentence is sent again.
                logger.warning(f"[MultihopBridge] brain answered not within {self._request_timeout}s")
                return _TIMED_OUT
            return self._mark_unreachable(e)
        except aiohttp.ClientError as e:
            return self._mark_unreachable(e)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[MultihopBridge] unexpected error: {e}")
            return None

    def _mark_unreachable(self, e: BaseException) -> None:
        """No connection to the Brain: stop sending for the backoff (see the module doc)."""
        # Refused, DNS fail, a dropped connection, or no connection within CONNECT_TIMEOUT_S
        # (on Windows a refused connect can hang until a timeout; sock_connect bounds it).
        # Same 30s backoff pattern as BrainOpenFangBridge.
        self._available = False
        self._down = "unreachable"
        try:
            asyncio.get_event_loop().call_later(self._backoff, self._re_enable)
        except RuntimeError:
            # No running loop (rare; e.g. called outside async ctx).
            # Mark unavailable; next event-loop tick may recover.
            pass
        logger.warning(
            f"[MultihopBridge] brain unreachable ({e}), disabled {self._backoff}s"
        )
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _accepted(data: Dict[str, Any], executed: Dict[str, Any]):
        """(accepted, targets): did the Brain take an order a model still works on?

        Read from the answer itself or from a hop and its result. A hop that failed for
        real (ok false without the mark) makes the plan no accepted order.
        """
        def marked(value: Any) -> bool:
            return isinstance(value, dict) and value.get("ok") is not False and (
                value.get("pending") is True or value.get("status") == "angenommen")

        targets: List[str] = []

        def collect(value: Any) -> None:
            if not isinstance(value, dict):
                return
            listed = value.get("targets")
            for item in listed if isinstance(listed, list) else []:
                if isinstance(item, (str, int)) and str(item).strip():
                    targets.append(str(item).strip())
            for key in ("card_id", "target_id"):
                item = value.get(key)
                if isinstance(item, (str, int)) and str(item).strip():
                    targets.append(str(item).strip())

        accepted = marked(data)
        if accepted:
            collect(data)
        failed = False
        for hop in (executed or {}).values() if isinstance(executed, dict) else []:
            if not isinstance(hop, dict):
                continue
            result = hop.get("result")
            # The step that hands an order to a model says {ok: false, pending: true,
            # result: {auftrag_id, status: "offen"}}: the order is taken, nothing failed.
            handed = hop.get("pending") is True
            if marked(hop) or marked(result) or handed:
                accepted = True
                collect(hop)
                collect(result)
            elif hop.get("ok") is False:
                failed = True
        if failed:
            return False, []
        return accepted, list(dict.fromkeys(targets))

    @staticmethod
    def _orders(data: Dict[str, Any], executed: Dict[str, Any]) -> List[str]:
        """Ids of the orders the Brain took (`auftraege: [{auftrag_id, …}]`), from the answer and its hops.

        The app ends its "arbeitet" line by them once the order is finished.
        """
        ids: List[str] = []

        def collect(value: Any) -> None:
            if not isinstance(value, dict):
                return
            one = value.get("auftrag_id")
            if isinstance(one, str) and one.strip():
                ids.append(one.strip())
            listed = value.get("auftraege")
            for item in listed if isinstance(listed, list) else []:
                if isinstance(item, dict) and isinstance(item.get("auftrag_id"), str) and item["auftrag_id"].strip():
                    ids.append(item["auftrag_id"].strip())

        collect(data)
        for hop in (executed or {}).values() if isinstance(executed, dict) else []:
            if isinstance(hop, dict):
                collect(hop)
                collect(hop.get("result"))
        return list(dict.fromkeys(ids))

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

    async def _reward_multihop(self, plan_id: str, success: bool) -> None:
        """POST /api/multihop/plan/{plan_id}/reward (fire-and-forget).

        MH-5 (Phase 0): plan_id is the verified reward correlate — the
        endpoint takes body {delta, reason} and forwards to
        PlanExecutor.record_plan_reward. Only gate-True/False outcomes
        reach this method (None is filtered at the call site)."""
        if not plan_id:
            return
        try:
            timeout = aiohttp.ClientTimeout(total=1.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                await session.post(
                    f"{self._brain_url}/api/multihop/plan/{plan_id}/reward",
                    json={
                        "delta": 1.0 if success else -1.0,
                        "reason": (
                            "voice-bridge outcome_gate: "
                            + ("verified" if success else "refuted")
                        ),
                    },
                )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[MultihopBridge] reward failed (non-critical): {e}")

    def _re_enable(self) -> None:
        """Re-enable bridge after backoff window expires."""
        self._available = True
        self._down = ""
        logger.info("[MultihopBridge] re-enabled after backoff")
