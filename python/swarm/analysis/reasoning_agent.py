"""
ReasoningAgent - Multi-step logical reasoning for intent classification

Part of Phase 13: Multi-Agent Intent Analysis System

Uses chain-of-thought reasoning to:
1. Parse the user request structure
2. Identify key action words and entities
3. Map to VibeMind event types
4. Validate parameter completeness
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# Multi-step reasoning prompt
REASONING_PROMPT = """Du bist ein Intent-Analyse-Agent fuer VibeMind.
Analysiere den User Intent mit logischem Schritt-fuer-Schritt Denken.

## Verfuegbare Event Types

### Spaces/Bubbles
- bubble.list: Spaces auflisten
- bubble.create: Space erstellen (title erforderlich)
- bubble.enter: Space betreten (bubble_name erforderlich)
- bubble.exit: Space verlassen
- bubble.delete: Space loeschen (bubble_name erforderlich)

### Ideen
- idea.list: Ideen auflisten
- idea.create: Idee erstellen (title + content erforderlich)
- idea.find: Idee suchen (query erforderlich)
- idea.update: Idee aktualisieren (idea_name erforderlich)
- idea.delete: Idee loeschen (idea_name erforderlich)
- idea.connect: Zwei SPEZIFISCHE Ideen verbinden (BEIDE Namen werden genannt!)
- idea.auto_link: ALLE Ideen automatisch verlinken (wenn "die Ideen", "systematisch", "relevante" ohne Namen)
- idea.analyze_links: Verlinkungsvorschlaege ANZEIGEN ohne auszufuehren ("beispiel", "schlage vor")
WICHTIG: Ohne konkrete Ideen-Namen -> idea.auto_link (NICHT idea.connect!)

### Zusammenfassungen
- idea.summarize: Zusammenfassung einer Idee/Space erstellen (title optional)
- idea.whitepaper: Whitepaper aus Ideen generieren (start_node optional)

### Desktop
- desktop.open_app: App oeffnen (app_name erforderlich)
- desktop.click: Element klicken (description erforderlich)
- desktop.type: Text tippen (text erforderlich)
- desktop.task: Komplexe Aufgabe (description erforderlich)

### Code
- code.generate: Code generieren (description erforderlich)
- code.modify: Code aendern (instruction erforderlich)
- code.status: Status abfragen

### Conversation
- conversation.greeting: Begruessing
- conversation.help: Hilfe
- conversation.unknown: Unklar

## User Input
{user_input}

## Analysiere in Schritten:

1. **Aktionswort identifizieren:**
   - Was ist die Hauptaktion? (erstellen, loeschen, verbinden, oeffnen, etc.)

2. **Entitaeten extrahieren:**
   - Welche Namen/Begriffe werden erwaehnt?
   - WICHTIG: Extrahiere EXAKT die Woerter des Users!

3. **Kontext bestimmen:**
   - Geht es um Spaces, Ideen, Desktop, oder Code?

4. **Event Type waehlen:**
   - Welcher Event Type passt am besten?

5. **Parameter ableiten:**
   - Welche Parameter sind noetig?
   - Sind alle erforderlichen Parameter vorhanden?

## Antwort Format (NUR JSON, kein anderer Text):
{{
    "thinking": {{
        "action_word": "das identifizierte Aktionswort",
        "entities": ["extrahierte", "entitaeten"],
        "context": "spaces|ideas|desktop|code|conversation",
        "missing_params": ["falls", "welche", "fehlen"]
    }},
    "hypothesis": {{
        "event_type": "der.event.type",
        "payload": {{"param": "EXAKTER_WERT_VOM_USER"}},
        "confidence": 0.0-1.0,
        "reasoning": "Kurze Begruendung"
    }}
}}
"""


class ReasoningAgent:
    """
    Multi-step reasoning agent for intent classification.

    Uses chain-of-thought prompting to analyze user requests
    and produce well-reasoned intent hypotheses.
    """

    def __init__(self, client, model: str):
        """
        Initialize the reasoning agent.

        Args:
            client: OpenAI-compatible client
            model: Model identifier to use
        """
        self.client = client
        self.model = model

    async def analyze(self, user_input: str) -> List['IntentHypothesis']:
        """
        Analyze user input with multi-step reasoning.

        Args:
            user_input: Natural language user request

        Returns:
            List of IntentHypothesis (usually 1, but may include alternatives)
        """
        from swarm.analysis.intent_analysis_team import IntentHypothesis

        try:
            prompt = REASONING_PROMPT.format(user_input=user_input)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=800,
            )

            content = response.choices[0].message.content.strip()

            # Extract JSON from response
            content = self._extract_json(content)

            result = json.loads(content)

            # Log the thinking process
            thinking = result.get("thinking", {})
            logger.debug(f"Reasoning thinking: action={thinking.get('action_word')}, "
                        f"context={thinking.get('context')}, "
                        f"entities={thinking.get('entities')}")

            hypothesis = result.get("hypothesis", {})

            hypotheses = [IntentHypothesis(
                event_type=hypothesis.get("event_type", "conversation.unknown"),
                payload=hypothesis.get("payload", {}),
                confidence=float(hypothesis.get("confidence", 0.5)),
                reasoning=hypothesis.get("reasoning", "Multi-step reasoning"),
                source="reasoning"
            )]

            # Check for missing parameters and reduce confidence
            missing = thinking.get("missing_params", [])
            if missing:
                hypotheses[0].confidence *= 0.7  # Reduce confidence
                hypotheses[0].reasoning += f" (Missing: {', '.join(missing)})"

            return hypotheses

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse reasoning response: {e}")
            return []
        except Exception as e:
            logger.error(f"Reasoning analysis error: {e}")
            return []

    def _extract_json(self, content: str) -> str:
        """Extract JSON from LLM response, handling markdown code blocks."""
        # Handle markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # Handle multiple JSON objects (take first one)
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

    async def analyze_with_alternatives(self, user_input: str) -> List['IntentHypothesis']:
        """
        Analyze with multiple alternative hypotheses.

        For ambiguous inputs, generates multiple possible interpretations.
        """
        from swarm.analysis.intent_analysis_team import IntentHypothesis

        # First get primary hypothesis
        primary = await self.analyze(user_input)

        if not primary:
            return []

        # Check if input is ambiguous
        ambiguous_markers = ["oder", "vielleicht", "entweder", "eventuell"]
        is_ambiguous = any(marker in user_input.lower() for marker in ambiguous_markers)

        if not is_ambiguous:
            return primary

        # Generate alternative hypothesis
        alternative_prompt = f"""Der User-Input ist moeglicherweise mehrdeutig.
Die primaere Interpretation ist: {primary[0].event_type}

Gibt es eine plausible alternative Interpretation?

User Input: {user_input}

Antworte NUR mit JSON:
{{"alternative": {{"event_type": "...", "payload": {{}}, "confidence": 0.0-1.0, "reasoning": "..."}}}}

Falls keine sinnvolle Alternative existiert, antworte:
{{"alternative": null}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": alternative_prompt}],
                temperature=0.2,
                max_tokens=300,
            )

            content = self._extract_json(response.choices[0].message.content.strip())
            result = json.loads(content)

            alt = result.get("alternative")
            if alt:
                primary.append(IntentHypothesis(
                    event_type=alt.get("event_type"),
                    payload=alt.get("payload", {}),
                    confidence=float(alt.get("confidence", 0.3)),
                    reasoning=alt.get("reasoning", "Alternative interpretation"),
                    source="reasoning"
                ))

        except Exception as e:
            logger.debug(f"Alternative analysis skipped: {e}")

        return primary


__all__ = ["ReasoningAgent"]
