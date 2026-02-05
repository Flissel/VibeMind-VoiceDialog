"""
Shuttle Swarm - AutoGen 4.0 Swarm for Shuttle Domain

Replaces direct event→tool dispatch of ShuttleOrchestratorAgent with a multi-agent
Swarm that uses LLM reasoning to select and execute tools.

Architecture:
    ShuttleCoordinator (0 tools, handoffs to all)
    ├── RequirementsAnalystWorker (~8 tools: CRUD)
    ├── PipelineManagerWorker (~6 tools: CRUD)
    ├── ValidatorWorker (~5 tools: validation)
    └── ExporterWorker (~4 tools: export)

Usage:
    swarm = create_shuttle_swarm()
    result = await swarm.run(task="Generiere Anforderungen für die Marketing bubble")
    response = result.messages[-1].content
"""

import os
import logging
from typing import Optional, List

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import (
    HandoffTermination,
    TextMentionTermination,
    MaxMessageTermination,
)
from autogen_agentchat.teams import Swarm

logger = logging.getLogger(__name__)

# --- Typed wrappers for format_dispatcher (Dict-based originals) ---

def convert_format(idea_name: str = "", target_format: str = "", columns: str = "") -> str:
    """
    Convert an idea to a different format.
    
    Args:
        idea_name: Name of idea to convert
        target_format: Target format (table, action_list, pros_cons, hierarchy, specs, note)
        columns: Optional column names for table format
    
    Returns:
        Success or error message
    """
    if not target_format:
        return "Bitte gib ein Zielformat an (table, action_list, pros_cons, hierarchy, specs, note)."
    
    from tools.format_dispatcher import convert_format as _convert_format
    return _convert_format({
        "idea_name": idea_name,
        "target_format": target_format,
        "columns": columns,
    })

def list_available_formats() -> str:
    """
    List all available format types for ideas.
    
    Returns:
        List of formats with descriptions
    """
    from tools.format_dispatcher import list_available_formats as _list_available_formats
    return _list_available_formats({})

# --- Shuttle Tools Import ---

try:
    from tools.bubble_requirements_tool import (
        list_bubbles_with_requirements,
        get_bubble_requirements,
        process_bubble_requirements,
    )
except ImportError as e:
    logger.warning(f"Could not import shuttle tools: {e}")
    # Create dummy tools for testing
    def list_bubbles_with_requirements(**kwargs):
        return {"bubbles": [], "count": 0}
    
    def get_bubble_requirements(**kwargs):
        return {"bubble_id": kwargs.get("bubble_id"), "requirements": []}
    
    def process_bubble_requirements(**kwargs):
        return {"status": "completed", "bubble_id": kwargs.get("bubble_id"), "requirements": []}

# --- Swarm Creation ---

def _get_model_client():
    """Get OpenRouter model client for AG2 agents."""
    from swarm.cloud_client import get_model_client
    return get_model_client()

