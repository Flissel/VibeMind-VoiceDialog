"""
Project/Code Generation IPC Handlers

Extracted from electron_backend.py — handles project listing,
code generation, Docker VNC preview, and quality callbacks.
"""

import asyncio
import subprocess
import logging

from electron_backend import debug_log

logger = logging.getLogger(__name__)


class ProjectManager:
    """Handles project and code generation IPC messages."""

    def __init__(self, backend):
        self.backend = backend
        self.send_message = backend.send_message

    # -- Properties delegated to backend --

    @property
    def coding_engine_runner(self):
        return getattr(self.backend, 'coding_engine_runner', None)

    @property
    def coding_engine_path(self):
        return getattr(self.backend, 'coding_engine_path', None)

    @property
    def active_previews(self):
        return self.backend.active_previews

    @property
    def shuttles_repo(self):
        return self.backend.shuttles_repo

    # -- Handlers --

    async def handle_get_generated_projects(self, message: dict):
        """Get list of all projects - both code-generated and shuttle-created."""
        try:
            from data.repository import ProjectsRepository
            repo = ProjectsRepository()

            # Discover projects from filesystem
            if self.coding_engine_path:
                try:
                    from spaces.coding.engine.project_discovery import ProjectDiscoveryService
                    discovery = ProjectDiscoveryService(self.coding_engine_path)
                    discovered = discovery.discover_projects()
                    synced_count = 0
                    for d in discovered:
                        result = repo.sync_from_discovery(d)
                        if result:
                            synced_count += 1
                    if synced_count > 0:
                        debug_log(f"Synced {synced_count} discovered projects to DB")
                except Exception as e:
                    debug_log(f"Project discovery failed: {e}")

            status_filter = message.get("status_filter")
            limit = int(message.get("limit", 20))

            if status_filter:
                projects = repo.list_by_generation_status(status_filter, limit=limit)
            else:
                all_projects = repo.list(limit=limit * 2)
                projects = [p for p in all_projects if (
                    p.job_id or
                    p.from_idea_id or
                    p.status in ('shuttling', 'active', 'generating', 'completed')
                )][:limit]

            projects_data = []
            shuttles_repo = self.shuttles_repo

            for p in projects:
                linked_shuttle = None
                if p.id and shuttles_repo:
                    shuttle = shuttles_repo.get_by_project_id(p.id)
                    if shuttle:
                        linked_shuttle = shuttle.shuttle_id

                proj_meta = p.metadata if isinstance(p.metadata, dict) else {}

                projects_data.append({
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "status": p.status,
                    "from_idea_id": p.from_idea_id,
                    "linked_shuttle": linked_shuttle,
                    "job_id": p.job_id,
                    "generation_status": p.generation_status,
                    "convergence_progress": p.convergence_progress,
                    "tech_stack": p.tech_stack,
                    "vnc_port": p.vnc_port,
                    "preview_url": p.preview_url,
                    "project_path": p.project_path,
                    "error_message": p.error_message,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "total_issues": proj_meta.get("total_issues", 0),
                    "issue_counts": proj_meta.get("issue_counts", {}),
                    "quality_score": proj_meta.get("quality_score", 0),
                    "total_artifacts": proj_meta.get("total_artifacts", 0),
                    "total_cost_usd": proj_meta.get("total_cost_usd", 0),
                    "total_duration_ms": proj_meta.get("total_duration_ms", 0),
                    "stages_completed": proj_meta.get("stages_completed", 0),
                    "total_stages": proj_meta.get("total_stages", 0),
                    "task_count": proj_meta.get("task_count", 0),
                    "diagram_count": proj_meta.get("diagram_count", 0),
                    "user_story_count": proj_meta.get("user_story_count", 0),
                })

            self.send_message({
                "type": "generated_projects_list",
                "projects": projects_data
            })

        except Exception as e:
            debug_log(f"Error getting generated projects: {e}")
            self.send_message({
                "type": "generated_projects_list",
                "projects": [],
                "error": str(e)
            })

    async def handle_get_generation_status(self, message: dict):
        """Get status of a specific generation job."""
        job_id = message.get("job_id")
        project_id = message.get("project_id")

        if not job_id and not project_id:
            self.send_message({
                "type": "generation_status",
                "error": "job_id or project_id required"
            })
            return

        try:
            from data.repository import ProjectsRepository
            repo = ProjectsRepository()
            project = None

            if job_id:
                project = repo.get_by_job_id(job_id)
            elif project_id:
                project = repo.get(project_id)

            if not project:
                self.send_message({
                    "type": "generation_status",
                    "error": "Project not found"
                })
                return

            live_status = None
            if self.coding_engine_runner and project.job_id:
                live_status = self.coding_engine_runner.get_job_status(project.job_id)

            self.send_message({
                "type": "generation_status",
                "job_id": project.job_id,
                "project_id": project.id,
                "name": project.name,
                "status": live_status.get("status") if live_status else project.generation_status,
                "progress": live_status.get("progress") if live_status else project.convergence_progress,
                "phase": live_status.get("phase") if live_status else "",
                "phase_error": live_status.get("phase_error") if live_status else project.phase_error,
            })

        except Exception as e:
            debug_log(f"Error getting generation status: {e}")
            self.send_message({
                "type": "generation_status",
                "error": str(e)
            })

    async def handle_start_code_generation(self, message: dict):
        """Start a new code generation job."""
        if not self.coding_engine_runner:
            self.send_message({
                "type": "generation_started",
                "success": False,
                "error": "Coding engine not available"
            })
            return

        try:
            title = message.get("title", "").strip()
            description = message.get("description", "")
            tech_stack = message.get("tech_stack", "react")
            requirements = message.get("requirements", [])

            if not title:
                self.send_message({
                    "type": "generation_started",
                    "success": False,
                    "error": "Project title required"
                })
                return

            result = await self.coding_engine_runner.run_generate_code(
                title, description, tech_stack, requirements
            )

            self.send_message({
                "type": "generation_started",
                "success": True,
                "message": result,
            })

        except Exception as e:
            debug_log(f"Error starting code generation: {e}")
            self.send_message({
                "type": "generation_started",
                "success": False,
                "error": str(e)
            })

    async def handle_cancel_code_generation(self, message: dict):
        """Cancel a running code generation job."""
        job_id = message.get("job_id")

        if not job_id:
            self.send_message({
                "type": "generation_cancelled",
                "success": False,
                "error": "job_id required"
            })
            return

        if not self.coding_engine_runner:
            self.send_message({
                "type": "generation_cancelled",
                "success": False,
                "error": "Coding engine not available"
            })
            return

        try:
            success = self.coding_engine_runner.cancel_job(job_id)
            self.send_message({
                "type": "generation_cancelled",
                "success": success,
                "job_id": job_id,
            })

        except Exception as e:
            debug_log(f"Error cancelling generation: {e}")
            self.send_message({
                "type": "generation_cancelled",
                "success": False,
                "error": str(e)
            })

    async def handle_enter_projects_space(self, message: dict):
        """Enter the Projects Space view."""
        debug_log("Entering Projects Space")
        await self.handle_get_generated_projects({"limit": 50})
        self.send_message({"type": "entered_projects_space"})

    async def handle_start_project_preview(self, project_id: str, project_path: str,
                                           enable_vnc: bool = True, vnc_resolution: str = "1280x720"):
        """Start a live preview for a project."""
        try:
            debug_log(f"Starting preview for {project_id}")

            if project_id in self.active_previews:
                existing = self.active_previews[project_id]
                if existing.get("status") == "running":
                    self.send_message({
                        "type": "project_preview_ready",
                        "projectId": project_id,
                        "vncUrl": existing.get("vnc_url"),
                        "status": "already_running"
                    })
                    return

            self.active_previews[project_id] = {
                "status": "starting",
                "project_path": project_path
            }

            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                vnc_port = s.getsockname()[1]

            docker_cmd = [
                "docker", "run", "-d",
                "--name", f"preview-{project_id[:8]}",
                "-p", f"{vnc_port}:6080",
                "-v", f"{project_path}:/app",
                "-e", f"DISPLAY_RESOLUTION={vnc_resolution}",
                "sandbox-vnc:latest",
            ]

            process = subprocess.Popen(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(timeout=30)

            if process.returncode == 0:
                container_id = stdout.decode().strip()
                vnc_url = self.backend._generate_vnc_url(project_id, vnc_port)

                self.active_previews[project_id] = {
                    "status": "running",
                    "vnc_url": vnc_url,
                    "vnc_port": vnc_port,
                    "container_id": container_id,
                    "project_path": project_path
                }

                await asyncio.sleep(3)

                self.send_message({
                    "type": "project_preview_ready",
                    "projectId": project_id,
                    "vncUrl": vnc_url
                })
            else:
                error = stderr.decode() or "Docker command failed"
                self.active_previews[project_id] = {"status": "error", "error": error}
                self.send_message({
                    "type": "project_preview_error",
                    "projectId": project_id,
                    "error": error
                })

        except Exception as e:
            debug_log(f"Error starting preview: {e}")
            self.active_previews[project_id] = {"status": "error", "error": str(e)}
            self.send_message({
                "type": "project_preview_error",
                "projectId": project_id,
                "error": str(e)
            })

    async def handle_stop_project_preview(self, project_id: str):
        """Stop a running project preview."""
        try:
            if project_id not in self.active_previews:
                return

            preview = self.active_previews[project_id]
            container_id = preview.get("container_id")

            if container_id:
                subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=10)
                subprocess.run(["docker", "rm", container_id], capture_output=True, timeout=10)

            preview_name = f"preview-{project_id[:8]}"
            subprocess.run(["docker", "stop", preview_name], capture_output=True, timeout=10)
            subprocess.run(["docker", "rm", preview_name], capture_output=True, timeout=10)

            del self.active_previews[project_id]

            self.send_message({
                "type": "project_preview_stopped",
                "projectId": project_id
            })

        except Exception as e:
            debug_log(f"Error stopping preview: {e}")
            self.send_message({
                "type": "project_preview_error",
                "projectId": project_id,
                "error": f"Failed to stop: {str(e)}"
            })

    # -- Callbacks (registered by electron_backend __init__) --

    def on_generation_status_update(self, job_id: str, status: str, progress: float,
                                    phase: str = "", error: str = None):
        """Callback from CodingEngineRunner when generation status changes."""
        debug_log(f"Generation status update: job={job_id}, status={status}, progress={progress}")
        self.send_message({
            "type": "generation_status_update",
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "phase": phase,
            "error": error
        })
        if status in ("completed", "failed"):
            self.send_message({
                "type": "generation_finished",
                "job_id": job_id,
                "success": status == "completed",
                "error": error
            })

    def on_issue_detected(self, job_id: str, issue: dict):
        """Callback when a quality issue is detected during generation."""
        debug_log(f"Issue detected in job {job_id}: {issue.get('id', '?')} [{issue.get('severity', '?')}]")
        self.send_message({
            "type": "project_issue_detected",
            "job_id": job_id,
            "issue": {
                "id": issue.get("id", ""),
                "category": issue.get("category", ""),
                "severity": issue.get("severity", "medium"),
                "title": issue.get("title", ""),
                "description": issue.get("description", ""),
                "affected_artifacts": issue.get("affected_artifacts", []),
                "suggestion": issue.get("suggestion", ""),
                "auto_fixable": issue.get("auto_fixable", False),
            }
        })

    def on_quality_summary_update(self, job_id: str, summary: dict):
        """Callback when quality summary is updated during generation."""
        debug_log(f"Quality summary update for job {job_id}: {summary.get('total_issues', 0)} issues")
        self.send_message({
            "type": "project_quality_update",
            "job_id": job_id,
            "summary": {
                "total_issues": summary.get("total_issues", 0),
                "by_severity": summary.get("by_severity", {}),
                "by_category": summary.get("by_category", {}),
                "auto_fixed": summary.get("auto_fixed", 0),
            }
        })
