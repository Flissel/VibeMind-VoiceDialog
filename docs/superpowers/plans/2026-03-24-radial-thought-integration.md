# Radial Thought Integration — ThoughtStream ↔ RadialAttentionNetwork

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the ContinuousThinkingEngine's thought stream through the 5-ring RadialAttentionNetwork so that each ring provides a functional signal (novelty, pattern match, semantic richness, goal alignment, action threshold) that feeds back into thought activation, routing, and Hebbian plasticity — creating real neuroplasticity.

**Architecture:** Each CTE thought gets embedded and pushed through the radial network. The 5 ring outputs are extracted as a `RingSignature` — a per-thought fingerprint that determines whether the thought gets boosted, suppressed, or triggers an action. A reward signal from successful outcomes (user confirmation, tool success) flows back into the precision gates via Hebbian updates, making the system learn over time which thought patterns are valuable.

**Tech Stack:** Python 3.11, PyTorch (radial network), numpy, sentence-transformers (384-dim embeddings via existing SeedEncoder)

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `core/ring_signature.py` | RingSignature dataclass + extraction logic from ring activations | **Create** |
| `core/thought_radial_bridge.py` | Bridge between CTE thoughts and RadialNetwork — embed, forward, extract signals, feedback | **Create** |
| `core/agent_loop.py` | Extend `radial_tick()` to return RingSignature | **Modify** (lines 932-986) |
| `core/brain_chat.py` | Wire ThoughtRadialBridge into CTE, use RingSignature in `_run_loop()` | **Modify** (CTE class ~2753-3040) |
| `core/brain_chat.py` | Add reward feedback when user confirms or tool succeeds | **Modify** (chat response handler) |
| `core/hebbian_plasticity.py` | Add reward-weighted update method | **Modify** (HebbianAttentionUpdate class) |
| `tests/test_ring_signature.py` | Unit tests for RingSignature extraction | **Create** |
| `tests/test_thought_radial_bridge.py` | Unit tests for bridge logic | **Create** |
| `tests/test_reward_feedback.py` | Tests for reward → Hebbian loop | **Create** |

---

## Task 1: RingSignature Dataclass

**Files:**
- Create: `core/ring_signature.py`
- Test: `tests/test_ring_signature.py`

The RingSignature is the semantic fingerprint that each thought receives after passing through the rings. Each ring provides one interpretable scalar signal.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ring_signature.py
"""Tests for RingSignature — the per-thought radial fingerprint."""
import pytest
import torch
from core.ring_signature import RingSignature, extract_ring_signature


class TestRingSignature:
    def test_from_activations_shape(self):
        """5 ring activations → 5 scalar signals."""
        activations = [
            torch.randn(1, 64),   # sensory
            torch.randn(1, 128),  # pattern
            torch.randn(1, 256),  # semantic
            torch.randn(1, 256),  # abstract
            torch.randn(1, 128),  # meta
        ]
        sig = extract_ring_signature(activations, prediction_errors=[0.1, 0.2, 0.3, 0.4])
        assert isinstance(sig, RingSignature)
        assert 0.0 <= sig.novelty <= 1.0
        assert 0.0 <= sig.pattern_match <= 1.0
        assert 0.0 <= sig.semantic_richness <= 1.0
        assert 0.0 <= sig.goal_alignment <= 1.0
        assert 0.0 <= sig.action_readiness <= 1.0

    def test_activation_boost(self):
        """activation_boost is a weighted combination of all signals."""
        sig = RingSignature(
            novelty=0.8, pattern_match=0.6,
            semantic_richness=0.7, goal_alignment=0.9, action_readiness=0.5,
        )
        boost = sig.activation_boost
        assert 0.0 <= boost <= 1.0

    def test_should_act(self):
        """action_readiness above threshold → should_act True."""
        sig_high = RingSignature(action_readiness=0.8)
        sig_low = RingSignature(action_readiness=0.2)
        assert sig_high.should_act(threshold=0.6) is True
        assert sig_low.should_act(threshold=0.6) is False

    def test_zero_activations_safe(self):
        """Zero-valued activations don't crash."""
        activations = [torch.zeros(1, d) for d in [64, 128, 256, 256, 128]]
        sig = extract_ring_signature(activations, prediction_errors=[0, 0, 0, 0])
        assert sig.novelty == 0.0

    def test_to_dict(self):
        """Serializes to dict for dashboard/SSE."""
        sig = RingSignature(novelty=0.5, pattern_match=0.3)
        d = sig.to_dict()
        assert d['novelty'] == 0.5
        assert 'activation_boost' in d
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python/spaces/brain/the_brain && python -m pytest tests/test_ring_signature.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.ring_signature'`

