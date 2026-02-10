"""
Transformation Tools - Orchestrators for bubble-to-coding transformation.

Main tools:
- transform_bubble_to_project_spec: Full transformation pipeline
- create_enriched_project: Create Project from ProjectSpec
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

from ..models.project_spec import ProjectSpec, UserStory
from .requirements_extractor import (
    extract_requirements_from_idea,
    generate_minimal_requirements,
)
from .techstack_recommender import (
    determine_tech_stack,
    TECH_STACKS,
)

logger = logging.getLogger(__name__)

# Global reference for Electron broadcast
_electron_sender = None


def set_electron_sender(sender):
    """Set the Electron IPC sender for broadcasts."""
    global _electron_sender
    _electron_sender = sender


def _broadcast_to_electron(message: Dict[str, Any]):
    """Broadcast message to Electron UI."""
    global _electron_sender
    if _electron_sender:
        try:
            _electron_sender(message)
        except Exception as e:
            logger.warning(f"Electron broadcast failed: {e}")


# =============================================================================
# MAIN TRANSFORMATION PIPELINE
# =============================================================================

def transform_bubble_to_project_spec(
    idea_id: str = None,
    idea_name: str = None,
    bubble_id: str = None,
    transform_mode: str = "full",
    user_preference_stack: str = None,
    auto_create_project: bool = True,
) -> Dict[str, Any]:
    """
    Full transformation pipeline: Bubble/Idea -> ProjectSpec -> Project.

    This is the main orchestrator that:
    1. Loads the idea/bubble from database
    2. Extracts requirements via LLM
    3. Determines optimal tech stack
    4. Builds a complete ProjectSpec
    5. Optionally creates an enriched Project

    Args:
        idea_id: ID of the idea to transform
        idea_name: Name of the idea (alternative to ID)
        bubble_id: ID of the bubble (for nested ideas)
        transform_mode: "quick" (minimal LLM), "full" (detailed), "shuttle" (future)
        user_preference_stack: User's preferred tech stack
        auto_create_project: Whether to create Project in DB

    Returns:
        Dict with:
        - success: bool
        - project_spec: ProjectSpec as dict
        - project_id: str (if project created)
        - message: str (human-readable summary)
        - error: str (if failed)
    """
    result = {
        "success": False,
        "project_spec": None,
        "project_id": None,
        "message": "",
    }

    try:
        # 1. Load idea from database
        logger.info(f"Starting transformation: idea_id={idea_id}, idea_name={idea_name}, mode={transform_mode}")

        idea_data = _load_idea(idea_id, idea_name, bubble_id)
        if not idea_data:
            result["error"] = f"Idee nicht gefunden: {idea_name or idea_id or bubble_id}"
            result["message"] = result["error"]
            return result

        title = idea_data["title"]
        description = idea_data["description"]
        scoring = {
            "feasibility": idea_data.get("feasibility", 0),
            "impact": idea_data.get("impact", 0),
            "novelty": idea_data.get("novelty", 0),
            "urgency": idea_data.get("urgency", 0),
        }

        logger.info(f"Loaded idea: '{title}' (scoring: {scoring})")

        # 2. Extract requirements
        if transform_mode == "quick":
            # Minimal requirements without full LLM
            reqs_result = generate_minimal_requirements(title, description)
        else:
            # Full LLM-based extraction
            reqs_result = extract_requirements_from_idea(
                title=title,
                description=description,
                scoring=scoring,
                mode=transform_mode,
            )

        if not reqs_result.get("success", False):
            logger.warning(f"Requirements extraction failed, using fallback: {reqs_result.get('error')}")
            reqs_result = generate_minimal_requirements(title, description)

        # 3. Determine tech stack
        tech_result = determine_tech_stack(
            functional_requirements=reqs_result.get("functional_requirements", []),
            non_functional_requirements=reqs_result.get("non_functional_requirements", []),
            title=title,
            description=description,
            user_preference=user_preference_stack,
        )

        recommended_stack = tech_result.get("recommended_stack", "react")
        stack_reasoning = tech_result.get("reasoning", "")

        # 4. Build ProjectSpec
        user_stories = [
            UserStory(**story) if isinstance(story, dict) else story
            for story in reqs_result.get("user_stories", [])
        ]

        spec = ProjectSpec(
            source_idea_id=str(idea_data["id"]),
            source_bubble_id=str(bubble_id) if bubble_id else None,
            title=title,
            description=description,
            feasibility=scoring["feasibility"],
            impact=scoring["impact"],
            novelty=scoring["novelty"],
            urgency=scoring["urgency"],
            composite_score=0.0,  # Will be calculated
            functional_requirements=reqs_result.get("functional_requirements", []),
            non_functional_requirements=reqs_result.get("non_functional_requirements", []),
            user_stories=user_stories,
            acceptance_criteria=reqs_result.get("acceptance_criteria", []),
            recommended_tech_stack=recommended_stack,
            tech_stack_reasoning=stack_reasoning,
            alternative_stacks=tech_result.get("alternatives", []),
            generated_at=datetime.now(),
            generation_model="anthropic/claude-sonnet-4",
            confidence_score=(
                reqs_result.get("confidence", 0.5) + tech_result.get("confidence", 0.5)
            ) / 2,
            transform_mode=transform_mode,
        )

        # Calculate composite score
        spec.composite_score = spec.calculate_composite_score()

        logger.info(
            f"Built ProjectSpec: {spec.requirements_count()} requirements, "
            f"stack={spec.recommended_tech_stack}, score={spec.composite_score:.1f}"
        )

        # 5. Create Project (optional)
        project_id = None
        if auto_create_project:
            project_result = create_enriched_project(spec)
            if project_result.get("success"):
                project_id = project_result.get("project_id")

        # 6. Build result
        result["success"] = True
        result["project_spec"] = spec.to_dict()
        result["project_id"] = project_id
        result["message"] = (
            f"Transformation abgeschlossen: '{title}' → {spec.requirements_count()} Requirements, "
            f"Tech-Stack: {TECH_STACKS.get(recommended_stack, {}).get('name', recommended_stack)}"
        )

        # 7. Broadcast to Electron
        _broadcast_to_electron({
            "type": "transformation_completed",
            "idea_id": str(idea_data["id"]),
            "project_id": project_id,
            "spec_summary": {
                "title": title,
                "requirements_count": spec.requirements_count(),
                "tech_stack": recommended_stack,
                "composite_score": spec.composite_score,
            },
        })

        return result

    except Exception as e:
        logger.error(f"Transformation failed: {e}", exc_info=True)
        result["error"] = str(e)
        result["message"] = f"Transformation fehlgeschlagen: {str(e)}"
        return result


# =============================================================================
# PROJECT CREATION
# =============================================================================

def create_enriched_project(
    spec: ProjectSpec = None,
    project_spec: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Create an enriched Project from ProjectSpec.

    Args:
        spec: ProjectSpec object
        project_spec: ProjectSpec as dict (alternative)

    Returns:
        Dict with:
        - success: bool
        - project_id: str
        - message: str
        - error: Optional[str]
    """
    result = {
        "success": False,
        "project_id": None,
        "message": "",
    }

    try:
        # Convert dict to ProjectSpec if needed
        if spec is None and project_spec:
            spec = ProjectSpec.from_dict(project_spec)

        if spec is None:
            result["error"] = "Keine ProjectSpec vorhanden"
            return result

        # Import repository
        from data.repository import ProjectsRepository, IdeasRepository

        projects_repo = ProjectsRepository()
        ideas_repo = IdeasRepository()

        # Create project
        project = projects_repo.create(
            name=spec.title,
            description=spec.description,
            from_idea_id=int(spec.source_idea_id) if spec.source_idea_id else None,
            tech_stack=spec.recommended_tech_stack,
            requirements_json=spec.to_requirements_json(),
        )

        if project:
            # Update source idea with project link
            if spec.source_idea_id:
                try:
                    idea = ideas_repo.get(int(spec.source_idea_id))
                    if idea:
                        idea.promoted_to_project_id = project.id
                        idea.status = "promoted"
                        ideas_repo.update(idea)
                except Exception as e:
                    logger.warning(f"Could not update idea status: {e}")

            result["success"] = True
            result["project_id"] = str(project.id)
            result["message"] = f"Projekt '{spec.title}' erstellt (ID: {project.id})"

            # Broadcast to Electron
            _broadcast_to_electron({
                "type": "project_created",
                "project_id": str(project.id),
                "project_name": spec.title,
                "from_idea_id": spec.source_idea_id,
                "tech_stack": spec.recommended_tech_stack,
            })

            logger.info(f"Created project {project.id} from idea {spec.source_idea_id}")

        else:
            result["error"] = "Projekt konnte nicht erstellt werden"

        return result

    except Exception as e:
        logger.error(f"Project creation failed: {e}", exc_info=True)
        result["error"] = str(e)
        return result


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _load_idea(
    idea_id: str = None,
    idea_name: str = None,
    bubble_id: str = None,
) -> Optional[Dict[str, Any]]:
    """Load idea from database."""
    try:
        from data.repository import IdeasRepository
        repo = IdeasRepository()

        idea = None

        # Try to load by different identifiers
        if idea_id:
            try:
                idea = repo.get(int(idea_id))
            except (ValueError, TypeError):
                pass

        if not idea and idea_name:
            idea = repo.get_by_title_fuzzy(idea_name)

        if not idea and bubble_id:
            try:
                idea = repo.get(int(bubble_id))
            except (ValueError, TypeError):
                pass

        if idea:
            return {
                "id": idea.id,
                "title": idea.title,
                "description": idea.description or "",
                "feasibility": getattr(idea, 'feasibility', None) or 0,
                "impact": getattr(idea, 'impact', None) or 0,
                "novelty": getattr(idea, 'novelty', None) or 0,
                "urgency": getattr(idea, 'urgency', None) or 0,
                "status": getattr(idea, 'status', 'raw'),
                "parent_id": getattr(idea, 'parent_id', None),
            }

    except Exception as e:
        logger.error(f"Failed to load idea: {e}")

    return None


def get_transformation_status() -> Dict[str, Any]:
    """
    Get status of the transformation system.

    Returns info about available tools and configuration.
    """
    try:
        from openai import OpenAI
        import os

        has_api_key = bool(os.getenv("OPENROUTER_API_KEY"))

        return {
            "available": True,
            "has_api_key": has_api_key,
            "model": os.getenv("TRANSFORMER_MODEL", "anthropic/claude-sonnet-4"),
            "available_stacks": list(TECH_STACKS.keys()),
            "modes": ["quick", "full", "shuttle"],
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
        }


__all__ = [
    "transform_bubble_to_project_spec",
    "create_enriched_project",
    "get_transformation_status",
    "set_electron_sender",
]
