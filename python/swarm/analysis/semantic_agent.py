"""
SemanticAgent - Enhanced NLP analysis with ElevenLabs metadata integration

Phase 15: Enhanced Reasoning with Semantic Analysis
- Multi-modal confidence calculation (text + audio metadata)
- Context-aware reasoning with user history patterns
- Semantic similarity matching for hypothesis merging
- Pattern-based reasoning with ML-like features
- Adaptive confidence thresholds based on context
"""

import logging
import re
from typing import List, Optional, Dict, Any, Tuple
from collections import defaultdict
import math

from swarm.analysis.intent_analysis_team import IntentHypothesis
from swarm.analysis.user_context import UserContext
from swarm.elevenlabs_input import ElevenLabsInput

logger = logging.getLogger(__name__)


class SemanticAgent:
    """
    Enhanced Semantic Analysis Agent with Multi-Modal Reasoning.

    Phase 15 Features:
    - Multi-modal confidence calculation (text + audio + context)
    - Context-aware reasoning with user history patterns
    - Semantic similarity matching for hypothesis consolidation
    - Pattern-based reasoning with adaptive thresholds
    - Enhanced hypothesis merging with conflict resolution
    """

    # Semantic similarity patterns for hypothesis merging
    SEMANTIC_CLUSTERS = {
        "creation": ["idea.create", "bubble.create", "code.generate"],
        "navigation": ["bubble.enter", "bubble.exit", "idea.move"],
        "information": ["idea.list", "bubble.list", "idea.find"],
        "modification": ["idea.update", "idea.connect", "idea.expand"],
        "deletion": ["idea.delete", "bubble.delete"],
        "conversation": ["conversation.greeting", "conversation.help", "conversation.unknown"]
    }

    # Pattern weights for confidence calculation
    PATTERN_WEIGHTS = {
        "elevenlabs_intent": 0.4,    # Highest weight for direct intent detection
        "transcript_confidence": 0.25, # Audio quality affects confidence
        "language_patterns": 0.15,    # Language-specific patterns
        "context_history": 0.1,       # User behavior patterns
        "semantic_similarity": 0.1    # Similarity to known patterns
    }

    def __init__(self):
        """Initialize Enhanced SemanticAgent."""
        self.name = "enhanced_semantic"

        # Initialize pattern learning (could be persisted in future)
        self.user_patterns = defaultdict(lambda: defaultdict(float))
        self.intent_patterns = self._initialize_intent_patterns()

        logger.info("Enhanced SemanticAgent initialized with multi-modal reasoning")

    async def analyze(
        self,
        user_input: str,
        context: UserContext,
        elevenlabs_input: Optional[ElevenLabsInput] = None
    ) -> List[IntentHypothesis]:
        """
        Enhanced semantic analysis with multi-modal reasoning.

        Phase 15: Multi-stage analysis pipeline:
        1. Multi-modal confidence assessment
        2. Context-aware pattern matching
        3. Semantic similarity clustering
        4. Enhanced hypothesis merging

        Args:
            user_input: Raw user input text
            context: User context for analysis
            elevenlabs_input: ElevenLabs metadata (optional)

        Returns:
            List of IntentHypothesis with enhanced semantic analysis
        """
        hypotheses = []

        # =================================================================
        # PHASE 1: MULTI-MODAL CONFIDENCE ASSESSMENT
        # =================================================================
        base_confidence = self._calculate_multi_modal_confidence(user_input, context, elevenlabs_input)

        # =================================================================
        # PHASE 2: CONTEXT-AWARE PATTERN MATCHING
        # =================================================================
        context_hypotheses = self._context_aware_analysis(user_input, context, base_confidence)
        hypotheses.extend(context_hypotheses)

        # =================================================================
        # PHASE 3: ELEVENLABS ENHANCED ANALYSIS (if available)
        # =================================================================
        if elevenlabs_input:
            elevenlabs_hypotheses = self._enhanced_elevenlabs_analysis(user_input, elevenlabs_input, base_confidence)
            hypotheses.extend(elevenlabs_hypotheses)

        # =================================================================
        # PHASE 4: PATTERN-BASED REASONING
        # =================================================================
        pattern_hypotheses = self._pattern_based_reasoning(user_input, context, base_confidence)
        hypotheses.extend(pattern_hypotheses)

        # =================================================================
        # PHASE 5: ENHANCED HYPOTHESIS MERGING
        # =================================================================
        merged_hypotheses = self._enhanced_hypothesis_merging(hypotheses, context)

        logger.info(f"Enhanced SemanticAgent generated {len(merged_hypotheses)} merged hypotheses")
        return merged_hypotheses

    def _initialize_intent_patterns(self) -> Dict[str, Dict[str, float]]:
        """Initialize pattern recognition for different intent types."""
        return {
            "creation": {
                "patterns": [r"(erstelle|erstellen|create|new|make|neu|neue)", r"(eine?n?\s+)?idee", r"(ein\s+)?space"],
                "base_confidence": 0.6
            },
            "navigation": {
                "patterns": [r"(gehe|geh|go|enter|betrete|wechsle)", r"(verlasse|exit|leave)", r"(finde|find|suche)"],
                "base_confidence": 0.5
            },
            "information": {
                "patterns": [r"(zeig|zeige|show|liste|list|display)", r"(gib|give|tell)", r"(wie\s+viel|how\s+many)"],
                "base_confidence": 0.55
            },
            "modification": {
                "patterns": [r"(ändere|änder|update|change|bearbeite)", r"(verbinde|connect|link)", r"(erweitere|expand)"],
                "base_confidence": 0.5
            },
            "deletion": {
                "patterns": [r"(lösche|delete|remove|entferne)", r"(weg|away)"],
                "base_confidence": 0.7  # Higher confidence for destructive actions
            }
        }

    def _calculate_multi_modal_confidence(
        self,
        user_input: str,
        context: UserContext,
        elevenlabs_input: Optional[ElevenLabsInput]
    ) -> float:
        """
        Calculate base confidence using multi-modal factors.

        Combines:
        - Text clarity and length
        - ElevenLabs audio metadata (if available)
        - User context reliability
        - Historical pattern matching
        """
        confidence_factors = {}

        # Text-based confidence
        text_confidence = self._calculate_text_confidence(user_input)
        confidence_factors["text"] = text_confidence * 0.3

        # ElevenLabs confidence (if available)
        if elevenlabs_input:
            audio_confidence = self._calculate_audio_confidence(elevenlabs_input)
            confidence_factors["audio"] = audio_confidence * 0.4
        else:
            confidence_factors["audio"] = 0.2  # Neutral fallback

        # Context confidence
        context_confidence = self._calculate_context_confidence(context)
        confidence_factors["context"] = context_confidence * 0.3

        # Weighted average
        total_weight = sum(self.PATTERN_WEIGHTS.values())
        final_confidence = sum(
            factor_value * (weight / total_weight)
            for factor_value, weight in zip(confidence_factors.values(), self.PATTERN_WEIGHTS.values())
        )

        return min(final_confidence, 0.95)  # Cap at 95%

    def _calculate_text_confidence(self, user_input: str) -> float:
        """Calculate confidence based on text characteristics."""
        text = user_input.strip()

        # Length factor (too short = low confidence, too long = potentially unclear)
        length = len(text.split())
        if length < 2:
            return 0.3  # Too short
        elif length > 20:
            return 0.6  # Potentially complex
        else:
            return 0.8  # Optimal length

    def _calculate_audio_confidence(self, elevenlabs_input: ElevenLabsInput) -> float:
        """Calculate confidence based on ElevenLabs audio metadata."""
        if not elevenlabs_input:
            return 0.5

        confidence = 0.5  # Base

        # Transcript confidence
        if elevenlabs_input.transcript_confidence:
            confidence += elevenlabs_input.transcript_confidence * 0.3

        # Intent confidence (if detected)
        if elevenlabs_input.intent_confidence:
            confidence += elevenlabs_input.intent_confidence * 0.4

        # Language detection confidence
        if elevenlabs_input.detected_language and elevenlabs_input.detected_language != "unknown":
            confidence += 0.1

        return min(confidence, 1.0)

    def _calculate_context_confidence(self, context: UserContext) -> float:
        """Calculate confidence based on user context reliability."""
        if not context:
            return 0.4

        confidence = 0.5  # Base

        # Recent actions indicate active context
        if context.recent_actions and len(context.recent_actions) > 0:
            confidence += 0.2

        # Current space indicates focused context
        if context.current_space:
            confidence += 0.1

        # Session continuity
        if context.session_id:
            confidence += 0.1

        return min(confidence, 0.9)

    def _context_aware_analysis(
        self,
        user_input: str,
        context: UserContext,
        base_confidence: float
    ) -> List[IntentHypothesis]:
        """
        Generate hypotheses based on user context and behavior patterns.

        Considers:
        - Recent actions (what user just did)
        - Current space (where user is working)
        - Historical patterns (what user typically does)
        """
        hypotheses = []

        if not context:
            return hypotheses

        # Recent action patterns
        if context.recent_actions:
            recent_hypotheses = self._analyze_recent_actions(user_input, context.recent_actions, base_confidence)
            hypotheses.extend(recent_hypotheses)

        # Current space context
        if context.current_space:
            space_hypotheses = self._analyze_current_space(user_input, context.current_space, base_confidence)
            hypotheses.extend(space_hypotheses)

        # User behavior patterns (learned from history)
        pattern_hypotheses = self._analyze_user_patterns(user_input, context, base_confidence)
        hypotheses.extend(pattern_hypotheses)

        return hypotheses

    def _analyze_recent_actions(
        self,
        user_input: str,
        recent_actions: List[Any],
        base_confidence: float
    ) -> List[IntentHypothesis]:
        """Analyze patterns based on user's recent actions."""
        hypotheses = []

        if not recent_actions:
            return hypotheses

        # Look at last few actions for context
        recent_types = [action.get('type', '') for action in recent_actions[-3:] if action]

        # Continuation patterns
        if any('create' in action for action in recent_types):
            # User recently created something - might want to continue creating
            if self._contains_creation_keywords(user_input):
                hypotheses.append(IntentHypothesis(
                    event_type="idea.create",
                    payload={},
                    confidence=min(base_confidence + 0.2, 0.8),
                    reasoning="Recent creation activity suggests continuation",
                    source="context_recent_actions"
                ))

        if any('list' in action for action in recent_types):
            # User recently listed something - might want more information
            if self._contains_information_keywords(user_input):
                hypotheses.append(IntentHypothesis(
                    event_type="idea.list",
                    payload={},
                    confidence=min(base_confidence + 0.15, 0.75),
                    reasoning="Recent listing activity suggests information seeking",
                    source="context_recent_actions"
                ))

        return hypotheses

    def _analyze_current_space(
        self,
        user_input: str,
        current_space: str,
        base_confidence: float
    ) -> List[IntentHypothesis]:
        """Analyze intent based on current working space."""
        hypotheses = []

        space_lower = current_space.lower()

        # Space-specific patterns
        if 'projekt' in space_lower or 'project' in space_lower:
            if self._contains_creation_keywords(user_input):
                hypotheses.append(IntentHypothesis(
                    event_type="idea.create",
                    payload={"space_context": current_space},
                    confidence=min(base_confidence + 0.1, 0.7),
                    reasoning=f"Working in project space '{current_space}' suggests project-related creation",
                    source="context_current_space"
                ))

        elif 'ideen' in space_lower or 'ideas' in space_lower:
            if self._contains_information_keywords(user_input):
                hypotheses.append(IntentHypothesis(
                    event_type="idea.list",
                    payload={"space_context": current_space},
                    confidence=min(base_confidence + 0.1, 0.7),
                    reasoning=f"Working in ideas space '{current_space}' suggests idea exploration",
                    source="context_current_space"
                ))

        return hypotheses

    def _analyze_user_patterns(
        self,
        user_input: str,
        context: UserContext,
        base_confidence: float
    ) -> List[IntentHypothesis]:
        """Analyze based on learned user behavior patterns."""
        hypotheses = []

        # Simple pattern learning - could be enhanced with ML
        user_id = context.user_id or "default"

        # Check if user frequently creates ideas
        creation_frequency = self.user_patterns[user_id].get("idea.create", 0.0)
        if creation_frequency > 0.3:  # User creates ideas >30% of the time
            if self._contains_creation_keywords(user_input):
                hypotheses.append(IntentHypothesis(
                    event_type="idea.create",
                    payload={},
                    confidence=min(base_confidence + 0.1, 0.75),
                    reasoning="User frequently creates ideas - pattern matching",
                    source="context_user_patterns"
                ))

        return hypotheses

    def _contains_creation_keywords(self, text: str) -> bool:
        """Check if text contains creation-related keywords."""
        keywords = ["erstelle", "erstellen", "create", "new", "neu", "neue", "make", "generiere"]
        return any(keyword in text.lower() for keyword in keywords)

    def _contains_information_keywords(self, text: str) -> bool:
        """Check if text contains information-seeking keywords."""
        keywords = ["zeig", "zeige", "show", "liste", "list", "gib", "give", "finde", "find"]
        return any(keyword in text.lower() for keyword in keywords)

    def _enhanced_elevenlabs_analysis(
        self,
        user_input: str,
        elevenlabs_input: ElevenLabsInput,
        base_confidence: float
    ) -> List[IntentHypothesis]:
        """Enhanced ElevenLabs analysis with multi-modal reasoning."""
        hypotheses = []

        # Original ElevenLabs intent detection
        if elevenlabs_input.has_detected_intent():
            hypothesis = self._create_enhanced_elevenlabs_hypothesis(elevenlabs_input, base_confidence)
            if hypothesis:
                hypotheses.append(hypothesis)

        # Language-enhanced analysis
        if elevenlabs_input.detected_language and elevenlabs_input.detected_language != "unknown":
            lang_hypotheses = self._enhanced_language_analysis(user_input, elevenlabs_input, base_confidence)
            hypotheses.extend(lang_hypotheses)

        # Audio quality-based analysis
        if elevenlabs_input.has_confident_transcript():
            audio_hypotheses = self._audio_quality_analysis(user_input, elevenlabs_input, base_confidence)
            hypotheses.extend(audio_hypotheses)

        return hypotheses

    def _create_enhanced_elevenlabs_hypothesis(
        self,
        elevenlabs_input: ElevenLabsInput,
        base_confidence: float
    ) -> Optional[IntentHypothesis]:
        """Create enhanced hypothesis from ElevenLabs with confidence boosting."""
        if not elevenlabs_input.intent_detected or not elevenlabs_input.intent_confidence:
            return None

        event_type = self._map_elevenlabs_intent(elevenlabs_input.intent_detected)

        # Enhanced confidence calculation
        elevenlabs_conf = elevenlabs_input.intent_confidence
        transcript_conf = elevenlabs_input.transcript_confidence or 0.5

        # Boost confidence based on multiple factors
        enhanced_confidence = (
            elevenlabs_conf * 0.6 +      # Direct intent confidence
            transcript_conf * 0.3 +      # Audio quality
            base_confidence * 0.1        # Base context confidence
        )

        enhanced_confidence = min(enhanced_confidence, 0.95)

        return IntentHypothesis(
            event_type=event_type,
            payload={},
            confidence=enhanced_confidence,
            reasoning=f"Enhanced ElevenLabs analysis: intent={elevenlabs_input.intent_detected} "
                     f"(confidence: {elevenlabs_conf:.2f}, audio: {transcript_conf:.2f})",
            source="enhanced_elevenlabs"
        )

    def _enhanced_language_analysis(
        self,
        user_input: str,
        elevenlabs_input: ElevenLabsInput,
        base_confidence: float
    ) -> List[IntentHypothesis]:
        """Enhanced language-based analysis with confidence weighting."""
        hypotheses = []
        language = elevenlabs_input.detected_language

        # Language-specific enhanced patterns
        if language == "de":
            hypotheses.extend(self._german_enhanced_patterns(user_input, base_confidence))
        elif language == "en":
            hypotheses.extend(self._english_enhanced_patterns(user_input, base_confidence))

        return hypotheses

    def _german_enhanced_patterns(self, user_input: str, base_confidence: float) -> List[IntentHypothesis]:
        """Enhanced German pattern recognition."""
        hypotheses = []
        text_lower = user_input.lower()

        # Complex German patterns
        if re.search(r"(ich\s+will|mich\s+interessiert|ich\s+brauche)", text_lower):
            # Expressing personal needs - likely creation or information
            if "idee" in text_lower or "konzept" in text_lower:
                hypotheses.append(IntentHypothesis(
                    event_type="idea.create",
                    payload={},
                    confidence=min(base_confidence + 0.15, 0.75),
                    reasoning="German personal need expression with idea keywords",
                    source="enhanced_german_patterns"
                ))

        return hypotheses

    def _english_enhanced_patterns(self, user_input: str, base_confidence: float) -> List[IntentHypothesis]:
        """Enhanced English pattern recognition."""
        hypotheses = []
        text_lower = user_input.lower()

        # Complex English patterns
        if re.search(r"(i\s+want|i\s+need|i'd\s+like)", text_lower):
            # Expressing personal wants - likely creation or information
            if "idea" in text_lower or "concept" in text_lower:
                hypotheses.append(IntentHypothesis(
                    event_type="idea.create",
                    payload={},
                    confidence=min(base_confidence + 0.15, 0.75),
                    reasoning="English personal want expression with idea keywords",
                    source="enhanced_english_patterns"
                ))

        return hypotheses

    def _audio_quality_analysis(
        self,
        user_input: str,
        elevenlabs_input: ElevenLabsInput,
        base_confidence: float
    ) -> List[IntentHypothesis]:
        """Analyze intent based on audio quality indicators."""
        hypotheses = []

        transcript_conf = elevenlabs_input.transcript_confidence or 0.5

        if transcript_conf > 0.9:
            # Very clear audio - high confidence for direct actions
            hypotheses.append(IntentHypothesis(
                event_type="conversation.greeting",
                payload={},
                confidence=min(base_confidence + 0.1, 0.8),
                reasoning=f"Very clear audio (confidence: {transcript_conf}) suggests confident intent",
                source="audio_quality_analysis"
            ))
        elif transcript_conf < 0.7:
            # Unclear audio - suggest clarification
            hypotheses.append(IntentHypothesis(
                event_type="conversation.clarify",
                payload={"reason": "unclear_audio"},
                confidence=0.7,  # High confidence for clarification need
                reasoning=f"Unclear audio (confidence: {transcript_conf}) suggests clarification needed",
                source="audio_quality_analysis"
            ))

        return hypotheses

    def _pattern_based_reasoning(
        self,
        user_input: str,
        context: UserContext,
        base_confidence: float
    ) -> List[IntentHypothesis]:
        """Advanced pattern-based reasoning with regex and semantic analysis."""
        hypotheses = []

        for intent_type, pattern_data in self.intent_patterns.items():
            patterns = pattern_data["patterns"]
            base_pattern_confidence = pattern_data["base_confidence"]

            # Check each pattern
            for pattern in patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    event_type = self._map_pattern_to_event(intent_type, user_input)

                    # Adjust confidence based on context and base confidence
                    adjusted_confidence = min(
                        base_pattern_confidence + (base_confidence * 0.2),
                        0.85
                    )

                    hypotheses.append(IntentHypothesis(
                        event_type=event_type,
                        payload={},
                        confidence=adjusted_confidence,
                        reasoning=f"Pattern match for {intent_type}: '{pattern}'",
                        source="pattern_based_reasoning"
                    ))
                    break  # Only one hypothesis per intent type

        return hypotheses

    def _map_pattern_to_event(self, intent_type: str, user_input: str) -> str:
        """Map pattern type to specific event type."""
        mapping = {
            "creation": "idea.create",
            "navigation": "bubble.enter",
            "information": "idea.list",
            "modification": "idea.update",
            "deletion": "idea.delete"
        }
        return mapping.get(intent_type, "conversation.unknown")

    def _enhanced_hypothesis_merging(
        self,
        hypotheses: List[IntentHypothesis],
        context: UserContext
    ) -> List[IntentHypothesis]:
        """
        Enhanced hypothesis merging with semantic similarity and conflict resolution.

        Features:
        - Semantic clustering (similar intents grouped)
        - Confidence-based winner selection
        - Conflict resolution for contradictory hypotheses
        """
        if not hypotheses:
            return []

        # Group by semantic clusters
        clustered = self._cluster_hypotheses_by_semantics(hypotheses)

        merged = []
        for cluster_name, cluster_hypotheses in clustered.items():
            if len(cluster_hypotheses) == 1:
                merged.append(cluster_hypotheses[0])
            else:
                # Merge multiple hypotheses in same cluster
                merged_hypothesis = self._merge_cluster_hypotheses(cluster_hypotheses, cluster_name)
                merged.append(merged_hypothesis)

        # Sort by confidence (highest first)
        merged.sort(key=lambda h: h.confidence, reverse=True)

        # Limit to top hypotheses to avoid overwhelming
        return merged[:5]

    def _cluster_hypotheses_by_semantics(self, hypotheses: List[IntentHypothesis]) -> Dict[str, List[IntentHypothesis]]:
        """Cluster hypotheses by semantic similarity."""
        clusters = defaultdict(list)

        for hypothesis in hypotheses:
            cluster_name = self._find_semantic_cluster(hypothesis.event_type)
            clusters[cluster_name].append(hypothesis)

        return dict(clusters)

    def _find_semantic_cluster(self, event_type: str) -> str:
        """Find which semantic cluster an event type belongs to."""
        for cluster_name, event_types in self.SEMANTIC_CLUSTERS.items():
            if event_type in event_types:
                return cluster_name

        # Default cluster for unknown types
        if event_type.startswith("conversation"):
            return "conversation"
        else:
            return "other"

    def _merge_cluster_hypotheses(
        self,
        cluster_hypotheses: List[IntentHypothesis],
        cluster_name: str
    ) -> IntentHypothesis:
        """Merge multiple hypotheses in the same semantic cluster."""
        if not cluster_hypotheses:
            return None

        # Select the highest confidence hypothesis as base
        best_hypothesis = max(cluster_hypotheses, key=lambda h: h.confidence)

        # Boost confidence slightly for consensus (multiple sources agree)
        consensus_boost = min(len(cluster_hypotheses) * 0.05, 0.15)
        enhanced_confidence = min(best_hypothesis.confidence + consensus_boost, 0.95)

        # Combine reasoning from multiple sources
        all_sources = [h.source for h in cluster_hypotheses]
        unique_sources = list(set(all_sources))

        enhanced_reasoning = (
            f"Enhanced {cluster_name} hypothesis (confidence: {enhanced_confidence:.2f}) "
            f"from {len(unique_sources)} sources: {', '.join(unique_sources)}"
        )

        return IntentHypothesis(
            event_type=best_hypothesis.event_type,
            payload=best_hypothesis.payload,
            confidence=enhanced_confidence,
            reasoning=enhanced_reasoning,
            source=f"enhanced_{cluster_name}_merge"
        )

    def _create_elevenlabs_hypothesis(self, elevenlabs_input: ElevenLabsInput) -> Optional[IntentHypothesis]:
        """
        Create hypothesis from ElevenLabs intent detection.

        Args:
            elevenlabs_input: ElevenLabs metadata

        Returns:
            IntentHypothesis or None if invalid
        """
        if not elevenlabs_input.intent_detected or not elevenlabs_input.intent_confidence:
            return None

        # Map ElevenLabs intent to VibeMind event type
        event_type = self._map_elevenlabs_intent(elevenlabs_input.intent_detected)

        # Create hypothesis with ElevenLabs confidence
        return IntentHypothesis(
            event_type=event_type,
            payload={},  # Will be filled by other agents
            confidence=min(elevenlabs_input.intent_confidence, 0.95),  # Cap at 95%
            reasoning=f"ElevenLabs detected intent '{elevenlabs_input.intent_detected}' with confidence {elevenlabs_input.intent_confidence}",
            source="elevenlabs_semantic"
        )

    def _map_elevenlabs_intent(self, elevenlabs_intent: str) -> str:
        """
        Map ElevenLabs intent to VibeMind event type.

        Args:
            elevenlabs_intent: Intent string from ElevenLabs

        Returns:
            VibeMind event type
        """
        # Basic mapping - can be extended
        intent_mapping = {
            "create_idea": "idea.create",
            "list_ideas": "idea.list",
            "delete_idea": "idea.delete",
            "update_idea": "idea.update",
            "create_space": "bubble.create",
            "enter_space": "bubble.enter",
            "exit_space": "bubble.exit",
            "generate_code": "code.generate",
            "run_task": "desktop.task",
            "open_app": "desktop.open_app",
        }

        return intent_mapping.get(elevenlabs_intent, f"conversation.{elevenlabs_intent}")

    def _analyze_by_language(self, user_input: str, language: str) -> List[IntentHypothesis]:
        """
        Generate hypotheses based on detected language patterns.

        Args:
            user_input: User input text
            language: Detected language code

        Returns:
            List of language-based hypotheses
        """
        hypotheses = []

        # Language-specific patterns
        if language == "de":
            # German patterns
            if any(word in user_input.lower() for word in ["erstelle", "erstellen", "neu", "neue"]):
                hypotheses.append(IntentHypothesis(
                    event_type="idea.create",
                    payload={},
                    confidence=0.4,
                    reasoning="German creation keywords detected",
                    source="semantic_language"
                ))
            elif any(word in user_input.lower() for word in ["liste", "zeig", "zeige"]):
                hypotheses.append(IntentHypothesis(
                    event_type="idea.list",
                    payload={},
                    confidence=0.4,
                    reasoning="German list keywords detected",
                    source="semantic_language"
                ))

        elif language == "en":
            # English patterns
            if any(word in user_input.lower() for word in ["create", "new", "make"]):
                hypotheses.append(IntentHypothesis(
                    event_type="idea.create",
                    payload={},
                    confidence=0.4,
                    reasoning="English creation keywords detected",
                    source="semantic_language"
                ))
            elif any(word in user_input.lower() for word in ["show", "list", "display"]):
                hypotheses.append(IntentHypothesis(
                    event_type="idea.list",
                    payload={},
                    confidence=0.4,
                    reasoning="English list keywords detected",
                    source="semantic_language"
                ))

        return hypotheses

    def _analyze_transcript_confidence(self, user_input: str, elevenlabs_input: ElevenLabsInput) -> List[IntentHypothesis]:
        """
        Generate hypotheses based on transcript confidence.

        High confidence suggests clear intent, low confidence suggests clarification needed.

        Args:
            user_input: User input text
            elevenlabs_input: ElevenLabs metadata

        Returns:
            List of confidence-based hypotheses
        """
        hypotheses = []

        confidence = elevenlabs_input.transcript_confidence

        if confidence > 0.9:
            # Very high confidence - boost direct action hypotheses
            hypotheses.append(IntentHypothesis(
                event_type="conversation.greeting",
                payload={},
                confidence=min(confidence * 0.8, 0.7),  # Don't over-boost
                reasoning=f"High transcript confidence ({confidence}) suggests clear intent",
                source="semantic_confidence"
            ))
        elif confidence < 0.6:
            # Low confidence - suggest clarification
            hypotheses.append(IntentHypothesis(
                event_type="conversation.clarify",
                payload={"question": "Können Sie das bitte wiederholen? Die Aufnahme war nicht ganz klar."},
                confidence=0.6,
                reasoning=f"Low transcript confidence ({confidence}) suggests unclear audio",
                source="semantic_confidence"
            ))

        return hypotheses

    def _semantic_fallback_analysis(self, user_input: str, context: UserContext) -> List[IntentHypothesis]:
        """
        Fallback semantic analysis without ElevenLabs metadata.

        Args:
            user_input: User input text
            context: User context

        Returns:
            List of fallback hypotheses
        """
        hypotheses = []

        # Simple keyword-based analysis
        input_lower = user_input.lower()

        # Creation patterns
        if any(word in input_lower for word in ["create", "erstelle", "neu", "new", "make"]):
            hypotheses.append(IntentHypothesis(
                event_type="idea.create",
                payload={},
                confidence=0.3,
                reasoning="Creation keywords detected in fallback analysis",
                source="semantic_fallback"
            ))

        # List patterns
        elif any(word in input_lower for word in ["list", "liste", "show", "zeig", "display"]):
            hypotheses.append(IntentHypothesis(
                event_type="idea.list",
                payload={},
                confidence=0.3,
                reasoning="List keywords detected in fallback analysis",
                source="semantic_fallback"
            ))

        # Help patterns
        elif any(word in input_lower for word in ["help", "hilfe", "?", "was", "wie"]):
            hypotheses.append(IntentHypothesis(
                event_type="conversation.help",
                payload={},
                confidence=0.4,
                reasoning="Help keywords detected in fallback analysis",
                source="semantic_fallback"
            ))

        return hypotheses


# Singleton instance
_semantic_agent: Optional[SemanticAgent] = None


def get_semantic_agent() -> SemanticAgent:
    """Get or create SemanticAgent singleton."""
    global _semantic_agent
    if _semantic_agent is None:
        _semantic_agent = SemanticAgent()
    return _semantic_agent