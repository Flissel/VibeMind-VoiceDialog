"""
Transformer Space - Bubble-to-Coding Pipeline

Transforms ideas/bubbles into proper coding specifications with:
- LLM-based requirements extraction
- Tech stack recommendation
- Enriched project creation

Usage:
    from spaces.transformer import TransformerAgent, get_transformer_agent
    from spaces.transformer.models import ProjectSpec

Event Types:
    transform.bubble_to_spec    - Full transformation pipeline
    transform.extract_requirements - Requirements extraction only
    transform.determine_techstack - Tech stack recommendation only
    transform.create_project    - Create enriched project
    transform.via_shuttle       - Use Shuttle pipeline
"""

# Agent
from .agents import TransformerAgent, get_transformer_agent

# Models
from .models import ProjectSpec

# Tools
from .tools import (
    extract_requirements_from_idea,
    determine_tech_stack,
    transform_bubble_to_project_spec,
    create_enriched_project,
)

__all__ = [
    # Agent
    "TransformerAgent",
    "get_transformer_agent",
    # Models
    "ProjectSpec",
    # Tools
    "extract_requirements_from_idea",
    "determine_tech_stack",
    "transform_bubble_to_project_spec",
    "create_enriched_project",
]