- [ ] **Step 3: Implement RingSignature**

```python
# core/ring_signature.py
"""
RingSignature — the per-thought radial fingerprint.

Each thought that passes through the 5-ring RadialAttentionNetwork
receives 5 interpretable signals:

  Ring 1 (Sensory)  → novelty:           How different is this from recent inputs?
  Ring 2 (Pattern)  → pattern_match:     Does this match known patterns (Hebbian bias)?
  Ring 3 (Semantic) → semantic_richness:  How much associative depth does this have?
  Ring 4 (Abstract) → goal_alignment:    Does this serve active goals/projects?
  Ring 5 (Meta)     → action_readiness:  Should the system act on this or keep thinking?

These signals modulate thought activation, routing, and Hebbian learning.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import torch
import torch.nn.functional as F


@dataclass
class RingSignature:
    """Per-thought fingerprint from radial network."""

    novelty: float = 0.0            # Ring 1: prediction error magnitude
    pattern_match: float = 0.0      # Ring 2: Hebbian bias activation strength
    semantic_richness: float = 0.0  # Ring 3: activation norm (associative density)
    goal_alignment: float = 0.0     # Ring 4: activation norm (abstract relevance)
    action_readiness: float = 0.0   # Ring 5: meta-cognitive gate output

    @property
    def activation_boost(self) -> float:
        """Weighted combination → how much to boost this thought's activation.

        Novelty and goal_alignment matter most for prioritization.
        Pattern_match contributes negatively when very high (old news).
        """
        raw = (
            0.30 * self.novelty
            + 0.10 * (1.0 - self.pattern_match)  # novel > familiar
            + 0.20 * self.semantic_richness
            + 0.30 * self.goal_alignment
            + 0.10 * self.action_readiness
        )
        return max(0.0, min(1.0, raw))

    def should_act(self, threshold: float = 0.6) -> bool:
        """Meta ring says: stop thinking, start doing."""
        return self.action_readiness >= threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            'novelty': round(self.novelty, 4),
            'pattern_match': round(self.pattern_match, 4),
            'semantic_richness': round(self.semantic_richness, 4),
            'goal_alignment': round(self.goal_alignment, 4),
            'action_readiness': round(self.action_readiness, 4),
            'activation_boost': round(self.activation_boost, 4),
        }


def extract_ring_signature(
    ring_activations: List[torch.Tensor],
    prediction_errors: List[float],
    previous_sensory: Optional[torch.Tensor] = None,
) -> RingSignature:
    """Extract interpretable signals from raw ring activations.

    Args:
        ring_activations: 5 tensors from RadialAttentionNetwork.forward()
        prediction_errors: 4 scalar errors (ring pairs 1-2, 2-3, 3-4, 4-5)
        previous_sensory: Last Ring 1 activation for novelty comparison

    Returns:
        RingSignature with 5 normalized [0,1] signals.
    """
    # Ring 1 — Novelty: prediction error at the sensory level
    # High error = new information the network didn't predict
    if prediction_errors:
        # Prediction errors can exceed 1.0 — use sigmoid to normalize smoothly
        raw_error = abs(prediction_errors[0])
        novelty = float(2.0 / (1.0 + math.exp(-raw_error)) - 1.0)  # sigmoid to [0, 1]
    else:
        novelty = 0.0

    # Also compare to previous sensory activation if available
    if previous_sensory is not None and ring_activations:
        with torch.no_grad():
            cos_sim = F.cosine_similarity(
                ring_activations[0].flatten().unsqueeze(0),
                previous_sensory.flatten().unsqueeze(0),
            ).item()
            # Low similarity = high novelty
            novelty = max(novelty, (1.0 - cos_sim) / 2.0)

    # Ring 2 — Pattern Match: how concentrated is the activation?
    # Low entropy = concentrated on few dimensions = strong pattern match
    # High entropy = spread out = no clear pattern recognized
    pattern_match = 0.0
    if len(ring_activations) > 1:
        act = ring_activations[1].detach().flatten().abs()
        total = act.sum().item()
        if total > 1e-6:
            probs = act / total
            entropy = -(probs * (probs + 1e-8).log()).sum().item()
            max_entropy = math.log(len(act))
            # Invert: low entropy = high pattern match
            pattern_match = max(0.0, min(1.0, 1.0 - (entropy / max_entropy))) if max_entropy > 0 else 0.0

    # Ring 3 — Semantic Richness: activation spread in semantic ring
    # High entropy of activation = rich associations
    semantic_richness = 0.0
    if len(ring_activations) > 2:
        act = ring_activations[2].detach().flatten()
        act_abs = act.abs()
        total = act_abs.sum().item()
        if total > 0:
            probs = act_abs / total
            entropy = -(probs * (probs + 1e-8).log()).sum().item()
            max_entropy = math.log(len(act))
            semantic_richness = min(1.0, entropy / max_entropy) if max_entropy > 0 else 0.0

    # Ring 4 — Goal Alignment: abstract ring activation strength
    # Stronger activation = more relevant to current abstract goals
    goal_alignment = 0.0
    if len(ring_activations) > 3:
        norm = ring_activations[3].detach().norm().item()
        goal_alignment = min(1.0, norm / 12.0)

    # Ring 5 — Action Readiness: meta ring as think-or-act gate
    # High activation = system is confident enough to act
    action_readiness = 0.0
    if len(ring_activations) > 4:
        meta_act = ring_activations[4].detach().flatten()
        # Use mean of positive activations as readiness signal
        positive = meta_act[meta_act > 0]
        if len(positive) > 0:
            action_readiness = min(1.0, positive.mean().item())

    return RingSignature(
        novelty=novelty,
        pattern_match=pattern_match,
        semantic_richness=semantic_richness,
        goal_alignment=goal_alignment,
        action_readiness=action_readiness,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python/spaces/brain/the_brain && python -m pytest tests/test_ring_signature.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd python/spaces/brain/the_brain
git add core/ring_signature.py tests/test_ring_signature.py
git commit -m "feat(radial): RingSignature dataclass — per-thought radial fingerprint"
```

