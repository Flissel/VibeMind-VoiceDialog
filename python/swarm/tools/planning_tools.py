"""
Planning Tools for VibeMind Swarm

Tools for intelligent task planning and decomposition using conversation context.
Provides context-aware planning capabilities for complex user requests.
"""

import logging
from typing import Dict, Any, List, Optional
import sys
from pathlib import Path
import json

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


def analyze_transcript_and_plan(user_request: str) -> str:
    """
    Analyze conversation transcript and create a comprehensive execution plan.

    This is the main planning function that:
    1. Analyzes the full conversation context
    2. Identifies relevant information sources
    3. Creates a structured execution plan
    4. Defines task dependencies and coordination

    Args:
        user_request: The current user request to plan for

    Returns:
        JSON-formatted execution plan
    """
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_analyze_and_plan_async(user_request))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Planning analysis failed: {e}")
        return json.dumps({
            "error": f"Planning failed: {str(e)}",
            "fallback_plan": {
                "tasks": [{
                    "id": "direct_execution",
                    "description": f"Execute request directly: {user_request}",
                    "agent": "ideas_agent",
                    "action": "handle_request",
                    "params": {"request": user_request}
                }]
            }
        })


async def _analyze_and_plan_async(user_request: str) -> str:
    """Async implementation of transcript analysis and planning."""
    from swarm.tools.transcript_manager import get_conversation_context, search_transcript

    # Get full conversation context
    context = await get_conversation_context()

    # Search for related previous discussions
    related_entries = await search_transcript(user_request, 20)

    # Analyze the request and context
    analysis = await _analyze_request_context(user_request, context, related_entries)

    # Generate execution plan
    plan = await _generate_execution_plan(user_request, analysis)

    return json.dumps(plan, indent=2, ensure_ascii=False)


