"""Canvas Repository — CRUD operations for Canvas nodes and edges."""

import logging
from typing import Optional, List, Dict, Any

from .database import Database, get_database
from .models import CanvasNode, CanvasEdge
from .repository_utils import generate_id

logger = logging.getLogger(__name__)


class CanvasRepository:
    """Repository for Canvas node and edge operations"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    # Node operations

    def create_node(
        self,
        node_type: str,
        title: str = "",
        content: str = "",
        x: float = 0.0,
        y: float = 0.0,
        linked_idea_id: Optional[str] = None,
        linked_project_id: Optional[str] = None,
        summary: Optional[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> CanvasNode:
        """Create a new canvas node"""
        logger.debug("create_node: node_type=%s title=%s", node_type, title)
        node = CanvasNode(
            id=generate_id(),
            node_type=node_type,
            title=title,
            content=content,
            x=x,
            y=y,
            linked_idea_id=linked_idea_id,
            linked_project_id=linked_project_id,
            summary=summary,
            metadata=metadata or {},
        )

        data = node.to_dict()
        self.db.execute(
            """
            INSERT INTO canvas_nodes (id, node_type, title, content, x, y, linked_idea_id, linked_project_id, summary, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["node_type"],
                data["title"],
                data["content"],
                data["x"],
                data["y"],
                data["linked_idea_id"],
                data["linked_project_id"],
                data["summary"],
                data["metadata"],
            ),
        )

        return node

    def get_node(self, node_id: str) -> Optional[CanvasNode]:
        """Get canvas node by ID"""
        row = self.db.fetch_one("SELECT * FROM canvas_nodes WHERE id = ?", (node_id,))
        return CanvasNode.from_dict(dict(row)) if row else None

    def list_nodes(
        self,
        node_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[CanvasNode]:
        """List canvas nodes, optionally filtered by type"""
        if node_type:
            rows = self.db.fetch_all(
                "SELECT * FROM canvas_nodes WHERE node_type = ? LIMIT ?",
                (node_type, limit)
            )
        else:
            rows = self.db.fetch_all("SELECT * FROM canvas_nodes LIMIT ?", (limit,))

        return [CanvasNode.from_dict(dict(row)) for row in rows]

    def update_node(self, node: CanvasNode) -> CanvasNode:
        """Update an existing canvas node"""
        data = node.to_dict()
        self.db.execute(
            """
            UPDATE canvas_nodes SET
                node_type = ?,
                title = ?,
                content = ?,
                x = ?,
                y = ?,
                linked_idea_id = ?,
                linked_project_id = ?,
                summary = ?,
                metadata = ?,
                format_schema = ?,
                content_json = ?,
                previous_content_json = ?,
                last_formatted = ?
            WHERE id = ?
            """,
            (
                data["node_type"],
                data["title"],
                data["content"],
                data["x"],
                data["y"],
                data["linked_idea_id"],
                data["linked_project_id"],
                data["summary"],
                data["metadata"],
                data.get("format_schema"),
                data.get("content_json"),
                data.get("previous_content_json"),
                data.get("last_formatted"),
                data["id"],
            ),
        )

        return node

    def delete_node(self, node_id: str) -> bool:
        """Delete a canvas node and its connected edges"""
        self.db.execute("DELETE FROM canvas_edges WHERE from_node_id = ? OR to_node_id = ?", (node_id, node_id))
        self.db.execute("DELETE FROM canvas_nodes WHERE id = ?", (node_id,))
        return True

    # Edge operations

    def create_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        edge_type: str = "default",
    ) -> CanvasEdge:
        """Create a new canvas edge"""
        edge = CanvasEdge(
            id=generate_id(),
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_type=edge_type,
        )

        self.db.execute(
            """
            INSERT INTO canvas_edges (id, from_node_id, to_node_id, edge_type)
            VALUES (?, ?, ?, ?)
            """,
            (edge.id, edge.from_node_id, edge.to_node_id, edge.edge_type),
        )

        return edge

    def get_edges_for_node(self, node_id: str) -> List[CanvasEdge]:
        """Get all edges connected to a node"""
        rows = self.db.fetch_all(
            "SELECT * FROM canvas_edges WHERE from_node_id = ? OR to_node_id = ?",
            (node_id, node_id)
        )
        return [CanvasEdge.from_dict(dict(row)) for row in rows]

    def list_edges(self, limit: int = 100) -> List[CanvasEdge]:
        """List all canvas edges"""
        rows = self.db.fetch_all("SELECT * FROM canvas_edges LIMIT ?", (limit,))
        return [CanvasEdge.from_dict(dict(row)) for row in rows]

    def delete_edge(self, edge_id: str) -> bool:
        """Delete a canvas edge"""
        self.db.execute("DELETE FROM canvas_edges WHERE id = ?", (edge_id,))
        return True

    # ==============================================================================
    # GRAPH TRAVERSAL FOR WHITE PAPER GENERATION
    # ==============================================================================

    def traverse_linked_nodes(
        self,
        start_node_id: str,
        max_depth: int = 10,
        idea_id: Optional[str] = None
    ) -> Dict[int, List[CanvasNode]]:
        """
        Traverse the graph from a starting node using BFS.
        Returns nodes grouped by their distance from the start node.

        Args:
            start_node_id: The ID of the node to start traversal from
            max_depth: Maximum traversal depth (default: 10)
            idea_id: Optional - limit traversal to nodes within this idea/bubble

        Returns:
            Dict mapping distance (0, 1, 2, ...) to list of nodes at that distance
            Example: {0: [start_node], 1: [direct_neighbors], 2: [neighbors_of_neighbors]}
        """
        logger.debug("traverse_linked_nodes: start_node_id=%s max_depth=%s", start_node_id, max_depth)
        from collections import deque

        # Get all nodes and edges
        if idea_id:
            all_nodes = [n for n in self.list_nodes(limit=1000) if n.linked_idea_id == idea_id]
        else:
            all_nodes = self.list_nodes(limit=1000)

        all_edges = self.list_edges(limit=5000)

        # Build node lookup
        node_by_id = {n.id: n for n in all_nodes}

        # Build adjacency list from edges
        adjacency: Dict[str, List[str]] = {n.id: [] for n in all_nodes}
        for edge in all_edges:
            if edge.from_node_id in adjacency and edge.to_node_id in adjacency:
                adjacency[edge.from_node_id].append(edge.to_node_id)
                adjacency[edge.to_node_id].append(edge.from_node_id)  # Bidirectional

        # BFS traversal
        result: Dict[int, List[CanvasNode]] = {}
        visited: set = set()
        queue = deque([(start_node_id, 0)])  # (node_id, distance)

        while queue:
            node_id, distance = queue.popleft()

            if node_id in visited or distance > max_depth:
                continue

            visited.add(node_id)

            # Add node to result at this distance
            if node_id in node_by_id:
                if distance not in result:
                    result[distance] = []
                result[distance].append(node_by_id[node_id])

                # Queue neighbors
                for neighbor_id in adjacency.get(node_id, []):
                    if neighbor_id not in visited:
                        queue.append((neighbor_id, distance + 1))

        return result

    def get_node_by_title(
        self,
        title: str,
        idea_id: Optional[str] = None
    ) -> Optional[CanvasNode]:
        """
        Find a node by its title (case-insensitive partial match).

        Args:
            title: Title to search for
            idea_id: Optional - limit search to nodes within this idea/bubble

        Returns:
            The matching node or None
        """
        logger.debug("get_node_by_title: title=%s idea_id=%s", title, idea_id)
        title_lower = title.lower()

        if idea_id:
            nodes = [n for n in self.list_nodes(limit=1000) if n.linked_idea_id == idea_id]
        else:
            nodes = self.list_nodes(limit=1000)

        # Exact match first
        for node in nodes:
            if (node.title or "").lower() == title_lower:
                return node

        # Partial match
        for node in nodes:
            if title_lower in (node.title or "").lower():
                return node

        return None
