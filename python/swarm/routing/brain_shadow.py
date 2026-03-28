"""BrainShadowObserver — Brain watches every routing decision, learns, takes over at 95%.

Shadow Mode: The Brain observes every HybridRouter decision, compares with its own
prediction, trains on the ground truth, and tracks rolling accuracy. When accuracy
hits 95% on 100+ samples, the Brain is ready to take over routing.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger('swarm.brain_shadow')


class BrainShadowObserver:
    """Observes HybridRouter decisions and trains Brain's SpaceRoutingHead.

    Flow per observation:
    1. POST /api/cortex/route → Brain's prediction
    2. Compare with HybridRouter's actual decision
    3. POST /api/cortex/route/train → supervised centroid update
    4. Track rolling accuracy
    5. Activate brain routing at 95% accuracy
    """

    def __init__(self, brain_url: str = "http://localhost:5000",
                 window_size: int = 100,
                 activation_threshold: float = 0.95):
        self._brain_url = brain_url.rstrip('/')
        self._window: deque = deque(maxlen=window_size)
        self._activation_threshold = activation_threshold
        self._total_observations = 0
        self._total_correct = 0
        self._brain_available = True
        self._active = False
        self._last_check_time = 0.0

    async def observe(self, user_text: str, event_type: str,
                      actual_space: str, success: bool = True) -> None:
        """Called after every HybridRouter decision. Non-blocking.

        Args:
            user_text: Original user input
            event_type: Classified event type (e.g. "idea.create")
            actual_space: Space that HybridRouter routed to
            success: Whether agent execution succeeded
        """
        if not self._brain_available or not user_text or not actual_space:
            return

        try:
            timeout = aiohttp.ClientTimeout(total=0.5)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                # 1. Ask brain what it would route
                async with session.post(
                    f"{self._brain_url}/api/cortex/route",
                    json={"user_text": user_text, "event_type": event_type},
                ) as resp:
                    if resp.status != 200:
                        return
                    brain_decision = await resp.json()

                brain_space = brain_decision.get("primary_space", "")
                correct = (brain_space == actual_space)

                # 2. Log accuracy
                self._window.append(1 if correct else 0)
                self._total_observations += 1
                if correct:
                    self._total_correct += 1

                # 3. Train brain with ground truth (supervised)
                await session.post(
                    f"{self._brain_url}/api/cortex/route/train",
                    json={
                        "user_text": user_text,
                        "correct_space": actual_space,
                        "event_type": event_type,
                        "success": success,
                    },
                )

                # 4. Check activation (at most every 10 observations)
                if self._total_observations % 10 == 0 and len(self._window) >= self._window.maxlen:
                    accuracy = sum(self._window) / len(self._window)
                    if accuracy >= self._activation_threshold and not self._active:
                        self._active = True
                        logger.info(
                            f"BRAIN ACTIVATED: accuracy={accuracy:.1%} "
                            f"over {len(self._window)} samples"
                        )
                    elif accuracy < self._activation_threshold and self._active:
                        self._active = False
                        logger.warning(
                            f"Brain deactivated: accuracy dropped to {accuracy:.1%}"
                        )

                # Log periodically
                if self._total_observations % 25 == 0:
                    acc = sum(self._window) / len(self._window) if self._window else 0
                    logger.info(
                        f"Shadow: obs={self._total_observations} "
                        f"correct={self._total_correct} "
                        f"accuracy={acc:.1%} "
                        f"brain_active={self._active}"
                    )

        except aiohttp.ClientError:
            # Brain server not available — disable temporarily
            self._brain_available = False
            asyncio.get_event_loop().call_later(30, self._re_enable)
        except Exception as e:
            logger.debug(f"Shadow observe failed: {e}")

    def _re_enable(self):
        """Re-enable brain connection after backoff."""
        self._brain_available = True

    async def route_via_brain(self, user_text: str, event_type: str) -> Optional[Dict[str, Any]]:
        """Route directly via Brain (when active mode).

        Returns dict with 'space' and 'confidence', or None on failure.
        """
        if not self._brain_available:
            return None
        try:
            timeout = aiohttp.ClientTimeout(total=0.3)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self._brain_url}/api/cortex/route",
                    json={"user_text": user_text, "event_type": event_type},
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return {
                        'space': data.get('primary_space', ''),
                        'confidence': data.get('confidence', 0),
                        'routing_id': data.get('routing_id', ''),
                    }
        except Exception:
            return None

    @property
    def brain_active(self) -> bool:
        """Whether the Brain has graduated to active routing mode."""
        return self._active

    @property
    def accuracy(self) -> float:
        """Current rolling accuracy over the window."""
        if not self._window:
            return 0.0
        return sum(self._window) / len(self._window)

    def get_stats(self) -> Dict[str, Any]:
        """Stats for monitoring and diagnostics."""
        return {
            "total_observations": self._total_observations,
            "total_correct": self._total_correct,
            "window_size": len(self._window),
            "window_max": self._window.maxlen,
            "accuracy": round(self.accuracy, 4),
            "brain_active": self._active,
            "brain_available": self._brain_available,
            "activation_threshold": self._activation_threshold,
        }