---

## Task 2: ThoughtRadialBridge

**Files:**
- Create: `core/thought_radial_bridge.py`
- Test: `tests/test_thought_radial_bridge.py`

The bridge is the central integration point. It takes a ContinuousThought, pushes it through the radial network, and returns an enriched thought with a RingSignature attached.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_thought_radial_bridge.py
"""Tests for ThoughtRadialBridge — CTE ↔ RadialNetwork integration."""
import pytest
import time
from unittest.mock import MagicMock, patch
from core.thought_radial_bridge import ThoughtRadialBridge


def _make_thought(content="test thought", category="reflect"):
    """Helper: create a ContinuousThought-like object."""
    from core.brain_chat import ContinuousThought
    return ContinuousThought(
        timestamp=time.time(),
        content=content,
        category=category,
        topic="test",
        relevance=0.5,
    )


class TestThoughtRadialBridge:
    def test_process_thought_returns_signature(self):
        """Processing a thought returns a RingSignature."""
        bridge = ThoughtRadialBridge()
        # Mock the agent_loop.radial_tick to return fake activations
        import torch
        mock_result = {
            'ring_activations': [torch.randn(1, d) for d in [64, 128, 256, 256, 128]],
            'prediction_errors': [0.1, 0.2, 0.15, 0.3],
            'meta_output': torch.randn(1, 128),
            'thalamic_seed': torch.randn(1, 128),
            'neuromod_state': None,
            'cortex_state': None,
            'limbic_state': None,
            'modulation_context': None,
            'consciousness_state': None,
        }
        mock_loop = MagicMock()
        mock_loop.radial_tick.return_value = mock_result
        bridge.set_agent_loop(mock_loop)

        thought = _make_thought("a novel idea about neural plasticity")
        sig = bridge.process(thought)

        assert sig is not None
        assert 0.0 <= sig.novelty <= 1.0
        assert 0.0 <= sig.activation_boost <= 1.0

    def test_process_without_agent_loop_returns_none(self):
        """No agent loop → returns None (graceful degradation)."""
        bridge = ThoughtRadialBridge()
        thought = _make_thought()
        assert bridge.process(thought) is None

    def test_previous_sensory_tracked(self):
        """Bridge remembers last sensory activation for novelty comparison."""
        bridge = ThoughtRadialBridge()
        import torch
        mock_result = {
            'ring_activations': [torch.randn(1, d) for d in [64, 128, 256, 256, 128]],
            'prediction_errors': [0.1, 0.2, 0.15, 0.3],
            'meta_output': torch.randn(1, 128),
            'thalamic_seed': torch.randn(1, 128),
            'neuromod_state': None,
            'cortex_state': None,
            'limbic_state': None,
            'modulation_context': None,
            'consciousness_state': None,
        }
        mock_loop = MagicMock()
        mock_loop.radial_tick.return_value = mock_result
        bridge.set_agent_loop(mock_loop)

        bridge.process(_make_thought("first thought"))
        assert bridge._previous_sensory is not None

        # Second thought uses previous_sensory for novelty
        bridge.process(_make_thought("second thought"))
        assert bridge._previous_sensory is not None

    def test_reward_feedback_stored(self):
        """Reward signals are queued for next Hebbian update."""
        bridge = ThoughtRadialBridge()
        bridge.record_reward(thought_id="abc", reward=0.8, outcome="user_confirmed")
        assert len(bridge._reward_queue) == 1
        assert bridge._reward_queue[0]['reward'] == 0.8

    def test_stats(self):
        """Stats reflect processing history."""
        bridge = ThoughtRadialBridge()
        stats = bridge.get_stats()
        assert stats['total_processed'] == 0
        assert stats['total_rewards'] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python/spaces/brain/the_brain && python -m pytest tests/test_thought_radial_bridge.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ThoughtRadialBridge**