def create_shuttle_swarm(model_client=None):
    """
    Create a Shuttle Swarm with LLM-based reasoning.
    
    6 agents with ~10 tools each, coordinated by ShuttleCoordinator.
    
    Args:
        model_client: Optional pre-configured model client.
                  Uses OpenRouter via cloud_client if not provided.
    
    Returns:
        Swarm team instance
    """
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.conditions import (
        HandoffTermination,
        TextMentionTermination,
        MaxMessageTermination,
    )
    from autogen_agentchat.teams import Swarm
    
    if model_client is None:
        model_client = _get_model_client()
    
    # --- Define Shuttle Coordinator ---
    coordinator = AssistantAgent(
        name="shuttle_coordinator",
        model_client=model_client,
        handoffs=[
            "requirements_analyst",
            "pipeline_manager",
            "validator",
            "exporter",
        ],
        system_message=(
            "Du koordinierst den Shuttle Workflow. Analysiere die Aufgabe und "
            "delegiere an den richtigen Spezialisten:\n\n"
            "- requirements_analyst: Anforderungen analysieren und generieren\n"
            "- pipeline_manager: Pipeline-Management und Koordination\n"
            "- validator: Anforderungen validieren\n"
            "- exporter: Anforderungen exportieren\n"
            "Fasse Ergebnisse zusammen und gib an user zurück wenn fertig.\n\n"
            "Bei Unklarheit über die Absicht, frag beim user nach."
        ),
    )
    
    # --- Define Requirements Analyst Worker ---
    requirements_analyst = AssistantAgent(
        name="requirements_analyst",
        model_client=model_client,
        handoffs=["shuttle_coordinator"],
        tools=[
            list_bubbles_with_requirements,
            get_bubble_requirements,
            process_bubble_requirements,
        ],
        system_message=(
            "Du analysierst Bubble-Inhalte und generierst Anforderungen.\n"
            "Nutze die verfügbaren Tools für CRUD-Operationen:\n"
            "- list_bubbles_with_requirements: Alle Bubbles mit Anforderungen auflisten\n"
            "- get_bubble_requirements: Anforderungen für eine Bubble abrufen\n"
            "- process_bubble_requirements: Anforderungen für eine Bubble verarbeiten\n"
            "Gib nach Abschluss an shuttle_coordinator zurück."
        ),
    )
    
    # --- Define Pipeline Manager Worker ---
    pipeline_manager = AssistantAgent(
        name="pipeline_manager",
        model_client=model_client,
        handoffs=["shuttle_coordinator"],
        tools=[
            list_bubbles_with_requirements,
            get_bubble_requirements,
            process_bubble_requirements,
        ],
        system_message=(
            "Du verwaltest Pipelines und koordinierst die Ausführung.\n"
            "Nutze die verfügbaren Tools für CRUD-Operationen:\n"
            "- list_bubbles_with_requirements: Alle Bubbles mit Anforderungen auflisten\n"
            "- get_bubble_requirements: Anforderungen für eine Bubble abrufen\n"
            "- process_bubble_requirements: Anforderungen für eine Bubble verarbeiten\n"
            "Erstelle, aktualisiere und führe Pipelines aus.\n"
            "Gib nach Abschluss an shuttle_coordinator zurück."
        ),
    )
    
    # --- Define Validator Worker ---
    validator = AssistantAgent(
        name="validator",
        model_client=model_client,
        handoffs=["shuttle_coordinator"],
        tools=[
            list_bubbles_with_requirements,
            get_bubble_requirements,
            process_bubble_requirements,
        ],
        system_message=(
            "Du validierst generierte Anforderungen gegen Spezifikationen.\n"
            "Nutze die verfügbaren Tools für CRUD-Operationen:\n"
            "- list_bubbles_with_requirements: Alle Bubbles mit Anforderungen auflisten\n"
            "- get_bubble_requirements: Anforderungen für eine Bubble abrufen\n"
            "- process_bubble_requirements: Anforderungen für eine Bubble verarbeiten\n"
            "Prüfe Vollständigkeit, Konsistenz und Spezifikationskonformität.\n"
            "Gib nach Abschluss an shuttle_coordinator zurück."
        ),
    )
    
    # --- Define Exporter Worker ---
    exporter = AssistantAgent(
        name="exporter",
        model_client=model_client,
        handoffs=["shuttle_coordinator"],
        tools=[
            list_bubbles_with_requirements,
            get_bubble_requirements,
            process_bubble_requirements,
        ],
        system_message=(
            "Du exportierst Anforderungen in verschiedene Formate.\n"
            "Nutze die verfügbaren Tools für CRUD-Operationen:\n"
            "- list_bubbles_with_requirements: Alle Bubbles mit Anforderungen auflisten\n"
            "- get_bubble_requirements: Anforderungen für eine Bubble abrufen\n"
            "- process_bubble_requirements: Anforderungen für eine Bubble verarbeiten\n"
            "Exportiere als JSON, CSV, Markdown oder andere Formate.\n"
            "Gib nach Abschluss an shuttle_coordinator zurück."
        ),
    )
    
    # --- Create Swarm ---
    swarm = Swarm(
        participants=[
            coordinator,
            requirements_analyst,
            pipeline_manager,
            validator,
            exporter,
        ],
        termination_condition=(
            HandoffTermination(target="user")
            | TextMentionTermination("DONE")
            | MaxMessageTermination(max_messages=15)
        )
    )
    
    logger.info(
        "Created Shuttle Swarm: 4 agents "
        "(coordinator + requirements_analyst + pipeline_manager + validator + exporter)"
    )
    return swarm

# --- Singleton ---

_shuttle_swarm = None

def get_shuttle_swarm(model_client=None):
    """Get or create Shuttle Swarm singleton."""
    global _shuttle_swarm
    if _shuttle_swarm is None:
        _shuttle_swarm = create_shuttle_swarm(model_client)
    return _shuttle_swarm

# --- Exports ---

__all__ = [
    "create_shuttle_swarm",
    "get_shuttle_swarm",
]
