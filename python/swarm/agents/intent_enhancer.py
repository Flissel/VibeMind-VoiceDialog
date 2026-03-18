"""
Intent Enhancer Agent - Preprocesses user input for better classification.

Part of the 3-Agent Enhancement Pipeline:
1. CollectorAgent - Accumulates short inputs
2. IntentEnhancer - Normalizes and enhances input (THIS FILE)
3. ExecutionValidator - Validates execution and triggers learning

Purpose:
- Fix ASR (speech-to-text) errors
- Normalize regional dialects to standard German
- Resolve mid-sentence corrections
- Resolve contextual references
- Make implicit intents explicit
"""

import re
import json
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


# Default path for rules JSON
DEFAULT_RULES_PATH = Path(__file__).parent.parent.parent / "data" / "enhancement_rules.json"


@dataclass
class EnhancementRule:
    """
    A single enhancement rule with evolutionary learning metrics.

    Rules track their own success/failure rates and automatically
    adjust their confidence scores based on feedback.
    """
    id: str
    pattern: str           # String match or regex pattern
    replacement: str       # What to replace with
    category: str          # "asr", "dialect", "correction", "informal", "contextual"

    # Evolutionary metrics
    times_applied: int = 0
    times_successful: int = 0
    times_failed: int = 0
    confidence_score: float = 0.5

    # Flags
    active: bool = True
    auto_generated: bool = False
    is_regex: bool = False

    def success_rate(self) -> float:
        """Calculate success rate of this rule."""
        if self.times_applied == 0:
            return 0.5  # Neutral for new rules
        return self.times_successful / self.times_applied

    def update_score(self, was_successful: bool):
        """Update score after execution feedback."""
        self.times_applied += 1
        if was_successful:
            self.times_successful += 1
            self.confidence_score = min(1.0, self.confidence_score + 0.05)
        else:
            self.times_failed += 1
            self.confidence_score = max(0.1, self.confidence_score - 0.1)

    def apply(self, text: str) -> Tuple[str, bool]:
        """
        Apply this rule to text.

        Returns:
            Tuple of (transformed_text, was_applied)
        """
        if not self.active:
            return text, False

        original = text
        if self.is_regex:
            try:
                new_text = re.sub(self.pattern, self.replacement, text, flags=re.IGNORECASE)
            except re.error as e:
                logger.warning(f"[Enhancer] Regex error in rule {self.id}: {e}")
                return text, False
        else:
            new_text = text.replace(self.pattern, self.replacement)

        was_applied = new_text != original
        return new_text, was_applied


@dataclass
class EnhancedInput:
    """Result of enhancement process."""
    original: str
    normalized_text: str
    rules_applied: List[str] = field(default_factory=list)
    confidence_boost: float = 0.0
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    enhancement_log: List[str] = field(default_factory=list)

    @property
    def was_enhanced(self) -> bool:
        return len(self.rules_applied) > 0