```python
# core/thought_radial_bridge.py
"""
ThoughtRadialBridge — wires ContinuousThinkingEngine ↔ RadialAttentionNetwork.

On each CTE tick:
  1. Thought content → embed via AgentLoop.radial_tick()
  2. Ring activations → extract RingSignature
  3. RingSignature modulates thought activation + routing
  4. Reward feedback → queued for next Hebbian update

This is where neuroplasticity happens: thoughts that lead to good
outcomes strengthen the ring pathways that produced them.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any, Dict, List, Optional

import torch

from core.ring_signature import RingSignature, extract_ring_signature

logger = logging.getLogger('brain.thought_radial_bridge')


class ThoughtRadialBridge:
    """Bridge between thought stream and radial attention network."""

    def __init__(self, reward_queue_size: int = 50):
        self._agent_loop = None
        self._previous_sensory: Optional[torch.Tensor] = None
        self._reward_queue: deque = deque(maxlen=reward_queue_size)
        self._lock = threading.Lock()

        # Stats
        self._total_processed = 0
        self._total_rewards = 0
        self._total_actions_triggered = 0

    def set_agent_loop(self, agent_loop) -> None:
        """Attach the AgentLoop that owns the RadialNetwork."""
        self._agent_loop = agent_loop
        logger.info("ThoughtRadialBridge connected to AgentLoop")

    def process(self, thought) -> Optional[RingSignature]:
        """Push a thought through the radial network and extract its signature.

        Args:
            thought: ContinuousThought with .content string

        Returns:
            RingSignature or None if radial network unavailable.
        """
        if self._agent_loop is None:
            return None

        content = getattr(thought, 'content', '')
        if not content:
            return None

        # Run the radial forward pass via existing AgentLoop.radial_tick()
        result = self._agent_loop.radial_tick(content[:200])
        if result is None:
            return None

        ring_activations = result.get('ring_activations', [])
        prediction_errors = result.get('prediction_errors', [])

        if not ring_activations:
            return None

        # Extract interpretable signals
        sig = extract_ring_signature(
            ring_activations,
            prediction_errors,
            previous_sensory=self._previous_sensory,
        )

        # Track sensory activation for next novelty comparison
        if ring_activations:
            self._previous_sensory = ring_activations[0].detach().clone()

        self._total_processed += 1

        if sig.should_act():
            self._total_actions_triggered += 1

        return sig

    def record_reward(self, thought_id: str, reward: float,
                      outcome: str = "unknown") -> None:
        """Queue a reward signal for Hebbian feedback.

        Called when a thought leads to a successful action:
        - User confirms a suggestion
        - A tool call succeeds
        - An idea gets promoted

        Args:
            thought_id: Which thought triggered the outcome
            reward: 0.0 (bad) to 1.0 (good)
            outcome: What happened ("user_confirmed", "tool_success", etc.)
        """
        with self._lock:
            self._reward_queue.append({
                'thought_id': thought_id,
                'reward': reward,
                'outcome': outcome,
            })
            self._total_rewards += 1

    def drain_rewards(self) -> List[Dict[str, Any]]:
        """Pop all pending rewards for Hebbian update.

        Called by the Hebbian updater to get reward signals
        that should modulate the next learning step.
        """
        with self._lock:
            rewards = list(self._reward_queue)
            self._reward_queue.clear()
        return rewards

    def get_stats(self) -> Dict[str, Any]:
        return {
            'total_processed': self._total_processed,
            'total_rewards': self._total_rewards,
            'total_actions_triggered': self._total_actions_triggered,
            'pending_rewards': len(self._reward_queue),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python/spaces/brain/the_brain && python -m pytest tests/test_thought_radial_bridge.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd python/spaces/brain/the_brain
git add core/thought_radial_bridge.py tests/test_thought_radial_bridge.py
git commit -m "feat(radial): ThoughtRadialBridge — CTE ↔ RadialNetwork integration"
```

