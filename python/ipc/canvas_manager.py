"""
Canvas Manager — extracted from electron_backend.py

Manages all canvas/bubble operations: collision detection, position finding,
bubble CRUD, canvas node CRUD, shuttle queries, and bubble enter/exit.
"""

import logging
from typing import Dict, List, Optional

import electron_backend
from electron_backend import debug_log

logger = logging.getLogger(__name__)


class CanvasManager:
    """Manages canvas/bubble state and operations for the Electron backend."""

    def __init__(self, backend):
        self.backend = backend
        self.send_message = backend.send_message

    # ========================================================================
    # COLLISION / POSITION
    # ========================================================================

    def _check_collision(self, new_pos: Dict[str, float], min_distance: float = 1.2) -> bool:
        """Check if a position collides with existing bubbles."""
        for bubble in self.backend.bubbles.values():
            dx = new_pos["x"] - bubble.position["x"]
            dy = new_pos["y"] - bubble.position["y"]
            dz = new_pos["z"] - bubble.position["z"]
            distance = (dx*dx + dy*dy + dz*dz) ** 0.5

            # Check against bubble radius + minimum spacing
            bubble_radius = bubble.radius
            if distance < (bubble_radius + min_distance):
                return True
        return False

    def _find_free_position(self, angle: float, base_radius: float, max_attempts: int = 20) -> Dict[str, float]:
        """Find a collision-free position using spiral pattern with collision avoidance."""
        import math
        import random

        for attempt in range(max_attempts):
            # Increase radius slightly for each attempt
            radius_pos = base_radius + (attempt * 0.4)
            # Add some randomness to angle to avoid patterns
            adjusted_angle = angle + (attempt * 0.3) + (random.random() - 0.5) * 0.5

            x = math.cos(adjusted_angle) * radius_pos
            z = math.sin(adjusted_angle) * radius_pos
            y = (attempt % 4 - 1.5) * 0.6  # More varied heights

            new_pos = {"x": x, "y": y, "z": z}

            if not self._check_collision(new_pos):
                return new_pos

        # If no free position found, use a fallback with larger spacing
        fallback_angle = angle + random.random() * math.pi * 2
        fallback_radius = base_radius + max_attempts * 0.5
        return {
            "x": math.cos(fallback_angle) * fallback_radius,
            "y": (random.random() - 0.5) * 2.0,
            "z": math.sin(fallback_angle) * fallback_radius
        }

    # ========================================================================
    # BUBBLE LOADING / CRUD
    # ========================================================================

    def _load_bubbles_from_db(self):
        """Load bubbles from IdeasRepository into in-memory state."""
        from electron_backend import Bubble

        if not self.backend.ideas_repo:
            return

        try:
            import math
            ideas = self.backend.ideas_repo.list(limit=50, order_by="created_at DESC")

            # Color palette for bubbles
            colors = [0x66aaff, 0xff66aa, 0x66ffaa, 0xffcc66, 0xcc66ff,
                      0xff9966, 0x66ffcc, 0x9966ff, 0xff6666, 0x66ff66]

            for i, idea in enumerate(ideas):
                # Check for stored position in metadata (persists across restarts)
                stored_pos = None
                if idea.metadata and isinstance(idea.metadata, dict):
                    stored_pos = idea.metadata.get("position")

                if stored_pos and all(k in stored_pos for k in ["x", "y", "z"]):
                    # Use stored position but check if it still works
                    x, y, z = stored_pos["x"], stored_pos["y"], stored_pos["z"]
                    test_pos = {"x": x, "y": y, "z": z}

                    if not self._check_collision(test_pos):
                        debug_log(f"Using stored position for '{idea.title}': ({x}, {y}, {z})")
                    else:
                        # Stored position collides, find a new one
                        debug_log(f"Stored position collides for '{idea.title}', finding new position")
                        base_angle = i * 0.8
                        base_radius = 1.5 + (i * 0.3)
                        new_pos = self._find_free_position(base_angle, base_radius)
                        x, y, z = new_pos["x"], new_pos["y"], new_pos["z"]

                        # Update stored position
                        new_metadata = idea.metadata.copy() if idea.metadata else {}
                        new_metadata["position"] = {"x": x, "y": y, "z": z}
                        try:
                            idea.metadata = new_metadata
                            self.backend.ideas_repo.update(idea)
                            debug_log(f"Updated position for '{idea.title}': ({x}, {y}, {z})")
                        except Exception as e:
                            debug_log(f"Failed to update position for '{idea.title}': {e}")
                else:
                    # Generate new position with collision avoidance
                    base_angle = i * 0.8
                    base_radius = 1.5 + (i * 0.3)
                    new_pos = self._find_free_position(base_angle, base_radius)
                    x, y, z = new_pos["x"], new_pos["y"], new_pos["z"]

                    # Save generated position to metadata for persistence
                    new_metadata = idea.metadata.copy() if idea.metadata else {}
                    new_metadata["position"] = {"x": x, "y": y, "z": z}
                    try:
                        # Update the idea object's metadata and save
                        idea.metadata = new_metadata
                        self.backend.ideas_repo.update(idea)
                        debug_log(f"Saved position for '{idea.title}': ({x}, {y}, {z})")
                    except Exception as e:
                        debug_log(f"Failed to save position for '{idea.title}': {e}")

                bubble = Bubble(
                    id=self.backend.next_bubble_id,
                    title=idea.title,
                    position={"x": x, "y": y, "z": z},
                    color=colors[i % len(colors)],
                    radius=0.6 + (idea.score / 200),  # Bigger bubbles for higher scores
                    db_id=idea.id  # Store the database UUID
                )

                # Store mappings (both instance and module-level)
                self.backend.bubbles[bubble.id] = bubble
                self.backend.bubble_id_map[idea.id] = bubble.id
                electron_backend._bubble_id_map[idea.id] = bubble.id  # Sync module-level
                self.backend.next_bubble_id += 1

            logger.info(f"Loaded {len(ideas)} bubbles from database")

        except Exception as e:
            logger.warning(f"Failed to load bubbles from database: {e}")

    def _generate_vnc_url(self, project_id: str, vnc_port: int) -> str:
        """
        Generate VNC URL based on configuration.

        Modes:
        1. Proxy Mode (VNC_BASE_URL set): https://preview.domain.com/vnc/{project_id}
        2. Direct Mode (VNC_HOST set): http://{host}:{port}/vnc.html
        3. Default: http://localhost:{port}/vnc.html
        """
        if self.backend.vnc_use_proxy and self.backend.vnc_base_url:
            # Cloud Production: Use reverse proxy URL
            # URL format: {base_url}/{project_id}
            # Example: https://preview.vibemind.io/vnc/proj-abc123
            base = self.backend.vnc_base_url.rstrip('/')
            return f"{base}/{project_id}"
        else:
            # Direct connection mode
            return f"http://{self.backend.vnc_host}:{vnc_port}/vnc.html"

    def add_bubble(self, title: str, position: Dict = None,
                   color: int = 0x4488ff, radius: float = 0.7):
        """Add a new bubble."""
        from electron_backend import Bubble

        bubble = Bubble(
            id=self.backend.next_bubble_id,
            title=title,
            position=position or {"x": 0, "y": 0, "z": 0},
            color=color,
            radius=radius
        )
        self.backend.bubbles[bubble.id] = bubble
        self.backend.next_bubble_id += 1
        return bubble

    def remove_bubble(self, bubble_id: int) -> bool:
        """Remove a bubble by ID."""
        if bubble_id in self.backend.bubbles:
            del self.backend.bubbles[bubble_id]
            return True
        return False

    def get_all_bubbles(self) -> List[dict]:
        """Get all bubbles as dictionaries with numbered titles."""
        bubbles_list = []
        for i, bubble in enumerate(self.backend.bubbles.values(), 1):
            bubble_dict = bubble.to_dict()
            # Add numbered title for navigation (e.g., "1. Universe A")
            bubble_dict["numbered_title"] = f"{i}. {bubble.title}"
            bubbles_list.append(bubble_dict)
        return bubbles_list

    def get_all_bubbles_with_embeddings(self) -> List[dict]:
        """Get all bubbles with their embeddings for exploration.

        Returns list of dicts with id, title, description, embedding.
        """
        if not self.backend.ideas_repo:
            return []

        try:
            import json
            ideas = self.backend.ideas_repo.list(limit=100)
            bubbles = []

            for idea in ideas:
                # Only top-level ideas (bubbles) - no parent_id
                if idea.parent_id:
                    continue

                bubble = {
                    "id": idea.id,
                    "title": idea.title,
                    "description": idea.description or "",
                }

                # Parse embedding if available
                if idea.embedding_vector:
                    try:
                        bubble["embedding"] = json.loads(idea.embedding_vector)
                    except (json.JSONDecodeError, TypeError):
                        bubble["embedding"] = None
                else:
                    bubble["embedding"] = None

                bubbles.append(bubble)

            debug_log(f"get_all_bubbles_with_embeddings: Found {len(bubbles)} bubbles")
            return bubbles

        except Exception as e:
            debug_log(f"Failed to get bubbles with embeddings: {e}")
            logger.warning(f"Failed to get bubbles with embeddings: {e}")
            return []

    @property
    def current_bubble(self) -> Optional[dict]:
        """Get the current bubble as a dict (for exploration tools)."""
        if self.backend.current_bubble_id is None:
            return None

        bubble = self.backend.bubbles.get(self.backend.current_bubble_id)
        if not bubble:
            return None

        return {
            "id": bubble.db_id,
            "title": bubble.title,
            "local_id": self.backend.current_bubble_id,
        }

    def _get_bubble_position_by_db_id(self, bubble_db_id: str) -> Optional[dict]:
        """Get bubble position by database ID. Used by tools to store positions."""
        for bubble in self.backend.bubbles.values():
            if bubble.db_id == bubble_db_id:
                return bubble.position
        return None

    def get_active_shuttles(self) -> List[dict]:
        """Get active shuttles for visualization restoration."""
        if not self.backend.shuttles_repo:
            return []

        try:
            shuttles = self.backend.shuttles_repo.list_active(limit=50)
            result = []
            for s in shuttles:
                shuttle_dict = s.to_dict()
                # ALWAYS use bubble's CURRENT position (from self.bubbles)
                # This ensures shuttle and bubble positions are in sync
                bubble_pos = None
                for bubble in self.backend.bubbles.values():
                    if bubble.db_id == s.bubble_id:
                        bubble_pos = bubble.position
                        break
                shuttle_dict["start_position"] = bubble_pos
                result.append(shuttle_dict)
            return result
        except Exception as e:
            debug_log(f"Failed to get active shuttles: {e}")
            logger.warning(f"Failed to get active shuttles: {e}")
            return []

    # ========================================================================
    # BUBBLE NAVIGATION
    # ========================================================================

    def enter_bubble(self, bubble_id: int):
        """Enter a bubble to view its canvas."""
        from electron_backend import HAS_BUBBLE_TOOLS, bubble_tools_module

        if bubble_id not in self.backend.bubbles:
            return

        self.backend.current_bubble_id = bubble_id
        electron_backend._current_bubble_id = bubble_id  # Sync module-level state

        # Find the database UUID for this bubble
        db_bubble_id = None
        for db_id, local_id in self.backend.bubble_id_map.items():
            if local_id == bubble_id:
                db_bubble_id = db_id
                break

        logger.info(f"Entering bubble {bubble_id} (db_id: {db_bubble_id})")

        # CRITICAL: Sync _current_bubble_db_id in bubble_tools for list_ideas to work
        if HAS_BUBBLE_TOOLS and bubble_tools_module and db_bubble_id:
            bubble_tools_module._current_bubble_db_id = db_bubble_id
            logger.info(f"Synced _current_bubble_db_id to '{db_bubble_id}'")

        # Load nodes from database if available
        bubble_nodes = []
        if self.backend.canvas_repo and db_bubble_id:
            try:
                db_nodes = self.backend.canvas_repo.list_nodes(limit=1000)
                # Filter nodes by linked_idea_id (the DB UUID of the bubble)
                for db_node in db_nodes:
                    if db_node.linked_idea_id == db_bubble_id:
                        # Map DB UUID to local int ID
                        if db_node.id not in self.backend.db_id_map:
                            local_id = self.backend.next_node_id
                            self.backend.next_node_id += 1
                            self.backend.db_id_map[db_node.id] = local_id
                            self.backend.node_id_map[local_id] = db_node.id
                        else:
                            local_id = self.backend.db_id_map[db_node.id]

                        node = {
                            "id": local_id,
                            "type": db_node.node_type or "note",
                            "position": {"x": db_node.x or 100, "y": db_node.y or 100},
                            "content": {
                                "title": db_node.title or "",
                                "text": db_node.content or "",
                            },
                            "connections": []
                        }
                        bubble_nodes.append(node)

                logger.info(f"Loaded {len(bubble_nodes)} nodes for bubble {db_bubble_id}")
            except Exception as e:
                logger.warning(f"Failed to load nodes from database: {e}")

        # Update in-memory content
        self.backend.bubbles[bubble_id].content = bubble_nodes

        # Also load edges if available
        edges = []
        if self.backend.canvas_repo:
            try:
                db_edges = self.backend.canvas_repo.list_edges(limit=1000)
                for db_edge in db_edges:
                    from_local = self.backend.db_id_map.get(db_edge.from_node_id)
                    to_local = self.backend.db_id_map.get(db_edge.to_node_id)
                    if from_local and to_local:
                        edges.append({
                            "from_node_id": from_local,
                            "to_node_id": to_local
                        })
            except Exception as e:
                logger.warning(f"Failed to load edges from database: {e}")

        self.send_message({
            "type": "entered_bubble",
            "bubble_id": bubble_id,
            "bubble_title": self.backend.bubbles[bubble_id].title,
            "content": self.backend.bubbles[bubble_id].content,
            "edges": edges
        })

    def exit_bubble(self):
        """Exit current bubble back to multiverse view."""
        from electron_backend import HAS_BUBBLE_TOOLS, bubble_tools_module

        self.backend.current_bubble_id = None
        electron_backend._current_bubble_id = None  # Sync module-level state

        # CRITICAL: Clear _current_bubble_db_id in bubble_tools
        if HAS_BUBBLE_TOOLS and bubble_tools_module:
            bubble_tools_module._current_bubble_db_id = None
            logger.info("Cleared _current_bubble_db_id (exited bubble)")

        self.send_message({"type": "exited_bubble"})

    # ========================================================================
    # CANVAS OPERATIONS
    # ========================================================================

    def add_canvas_node(self, bubble_id: int, node_type: str,
                        position: Dict, content: Dict) -> Optional[int]:
        """Add a node to a bubble's canvas."""
        if bubble_id not in self.backend.bubbles:
            return None

        local_id = self.backend.next_node_id
        self.backend.next_node_id += 1

        node = {
            "id": local_id,
            "type": node_type,
            "position": position or {"x": 100, "y": 100},
            "content": content or {},
            "connections": []
        }
        self.backend.bubbles[bubble_id].content.append(node)

        # Save to database
        if self.backend.canvas_repo:
            try:
                # Store extra content fields in metadata
                content_extra = {k: v for k, v in (content or {}).items()
                               if k not in ("title", "text")}
                metadata = {
                    "bubble_id": bubble_id,
                    "content_extra": content_extra if content_extra else None
                }

                db_node = self.backend.canvas_repo.create_node(
                    node_type=node_type or "note",
                    title=(content or {}).get("title", ""),
                    content=(content or {}).get("text", ""),
                    x=(position or {}).get("x", 100),
                    y=(position or {}).get("y", 100),
                    metadata=metadata
                )

                # Store ID mapping
                self.backend.node_id_map[local_id] = db_node.id
                self.backend.db_id_map[db_node.id] = local_id
                logger.info(f"Saved node to DB: {db_node.id} -> local {local_id}")
            except Exception as e:
                logger.warning(f"Failed to save node to database: {e}")

        self.send_message({
            "type": "node_added",
            "bubble_id": bubble_id,
            "node": node
        })

        return local_id

    def update_canvas_node(self, bubble_id: int, node_id: int, updates: Dict):
        """Update a canvas node."""
        if bubble_id not in self.backend.bubbles:
            return

        for node in self.backend.bubbles[bubble_id].content:
            if node["id"] == node_id:
                node.update(updates)

                # Update in database
                if self.backend.canvas_repo and node_id in self.backend.node_id_map:
                    try:
                        db_id = self.backend.node_id_map[node_id]
                        db_node = self.backend.canvas_repo.get_node(db_id)
                        if db_node:
                            # Update position
                            if "position" in updates:
                                db_node.x = updates["position"].get("x", db_node.x)
                                db_node.y = updates["position"].get("y", db_node.y)
                            # Update content
                            if "content" in updates:
                                if "title" in updates["content"]:
                                    db_node.title = updates["content"]["title"]
                                if "text" in updates["content"]:
                                    db_node.content = updates["content"]["text"]
                                # Store extra content in metadata
                                content_extra = {k: v for k, v in updates["content"].items()
                                               if k not in ("title", "text")}
                                if content_extra:
                                    metadata = db_node.metadata or {}
                                    metadata["content_extra"] = content_extra
                                    db_node.metadata = metadata
                            self.backend.canvas_repo.update_node(db_node)
                            logger.info(f"Updated node in DB: {db_id}")
                    except Exception as e:
                        logger.warning(f"Failed to update node in database: {e}")

                self.send_message({
                    "type": "node_updated",
                    "bubble_id": bubble_id,
                    "node_id": node_id,
                    "updates": updates
                })
                break

    def delete_canvas_node(self, bubble_id: int, node_id: int):
        """Delete a canvas node."""
        if bubble_id not in self.backend.bubbles:
            return

        bubble = self.backend.bubbles[bubble_id]
        bubble.content = [n for n in bubble.content if n["id"] != node_id]

        # Delete from database
        if self.backend.canvas_repo and node_id in self.backend.node_id_map:
            try:
                db_id = self.backend.node_id_map[node_id]
                self.backend.canvas_repo.delete_node(db_id)
                # Clean up mappings
                del self.backend.node_id_map[node_id]
                del self.backend.db_id_map[db_id]
                logger.info(f"Deleted node from DB: {db_id}")
            except Exception as e:
                logger.warning(f"Failed to delete node from database: {e}")

        self.send_message({
            "type": "node_deleted",
            "bubble_id": bubble_id,
            "node_id": node_id
        })