class RuleStore:
    """
    Persistent storage for enhancement rules with JSON backing.

    Rules are loaded from JSON on init and saved after modifications.
    """

    def __init__(self, rules_path: Optional[Path] = None):
        self.rules_path = rules_path or DEFAULT_RULES_PATH
        self.rules: Dict[str, EnhancementRule] = {}
        self._load()

    def _load(self):
        """Load rules from JSON file."""
        if self.rules_path.exists():
            try:
                with open(self.rules_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for rule_data in data.get("rules", []):
                    rule = EnhancementRule(
                        id=rule_data["id"],
                        pattern=rule_data["pattern"],
                        replacement=rule_data["replacement"],
                        category=rule_data["category"],
                        times_applied=rule_data.get("times_applied", 0),
                        times_successful=rule_data.get("times_successful", 0),
                        times_failed=rule_data.get("times_failed", 0),
                        confidence_score=rule_data.get("confidence_score", 0.5),
                        active=rule_data.get("active", True),
                        auto_generated=rule_data.get("auto_generated", False),
                        is_regex=rule_data.get("is_regex", False)
                    )
                    self.rules[rule.id] = rule

                logger.info(f"[RuleStore] Loaded {len(self.rules)} rules from {self.rules_path}")
            except Exception as e:
                logger.error(f"[RuleStore] Failed to load rules: {e}")
                self.rules = {}
        else:
            logger.warning(f"[RuleStore] Rules file not found: {self.rules_path}")
            self.rules = {}

    def save(self):
        """Save rules to JSON file."""
        try:
            data = {
                "version": "1.0",
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "rules": [
                    {
                        "id": r.id,
                        "pattern": r.pattern,
                        "replacement": r.replacement,
                        "category": r.category,
                        "times_applied": r.times_applied,
                        "times_successful": r.times_successful,
                        "times_failed": r.times_failed,
                        "confidence_score": r.confidence_score,
                        "active": r.active,
                        "auto_generated": r.auto_generated,
                        "is_regex": r.is_regex
                    }
                    for r in self.rules.values()
                ]
            }

            with open(self.rules_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(f"[RuleStore] Saved {len(self.rules)} rules")
        except Exception as e:
            logger.error(f"[RuleStore] Failed to save rules: {e}")

    def get(self, rule_id: str) -> Optional[EnhancementRule]:
        return self.rules.get(rule_id)

    def add(self, rule: EnhancementRule):
        """Add a new rule."""
        self.rules[rule.id] = rule
        logger.info(f"[RuleStore] Added rule: {rule.id}")

    def remove(self, rule_id: str):
        """Remove a rule."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"[RuleStore] Removed rule: {rule_id}")

    def get_active_rules(self, category: Optional[str] = None) -> List[EnhancementRule]:
        """Get active rules, optionally filtered by category, sorted by confidence."""
        rules = [r for r in self.rules.values() if r.active]
        if category:
            rules = [r for r in rules if r.category == category]
        return sorted(rules, key=lambda r: r.confidence_score, reverse=True)

    def all(self) -> List[EnhancementRule]:
        """Get all rules."""
        return list(self.rules.values())


class IntentEnhancer:
    """
    Preprocesses user input for better intent classification.

    Enhancement Pipeline:
    1. ASR error correction (speech-to-text fixes)
    2. Dialect normalization (regional -> standard German)
    3. Correction resolution (handle "nein warte...")
    4. Contextual reference resolution (optional)
    5. Implicit -> explicit intent expansion

    All rules are learnable - they track success/failure rates
    and auto-adjust their confidence scores.
    """

    def __init__(self, rule_store: Optional[RuleStore] = None):
        self.rules = rule_store or RuleStore()

    async def enhance(
        self,
        user_input: str,
        bubble_context: Optional[Dict[str, Any]] = None
    ) -> EnhancedInput:
        """
        Transform unclear input into classifiable text.

        Args:
            user_input: Raw user input
            bubble_context: Optional context about current bubble/space

        Returns:
            EnhancedInput with normalized text and metadata
        """
        logger.debug("enhance: user_input=%s", user_input[:50])
        result = EnhancedInput(
            original=user_input,
            normalized_text=user_input
        )
        text = user_input.lower().strip()

        # Step 1: ASR error correction
        text, applied = self._apply_category_rules(text, "asr", result)

        # Step 2: Dialect normalization
        text, applied = self._apply_category_rules(text, "dialect", result)

        # Step 3: Resolve corrections
        text, applied = self._apply_category_rules(text, "correction", result)

        # Step 4: Informal language normalization
        text, applied = self._apply_category_rules(text, "informal", result)

        # Step 5: Contextual reference resolution (always apply contextual rules)
        text = await self._resolve_context_refs(text, bubble_context or {}, result)

        # Calculate confidence boost based on rules applied
        result.confidence_boost = self._calculate_boost(result)
        result.normalized_text = text.strip()

        if result.was_enhanced:
            logger.info(
                f"[Enhancer] Enhanced: '{user_input}' -> '{result.normalized_text}' "
                f"(rules: {result.rules_applied}, boost: {result.confidence_boost:.2f})"
            )

        return result

    def _apply_category_rules(
        self,
        text: str,
        category: str,
        result: EnhancedInput
    ) -> Tuple[str, bool]:
        """Apply all active rules in a category."""
        rules = self.rules.get_active_rules(category)
        any_applied = False

        for rule in rules:
            new_text, was_applied = rule.apply(text)
            if was_applied:
                text = new_text
                result.rules_applied.append(rule.id)
                result.enhancement_log.append(
                    f"[{category}] Applied {rule.id}: '{rule.pattern}' -> '{rule.replacement}'"
                )
                any_applied = True

        return text, any_applied

    async def _resolve_context_refs(
        self,
        text: str,
        bubble_context: Dict[str, Any],
        result: EnhancedInput
    ) -> str:
        """
        Resolve contextual references using bubble context.

        Examples:
        - "das da" -> "die Idee 'Marketing'" (if idea in context)
        - "der Space" -> "der Space 'Projekte'" (if space in context)
        """
        # Apply contextual rules
        text, _ = self._apply_category_rules(text, "contextual", result)

        # Dynamic context resolution
        current_space = bubble_context.get("current_space", "")
        current_idea = bubble_context.get("current_idea", "")
        recent_ideas = bubble_context.get("recent_ideas", [])

        # Replace "diesen space" with actual space name
        if current_space and "diesen space" in text:
            text = text.replace("diesen space", f"den space '{current_space}'")
            result.enhancement_log.append(f"[context] Resolved 'diesen space' -> '{current_space}'")

        # Replace "diese idee" / "aktuelle idee" with actual idea name
        if current_idea:
            for ref in ["diese idee", "aktuelle idee", "die aktuelle idee"]:
                if ref in text:
                    text = text.replace(ref, f"die idee '{current_idea}'")
                    result.enhancement_log.append(f"[context] Resolved '{ref}' -> '{current_idea}'")

        # Store extracted entities
        if current_space:
            result.extracted_entities["current_space"] = current_space
        if current_idea:
            result.extracted_entities["current_idea"] = current_idea

        return text

    def _calculate_boost(self, result: EnhancedInput) -> float:
        """
        Calculate confidence boost based on rules applied.

        High-confidence rules (successful history) give more boost.
        """
        if not result.rules_applied:
            return 0.0

        # Average confidence of applied rules
        total_conf = 0.0
        for rule_id in result.rules_applied:
            rule = self.rules.get(rule_id)
            if rule:
                total_conf += rule.confidence_score

        avg_conf = total_conf / len(result.rules_applied)

        # Boost is scaled by number of rules applied and their confidence
        # More rules = potentially more cleanup = higher boost (up to a point)
        num_rules_factor = min(len(result.rules_applied) / 3.0, 1.0)

        return avg_conf * num_rules_factor * 0.15  # Max ~15% boost

    def update_rule(self, rule_id: str, was_successful: bool):
        """Update a rule's score after execution feedback."""
        rule = self.rules.get(rule_id)
        if rule:
            rule.update_score(was_successful)
            logger.debug(
                f"[Enhancer] Updated rule {rule_id}: "
                f"success_rate={rule.success_rate():.2%}, "
                f"confidence={rule.confidence_score:.2f}"
            )

    def update_rules_batch(self, rule_ids: List[str], was_successful: bool):
        """Update multiple rules at once."""
        logger.debug("update_rules_batch: count=%s success=%s", len(rule_ids), was_successful)
        for rule_id in rule_ids:
            self.update_rule(rule_id, was_successful)
        self.rules.save()

    def add_rule_from_correction(
        self,
        original: str,
        corrected: str,
        category: str = "auto"
    ) -> Optional[EnhancementRule]:
        """
        Generate a new rule from user correction.

        Called when user corrects the system:
        "nein ich meinte [corrected]" after system misunderstood [original]
        """
        logger.debug("add_rule_from_correction: original=%s", original[:50])
        # Extract pattern from original
        pattern = self._extract_pattern(original)
        if not pattern:
            return None

        # Determine category
        if category == "auto":
            category = self._classify_pattern(original)

        # Generate unique ID
        rule_id = f"auto_{category}_{int(time.time())}"

        new_rule = EnhancementRule(
            id=rule_id,
            pattern=pattern,
            replacement=corrected,
            category=category,
            confidence_score=0.6,  # Start conservative
            auto_generated=True,
            is_regex=False
        )

        self.rules.add(new_rule)
        self.rules.save()

        logger.info(f"[Enhancer] Generated new rule: {rule_id} ({pattern} -> {corrected})")
        return new_rule

    def _extract_pattern(self, text: str) -> Optional[str]:
        """Extract a reusable pattern from text."""
        text = text.lower().strip()

        # Short texts become direct patterns
        if len(text.split()) <= 4:
            return text

        # Longer texts - could use LLM for better extraction
        # For now, just use the full text
        return text

    def _classify_pattern(self, text: str) -> str:
        """Determine category of a pattern."""
        text = text.lower()

        # Known ASR error patterns
        asr_markers = ["idden", "speiss", "erstele", "formatiren", "tabelen"]
        if any(m in text for m in asr_markers):
            return "asr"

        # Dialect markers
        dialect_markers = ["amoi", "dat", "wat", "geh ma", "schaug", "zamfass"]
        if any(m in text for m in dialect_markers):
            return "dialect"

        # Correction markers
        correction_markers = ["nein", "warte", "doch", "nee", "andersrum"]
        if any(m in text for m in correction_markers):
            return "correction"

        # Default to informal
        return "informal"

    def prune_bad_rules(self, threshold: float = 0.3, min_applications: int = 10):
        """Deactivate rules with poor success rates."""
        logger.debug("prune_bad_rules: threshold=%s min_applications=%s", threshold, min_applications)
        pruned = 0
        for rule in self.rules.all():
            if rule.times_applied >= min_applications and rule.success_rate() < threshold:
                rule.active = False
                pruned += 1
                logger.warning(
                    f"[Enhancer] Deactivated rule {rule.id}: "
                    f"success_rate={rule.success_rate():.2%}"
                )

        if pruned > 0:
            self.rules.save()
            logger.info(f"[Enhancer] Pruned {pruned} underperforming rules")

        return pruned

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about rules."""
        logger.debug("get_stats called")
        all_rules = self.rules.all()
        active = [r for r in all_rules if r.active]

        by_category = {}
        for rule in active:
            cat = rule.category
            if cat not in by_category:
                by_category[cat] = {"count": 0, "avg_success": 0.0}
            by_category[cat]["count"] += 1

        # Calculate avg success per category
        for cat in by_category:
            cat_rules = [r for r in active if r.category == cat]
            rates = [r.success_rate() for r in cat_rules if r.times_applied > 0]
            by_category[cat]["avg_success"] = sum(rates) / len(rates) if rates else 0.5

        return {
            "total_rules": len(all_rules),
            "active_rules": len(active),
            "auto_generated": len([r for r in all_rules if r.auto_generated]),
            "by_category": by_category
        }


# Singleton instance
_enhancer: Optional[IntentEnhancer] = None


def get_intent_enhancer() -> IntentEnhancer:
    """Get or create the singleton IntentEnhancer instance."""
    global _enhancer
    if _enhancer is None:
        _enhancer = IntentEnhancer()
    return _enhancer


def reset_intent_enhancer():
    """Reset the singleton instance."""
    global _enhancer
    _enhancer = None
