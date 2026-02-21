"""
Enhanced Ideas Agent - Advanced Idea Management with Learning Capabilities

Demonstrates the enhanced agent framework with:
- Plugin architecture for learning
- Workflow state management
- Event-driven communication
- Agent coordination
- Health monitoring
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from swarm.backend_agents.enhanced_base_agent import (
    EnhancedBaseAgent,
    AgentCapability,
    AgentPlugin,
    WorkflowState
)
from swarm.backend_agents.plugins.learning_plugin import LearningPlugin
from swarm.navigation import SpaceType

logger = logging.getLogger(__name__)


class EnhancedIdeasAgent(EnhancedBaseAgent):
    """
    Enhanced Ideas Agent with advanced capabilities.

    Features:
    - Learning-based idea management
    - Workflow coordination for complex idea operations
    - Event-driven collaboration with other agents
    - Health monitoring and self-healing
    - Plugin-based extensibility
    """

    def __init__(self):
        super().__init__()
        self._capabilities.update({
            AgentCapability.TASK_EXECUTION,
            AgentCapability.DATA_PROCESSING,
            AgentCapability.COORDINATION,
            AgentCapability.LEARNING
        })

    @property
    def stream(self) -> str:
        return "events:ideas"

    @property
    def name(self) -> str:
        return "enhanced_ideas_agent"

    def _load_tools(self) -> Dict[str, Any]:
        """Load idea management tools."""
        try:
            from tools.idea_tools import (
                create_idea, list_ideas, find_idea, delete_idea,
                update_idea, connect_ideas, add_image, get_current_space,
                expand_ideas, move_idea
            )

            return {
                "create_idea": create_idea,
                "list_ideas": list_ideas,
                "find_idea": find_idea,
                "delete_idea": delete_idea,
                "update_idea": update_idea,
                "connect_ideas": connect_ideas,
                "add_image": add_image,
                "get_current_space": get_current_space,
                "expand_ideas": expand_ideas,
                "move_idea": move_idea,
            }
        except ImportError as e:
            logger.warning(f"Could not load idea tools: {e}")
            return {}

    def _get_tool_name(self, event_type: str) -> Optional[str]:
        """Map event type to tool name."""
        mapping = {
            "idea.create": "create_idea",
            "idea.list": "list_ideas",
            "idea.find": "find_idea",
            "idea.delete": "delete_idea",
            "idea.update": "update_idea",
            "idea.connect": "connect_ideas",
            "idea.add_image": "add_image",
            "idea.expand": "expand_ideas",
            "idea.move": "move_idea",
            "bubble.current": "get_current_space",
        }
        return mapping.get(event_type)

    async def _initialize_plugins(self) -> None:
        """Initialize plugins for enhanced capabilities."""
        # Register learning plugin
        learning_plugin = LearningPlugin()
        await self.register_plugin(learning_plugin)

        # Subscribe to learning-related events
        await self.subscribe_to_events("learning.*", self._handle_learning_event)

        logger.info("Enhanced Ideas Agent plugins initialized")

    async def _execute_base_task(self, task_type: str, payload: Dict[str, Any]) -> Any:
        """Execute base task using tools."""
        tool_name = self._get_tool_name(task_type)
        if not tool_name:
            raise ValueError(f"Unknown task type: {task_type}")

        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not available: {tool_name}")

        # Remove internal fields
        tool_params = {k: v for k, v in payload.items()
                      if k not in ["job_id", "user_id", "session_id", "priority", "bubble_context", "metadata"]}

        # Execute tool
        result = tool(**tool_params)
        if asyncio.iscoroutine(result):
            result = await result

        return result

    async def _handle_learning_event(self, event) -> None:
        """Handle learning-related events."""
        if event.event_type == "learning.performance_update":
            # Update learning model with new performance data
            payload = event.payload
            task_type = payload.get("task_type")
            success = payload.get("success", False)
            response_time = payload.get("response_time", 0.0)
            context = payload.get("context", {})

            learning_plugin = None
            for plugin in self._plugins.values():
                if plugin.name == "learning":
                    learning_plugin = plugin
                    break

            if learning_plugin:
                await learning_plugin.record_task_result(task_type, success, response_time, context)

    async def _handle_collaboration_request(self, from_agent: str, payload: Dict[str, Any]) -> None:
        """Handle collaboration requests from other agents."""
        request_type = payload.get("request_type")

        if request_type == "idea_expansion":
            # Collaborate on idea expansion
            idea_id = payload.get("idea_id")
            expansion_suggestions = await self._generate_expansion_suggestions(idea_id)

            # Send response
            response_payload = {
                "workflow_id": payload.get("workflow_id"),
                "suggestions": expansion_suggestions,
                "agent": self.name
            }
            await self.send_coordination_message(from_agent, "collaboration_response", response_payload)

        elif request_type == "idea_connection":
            # Help with connecting ideas
            source_idea = payload.get("source_idea")
            target_ideas = payload.get("target_ideas", [])
            connections = await self._analyze_connections(source_idea, target_ideas)

            response_payload = {
                "workflow_id": payload.get("workflow_id"),
                "connections": connections,
                "agent": self.name
            }
            await self.send_coordination_message(from_agent, "collaboration_response", response_payload)

    async def _generate_expansion_suggestions(self, idea_id: str) -> list:
        """Generate intelligent expansion suggestions for an idea."""
        # This would use learning data to suggest expansions
        # For now, return mock suggestions
        return [
            "Add implementation details",
            "Consider edge cases",
            "Link to related concepts",
            "Add visual representation"
        ]

    async def _analyze_connections(self, source_idea: str, target_ideas: list) -> list:
        """Analyze potential connections between ideas."""
        # This would use learning data for connection analysis
        # For now, return mock analysis
        connections = []
        for target in target_ideas:
            connections.append({
                "source": source_idea,
                "target": target,
                "strength": 0.7,
                "reason": "Semantic similarity detected"
            })
        return connections

    async def create_complex_idea_workflow(
        self,
        workflow_id: str,
        idea_description: str,
        auto_expand: bool = True,
        connect_similar: bool = True
    ) -> WorkflowState:
        """
        Create a complex workflow for idea creation with expansion and connections.

        Demonstrates workflow state management and agent coordination.
        """
        # Define workflow steps
        steps = [
            "create_idea",
            "expand_idea",
            "find_similar_ideas",
            "create_connections",
            "validate_workflow"
        ]

        # Create workflow state
        workflow_state = await self.create_workflow_state(workflow_id, steps)

        # Store workflow context
        workflow_state.shared_data.update({
            "idea_description": idea_description,
            "auto_expand": auto_expand,
            "connect_similar": connect_similar,
            "created_idea_id": None,
            "similar_ideas": [],
            "connections_created": 0
        })

        # Start workflow execution
        asyncio.create_task(self._execute_idea_workflow(workflow_state))

        return workflow_state

    async def _execute_idea_workflow(self, workflow_state: WorkflowState) -> None:
        """Execute the complex idea creation workflow."""
        try:
            # Step 1: Create the idea
            idea_data = workflow_state.shared_data["idea_description"]
            result = await self._execute_base_task("idea.create", {"title": idea_data})
            idea_id = result.get("id") if isinstance(result, dict) else "mock_id"

            workflow_state.shared_data["created_idea_id"] = idea_id
            await self.update_workflow_state(workflow_state.workflow_id, completed_step="create_idea")

            # Step 2: Expand idea (if requested)
            if workflow_state.shared_data["auto_expand"]:
                expansion_result = await self._execute_base_task("idea.expand", {"idea_id": idea_id})
                await self.update_workflow_state(workflow_state.workflow_id, completed_step="expand_idea")

            # Step 3: Find similar ideas
            similar_result = await self._execute_base_task("idea.list", {})
            similar_ideas = similar_result.get("ideas", []) if isinstance(similar_result, dict) else []
            workflow_state.shared_data["similar_ideas"] = similar_ideas
            await self.update_workflow_state(workflow_state.workflow_id, completed_step="find_similar_ideas")

            # Step 4: Create connections (if requested and similar ideas found)
            if workflow_state.shared_data["connect_similar"] and similar_ideas:
                connections_created = 0
                for similar_idea in similar_ideas[:3]:  # Limit to 3 connections
                    try:
                        await self._execute_base_task("idea.connect", {
                            "source_id": idea_id,
                            "target_id": similar_idea.get("id")
                        })
                        connections_created += 1
                    except Exception as e:
                        logger.warning(f"Failed to create connection: {e}")

                workflow_state.shared_data["connections_created"] = connections_created
                await self.update_workflow_state(workflow_state.workflow_id, completed_step="create_connections")

            # Step 5: Validate workflow
            validation_result = {
                "idea_created": idea_id is not None,
                "expansions_done": workflow_state.shared_data["auto_expand"],
                "connections_created": workflow_state.shared_data["connections_created"],
                "workflow_complete": True
            }

            await self.update_workflow_state(
                workflow_state.workflow_id,
                completed_step="validate_workflow",
                shared_data={"validation": validation_result}
            )

            logger.info(f"Complex idea workflow {workflow_state.workflow_id} completed successfully")

        except Exception as e:
            logger.error(f"Workflow {workflow_state.workflow_id} failed: {e}")
            await self.update_workflow_state(workflow_state.workflow_id, failed_step="workflow_execution")

    def get_enhanced_stats(self) -> Dict[str, Any]:
        """Get enhanced agent statistics including learning metrics."""
        base_stats = self.get_agent_stats()

        # Add learning-specific stats
        learning_plugin = None
        for plugin in self._plugins.values():
            if plugin.name == "learning":
                learning_plugin = plugin
                break

        if learning_plugin:
            learning_stats = {}
            for task_type in learning_plugin._task_performance.keys():
                learning_stats[task_type] = learning_plugin.get_performance_insights(task_type)

            base_stats["learning"] = {
                "tracked_task_types": len(learning_plugin._task_performance),
                "adaptive_thresholds": learning_plugin._adaptive_thresholds,
                "performance_insights": learning_stats
            }

        return base_stats


# Factory function for creating enhanced agents
async def create_enhanced_ideas_agent() -> EnhancedIdeasAgent:
    """Create and initialize an enhanced ideas agent."""
    agent = EnhancedIdeasAgent()
    await agent.start()
    return agent


__all__ = ["EnhancedIdeasAgent", "create_enhanced_ideas_agent"]