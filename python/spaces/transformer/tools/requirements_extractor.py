"""
Requirements Extractor - LLM-based requirements extraction from idea content.

Uses Claude via OpenRouter to extract structured requirements:
- Functional Requirements
- Non-Functional Requirements
- User Stories
- Acceptance Criteria
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


# =============================================================================
# LLM PROMPTS
# =============================================================================

REQUIREMENTS_EXTRACTION_PROMPT = """Analysiere den folgenden Idee-Inhalt und extrahiere strukturierte Software-Requirements.

## Idee
**Titel:** {title}
**Beschreibung:** {description}
{scoring_section}

## Aufgabe
Extrahiere aus der Beschreibung:

1. **Functional Requirements (FR)** - Was das System tun muss
   Format: FR-001: <Anforderung>

2. **Non-Functional Requirements (NFR)** - Qualitaetsmerkmale
   Format: NFR-001: <Anforderung>
   Kategorien: Performance, Sicherheit, Skalierbarkeit, Usability, Wartbarkeit

3. **User Stories** - Im Format "Als [Rolle] moechte ich [Aktion], damit [Nutzen]"

4. **Acceptance Criteria (AC)** - Konkrete Erfolgskriterien
   Format: AC-001: <Kriterium>

## Regeln
- Mindestens 3 funktionale Requirements
- Mindestens 2 nicht-funktionale Requirements
- Mindestens 2 User Stories
- Bleibe bei der Beschreibung - erfinde nichts dazu
- Wenn die Beschreibung vage ist, formuliere allgemeinere Requirements

## Antwort-Format (JSON)
{{
    "functional_requirements": [
        "FR-001: ...",
        "FR-002: ..."
    ],
    "non_functional_requirements": [
        "NFR-001: Performance - ...",
        "NFR-002: Sicherheit - ..."
    ],
    "user_stories": [
        {{"role": "User", "action": "...", "benefit": "...", "priority": "high"}},
        {{"role": "Admin", "action": "...", "benefit": "...", "priority": "medium"}}
    ],
    "acceptance_criteria": [
        "AC-001: ...",
        "AC-002: ..."
    ],
    "confidence": 0.85
}}

Antworte NUR mit dem JSON-Objekt, kein zusaetzlicher Text."""


QUICK_REQUIREMENTS_PROMPT = """Erstelle schnell 3 grundlegende Requirements fuer:

**{title}**: {description}

Antwort-Format (JSON):
{{
    "functional_requirements": ["FR-001: ...", "FR-002: ...", "FR-003: ..."],
    "non_functional_requirements": ["NFR-001: ..."],
    "user_stories": [{{"role": "User", "action": "...", "benefit": "..."}}],
    "acceptance_criteria": ["AC-001: ..."],
    "confidence": 0.5
}}

Nur JSON, kein Text."""


# =============================================================================
# LLM CLIENT
# =============================================================================

_llm_client = None


def _get_llm_client():
    """Get or create OpenAI-compatible LLM client via OpenRouter."""
    global _llm_client
    if _llm_client is None:
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY not set")

            _llm_client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            logger.info("Requirements extractor LLM client created")
        except Exception as e:
            logger.error(f"Failed to create LLM client: {e}")
            raise

    return _llm_client


def _call_llm(prompt: str, model: str = None) -> str:
    """Call LLM and return response text."""
    model = model or os.getenv("TRANSFORMER_MODEL", "anthropic/claude-sonnet-4")

    try:
        client = _get_llm_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise


# =============================================================================
# REQUIREMENTS EXTRACTION
# =============================================================================

def extract_requirements_from_idea(
    idea_id: str = None,
    idea_name: str = None,
    idea_content: str = None,
    title: str = None,
    description: str = None,
    scoring: Dict[str, float] = None,
    mode: str = "full",
) -> Dict[str, Any]:
    """
    Extract structured requirements from idea content using LLM.

    Args:
        idea_id: ID of the idea (optional, for loading from DB)
        idea_name: Name/title of the idea (alternative to idea_id)
        idea_content: Raw content/description (alternative to loading from DB)
        title: Direct title override
        description: Direct description override
        scoring: Dict with feasibility, impact, novelty, urgency (0-10)
        mode: "full" (detailed) or "quick" (minimal)

    Returns:
        Dict with:
        - functional_requirements: List[str]
        - non_functional_requirements: List[str]
        - user_stories: List[Dict]
        - acceptance_criteria: List[str]
        - confidence: float (0-1)
        - success: bool
        - error: Optional[str]
    """
    # Default result for errors
    error_result = {
        "functional_requirements": [],
        "non_functional_requirements": [],
        "user_stories": [],
        "acceptance_criteria": [],
        "confidence": 0.0,
        "success": False,
    }

    try:
        # Resolve title and description
        resolved_title = title
        resolved_description = description or idea_content

        # Try to load from database if id or name provided
        if not resolved_title or not resolved_description:
            if idea_id or idea_name:
                loaded = _load_idea_from_db(idea_id, idea_name)
                if loaded:
                    resolved_title = resolved_title or loaded.get("title")
                    resolved_description = resolved_description or loaded.get("description")
                    if not scoring:
                        scoring = {
                            "feasibility": loaded.get("feasibility", 0),
                            "impact": loaded.get("impact", 0),
                            "novelty": loaded.get("novelty", 0),
                            "urgency": loaded.get("urgency", 0),
                        }

        if not resolved_title:
            resolved_title = "Unbenannte Idee"
        if not resolved_description:
            error_result["error"] = "Keine Beschreibung vorhanden"
            return error_result

        # Build scoring section if available
        scoring_section = ""
        if scoring and any(v > 0 for v in scoring.values()):
            scoring_section = f"""