async def _analyze_request_context(user_request: str, context: Dict[str, Any], related_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze the request in conversation context."""

    analysis = {
        "request": user_request,
        "conversation_context": {
            "total_entries": context.get("total_entries", 0),
            "time_range": context.get("time_range"),
            "recent_activity": len(context.get("recent_activity", [])),
            "conversation_summary": context.get("conversation_summary", "")
        },
        "related_discussions": len(related_entries),
        "key_insights": [],
        "required_capabilities": [],
        "information_sources": [],
        "complexity_level": "simple"  # simple, moderate, complex
    }

    # Analyze request complexity
    request_lower = user_request.lower()

    # Check for complex indicators
    complex_indicators = [
        "system", "architecture", "integration", "automatisch", "erweitern",
        "analysieren", "entwickeln", "implementieren", "conversion", "alliance",
        "self-aware", "intelligent", "plan", "strategie"
    ]

    complexity_score = sum(1 for indicator in complex_indicators if indicator in request_lower)

    if complexity_score >= 3:
        analysis["complexity_level"] = "complex"
    elif complexity_score >= 1:
        analysis["complexity_level"] = "moderate"

    # Identify required capabilities
    if "datenbank" in request_lower or "sql" in request_lower:
        analysis["required_capabilities"].append("database_query")
        analysis["information_sources"].append("postgresql")

    if "ideen" in request_lower or "expand" in request_lower:
        analysis["required_capabilities"].append("idea_expansion")
        analysis["information_sources"].append("canvas_repository")

    if "code" in request_lower or "programmier" in request_lower:
        analysis["required_capabilities"].append("code_generation")
        analysis["information_sources"].append("coding_agent")

    if "analyse" in request_lower or "untersuch" in request_lower:
        analysis["required_capabilities"].append("data_analysis")
        analysis["information_sources"].append("query_agent")

    # Extract key insights from related discussions
    for entry in related_entries[:5]:  # Limit to most recent
        if entry["type"] == "user_input":
            analysis["key_insights"].append(f"Previous user interest: {entry['content'][:100]}...")
        elif entry["type"] == "agent_response":
            analysis["key_insights"].append(f"Previous system capability: {entry['content'][:100]}...")

    return analysis


async def _generate_execution_plan(user_request: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a structured execution plan based on analysis."""

    plan = {
        "objective": user_request,
        "analysis": analysis,
        "execution_strategy": _determine_execution_strategy(analysis),
        "tasks": [],
        "coordination_notes": [],
        "estimated_complexity": analysis["complexity_level"]
    }

    # Generate tasks based on complexity and requirements
    if analysis["complexity_level"] == "complex":
        plan["tasks"] = await _generate_complex_plan_tasks(user_request, analysis)
    elif analysis["complexity_level"] == "moderate":
        plan["tasks"] = await _generate_moderate_plan_tasks(user_request, analysis)
    else:
        plan["tasks"] = await _generate_simple_plan_tasks(user_request, analysis)

    # Add coordination notes
    plan["coordination_notes"] = _generate_coordination_notes(plan["tasks"])

    return plan


def _determine_execution_strategy(analysis: Dict[str, Any]) -> str:
    """Determine the best execution strategy."""
    capabilities = analysis.get("required_capabilities", [])

    if "database_query" in capabilities and "idea_expansion" in capabilities:
        return "multi_agent_coordination"
    elif len(capabilities) > 2:
        return "parallel_execution"
    elif analysis.get("complexity_level") == "complex":
        return "sequential_decomposition"
    else:
        return "direct_execution"


async def _generate_complex_plan_tasks(user_request: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate tasks for complex requests."""
    tasks = []

    # Task 1: Context gathering
    tasks.append({
        "id": "gather_context",
        "description": "Gather relevant context from conversation history and current state",
        "agent": "query_agent",
        "action": "get_bubble_statistics",
        "params": {},
        "required": True,
        "depends_on": []
    })

    # Task 2: Information source identification
    if "postgresql" in analysis.get("information_sources", []):
        tasks.append({
            "id": "identify_data_sources",
            "description": "Identify relevant data sources in PostgreSQL",
            "agent": "query_agent",
            "action": "search_ideas_by_content",
            "params": {"query": user_request.split()[:3], "limit": 20},
            "required": True,
            "depends_on": ["gather_context"]
        })

    # Task 3: Analysis and planning
    tasks.append({
        "id": "analyze_requirements",
        "description": "Analyze requirements and create detailed plan",
        "agent": "ideas_agent",
        "action": "expand_ideas",
        "params": {"source_idea": "", "count": 3},
        "required": True,
        "depends_on": ["identify_data_sources"] if "postgresql" in analysis.get("information_sources", []) else ["gather_context"]
    })

    # Task 4: Execution coordination
    if "code_generation" in analysis.get("required_capabilities", []):
        tasks.append({
            "id": "coordinate_execution",
            "description": "Coordinate execution across multiple agents",
            "agent": "coding_agent",
            "action": "generate_code_structure",
            "params": {"requirements": user_request},
            "required": True,
            "depends_on": ["analyze_requirements"]
        })

    return tasks


async def _generate_moderate_plan_tasks(user_request: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate tasks for moderate complexity requests."""
    tasks = []

    # Primary task based on main capability needed
    capabilities = analysis.get("required_capabilities", [])

    if "idea_expansion" in capabilities:
        tasks.append({
            "id": "expand_ideas",
            "description": "Expand existing ideas based on request",
            "agent": "ideas_agent",
            "action": "expand_ideas",
            "params": {"count": 5},
            "required": True,
            "depends_on": []
        })
    elif "database_query" in capabilities:
        tasks.append({
            "id": "query_database",
            "description": "Query database for relevant information",
            "agent": "query_agent",
            "action": "search_ideas_by_content",
            "params": {"query": user_request, "limit": 10},
            "required": True,
            "depends_on": []
        })
    else:
        tasks.append({
            "id": "handle_request",
            "description": f"Handle user request: {user_request[:50]}...",
            "agent": "ideas_agent",
            "action": "create_idea",
            "params": {"title": f"Request: {user_request[:30]}...", "content": user_request},
            "required": True,
            "depends_on": []
        })

    return tasks


async def _generate_simple_plan_tasks(user_request: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate tasks for simple requests."""
    return [{
        "id": "direct_execution",
        "description": f"Execute simple request: {user_request[:50]}...",
        "agent": "ideas_agent",
        "action": "create_idea",
        "params": {"title": f"Task: {user_request[:30]}...", "content": user_request},
        "required": True,
        "depends_on": []
    }]


def _generate_coordination_notes(tasks: List[Dict[str, Any]]) -> List[str]:
    """Generate coordination notes for the execution plan."""
    notes = []

    # Count agents involved
    agents = set(task["agent"] for task in tasks)
    if len(agents) > 1:
        notes.append(f"Coordination required between {len(agents)} agents: {', '.join(agents)}")

    # Check for dependencies
    has_dependencies = any(task.get("depends_on") for task in tasks)
    if has_dependencies:
        notes.append("Task dependencies detected - execute in specified order")

    # Check for parallel execution opportunities
    independent_tasks = [task for task in tasks if not task.get("depends_on")]
    if len(independent_tasks) > 1:
        notes.append(f"{len(independent_tasks)} tasks can be executed in parallel")

    return notes


def validate_plan_execution(plan_json: str) -> str:
    """
    Validate that a plan can be executed with current system capabilities.

    Args:
        plan_json: JSON string of the execution plan

    Returns:
        Validation results
    """
    try:
        plan = json.loads(plan_json)

        validation = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }

        # Validate tasks
        tasks = plan.get("tasks", [])
        if not tasks:
            validation["errors"].append("No tasks defined in plan")
            validation["is_valid"] = False

        # Check agent availability
        available_agents = {"ideas_agent", "query_agent", "coding_agent", "desktop_agent", "data_agent"}
        for task in tasks:
            agent = task.get("agent")
            if agent not in available_agents:
                validation["errors"].append(f"Agent '{agent}' not available")
                validation["is_valid"] = False

        # Check dependencies
        task_ids = {task["id"] for task in tasks}
        for task in tasks:
            depends_on = task.get("depends_on", [])
            for dep in depends_on:
                if dep not in task_ids:
                    validation["errors"].append(f"Task '{task['id']}' depends on unknown task '{dep}'")
                    validation["is_valid"] = False

        # Performance recommendations
        if len(tasks) > 5:
            validation["warnings"].append("Plan has many tasks - consider optimization")

        parallel_tasks = len([t for t in tasks if not t.get("depends_on")])
        if parallel_tasks > 2:
            validation["recommendations"].append(f"Consider parallel execution of {parallel_tasks} independent tasks")

        return json.dumps(validation, indent=2)

    except json.JSONDecodeError as e:
        return json.dumps({
            "is_valid": False,
            "errors": [f"Invalid JSON: {str(e)}"]
        })


def optimize_plan(plan_json: str) -> str:
    """
    Optimize an execution plan for better performance.

    Args:
        plan_json: JSON string of the execution plan

    Returns:
        Optimized plan
    """
    try:
        plan = json.loads(plan_json)

        # Identify optimization opportunities
        tasks = plan.get("tasks", [])

        # Group independent tasks for parallel execution
        independent_tasks = []
        dependent_tasks = []

        for task in tasks:
            if task.get("depends_on"):
                dependent_tasks.append(task)
            else:
                independent_tasks.append(task)

        # Create optimized plan
        optimized_plan = {
            "original_plan": plan,
            "optimization": {
                "parallel_tasks": len(independent_tasks),
                "sequential_tasks": len(dependent_tasks),
                "estimated_improvement": f"{len(independent_tasks) * 20}% faster with parallel execution"
            },
            "execution_groups": [
                {
                    "name": "parallel_group",
                    "tasks": [t["id"] for t in independent_tasks],
                    "execution": "parallel"
                },
                {
                    "name": "sequential_group",
                    "tasks": [t["id"] for t in dependent_tasks],
                    "execution": "sequential"
                }
            ]
        }

        return json.dumps(optimized_plan, indent=2)

    except Exception as e:
        return json.dumps({
            "error": f"Optimization failed: {str(e)}",
            "original_plan": plan_json
        })


# Collect all planning tools for export
PLANNING_TOOLS = [
    analyze_transcript_and_plan,
    validate_plan_execution,
    optimize_plan,
]


__all__ = [
    "analyze_transcript_and_plan",
    "validate_plan_execution",
    "optimize_plan",
    "PLANNING_TOOLS",
]