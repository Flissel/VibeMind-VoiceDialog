"""
ClawPort Dashboard IPC Handlers

Extracted from electron_backend.py — handles all ClawPort dashboard
tab messages: Schedule, Agents, Chat, Memory, Plugins.
"""

from electron_backend import debug_log


class ClawPortHandlers:
    """Handles IPC messages for the ClawPort dashboard tabs."""

    def __init__(self, backend):
        self.backend = backend
        self.send_message = backend.send_message

    async def handle_get_scheduled_tasks(self, message: dict):
        """Get scheduled tasks for ClawPort Schedule tab."""
        try:
            from data import ScheduledTasksRepository
            repo = ScheduledTasksRepository()
            status = message.get("status")
            limit = int(message.get("limit", 50))
            tasks = repo.list(status=status, limit=limit)
            tasks_data = []
            for t in tasks:
                tasks_data.append({
                    "id": t.id,
                    "title": t.title,
                    "description": t.description or "",
                    "action_text": t.action_text or "",
                    "trigger_type": t.trigger_type,
                    "trigger_config": t.trigger_config or "",
                    "execution_mode": t.execution_mode or "",
                    "timezone": t.timezone or "Europe/Berlin",
                    "status": t.status,
                    "next_run_at": t.next_run_at.isoformat() if t.next_run_at else None,
                    "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
                    "run_count": t.run_count or 0,
                    "max_runs": t.max_runs,
                    "last_result": t.last_result,
                    "last_error": t.last_error,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                    "metadata": t.metadata if isinstance(t.metadata, dict) else {},
                })
            self.send_message({
                "type": "scheduled_tasks_list",
                "tasks": tasks_data,
                "total": len(tasks_data),
            })
        except Exception as e:
            debug_log(f"Error getting scheduled tasks: {e}")
            self.send_message({
                "type": "scheduled_tasks_list",
                "tasks": [],
                "total": 0,
                "error": str(e),
            })

    async def handle_update_task_status(self, message: dict):
        """Update a scheduled task's status (pause/resume/cancel)."""
        try:
            from data import ScheduledTasksRepository
            repo = ScheduledTasksRepository()
            task_id = message.get("task_id")
            new_status = message.get("new_status")
            if not task_id or not new_status:
                self.send_message({
                    "type": "task_status_updated",
                    "success": False,
                    "task_id": task_id,
                    "new_status": new_status,
                    "error": "task_id and new_status required",
                })
                return
            repo.update_status(task_id, new_status)
            self.send_message({
                "type": "task_status_updated",
                "success": True,
                "task_id": task_id,
                "new_status": new_status,
            })
        except Exception as e:
            debug_log(f"Error updating task status: {e}")
            self.send_message({
                "type": "task_status_updated",
                "success": False,
                "task_id": message.get("task_id"),
                "new_status": message.get("new_status"),
                "error": str(e),
            })

    async def handle_get_agent_status_sync(self):
        """Get status of all backend agents for ClawPort Agents tab."""
        try:
            from swarm.listeners.status_listener import get_status_listener
            listener = get_status_listener()
            agents_data = []
            for name, info in listener.get_all_status().items():
                agents_data.append({
                    "name": name,
                    "status": info.get("status", "idle"),
                    "last_event_type": info.get("last_event_type"),
                    "last_event_at": info.get("last_event_at"),
                    "last_result": info.get("last_result"),
                    "error": info.get("error"),
                })
            self.send_message({
                "type": "agent_status_list",
                "agents": agents_data,
            })
        except Exception as e:
            debug_log(f"Error getting agent status: {e}")
            self.send_message({
                "type": "agent_status_list",
                "agents": [],
                "error": str(e),
            })

    async def handle_chat_text_input(self, message: dict):
        """Handle text chat input from ClawPort Chat tab."""
        text = message.get("text", "").strip()
        if not text:
            self.send_message({
                "type": "chat_response",
                "success": False,
                "message": "Empty input",
            })
            return
        try:
            from swarm.orchestrator import get_orchestrator
            orchestrator = get_orchestrator()
            if not orchestrator:
                self.send_message({
                    "type": "chat_response",
                    "success": False,
                    "message": "Orchestrator not available",
                })
                return
            result = await orchestrator.process_intent(text)
            self.send_message({
                "type": "chat_response",
                "success": True,
                "message": result.response_hint if result else "OK",
                "event_type": result.event_type if result else None,
            })
        except Exception as e:
            debug_log(f"Chat input error: {e}")
            self.send_message({
                "type": "chat_response",
                "success": False,
                "message": str(e),
            })

    async def handle_get_conversation_history(self, message: dict):
        """Get conversation history for ClawPort Chat tab."""
        try:
            limit = int(message.get("limit", 50))
            from tools.conversation_tools import get_conversation_history
            history = get_conversation_history(limit=limit)
            self.send_message({
                "type": "conversation_history",
                "messages": history if isinstance(history, list) else [],
            })
        except Exception as e:
            debug_log(f"Error getting conversation history: {e}")
            self.send_message({
                "type": "conversation_history",
                "messages": [],
            })

    async def handle_get_memory_overview(self):
        """Get memory services overview for ClawPort Memory tab."""
        try:
            from tools.memory_tools import get_memory_overview
            overview = get_memory_overview()
            self.send_message({
                "type": "memory_overview",
                "data": overview if isinstance(overview, dict) else {
                    "task_memory": {"available": False},
                    "conversation_memory": {"available": False},
                    "user_profiles": {"available": False},
                },
            })
        except Exception as e:
            debug_log(f"Error getting memory overview: {e}")
            self.send_message({
                "type": "memory_overview",
                "data": {
                    "task_memory": {"available": False, "error": str(e)},
                    "conversation_memory": {"available": False},
                    "user_profiles": {"available": False},
                },
            })

    async def handle_search_memory(self, message: dict):
        """Search memory for ClawPort Memory tab."""
        try:
            query = message.get("query", "")
            category = message.get("category", "task_memory")
            limit = int(message.get("limit", 10))
            from tools.memory_tools import search_memory
            results = search_memory(query=query, category=category, limit=limit)
            self.send_message({
                "type": "memory_search_results",
                "category": category,
                "results": results if isinstance(results, list) else [],
            })
        except Exception as e:
            debug_log(f"Error searching memory: {e}")
            self.send_message({
                "type": "memory_search_results",
                "category": message.get("category", "task_memory"),
                "results": [],
            })

    async def handle_get_recent_memory(self, message: dict):
        """Get recent memory entries for ClawPort Memory tab."""
        try:
            category = message.get("category", "task_memory")
            limit = int(message.get("limit", 10))
            from tools.memory_tools import get_recent_memory
            results = get_recent_memory(category=category, limit=limit)
            self.send_message({
                "type": "recent_memory",
                "category": category,
                "results": results if isinstance(results, list) else [],
            })
        except Exception as e:
            debug_log(f"Error getting recent memory: {e}")
            self.send_message({
                "type": "recent_memory",
                "category": message.get("category", "task_memory"),
                "results": [],
            })

    # ── Plugins Tab ──

    async def handle_get_plugins(self):
        """Get all plugin info for ClawPort Plugins tab."""
        try:
            from plugins.plugin_manager import get_plugin_manager
            pm = get_plugin_manager()
            plugins = pm.get_all_plugin_info()
            enabled_count = sum(1 for p in plugins if p.get("enabled"))
            self.send_message({
                "type": "plugin_list",
                "plugins": plugins,
                "total_enabled": enabled_count,
                "total_available": len(plugins),
            })
        except Exception as e:
            debug_log(f"Error getting plugins: {e}")
            self.send_message({
                "type": "plugin_list",
                "plugins": [],
                "total_enabled": 0,
                "total_available": 0,
                "error": str(e),
            })

    async def handle_accept_plugin(self, message: dict):
        """Accept (enable) a plugin."""
        plugin_id = message.get("plugin_id", "")
        try:
            from plugins.plugin_manager import get_plugin_manager
            pm = get_plugin_manager()
            success = pm.accept_plugin(plugin_id)
            self.send_message({
                "type": "plugin_action_result",
                "action": "accept",
                "plugin_id": plugin_id,
                "success": success,
            })
        except Exception as e:
            debug_log(f"Error accepting plugin '{plugin_id}': {e}")
            self.send_message({
                "type": "plugin_action_result",
                "action": "accept",
                "plugin_id": plugin_id,
                "success": False,
                "error": str(e),
            })

    async def handle_reject_plugin(self, message: dict):
        """Reject (disable) a plugin."""
        plugin_id = message.get("plugin_id", "")
        try:
            from plugins.plugin_manager import get_plugin_manager
            pm = get_plugin_manager()
            success = pm.reject_plugin(plugin_id)
            self.send_message({
                "type": "plugin_action_result",
                "action": "reject",
                "plugin_id": plugin_id,
                "success": success,
            })
        except Exception as e:
            debug_log(f"Error rejecting plugin '{plugin_id}': {e}")
            self.send_message({
                "type": "plugin_action_result",
                "action": "reject",
                "plugin_id": plugin_id,
                "success": False,
                "error": str(e),
            })

    async def handle_toggle_plugin(self, message: dict):
        """Toggle a plugin on/off."""
        plugin_id = message.get("plugin_id", "")
        enabled = message.get("enabled", False)
        try:
            from plugins.plugin_manager import get_plugin_manager
            pm = get_plugin_manager()
            success = pm.toggle_plugin(plugin_id, enabled)
            self.send_message({
                "type": "plugin_action_result",
                "action": "toggle",
                "plugin_id": plugin_id,
                "enabled": enabled,
                "success": success,
            })
        except Exception as e:
            debug_log(f"Error toggling plugin '{plugin_id}': {e}")
            self.send_message({
                "type": "plugin_action_result",
                "action": "toggle",
                "plugin_id": plugin_id,
                "success": False,
                "error": str(e),
            })
