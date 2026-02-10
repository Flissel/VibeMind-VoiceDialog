"""
Tech Stack Recommender - LLM-based technology stack recommendation.

Uses Claude via OpenRouter to recommend the optimal tech stack based on:
- Extracted requirements
- Project context
- User preferences
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# AVAILABLE TECH STACKS
# =============================================================================

TECH_STACKS = {
    "react": {
        "name": "React + Node.js",
        "description": "Modern web app with React frontend and Express backend",
        "best_for": ["Web-Apps", "SPAs", "Dashboards", "Interactive UIs"],
        "frameworks": ["React", "Node.js", "Express", "TypeScript"],
    },
    "vue": {
        "name": "Vue.js + Node.js",
        "description": "Progressive web app with Vue frontend",
        "best_for": ["Web-Apps", "Progressive Enhancement", "Leichtgewichtige Apps"],
        "frameworks": ["Vue.js", "Node.js", "Vite"],
    },
    "nextjs": {
        "name": "Next.js (Full-Stack React)",
        "description": "Server-side rendered React with API routes",
        "best_for": ["SEO-wichtige Apps", "E-Commerce", "Content-Plattformen", "SSR"],
        "frameworks": ["Next.js", "React", "TypeScript", "Vercel"],
    },
    "python-flask": {
        "name": "Python Flask API",
        "description": "Lightweight Python backend API",
        "best_for": ["REST APIs", "Microservices", "ML/AI Integration", "Schnelle Prototypen"],
        "frameworks": ["Flask", "Python", "SQLAlchemy"],
    },
    "python-django": {
        "name": "Python Django (Full-Stack)",
        "description": "Full-featured Python web framework",
        "best_for": ["Admin-Systeme", "Datenintensive Apps", "Rapid Development"],
        "frameworks": ["Django", "Python", "Django REST Framework"],
    },
    "electron": {
        "name": "Electron (Desktop App)",
        "description": "Cross-platform desktop application",
        "best_for": ["Desktop Apps", "Offline-First", "System Integration"],
        "frameworks": ["Electron", "React", "Node.js"],
    },
    "fastapi": {
        "name": "FastAPI (Modern Python API)",
        "description": "High-performance async Python API",
        "best_for": ["High-Performance APIs", "Async Operations", "OpenAPI/Swagger"],
        "frameworks": ["FastAPI", "Python", "Pydantic", "uvicorn"],
    },
}


# =============================================================================
# LLM PROMPT
# =============================================================================

TECHSTACK_RECOMMENDATION_PROMPT = """Basierend auf den folgenden Requirements, empfehle den optimalen Tech-Stack.

## Requirements
{requirements_json}

## Projekt-Kontext
{project_context}

## Verfuegbare Stacks
{stacks_description}

## Aufgabe
1. Analysiere die Requirements
2. Waehle den passendsten Stack
3. Begruende deine Entscheidung
4. Nenne 1-2 Alternativen

## Antwort-Format (JSON)
{{
    "recommended_stack": "react|vue|nextjs|python-flask|python-django|electron|fastapi",
    "reasoning": "Kurze Begruendung (2-3 Saetze)",
    "alternatives": ["stack1", "stack2"],
    "confidence": 0.85,
    "key_factors": ["Faktor 1", "Faktor 2"]
}}

