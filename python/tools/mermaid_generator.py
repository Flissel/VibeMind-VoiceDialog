"""
MermaidGenerator - Generate mermaid diagrams from requirements and ideas.

Maps requirements types to diagram types:
- User flows -> flowchart
- API interactions -> sequenceDiagram
- Data models -> classDiagram / erDiagram
- State transitions -> stateDiagram
- Project timelines -> gantt
- System components -> C4Context / flowchart
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from data.repository import (
    MermaidDiagramsRepository,
    IdeasRepository,
    ShuttlesRepository,
    CanvasRepository,
    generate_id,
)
from data.models import MermaidDiagram, MermaidDiagramType

logger = logging.getLogger(__name__)


class MermaidGenerator:
    """Generate mermaid diagrams from requirements and ideas."""

    # Mapping of requirement patterns to diagram types
    REQUIREMENT_TYPE_MAP = {
        # User-facing flows
        "user_flow": MermaidDiagramType.FLOWCHART,
        "workflow": MermaidDiagramType.FLOWCHART,
        "process": MermaidDiagramType.FLOWCHART,
        "decision": MermaidDiagramType.FLOWCHART,
        "ablauf": MermaidDiagramType.FLOWCHART,
        "prozess": MermaidDiagramType.FLOWCHART,

        # API and interactions
        "api": MermaidDiagramType.SEQUENCE,
        "integration": MermaidDiagramType.SEQUENCE,
        "communication": MermaidDiagramType.SEQUENCE,
        "request_response": MermaidDiagramType.SEQUENCE,
        "schnittstelle": MermaidDiagramType.SEQUENCE,

        # Data and models
        "data_model": MermaidDiagramType.ER,
        "database": MermaidDiagramType.ER,
        "entity": MermaidDiagramType.ER,
        "datenbank": MermaidDiagramType.ER,
        "class": MermaidDiagramType.CLASS,
        "object": MermaidDiagramType.CLASS,
        "inheritance": MermaidDiagramType.CLASS,
        "klasse": MermaidDiagramType.CLASS,

        # State and behavior
        "state": MermaidDiagramType.STATE,
        "status": MermaidDiagramType.STATE,
        "lifecycle": MermaidDiagramType.STATE,
        "zustand": MermaidDiagramType.STATE,

        # Time and planning
        "timeline": MermaidDiagramType.GANTT,
        "schedule": MermaidDiagramType.GANTT,
        "milestone": MermaidDiagramType.GANTT,
        "sprint": MermaidDiagramType.GANTT,
        "zeitplan": MermaidDiagramType.GANTT,

        # Architecture
        "component": MermaidDiagramType.FLOWCHART,
        "system": MermaidDiagramType.FLOWCHART,
        "architecture": MermaidDiagramType.FLOWCHART,
        "architektur": MermaidDiagramType.FLOWCHART,

        # Auth-specific
        "authentication": MermaidDiagramType.SEQUENCE,
        "authorization": MermaidDiagramType.FLOWCHART,
        "login": MermaidDiagramType.SEQUENCE,
        "session": MermaidDiagramType.STATE,
        "auth": MermaidDiagramType.SEQUENCE,
        "anmeldung": MermaidDiagramType.SEQUENCE,
    }

    def __init__(self):
        self.mermaid_repo = MermaidDiagramsRepository()
        self.ideas_repo = IdeasRepository()
        self.shuttles_repo = ShuttlesRepository()
        self.canvas_repo = CanvasRepository()

    def generate_from_idea(
        self,
        idea_id: str,
        diagram_type: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Optional[MermaidDiagram]:
        """
        Generate a mermaid diagram from an idea.

        Args:
            idea_id: ID of the source idea
            diagram_type: Override diagram type (auto-detected if None)
            title: Override title (uses idea title if None)

        Returns:
            Created MermaidDiagram or None on failure
        """
        idea = self.ideas_repo.get(idea_id)
        if not idea:
            logger.error(f"Idea not found: {idea_id}")
            return None

        # Detect diagram type from idea content
        if not diagram_type:
            diagram_type = self._detect_diagram_type(
                idea.title,
                idea.description,
                idea.metadata
            )

        # Generate diagram content using LLM
        content = self._generate_diagram_content(
            diagram_type=diagram_type,
            title=idea.title,
            description=idea.description,
            metadata=idea.metadata,
        )

        if not content:
            logger.error(f"Failed to generate diagram for idea: {idea_id}")
            return None

        # Create and persist diagram
        diagram = self.mermaid_repo.create(
            title=title or f"{diagram_type} - {idea.title}",
            content=content,
            diagram_type=diagram_type,
            source_idea_id=idea_id,
            metadata={
                "generated_from": "idea",
                "idea_title": idea.title,
                "generated_at": datetime.now().isoformat(),
            },
        )

        # Also create a canvas node for the diagram
        self._create_canvas_node_for_diagram(diagram, idea_id)

        return diagram

    def generate_from_shuttle(
        self,
        shuttle_id: str,
        diagram_type: Optional[str] = None,
    ) -> Optional[MermaidDiagram]:
        """
        Generate diagram from shuttle requirements.

        Uses requirement_results and stage_data from the shuttle.
        """
        shuttle = self.shuttles_repo.get_by_shuttle_id(shuttle_id)
        if not shuttle:
            logger.error(f"Shuttle not found: {shuttle_id}")
            return None

        # Extract requirements from shuttle
        requirements = self._extract_requirements_from_shuttle(shuttle)

        if not requirements:
            logger.warning(f"No requirements found in shuttle: {shuttle_id}")
            return None

        # Detect or use provided diagram type
        if not diagram_type:
            diagram_type = self._detect_type_from_requirements(requirements)

        # Generate content
        content = self._generate_from_requirements(
            requirements=requirements,
            diagram_type=diagram_type,
            context=shuttle.bubble_name,
        )

        if not content:
            return None

        # Create diagram
        requirement_ids = [r.get("id", "") for r in requirements if r.get("id")]

        diagram = self.mermaid_repo.create(
            title=f"{diagram_type} - {shuttle.bubble_name}",
            content=content,
            diagram_type=diagram_type,
            source_idea_id=shuttle.bubble_id,
            source_shuttle_id=shuttle.id,
            source_requirement_ids=requirement_ids,
            metadata={
                "generated_from": "shuttle",
                "shuttle_id": shuttle.shuttle_id,
                "requirement_count": len(requirements),
                "generated_at": datetime.now().isoformat(),
            },
        )

        return diagram

    def generate_from_requirements_list(
        self,
        requirements: List[Dict[str, Any]],
        diagram_type: str,
        title: str,
        source_idea_id: Optional[str] = None,
    ) -> Optional[MermaidDiagram]:
        """
        Generate diagram from a list of requirements.

        Args:
            requirements: List of requirement dicts with 'id', 'title', 'description'
            diagram_type: Type of mermaid diagram
            title: Diagram title
            source_idea_id: Optional link to source idea
        """
        content = self._generate_from_requirements(
            requirements=requirements,
            diagram_type=diagram_type,
            context=title,
        )

        if not content:
            return None

        requirement_ids = [r.get("id", "") for r in requirements if r.get("id")]

        return self.mermaid_repo.create(
            title=title,
            content=content,
            diagram_type=diagram_type,
            source_idea_id=source_idea_id,
            source_requirement_ids=requirement_ids,
            metadata={
                "generated_from": "requirements_list",
                "requirement_count": len(requirements),
                "generated_at": datetime.now().isoformat(),
            },
        )

    def generate_simple_flowchart(
        self,
        title: str,
        steps: List[str],
        source_idea_id: Optional[str] = None,
    ) -> MermaidDiagram:
        """
        Generate a simple flowchart from a list of steps.

        Args:
            title: Diagram title
            steps: List of step descriptions
            source_idea_id: Optional link to source idea

        Returns:
            Created MermaidDiagram
        """
        # Build flowchart content
        lines = ["flowchart TD"]

        for i, step in enumerate(steps):
            node_id = chr(65 + i)  # A, B, C, ...
            step_clean = step.replace('"', "'")
            lines.append(f'    {node_id}["{step_clean}"]')

        # Add connections
        for i in range(len(steps) - 1):
            from_id = chr(65 + i)
            to_id = chr(65 + i + 1)
            lines.append(f'    {from_id} --> {to_id}')

        content = "\n".join(lines)

        return self.mermaid_repo.create(
            title=title,
            content=content,
            diagram_type=MermaidDiagramType.FLOWCHART,
            source_idea_id=source_idea_id,
            metadata={
                "generated_from": "simple_flowchart",
                "step_count": len(steps),
                "generated_at": datetime.now().isoformat(),
            },
        )

    def _detect_diagram_type(
        self,
        title: str,
        description: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Detect appropriate diagram type from content."""
        combined = f"{title} {description}".lower()

        for keyword, dtype in self.REQUIREMENT_TYPE_MAP.items():
            if keyword in combined:
                return dtype

        # Check metadata tags
        tags = metadata.get("tags", [])
        for tag in tags:
            tag_lower = tag.lower()
            for keyword, dtype in self.REQUIREMENT_TYPE_MAP.items():
                if keyword in tag_lower:
                    return dtype

        # Default to flowchart
        return MermaidDiagramType.FLOWCHART

    def _detect_type_from_requirements(
        self,
        requirements: List[Dict[str, Any]],
    ) -> str:
        """Detect diagram type from requirements content."""
        all_text = " ".join([
            f"{r.get('title', '')} {r.get('description', '')}"
            for r in requirements
        ]).lower()

        for keyword, dtype in self.REQUIREMENT_TYPE_MAP.items():
            if keyword in all_text:
                return dtype

        return MermaidDiagramType.FLOWCHART

    def _extract_requirements_from_shuttle(
        self,
        shuttle,
    ) -> List[Dict[str, Any]]:
        """Extract requirements from shuttle data."""
        requirements = []

        # From stage_data (mining stage)
        if shuttle.stage_data:
            reqs = shuttle.stage_data.get("requirements", [])
            requirements.extend(reqs)

        # From requirement_results (validation stage)
        if shuttle.requirement_results:
            results = shuttle.requirement_results.get("results", [])
            for result in results:
                if isinstance(result, dict):
                    requirements.append({
                        "id": result.get("id", ""),
                        "title": result.get("requirement", ""),
                        "description": result.get("details", ""),
                        "passed": result.get("passed", False),
                        "score": result.get("score", 0),
                    })

        return requirements

    def _generate_diagram_content(
        self,
        diagram_type: str,
        title: str,
        description: str,
        metadata: Dict[str, Any],
    ) -> Optional[str]:
        """Generate mermaid diagram content using LLM."""
        try:
            from .format_dispatcher import _get_llm_client
        except ImportError:
            logger.warning("LLM client not available, using template-based generation")
            return self._generate_template_diagram(diagram_type, title, description)

        prompt = self._build_generation_prompt(
            diagram_type=diagram_type,
            context=f"Title: {title}\n\nDescription:\n{description}",
        )

        try:
            client = _get_llm_client()
            response = client.chat.completions.create(
                model="anthropic/claude-sonnet-4.5",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )

            content = response.choices[0].message.content.strip()

            # Extract mermaid block if wrapped in markdown
            if "```mermaid" in content:
                content = content.split("```mermaid")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return content

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._generate_template_diagram(diagram_type, title, description)

    def _generate_from_requirements(
        self,
        requirements: List[Dict[str, Any]],
        diagram_type: str,
        context: str,
    ) -> Optional[str]:
        """Generate diagram from requirements list."""
        try:
            from .format_dispatcher import _get_llm_client
        except ImportError:
            logger.warning("LLM client not available, using template-based generation")
            return self._generate_template_from_requirements(diagram_type, requirements, context)

        # Format requirements for prompt
        req_text = "\n".join([
            f"- {r.get('title', 'Requirement')}: {r.get('description', '')}"
            for r in requirements
        ])

        prompt = self._build_generation_prompt(
            diagram_type=diagram_type,
            context=f"Context: {context}\n\nRequirements:\n{req_text}",
        )

        try:
            client = _get_llm_client()
            response = client.chat.completions.create(
                model="anthropic/claude-sonnet-4.5",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )

            content = response.choices[0].message.content.strip()

            if "```mermaid" in content:
                content = content.split("```mermaid")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return content

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._generate_template_from_requirements(diagram_type, requirements, context)

    def _generate_template_diagram(
        self,
        diagram_type: str,
        title: str,
        description: str,
    ) -> str:
        """Generate a template-based diagram when LLM is not available."""
        title_clean = title.replace('"', "'")

        if diagram_type == MermaidDiagramType.FLOWCHART:
            return f'''flowchart TD
    A["{title_clean}"]
    A --> B["Step 1"]
    B --> C["Step 2"]
    C --> D["Complete"]'''

        elif diagram_type == MermaidDiagramType.SEQUENCE:
            return f'''sequenceDiagram
    participant User
    participant System
    User->>System: Request
    System-->>User: Response'''

        elif diagram_type == MermaidDiagramType.STATE:
            return f'''stateDiagram-v2
    [*] --> Initial
    Initial --> Processing
    Processing --> Complete
    Complete --> [*]'''

        elif diagram_type == MermaidDiagramType.ER:
            return f'''erDiagram
    ENTITY {{
        string id PK
        string name
        datetime created_at
    }}'''

        elif diagram_type == MermaidDiagramType.CLASS:
            return f'''classDiagram
    class {title_clean.replace(" ", "")} {{
        +String id
        +String name
        +execute()
    }}'''

        else:
            return f'''flowchart TD
    A["{title_clean}"]'''

    def _generate_template_from_requirements(
        self,
        diagram_type: str,
        requirements: List[Dict[str, Any]],
        context: str,
    ) -> str:
        """Generate template diagram from requirements."""
        if diagram_type == MermaidDiagramType.FLOWCHART:
            lines = ["flowchart TD"]
            for i, req in enumerate(requirements[:10]):  # Limit to 10 requirements
                node_id = chr(65 + i)
                title = req.get('title', f'Requirement {i+1}').replace('"', "'")
                lines.append(f'    {node_id}["{title}"]')

            for i in range(min(len(requirements) - 1, 9)):
                from_id = chr(65 + i)
                to_id = chr(65 + i + 1)
                lines.append(f'    {from_id} --> {to_id}')

            return "\n".join(lines)

        # Default fallback
        return f'''flowchart TD
    A["{context}"]
    A --> B["Requirements"]'''

    def _build_generation_prompt(self, diagram_type: str, context: str) -> str:
        """Build prompt for diagram generation."""
        type_instructions = {
            MermaidDiagramType.FLOWCHART: """Create a flowchart showing the process flow.
Use 'flowchart TD' for top-down or 'flowchart LR' for left-right.
Use descriptive node IDs and clear labels.
Include decision nodes where appropriate.""",

            MermaidDiagramType.SEQUENCE: """Create a sequence diagram showing interactions.
Define participants with clear names.
Use arrows to show message flow.
Include activation boxes for operations.""",

            MermaidDiagramType.CLASS: """Create a class diagram showing structure.
Define classes with attributes and methods.
Show relationships (inheritance, composition, association).""",

            MermaidDiagramType.ER: """Create an ER diagram showing data relationships.
Define entities with their attributes.
Show cardinality (one-to-many, many-to-many).""",

            MermaidDiagramType.STATE: """Create a state diagram showing state transitions.
Use 'stateDiagram-v2' syntax.
Define states and transitions with events.""",

            MermaidDiagramType.GANTT: """Create a Gantt chart showing timeline.
Define tasks with dates or durations.
Group related tasks in sections.""",
        }

        type_instr = type_instructions.get(
            diagram_type,
            f"Create a {diagram_type} diagram."
        )

        return f"""Generate a mermaid {diagram_type} diagram based on the following:

{context}

{type_instr}

Return ONLY the mermaid code, no markdown wrapper, no explanations.
Start directly with '{diagram_type}' or the appropriate syntax.
"""

    def _create_canvas_node_for_diagram(
        self,
        diagram: MermaidDiagram,
        idea_id: str,
    ) -> None:
        """Create a canvas node for the diagram."""
        try:
            self.canvas_repo.create_node(
                node_type="mermaid",
                title=diagram.title,
                content=diagram.content,
                linked_idea_id=idea_id,
                metadata={
                    "diagram_id": diagram.id,
                    "diagram_type": diagram.diagram_type,
                    "created_at": datetime.now().isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"Could not create canvas node for diagram: {e}")
