"""
MermaidAgent - AutoGen-compatible agent for mermaid diagram operations.

Integrates with the user_kilo_agent pattern for autonomous diagram generation.
"""

import json
import logging
from typing import Dict, Any, Optional, List

from data.repository import MermaidDiagramsRepository, IdeasRepository
from data.models import MermaidDiagram, MermaidDiagramType
from tools.mermaid_generator import MermaidGenerator

logger = logging.getLogger(__name__)


class MermaidAgent:
    """Agent for mermaid diagram operations."""

    def __init__(self):
        self.generator = MermaidGenerator()
        self.repo = MermaidDiagramsRepository()
        self.ideas_repo = IdeasRepository()

    async def generate_diagram(
        self,
        source: str,
        source_id: str,
        diagram_type: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a mermaid diagram.

        Args:
            source: 'idea' or 'shuttle'
            source_id: ID of the source
            diagram_type: Optional diagram type override
            title: Optional title override

        Returns:
            Result dict with diagram info or error
        """
        try:
            if source == "idea":
                diagram = self.generator.generate_from_idea(
                    idea_id=source_id,
                    diagram_type=diagram_type,
                    title=title,
                )
            elif source == "shuttle":
                diagram = self.generator.generate_from_shuttle(
                    shuttle_id=source_id,
                    diagram_type=diagram_type,
                )
            else:
                return {"success": False, "error": f"Unknown source: {source}"}

            if diagram:
                return {
                    "success": True,
                    "diagram_id": diagram.id,
                    "title": diagram.title,
                    "type": diagram.diagram_type,
                    "content": diagram.content,
                }
            else:
                return {"success": False, "error": "Failed to generate diagram"}

        except Exception as e:
            logger.error(f"Error generating diagram: {e}")
            return {"success": False, "error": str(e)}

    async def generate_simple_flowchart(
        self,
        title: str,
        steps: List[str],
        source_idea_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a simple flowchart from steps.

        Args:
            title: Diagram title
            steps: List of step descriptions
            source_idea_id: Optional link to source idea

        Returns:
            Result dict with diagram info
        """
        try:
            diagram = self.generator.generate_simple_flowchart(
                title=title,
                steps=steps,
                source_idea_id=source_idea_id,
            )
            return {
                "success": True,
                "diagram_id": diagram.id,
                "title": diagram.title,
                "type": diagram.diagram_type,
                "content": diagram.content,
            }
        except Exception as e:
            logger.error(f"Error generating flowchart: {e}")
            return {"success": False, "error": str(e)}

    async def get_diagram(self, diagram_id: str) -> Dict[str, Any]:
        """Get a diagram by ID."""
        diagram = self.repo.get(diagram_id)
        if diagram:
            return {
                "success": True,
                "diagram": diagram.to_dict(),
                "markdown": diagram.to_markdown(),
            }
        return {"success": False, "error": "Diagram not found"}

    async def list_diagrams(
        self,
        idea_id: Optional[str] = None,
        diagram_type: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List diagrams with optional filters."""
        diagrams = self.repo.list(
            source_idea_id=idea_id,
            diagram_type=diagram_type,
            limit=limit,
        )
        return {
            "success": True,
            "count": len(diagrams),
            "diagrams": [d.to_dict() for d in diagrams],
        }

    async def update_diagram(
        self,
        diagram_id: str,
        content: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a diagram."""
        diagram = self.repo.get(diagram_id)
        if not diagram:
            return {"success": False, "error": "Diagram not found"}

        if content:
            diagram.content = content
        if title:
            diagram.title = title

        updated = self.repo.update(diagram)
        return {
            "success": True,
            "diagram": updated.to_dict(),
        }

    async def delete_diagram(self, diagram_id: str) -> Dict[str, Any]:
        """Delete a diagram."""
        result = self.repo.delete(diagram_id)
        return {"success": result}

    async def search_diagrams(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search diagrams by title or content."""
        diagrams = self.repo.search(query, limit=limit)
        return {
            "success": True,
            "count": len(diagrams),
            "diagrams": [d.to_dict() for d in diagrams],
        }

    def to_autogen_tools(self):
        """Convert to AutoGen-compatible tools."""
        try:
            from autogen_core.tools import FunctionTool
        except ImportError:
            logger.warning("autogen_core not available, returning empty tools list")
            return []

        async def generate_mermaid_diagram(
            source: str,
            source_id: str,
            diagram_type: Optional[str] = None,
            title: Optional[str] = None,
        ) -> str:
            """
            Generate a mermaid diagram from an idea or shuttle.

            Args:
                source: 'idea' or 'shuttle'
                source_id: ID of the source idea or shuttle
                diagram_type: Optional diagram type (flowchart, sequenceDiagram, etc.)
                title: Optional diagram title

            Returns:
                JSON string with diagram details
            """
            result = await self.generate_diagram(source, source_id, diagram_type, title)
            return json.dumps(result, indent=2)

        async def generate_simple_mermaid_flowchart(
            title: str,
            steps: List[str],
            source_idea_id: Optional[str] = None,
        ) -> str:
            """
            Generate a simple mermaid flowchart from a list of steps.

            Args:
                title: Diagram title
                steps: List of step descriptions
                source_idea_id: Optional link to source idea

            Returns:
                JSON string with diagram details
            """
            result = await self.generate_simple_flowchart(title, steps, source_idea_id)
            return json.dumps(result, indent=2)

        async def get_mermaid_diagram(diagram_id: str) -> str:
            """
            Get a mermaid diagram by ID.

            Args:
                diagram_id: ID of the diagram

            Returns:
                JSON string with diagram details and markdown
            """
            result = await self.get_diagram(diagram_id)
            return json.dumps(result, indent=2)

        async def list_mermaid_diagrams(
            idea_id: Optional[str] = None,
            diagram_type: Optional[str] = None,
            limit: int = 20,
        ) -> str:
            """
            List mermaid diagrams with optional filters.

            Args:
                idea_id: Optional filter by source idea
                diagram_type: Optional filter by diagram type
                limit: Maximum number of results

            Returns:
                JSON string with diagram list
            """
            result = await self.list_diagrams(idea_id, diagram_type, limit)
            return json.dumps(result, indent=2)

        async def search_mermaid_diagrams(query: str, limit: int = 10) -> str:
            """
            Search mermaid diagrams by title or content.

            Args:
                query: Search query
                limit: Maximum number of results

            Returns:
                JSON string with matching diagrams
            """
            result = await self.search_diagrams(query, limit)
            return json.dumps(result, indent=2)

        async def update_mermaid_diagram(
            diagram_id: str,
            content: Optional[str] = None,
            title: Optional[str] = None,
        ) -> str:
            """
            Update a mermaid diagram.

            Args:
                diagram_id: ID of the diagram to update
                content: New mermaid content (optional)
                title: New title (optional)

            Returns:
                JSON string with updated diagram
            """
            result = await self.update_diagram(diagram_id, content, title)
            return json.dumps(result, indent=2)

        async def delete_mermaid_diagram(diagram_id: str) -> str:
            """
            Delete a mermaid diagram.

            Args:
                diagram_id: ID of the diagram to delete

            Returns:
                JSON string with success status
            """
            result = await self.delete_diagram(diagram_id)
            return json.dumps(result, indent=2)

        return [
            FunctionTool(
                generate_mermaid_diagram,
                name="generate_mermaid_diagram",
                description="Generate a mermaid diagram from an idea or shuttle requirements",
            ),
            FunctionTool(
                generate_simple_mermaid_flowchart,
                name="generate_simple_mermaid_flowchart",
                description="Generate a simple mermaid flowchart from a list of steps",
            ),
            FunctionTool(
                get_mermaid_diagram,
                name="get_mermaid_diagram",
                description="Get a mermaid diagram by its ID",
            ),
            FunctionTool(
                list_mermaid_diagrams,
                name="list_mermaid_diagrams",
                description="List mermaid diagrams with optional filters",
            ),
            FunctionTool(
                search_mermaid_diagrams,
                name="search_mermaid_diagrams",
                description="Search mermaid diagrams by title or content",
            ),
            FunctionTool(
                update_mermaid_diagram,
                name="update_mermaid_diagram",
                description="Update an existing mermaid diagram",
            ),
            FunctionTool(
                delete_mermaid_diagram,
                name="delete_mermaid_diagram",
                description="Delete a mermaid diagram",
            ),
        ]


# Convenience function for creating the agent
def create_mermaid_agent() -> MermaidAgent:
    """Create a new MermaidAgent instance."""
    return MermaidAgent()