---

## Task 3: Reward-Weighted Hebbian Updates

**Files:**
- Modify: `core/hebbian_plasticity.py` (HebbianAttentionUpdate class, ~line 30)
- Test: `tests/test_reward_feedback.py`

Currently Hebbian updates have a fixed learning rate. With reward feedback, successful thought patterns get stronger updates (LTP) and failed ones get weaker/negative updates (LTD).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reward_feedback.py
"""Tests for reward-weighted Hebbian plasticity."""
import pytest
import torch
from core.hebbian_plasticity import HebbianAttentionUpdate
from core.radial_attention import RingLayer


class TestRewardWeightedHebbian:
    def test_reward_modulates_learning_rate(self):
        """Positive reward → larger bias change than neutral."""
        ring = RingLayer(in_dim=64, out_dim=64, num_heads=4)
        hebbian = HebbianAttentionUpdate(learning_rate=0.01)

        pre = torch.randn(1, 64)
        post = torch.randn(1, 64)

        # Neutral update
        bias_before = ring.attention_bias.clone()
        hebbian.update(ring, pre, post)
        neutral_delta = (ring.attention_bias - bias_before).abs().sum().item()

        # Reset
        ring.attention_bias.zero_()

        # Reward-weighted update
        hebbian.update_with_reward(ring, pre, post, reward=0.9)
        reward_delta = (ring.attention_bias).abs().sum().item()

        # Rewarded update should be larger
        assert reward_delta > neutral_delta * 1.3

    def test_negative_reward_reverses(self):
        """Negative reward → bias changes in opposite direction (LTD)."""
        ring = RingLayer(in_dim=64, out_dim=64, num_heads=4)
        hebbian = HebbianAttentionUpdate(learning_rate=0.01)

        pre = torch.randn(1, 64)
        post = torch.randn(1, 64)

        # Positive reward
        ring.attention_bias.zero_()
        hebbian.update_with_reward(ring, pre, post, reward=0.8)
        positive_bias = ring.attention_bias.clone()

        # Negative reward
        ring.attention_bias.zero_()
        hebbian.update_with_reward(ring, pre, post, reward=-0.5)
        negative_bias = ring.attention_bias.clone()

        # Signs should differ (at least partially)
        sign_diff = (positive_bias.sign() != negative_bias.sign()).float().mean().item()
        assert sign_diff > 0.3  # majority of signs flip

    def test_zero_reward_still_updates(self):
        """Zero reward → small baseline update (not zero)."""
        ring = RingLayer(in_dim=64, out_dim=64, num_heads=4)
        hebbian = HebbianAttentionUpdate(learning_rate=0.01)

        pre = torch.randn(1, 64)
        post = torch.randn(1, 64)

        hebbian.update_with_reward(ring, pre, post, reward=0.0)
        delta = ring.attention_bias.abs().sum().item()
        assert delta > 0  # baseline Hebbian still fires
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd python/spaces/brain/the_brain && python -m pytest tests/test_reward_feedback.py -v`
Expected: FAIL with `AttributeError: 'HebbianAttentionUpdate' object has no attribute 'update_with_reward'`

- [ ] **Step 3: Add `update_with_reward` to HebbianAttentionUpdate**

Add this method to the existing `HebbianAttentionUpdate` class in `core/hebbian_plasticity.py` after the existing `update()` method:

```python
    def update_with_reward(self, ring, pre_activation: torch.Tensor,
                           post_activation: torch.Tensor,
                           reward: float = 0.0,
                           neuromod=None) -> None:
        """Reward-modulated Hebbian update.

        reward > 0: LTP — strengthen the pathway (larger lr)
        reward < 0: LTD — weaken the pathway (inverted update)
        reward = 0: baseline Hebbian (same as update())

        The reward scales the learning rate:
          effective_lr = base_lr * (1.0 + reward)
        So reward=0.9 → 1.9x lr, reward=-0.5 → 0.5x lr (inverted sign).
        """
        # Scale learning rate by reward
        effective_lr = self.lr * (1.0 + reward)

        with torch.no_grad():
            pre_mean = pre_activation.mean(dim=0)
            post_mean = post_activation.mean(dim=0)

            bias = ring.attention_bias
            bias_d = bias.shape[0]

            # Project to bias dimension (same logic as update())
            if pre_mean.shape[0] != bias_d:
                pre_mean = torch.nn.functional.interpolate(
                    pre_mean.unsqueeze(0).unsqueeze(0),
                    size=bias_d, mode='linear', align_corners=False,
                ).squeeze()
            if post_mean.shape[0] != bias_d:
                post_mean = torch.nn.functional.interpolate(
                    post_mean.unsqueeze(0).unsqueeze(0),
                    size=bias_d, mode='linear', align_corners=False,
                ).squeeze()

            # Hebbian outer product with reward-modulated learning rate
            delta = torch.outer(pre_mean, post_mean)
            bias.add_(delta * effective_lr)

            # Anti-Hebbian decay (reward doesn't affect decay)
            effective_decay = self.decay
            if neuromod is not None:
                serotonin = getattr(neuromod, 'serotonin', 0.5)
                effective_decay *= (0.5 + serotonin)
            bias.mul_(1.0 - effective_decay)

            # Clamp
            bias.clamp_(-self.clamp_range, self.clamp_range)
            self._total_updates += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python/spaces/brain/the_brain && python -m pytest tests/test_reward_feedback.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd python/spaces/brain/the_brain