**Scoring:**
- Feasibility: {scoring.get('feasibility', 0)}/10
- Impact: {scoring.get('impact', 0)}/10
- Novelty: {scoring.get('novelty', 0)}/10
- Urgency: {scoring.get('urgency', 0)}/10
"""

        # Select prompt based on mode
        if mode == "quick":
            prompt = QUICK_REQUIREMENTS_PROMPT.format(
                title=resolved_title,
                description=resolved_description[:500],  # Limit for quick mode
            )
        else:
            prompt = REQUIREMENTS_EXTRACTION_PROMPT.format(
                title=resolved_title,
                description=resolved_description,
                scoring_section=scoring_section,
            )

        # Call LLM
        logger.info(f"Extracting requirements for '{resolved_title}' (mode={mode})")
        response_text = _call_llm(prompt)

        # Parse JSON response
        result = _parse_requirements_response(response_text)
        result["success"] = True
        result["source_title"] = resolved_title

        logger.info(
            f"Extracted {len(result.get('functional_requirements', []))} FRs, "
            f"{len(result.get('user_stories', []))} user stories"
        )

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse requirements JSON: {e}")
        error_result["error"] = f"JSON parse error: {str(e)}"
        return error_result
    except Exception as e:
        logger.error(f"Requirements extraction failed: {e}")
        error_result["error"] = str(e)
        return error_result


def _load_idea_from_db(idea_id: str = None, idea_name: str = None) -> Optional[Dict]:
    """Load idea from database by ID or name."""
    try:
        from data.repository import IdeasRepository
        repo = IdeasRepository()

        idea = None
        if idea_id:
            idea = repo.get(idea_id)
        elif idea_name:
            idea = repo.get_by_title_fuzzy(idea_name)

        if idea:
            return {
                "id": idea.id,
                "title": idea.title,
                "description": idea.description,
                "feasibility": getattr(idea, 'feasibility', 0) or 0,
                "impact": getattr(idea, 'impact', 0) or 0,
                "novelty": getattr(idea, 'novelty', 0) or 0,
                "urgency": getattr(idea, 'urgency', 0) or 0,
            }
    except Exception as e:
        logger.warning(f"Could not load idea from DB: {e}")

    return None


def _parse_requirements_response(response_text: str) -> Dict[str, Any]:
    """Parse LLM response into structured requirements."""
    # Try to extract JSON from response
    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Parse JSON
    data = json.loads(text)

    # Normalize user stories format
    user_stories = data.get("user_stories", [])
    normalized_stories = []
    for story in user_stories:
        if isinstance(story, dict):
            normalized_stories.append({
                "role": story.get("role", "User"),
                "action": story.get("action", ""),
                "benefit": story.get("benefit", ""),
                "priority": story.get("priority", "medium"),
            })
        elif isinstance(story, str):
            # Try to parse "Als X moechte ich Y, damit Z" format
            normalized_stories.append({
                "role": "User",
                "action": story,
                "benefit": "",
                "priority": "medium",
            })

    return {
        "functional_requirements": data.get("functional_requirements", []),
        "non_functional_requirements": data.get("non_functional_requirements", []),
        "user_stories": normalized_stories,
        "acceptance_criteria": data.get("acceptance_criteria", []),
        "confidence": data.get("confidence", 0.5),
    }


# =============================================================================
# FALLBACK FOR NON-LLM MODE
# =============================================================================

def generate_minimal_requirements(title: str, description: str) -> Dict[str, Any]:
    """
    Generate minimal requirements without LLM (rule-based fallback).

    Used when LLM is unavailable or for very quick transformations.
    """
    # Extract key verbs and nouns from description
    words = description.lower().split()

    # Basic functional requirements based on description
    functional = [
        f"FR-001: Das System soll '{title}' implementieren",
        f"FR-002: Die Hauptfunktionalitaet muss wie beschrieben funktionieren",
        f"FR-003: Alle Eingaben muessen validiert werden",
    ]

    # Standard NFRs
    non_functional = [
        "NFR-001: Performance - Antwortzeiten unter 2 Sekunden",
        "NFR-002: Usability - Intuitive Benutzeroberflaeche",
    ]

    # Generic user story
    user_stories = [
        {
            "role": "User",
            "action": f"'{title}' nutzen",
            "benefit": "meine Aufgaben effizient erledigen",
            "priority": "high",
        }
    ]

    # Basic acceptance criteria
    acceptance_criteria = [
        "AC-001: Alle Hauptfunktionen sind zugaenglich",
        "AC-002: Keine kritischen Fehler bei normaler Nutzung",
    ]

    return {
        "functional_requirements": functional,
        "non_functional_requirements": non_functional,
        "user_stories": user_stories,
        "acceptance_criteria": acceptance_criteria,
        "confidence": 0.3,  # Low confidence for rule-based
        "success": True,
        "source_title": title,
        "mode": "fallback",
    }


__all__ = [
    "extract_requirements_from_idea",
    "generate_minimal_requirements",
]
