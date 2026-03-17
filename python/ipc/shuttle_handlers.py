"""
Shuttle IPC Handlers

Extracted from electron_backend.py — handles shuttle requirements,
stage data, and the wizard flow.
"""

import json
import logging

from electron_backend import debug_log

logger = logging.getLogger(__name__)


class ShuttleHandlers:
    """Handles shuttle and wizard IPC messages."""

    def __init__(self, backend):
        self.backend = backend
        self.send_message = backend.send_message

    @property
    def shuttles_repo(self):
        return self.backend.shuttles_repo

    @property
    def canvas_repo(self):
        return self.backend.canvas_repo

    async def handle_get_shuttle_requirements(self, shuttle_id: str):
        """Get requirements data for a shuttle's interior view."""
        if not shuttle_id:
            self.send_message({
                "type": "shuttle-requirements-loaded",
                "error": "shuttle_id required"
            })
            return

        try:
            if not self.shuttles_repo:
                self.send_message({
                    "type": "shuttle-requirements-loaded",
                    "shuttle_id": shuttle_id,
                    "requirements": [],
                    "error": "Database not available"
                })
                return

            shuttle = self.shuttles_repo.get_by_shuttle_id(shuttle_id)
            if not shuttle:
                self.send_message({
                    "type": "shuttle-requirements-loaded",
                    "shuttle_id": shuttle_id,
                    "requirements": [],
                    "error": f"Shuttle {shuttle_id} not found"
                })
                return

            requirements = []
            if shuttle.requirement_results:
                results = shuttle.requirement_results
                if isinstance(results, str):
                    results = json.loads(results)

                if isinstance(results, dict):
                    validation_data = results.get("validation", results)
                    if isinstance(validation_data, dict):
                        req_list = validation_data.get("results", [])
                    else:
                        req_list = validation_data if isinstance(validation_data, list) else []

                    for req in req_list:
                        requirements.append({
                            "id": req.get("id", req.get("requirement_id", "REQ-???")),
                            "text": req.get("text", req.get("original_text", "")),
                            "score": req.get("score", req.get("overall_score", 0)),
                            "status": "passed" if req.get("score", 0) >= 0.7 else "failed",
                            "criteria": req.get("criteria", {})
                        })
                elif isinstance(results, list):
                    for req in results:
                        requirements.append({
                            "id": req.get("id", "REQ-???"),
                            "text": req.get("text", ""),
                            "score": req.get("score", 0),
                            "status": "passed" if req.get("score", 0) >= 0.7 else "failed"
                        })

            if not requirements and shuttle.bubble_id:
                requirements = await self._extract_requirements_from_bubble(shuttle.bubble_id)

            self.send_message({
                "type": "shuttle-requirements-loaded",
                "shuttle_id": shuttle_id,
                "requirements": requirements,
                "total": shuttle.total_count or len(requirements),
                "passed": shuttle.passed_count or sum(1 for r in requirements if r.get("status") == "passed"),
                "failed": shuttle.failed_count or sum(1 for r in requirements if r.get("status") == "failed"),
                "score": shuttle.score or 0,
                "current_stage": shuttle.current_stage or "mining"
            })

        except Exception as e:
            debug_log(f"Error getting shuttle requirements: {e}")
            import traceback
            debug_log(traceback.format_exc())
            self.send_message({
                "type": "shuttle-requirements-loaded",
                "shuttle_id": shuttle_id,
                "requirements": [],
                "error": str(e)
            })

    async def _extract_requirements_from_bubble(self, bubble_id: str) -> list:
        """Extract requirements from a bubble's whitepaper/feature nodes."""
        requirements = []

        try:
            if not self.canvas_repo:
                return requirements

            nodes = self.canvas_repo.list_nodes(limit=1000)
            bubble_nodes = [n for n in nodes if n.linked_idea_id == bubble_id]

            req_id = 1
            for node in bubble_nodes:
                if node.node_type in ("feature", "note", "whitepaper"):
                    content = node.content or node.title or ""
                    if content:
                        requirements.append({
                            "id": f"REQ-{req_id:03d}",
                            "text": content[:500],
                            "score": 0,
                            "status": "pending",
                            "source": node.node_type
                        })
                        req_id += 1

        except Exception as e:
            debug_log(f"Error extracting requirements from bubble: {e}")

        return requirements

    async def handle_get_stage_shuttle_data(self, shuttle_id: str):
        """Get stage-specific shuttle data for the shuttle interior view."""
        if not shuttle_id:
            self.send_message({
                "type": "stage_shuttle_data",
                "error": "shuttle_id required"
            })
            return

        try:
            if not self.shuttles_repo:
                self.send_message({
                    "type": "stage_shuttle_data",
                    "shuttle_id": shuttle_id,
                    "error": "Database not available"
                })
                return

            shuttle = self.shuttles_repo.get_by_shuttle_id(shuttle_id)
            if not shuttle:
                self.send_message({
                    "type": "stage_shuttle_data",
                    "shuttle_id": shuttle_id,
                    "error": f"Shuttle {shuttle_id} not found"
                })
                return

            stage_data = shuttle.stage_data
            if isinstance(stage_data, str):
                stage_data = json.loads(stage_data)

            self.send_message({
                "type": "stage_shuttle_data",
                "shuttle_id": shuttle_id,
                "bubble_id": shuttle.bubble_id,
                "bubble_name": shuttle.bubble_name,
                "stage_type": shuttle.stage_type,
                "stage_data": stage_data or {},
                "score": shuttle.score or 0,
                "passed": shuttle.passed_count or 0,
                "failed": shuttle.failed_count or 0,
                "total": shuttle.total_count or 0,
                "status": shuttle.status
            })

            debug_log(f"Sent stage shuttle data for {shuttle_id} ({shuttle.stage_type})")

        except Exception as e:
            debug_log(f"Error getting stage shuttle data: {e}")
            import traceback
            debug_log(traceback.format_exc())
            self.send_message({
                "type": "stage_shuttle_data",
                "shuttle_id": shuttle_id,
                "error": str(e)
            })