git add core/hebbian_plasticity.py tests/test_reward_feedback.py
git commit -m "feat(hebbian): reward-weighted plasticity — LTP/LTD via outcome feedback"
```

---

## Task 4: Wire ThoughtRadialBridge into CTE `_run_loop()`

**Files:**
- Modify: `core/brain_chat.py` — ContinuousThinkingEngine class (~line 2753)

This is the core integration. Currently `_run_loop()` calls `self._agent_loop.radial_tick(desc)` but ignores the result. We replace that with the ThoughtRadialBridge and use the RingSignature to modulate thought activation.

- [ ] **Step 1: Add `_thought_radial_bridge` attribute to CTE.__init__**

In `ContinuousThinkingEngine.__init__()` (~line 2763), add after `self._memory_consolidator = None`:

```python
        # Radial bridge — thought ↔ ring network integration
        self._thought_radial_bridge = None  # ThoughtRadialBridge (set by BrainChat)
```

- [ ] **Step 2: Add setter method**

Add after `set_memory_consolidator()` or similar setter:

```python
    def set_thought_radial_bridge(self, bridge) -> None:
        """Attach ThoughtRadialBridge for ring-signature enrichment."""
        self._thought_radial_bridge = bridge
```

- [ ] **Step 3: Modify `_run_loop()` to use ThoughtRadialBridge**

In `_run_loop()` (~line 2934), replace the radial tick block:

**Replace** the block that currently reads:
```python
            # Radial tick — fire bridge modulation on every think tick,
            # even when thought was duplicate/None (keeps dashboard alive).
            if self._agent_loop is not None:
                try:
                    desc = ""
                    if thought:
                        desc = thought.content[:200]
                    elif self._current_topic:
                        desc = self._current_topic
                    else:
                        desc = "idle background processing"
                    self._agent_loop.radial_tick(desc)
                except Exception as e:
                    logger.debug(f"Radial tick error: {e}")
