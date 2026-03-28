"""
ContextAgent - User context aware intent analysis

Part of Phase 13: Multi-Agent Intent Analysis System

Uses user context to:
1. Understand current situation (space, recent actions)
2. Resolve ambiguous references ("die letzte Idee")
3. Predict likely actions based on patterns
4. Personalize parameter extraction
"""

import json
import logging
from typing import Dict, Any, List, Optional

from swarm.analysis.user_context import UserContext

logger = logging.getLogger(__name__)


# Context-aware analysis prompt
CONTEXT_PROMPT = """Du bist ein kontext-bewusster Intent-Analyse-Agent.
Nutze den User-Kontext um den Intent besser zu verstehen.

## Aktueller Kontext

### User Session
- Aktueller Space: {current_space}
- Interaktions-Stil: {interaction_style}

### Letzte Aktionen
{recent_actions}

### Erwähnte Entitäten
{mentioned_entities}

### Aktuelles Thema
{current_topic}

## User Input
{user_input}

## Kontext-Analyse

Beachte besonders:
1. **Relative Referenzen auflösen:**
   - "die letzte Idee" → Name der zuletzt erstellten Idee
   - "dieser Space" → Aktueller Space-Name
   - "das" → Bezug auf zuletzt erwähntes Objekt

2. **Implizite Parameter ableiten:**
   - Wenn im Space "Projekt" → neue Ideen gehören vermutlich dazu
   - Nach idea.create → "verbinde" bezieht sich wahrscheinlich auf neue Idee

3. **Kontext-basierte Präferenzen:**
   - User bevorzugt {interaction_style} Stil
   - Typische Aktionsmuster erkennen

## Antwort Format (NUR JSON):
{{
    "context_insights": {{
        "resolved_references": {{"was_aufgeloest": "wozu_aufgeloest"}},
        "implicit_params": {{"param": "abgeleiteter_wert"}},
        "pattern_match": "erkanntes_muster_oder_null"
    }},
    "hypothesis": {{
        "event_type": "der.event.type",
        "payload": {{"param": "WERT_MIT_KONTEXT"}},
        "confidence": 0.0-1.0,
        "reasoning": "Kontext-basierte Begruendung"
    }}
}}
"""


class ContextAgent:
    """
    Context-aware intent analysis agent.

    Uses user context to improve intent understanding:
    - Resolves relative references
    - Infers implicit parameters
    - Applies user preferences
    """

    def __init__(self, client, model: str):
        """
        Initialize the context agent.

        Args:
            client: OpenAI-compatible client
            model: Model identifier to use
        """
        self.client = client
        self.model = model

    async def analyze(self, user_input: str, context: UserContext) -> List['IntentHypothesis']:
        """
        Analyze user input with context awareness.

        Args:
            user_input: Natural language user request
            context: User context from UserContextBuilder

        Returns:
            List of context-aware IntentHypothesis
        """
        from swarm.analysis.intent_analysis_team import IntentHypothesis

        try:
            # Format context for prompt
            prompt = CONTEXT_PROMPT.format(
                user_input=user_input,
                current_space=context.current_space or "Keiner (Multiverse)",
                interaction_style=context.interaction_style,
                recent_actions=self._format_recent_actions(context),
                mentioned_entities=", ".join(context.mentioned_entities) if context.mentioned_entities else "Keine",
                current_topic=context.current_topic or "Kein spezifisches Thema"
            )

            from llm_config import token_kwargs
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                **token_kwargs(self.model, 600),
            )

            content = response.choices[0].message.content.strip()
            content = self._extract_json(content)

            result = json.loads(content)

            # Log context insights
            insights = result.get("context_insights", {})
            logger.debug(f"Context insights: resolved={insights.get('resolved_references')}, "
                        f"implicit={insights.get('implicit_params')}, "
                        f"pattern={insights.get('pattern_match')}")

            hypothesis = result.get("hypothesis", {})

            # Apply resolved references to payload
            payload = hypothesis.get("payload", {})
            if insights.get("resolved_references"):
                for key, value in insights["resolved_references"].items():
                    if key not in payload or not payload[key]:
                        payload[key] = value

            # Apply implicit params
            if insights.get("implicit_params"):
                for key, value in insights["implicit_params"].items():
                    if key not in payload or not payload[key]:
                        payload[key] = value

            hypotheses = [IntentHypothesis(
                event_type=hypothesis.get("event_type", "conversation.unknown"),
                payload=payload,
                confidence=float(hypothesis.get("confidence", 0.5)),
                reasoning=hypothesis.get("reasoning", "Context-based analysis"),
                source="context"
            )]

            # Boost confidence if pattern matches
            if insights.get("pattern_match"):
                hypotheses[0].confidence = min(1.0, hypotheses[0].confidence * 1.1)
                hypotheses[0].reasoning += f" (Pattern: {insights['pattern_match']})"

            return hypotheses

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse context response: {e}")
            return []
        except Exception as e:
            logger.error(f"Context analysis error: {e}")
            return []

    def _format_recent_actions(self, context: UserContext) -> str:
        """Format recent actions for the prompt."""
        if not context.recent_actions:
            return "Keine kürzlichen Aktionen"

        lines = []
        for action in context.recent_actions[-5:]:  # Last 5 actions
            result_preview = action.result[:50] + "..." if len(action.result) > 50 else action.result
            lines.append(f"- {action.event_type}: {result_preview}")

        return "\n".join(lines)

    def _extract_json(self, content: str) -> str:
        """Extract JSON from LLM response."""
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # Handle multiple JSON objects
        if content.startswith("{"):
            brace_count = 0
            end_pos = 0
            for i, char in enumerate(content):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            if end_pos > 0:
                content = content[:end_pos]

        return content

    async def resolve_reference(self, reference: str, context: UserContext) -> Optional[str]:
        """
        Resolve a relative reference to a concrete value.

        Args:
            reference: The reference to resolve ("letzte Idee", "dieser Space")
            context: User context

        Returns:
            Resolved value or None
        """
        reference_lower = reference.lower()

        # "letzte Idee" / "die neue Idee"
        if "idee" in reference_lower and any(w in reference_lower for w in ["letzte", "neue", "gerade"]):
            for action in reversed(context.recent_actions):
                if action.event_type == "idea.create":
                    # Extract idea name from result
                    if "erstellt" in action.result.lower():
                        # Try to extract name (pattern: "Idee 'X' erstellt")
                        parts = action.result.split("'")
                        if len(parts) >= 2:
                            return parts[1]
                    return action.metadata.get("title", action.result)

        # "dieser Space" / "aktueller Space"
        if "space" in reference_lower and any(w in reference_lower for w in ["dieser", "aktuell", "hier"]):
            return context.current_space

        # "das" / "die" - generic reference to last entity
        if reference_lower in ["das", "die", "den", "dem"]:
            # Return last mentioned entity
            if context.mentioned_entities:
                return context.mentioned_entities[-1]

        return None


__all__ = ["ContextAgent"]
