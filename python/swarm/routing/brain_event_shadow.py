"""BrainEventShadowObserver — Brain watches every intent classification, learns, takes over at 95%.

Mirrors BrainShadowObserver but for **event classification** (text → event_type)
rather than space routing (event_type → space). The two run in parallel and
graduate independently.

Lifecycle:
1. SHADOW: Every LLM classification is mirrored to /api/cortex/classify and
   the LLM's answer is sent to /api/cortex/classify/train as ground truth.
2. ROLLING: Track accuracy on a rolling window of last N samples.
3. ACTIVE: When accuracy ≥ threshold AND total observations ≥ min_samples,
   `_active = True`. The orchestrator can then call `classify_via_brain()`
   first and fall back to LLM only on low confidence.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger('swarm.brain_event_shadow')


class BrainEventShadowObserver:
    """Observes LLM classifications and trains Brain's EventRoutingHead."""

    def __init__(
        self,
        brain_url: str = "http://localhost:5000",
        window_size: int = 100,
        min_samples_for_activation: int = 500,
        activation_threshold: float = 0.95,
    ):
        self._brain_url = brain_url.rstrip('/')
        self._window: deque = deque(maxlen=window_size)
        self._activation_threshold = activation_threshold
        self._min_samples = min_samples_for_activation
        self._total_observations = 0
        self._total_correct = 0
        self._brain_available = True
        self._brain_disabled_at: float = 0.0  # timestamp when disabled
        self._brain_backoff_s: float = 10.0   # re-enable after N seconds
        self._active = False

    # ------------------------------------------------------------------
    # Shadow path — called after every LLM classification
    # ------------------------------------------------------------------

    async def observe(
        self,
        user_text: str,
        actual_event_type: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Called after every LLM classification. Non-blocking, fire-and-forget.

        Asks the Brain what it would classify, compares to LLM ground truth,
        records accuracy, and trains the Brain with the LLM's answer. When
        user_id is given, the brain also updates that user's delta.
        """
        if not self._brain_available or not user_text or not actual_event_type:
            return
        if actual_event_type == "conversation.unknown":
            # Don't train on parser failures
            return

        try:
            timeout = aiohttp.ClientTimeout(total=0.5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # 1. Ask brain what it would classify
                classify_payload: Dict[str, Any] = {"user_text": user_text}
                if user_id:
                    classify_payload["user_id"] = user_id
                async with session.post(
                    f"{self._brain_url}/api/cortex/classify",
                    json=classify_payload,
                ) as resp:
                    if resp.status != 200:
                        return
                    brain_decision = await resp.json()

                brain_event = brain_decision.get("event_type", "")
                correct = (brain_event == actual_event_type)

                # 2. Record accuracy
                self._window.append(1 if correct else 0)
                self._total_observations += 1
                if correct:
                    self._total_correct += 1

                # 3. Train brain with ground truth (supervised)
                train_payload: Dict[str, Any] = {
                    "user_text": user_text,
                    "correct_event_type": actual_event_type,
                }
                if user_id:
                    train_payload["user_id"] = user_id
                await session.post(
                    f"{self._brain_url}/api/cortex/classify/train",
                    json=train_payload,
                )

                # 4. Check activation periodically
                if self._total_observations % 10 == 0 and len(self._window) >= self._window.maxlen:
                    accuracy = sum(self._window) / len(self._window)
                    enough_data = self._total_observations >= self._min_samples
                    if accuracy >= self._activation_threshold and enough_data and not self._active:
                        self._active = True
                        logger.info(
                            f"BRAIN EVENT-CLASSIFIER ACTIVATED: accuracy={accuracy:.1%} "
                            f"over {len(self._window)} samples (total obs={self._total_observations})"
                        )
                    elif accuracy < (self._activation_threshold - 0.05) and self._active:
                        self._active = False
                        logger.warning(
                            f"Brain event-classifier deactivated: accuracy dropped to {accuracy:.1%}"
                        )

                if self._total_observations % 25 == 0:
                    acc = sum(self._window) / len(self._window) if self._window else 0
                    logger.info(
                        f"EventShadow: obs={self._total_observations} "
                        f"correct={self._total_correct} "
                        f"accuracy={acc:.1%} "
                        f"brain_active={self._active}"
                    )

        except aiohttp.ClientError:
            import time as _time
            self._brain_available = False
            self._brain_disabled_at = _time.time()
            logger.debug("Brain classify unavailable, backing off")
        except Exception as e:
            logger.debug(f"EventShadow observe failed: {e}")

    # ------------------------------------------------------------------
    # Active path — called by orchestrator when _active is True
    # ------------------------------------------------------------------

    async def classify_via_brain(
        self,
        user_text: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Classify directly via Brain. Returns dict or None on failure.

        Returns: {event_type, confidence, routing_id, alternatives, latency_ms}
        When user_id is given, the brain applies that user's personalization delta.
        """
        # When force_active is set via env, ALWAYS try the brain — never skip.
        # This overrides the backoff logic for development/testing.
        _force = os.environ.get("BRAIN_EVENT_FORCE_ACTIVE", "").lower() == "true"

        if not self._brain_available and not _force:
            import time as _time
            if (_time.time() - self._brain_disabled_at) > self._brain_backoff_s:
                self._brain_available = True
                logger.debug("Brain re-enabled after backoff")
            else:
                return None
        try:
            # 2s timeout — the first SBERT call on the Brain can take ~500ms
            # (model warm-up); subsequent calls are <100ms.
            timeout = aiohttp.ClientTimeout(total=2.0)
            payload: Dict[str, Any] = {"user_text": user_text}
            if user_id:
                payload["user_id"] = user_id
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self._brain_url}/api/cortex/classify",
                    json=payload,
                ) as resp:
                    if resp.status != 200:
                        return None
                    return await resp.json()
        except Exception:
            return None

    async def reward(self, routing_id: str, success: bool) -> None:
        """Send a reward signal for a previous classification (fire-and-forget)."""
        if not routing_id:
            return
        try:
            timeout = aiohttp.ClientTimeout(total=1.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                await session.post(
                    f"{self._brain_url}/api/cortex/classify/reward",
                    json={"routing_id": routing_id, "success": success},
                )
        except Exception as e:
            logger.debug(f"EventShadow reward failed (non-critical): {e}")

    async def correct(
        self,
        user_text: str,
        correct_event_type: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Explicit user correction → strong supervised retrain.

        Passes user_id through so the retrain also shifts the per-user delta.
        """
        if not user_text or not correct_event_type:
            return
        try:
            timeout = aiohttp.ClientTimeout(total=1.0)
            payload: Dict[str, Any] = {
                "user_text": user_text,
                "correct_event_type": correct_event_type,
            }
            if user_id:
                payload["user_id"] = user_id
            async with aiohttp.ClientSession(timeout=timeout) as session:
                await session.post(
                    f"{self._brain_url}/api/cortex/classify/train",
                    json=payload,
                )
                logger.info(
                    f"EventShadow correction: '{user_text[:40]}' -> {correct_event_type}"
                    + (f" (user={user_id})" if user_id else "")
                )
        except Exception as e:
            logger.debug(f"EventShadow correct failed: {e}")

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def _re_enable(self) -> None:
        self._brain_available = True

    @property
    def brain_active(self) -> bool:
        return self._active

    @property
    def accuracy(self) -> float:
        if not self._window:
            return 0.0
        return sum(self._window) / len(self._window)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_observations": self._total_observations,
            "total_correct": self._total_correct,
            "window_size": len(self._window),
            "window_max": self._window.maxlen,
            "accuracy": round(self.accuracy, 4),
            "brain_active": self._active,
            "brain_available": self._brain_available,
            "activation_threshold": self._activation_threshold,
            "min_samples": self._min_samples,
        }