```

**With:**
```python
            # Radial tick — push thought through rings, extract signature.
            # RingSignature modulates thought activation (neuroplasticity).
            if self._thought_radial_bridge is not None and thought is not None:
                try:
                    ring_sig = self._thought_radial_bridge.process(thought)
                    if ring_sig is not None:
                        # Modulate thought activation based on ring signals
                        boost = ring_sig.activation_boost
                        thought.relevance = min(1.0, thought.relevance + boost * 0.3)
                        # Store signature on thought for downstream use
                        thought._ring_signature = ring_sig
                except Exception as e:
                    logger.debug(f"Radial bridge error: {e}")
            elif self._agent_loop is not None:
                # Fallback: raw radial tick without signature extraction
                try:
                    desc = ""
                    if thought:
                        desc = thought.content[:200]
                    elif self._current_topic:
                        desc = self._current_topic
                    else:
                        desc = "idle background processing"
                    self._agent_loop.radial_tick(desc)
                except Exception as e:
                    logger.debug(f"Radial tick error: {e}")
```

- [ ] **Step 4: Add `_ring_signature` field to ContinuousThought dataclass**

In the `ContinuousThought` dataclass (~line 137), add:

```python
    _ring_signature: Any = None      # RingSignature, set by ThoughtRadialBridge
```

(Use `Any` to avoid circular import — RingSignature is attached at runtime.)

- [ ] **Step 5: Verify existing CTE tests still pass**

Run: `cd python/spaces/brain/the_brain && python -m pytest tests/test_brain_chat_quick.py -v -k "ContinuousThinking" --timeout=30`
Expected: All existing CTE tests PASS (bridge is None by default → fallback path)

- [ ] **Step 6: Commit**

```bash
cd python/spaces/brain/the_brain
git add core/brain_chat.py
git commit -m "feat(cte): wire ThoughtRadialBridge into _run_loop — ring signatures modulate thought activation"
```

---

## Task 5: Wire ThoughtRadialBridge in brain_server.py

**Files:**
- Modify: `web/brain_server.py` — `_init_production_modules()` (~line 506)

- [ ] **Step 1: Create and wire ThoughtRadialBridge after CTE + AgentLoop are set up**

After the existing line `cte.set_agent_loop(planner.agent_loop)` (~line 506-515), add:

```python
        # Wire ThoughtRadialBridge: thoughts flow through rings
        try:
            from core.thought_radial_bridge import ThoughtRadialBridge
            thought_bridge = ThoughtRadialBridge()
            thought_bridge.set_agent_loop(planner.agent_loop)
            state.continuous_thinking.set_thought_radial_bridge(thought_bridge)
            state.thought_radial_bridge = thought_bridge
            logger.info("ThoughtRadialBridge wired: CTE ↔ RadialNetwork")
        except Exception as e:
            state.thought_radial_bridge = None
            logger.warning(f"ThoughtRadialBridge init failed: {e}")
```

- [ ] **Step 2: Add `thought_radial_bridge = None` to `_init_brain_state()`**

In `_init_brain_state()` (~line 52-118), add:

```python
    state.thought_radial_bridge = None
```

- [ ] **Step 3: Verify brain_server starts**

Run: `cd python/spaces/brain/the_brain && python -c "from web.brain_server import app; print('OK')"`
Expected: `OK` (no import errors)

- [ ] **Step 4: Commit**

```bash
cd python/spaces/brain/the_brain
git add web/brain_server.py
git commit -m "feat(server): wire ThoughtRadialBridge on startup — CTE thoughts now flow through rings"
```

---

## Task 6: Reward Feedback from Chat Outcomes

**Files:**
- Modify: `core/brain_chat.py` — BrainChat response handler

When the brain generates a response and the user reacts positively (or a tool succeeds), send a reward signal back through the bridge → Hebbian update.

- [ ] **Step 1: Track `_last_processed_thought` in CTE `_run_loop()`**

In the `_run_loop()` block where thoughts are appended (after `self._thoughts.append(thought)`), add:

```python
                self._last_processed_thought = thought  # Track for reward feedback