Antworte NUR mit dem JSON-Objekt."""


# =============================================================================
# LLM CLIENT (shared with requirements_extractor)
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
            logger.info("Tech stack recommender LLM client created")
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
            temperature=0.2,  # Lower temperature for more consistent recommendations
            max_tokens=800,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise


# =============================================================================
# TECH STACK RECOMMENDATION
# =============================================================================

def determine_tech_stack(
    requirements_list: List[str] = None,
    functional_requirements: List[str] = None,
    non_functional_requirements: List[str] = None,
    project_context: str = "",
    user_preference: str = None,
    title: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """
    Determine optimal tech stack based on requirements.

    Args:
        requirements_list: Combined list of all requirements (alternative input)
        functional_requirements: List of functional requirements
        non_functional_requirements: List of non-functional requirements
        project_context: Additional context about the project
        user_preference: User's preferred stack (will be weighted higher)
        title: Project title for context
        description: Project description for context

    Returns:
        Dict with:
        - recommended_stack: str (e.g., "react", "python-flask")
        - stack_info: Dict with name, description, frameworks
        - reasoning: str
        - alternatives: List[str]
        - confidence: float (0-1)
        - success: bool
        - error: Optional[str]
    """
    # Default result for errors
    error_result = {
        "recommended_stack": "react",  # Safe default
        "stack_info": TECH_STACKS["react"],
        "reasoning": "Standardempfehlung aufgrund fehlender Daten",
        "alternatives": ["nextjs", "vue"],
        "confidence": 0.3,
        "success": False,
    }

    try:
        # Combine requirements
        all_requirements = []
        if requirements_list:
            all_requirements.extend(requirements_list)
        if functional_requirements:
            all_requirements.extend(functional_requirements)
        if non_functional_requirements:
            all_requirements.extend(non_functional_requirements)

        # If no requirements provided, use description-based heuristics
        if not all_requirements:
            if description:
                return _heuristic_recommendation(title, description, user_preference)
            else:
                error_result["error"] = "Keine Requirements oder Beschreibung vorhanden"
                return error_result

        # Build requirements JSON for LLM
        requirements_json = json.dumps({
            "title": title,
            "functional_requirements": functional_requirements or [],
            "non_functional_requirements": non_functional_requirements or [],
            "all_requirements": all_requirements[:20],  # Limit to avoid token overflow
        }, indent=2, ensure_ascii=False)

        # Build stacks description
        stacks_desc = "\n".join([
            f"- **{key}**: {info['name']} - {info['description']}. Ideal fuer: {', '.join(info['best_for'])}"
            for key, info in TECH_STACKS.items()
        ])

        # Add user preference context
        context = project_context
        if user_preference and user_preference in TECH_STACKS:
            context += f"\n\nUser-Praeferenz: {user_preference} (sollte bevorzugt werden wenn passend)"

        # Build prompt
        prompt = TECHSTACK_RECOMMENDATION_PROMPT.format(
            requirements_json=requirements_json,
            project_context=context or "Keine zusaetzlichen Kontext-Informationen",
            stacks_description=stacks_desc,
        )

        # Call LLM
        logger.info(f"Determining tech stack for '{title}' with {len(all_requirements)} requirements")
        response_text = _call_llm(prompt)

        # Parse response
        result = _parse_techstack_response(response_text)
        result["success"] = True

        # Add stack info
        recommended = result.get("recommended_stack", "react")
        if recommended in TECH_STACKS:
            result["stack_info"] = TECH_STACKS[recommended]
        else:
            # Fallback if LLM returned unknown stack
            result["recommended_stack"] = "react"
            result["stack_info"] = TECH_STACKS["react"]
            result["reasoning"] += " (korrigiert zu unterstuetztem Stack)"

        logger.info(f"Recommended stack: {result['recommended_stack']} (confidence: {result.get('confidence', 0):.2f})")

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse tech stack JSON: {e}")
        error_result["error"] = f"JSON parse error: {str(e)}"
        return error_result
    except Exception as e:
        logger.error(f"Tech stack recommendation failed: {e}")
        error_result["error"] = str(e)
        return error_result


def _parse_techstack_response(response_text: str) -> Dict[str, Any]:
    """Parse LLM response into structured tech stack recommendation."""
    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    data = json.loads(text)

    # Validate recommended stack
    recommended = data.get("recommended_stack", "react").lower()
    if recommended not in TECH_STACKS:
        # Try to map common variations
        stack_mapping = {
            "react.js": "react",
            "reactjs": "react",
            "vue.js": "vue",
            "vuejs": "vue",
            "next.js": "nextjs",
            "next": "nextjs",
            "flask": "python-flask",
            "django": "python-django",
            "fast-api": "fastapi",
        }
        recommended = stack_mapping.get(recommended, "react")

    return {
        "recommended_stack": recommended,
        "reasoning": data.get("reasoning", ""),
        "alternatives": [
            alt.lower() for alt in data.get("alternatives", [])
            if alt.lower() in TECH_STACKS
        ][:2],  # Max 2 alternatives
        "confidence": data.get("confidence", 0.5),
        "key_factors": data.get("key_factors", []),
    }


def _heuristic_recommendation(
    title: str,
    description: str,
    user_preference: str = None
) -> Dict[str, Any]:
    """
    Heuristic-based tech stack recommendation (no LLM required).

    Used as fallback when requirements are not available.
    """
    text = (title + " " + description).lower()

    # Keyword-based matching
    if any(kw in text for kw in ["desktop", "offline", "system", "native"]):
        stack = "electron"
        reasoning = "Desktop-Keywords erkannt - Electron fuer Cross-Platform Desktop"
    elif any(kw in text for kw in ["api", "backend", "microservice", "rest"]):
        if any(kw in text for kw in ["schnell", "fast", "async", "performance"]):
            stack = "fastapi"
            reasoning = "API mit Performance-Anforderung - FastAPI empfohlen"
        else:
            stack = "python-flask"
            reasoning = "Backend/API Projekt - Flask als leichtgewichtige Option"
    elif any(kw in text for kw in ["admin", "verwaltung", "dashboard", "daten"]):
        stack = "python-django"
        reasoning = "Datenintensive Verwaltung - Django mit Admin-Interface"
    elif any(kw in text for kw in ["seo", "blog", "content", "marketing"]):
        stack = "nextjs"
        reasoning = "Content/SEO-fokussiert - Next.js fuer SSR"
    elif any(kw in text for kw in ["ml", "ki", "ai", "machine learning"]):
        stack = "python-flask"
        reasoning = "ML/AI Integration - Python-basierter Stack"
    else:
        # Default to React for general web apps
        stack = user_preference if user_preference in TECH_STACKS else "react"
        reasoning = "Standard-Webprojekt - React als vielseitige Option"

    return {
        "recommended_stack": stack,
        "stack_info": TECH_STACKS[stack],
        "reasoning": reasoning,
        "alternatives": ["nextjs", "vue"] if stack == "react" else ["react"],
        "confidence": 0.5,  # Lower confidence for heuristic
        "success": True,
        "mode": "heuristic",
    }


def get_available_stacks() -> Dict[str, Dict[str, Any]]:
    """Return all available tech stacks with their info."""
    return TECH_STACKS.copy()


__all__ = [
    "determine_tech_stack",
    "get_available_stacks",
    "TECH_STACKS",
]