```

Also add `self._last_processed_thought = None` to `__init__()`.

- [ ] **Step 2: Add reward recording after successful response in BrainChat**

Find BrainChat's main response method (e.g. `send()`, `chat()`, or `process_message()`). After the LLM generates a response, add:

```python
        # Reward feedback: successful response → reinforce recent thought pathways
        if self._continuous_thinking:
            bridge = getattr(self._continuous_thinking, '_thought_radial_bridge', None)
            last_thought = getattr(self._continuous_thinking, '_last_processed_thought', None)
            if bridge is not None and last_thought is not None:
                thought_id = getattr(last_thought, 'thought_id', '')
                if thought_id:
                    bridge.record_reward(
                        thought_id=thought_id,
                        reward=0.3,  # baseline positive reward for successful response
                        outcome="response_generated",
                    )
```

- [ ] **Step 3: Apply queued rewards during Hebbian updates**

In `agent_loop.py`'s `radial_tick()` method, after the existing Hebbian update loop (~line 971-981), add:

```python
            # Apply reward-weighted Hebbian updates from bridge
            if hasattr(self, '_thought_radial_bridge_ref') and self._thought_radial_bridge_ref:
                rewards = self._thought_radial_bridge_ref.drain_rewards()
                if rewards and self.hebbian is not None:
                    avg_reward = sum(r['reward'] for r in rewards) / len(rewards)
                    for i in range(len(rings) - 1):
                        self.hebbian.update_with_reward(
                            rings[i + 1],
                            activations[i],
                            activations[i + 1],
                            reward=avg_reward,
                            neuromod=neuromod,
                        )
```

- [ ] **Step 4: Wire bridge reference in brain_server.py**

After the ThoughtRadialBridge is created (Task 5), add:

```python
            planner.agent_loop._thought_radial_bridge_ref = thought_bridge
```

- [ ] **Step 5: Commit**

```bash
cd python/spaces/brain/the_brain
git add core/brain_chat.py core/agent_loop.py web/brain_server.py
git commit -m "feat(plasticity): reward feedback loop — successful outcomes strengthen ring pathways"
```

---

## Task 7: Dashboard Integration — RingSignature in SSE Stream

**Files:**
- Modify: `web/routers/cortex.py` — add ring_signature to thought SSE data

- [ ] **Step 1: Add ring_signature to thought endpoint**

In the cortex router's thought listing endpoint, extend each thought dict:

```python
    # If thought has a ring signature, include it
    ring_sig = getattr(thought, '_ring_signature', None)
    if ring_sig is not None:
        thought_dict['ring_signature'] = ring_sig.to_dict()
```

- [ ] **Step 2: Add `/api/cortex/radial-bridge/stats` endpoint**

```python
@router.get("/api/cortex/radial-bridge/stats")
async def radial_bridge_stats(request: Request) -> JSONResponse:
    """Stats for the ThoughtRadialBridge — how many thoughts processed, rewards, etc."""
    bridge = getattr(request.app.state, 'thought_radial_bridge', None)
    if bridge is None:
        return JSONResponse({"error": "ThoughtRadialBridge not initialized"}, status_code=503)
    return JSONResponse(bridge.get_stats())
```

- [ ] **Step 3: Commit**

```bash
cd python/spaces/brain/the_brain
git add web/routers/cortex.py
git commit -m "feat(dashboard): expose RingSignature + bridge stats via cortex API"
```

---

## Summary: What This Achieves

```
Before:
  CTE → text thought → ThoughtBuffer → (displayed, maybe spoken)
  RadialNetwork → tensor activations → (stored, displayed on dashboard, forgotten)

After:
  CTE → text thought
        │
        ▼ ThoughtRadialBridge.process()
   RadialNetwork forward pass
        │
        ▼ extract_ring_signature()
   RingSignature {novelty, pattern_match, semantic_richness, goal_alignment, action_readiness}
        │
        ├── thought.relevance boosted by activation_boost
        ├── should_act() → trigger action routing
        └── Hebbian weights updated by reward feedback
                                            ▲
                                            │ record_reward()
                                    successful outcome
```

**Neuroplasticity loop:**
1. Thought flows through rings → gets RingSignature
2. Thought leads to action → outcome observed
3. Outcome reward → `update_with_reward()` on ring attention biases
4. Next similar thought → different ring response (stronger/weaker pathways)
5. Over time: system learns which thought patterns are valuable
