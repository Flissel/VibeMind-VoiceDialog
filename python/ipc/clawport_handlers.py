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
            from data import ScheduledTaskRepository
            repo = ScheduledTaskRepository()
            status = message.get("status")
            limit = int(message.get("limit", 50))
            if status:
                tasks = repo.get_by_status(status)[:limit]
            else:
                tasks = repo.list_all(limit=limit)
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
            from data import ScheduledTaskRepository
            repo = ScheduledTaskRepository()
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

    # Known backend agents for status display
    _KNOWN_AGENTS = [
        "bubbles", "ideas", "coding", "desktop", "rowboat",
        "research", "minibook", "schedule", "n8n", "agentfarm",
        "flowzen", "video", "mirofish",
    ]

    async def handle_get_agent_status_sync(self):
        """Get status of all backend agents for ClawPort Agents tab."""
        try:
            from swarm.backend_agents import get_agent
            agents_data = []
            for name in self._KNOWN_AGENTS:
                try:
                    agent = get_agent(name)
                    status = "loaded" if agent else "idle"
                except Exception:
                    status = "unavailable"
                agents_data.append({
                    "name": name,
                    "status": status,
                    "last_event_type": None,
                    "last_event_at": None,
                    "last_result": None,
                    "error": None,
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
        """Handle text chat input from ClawPort Chat tab.

        If a VibeCoder session is active, routes follow-up messages to it.
        Otherwise routes through the normal intent orchestrator.
        """
        text = message.get("text", "").strip()
        if not text:
            self.send_message({
                "type": "chat_response",
                "success": False,
                "message": "Empty input",
            })
            return

        # Check if there's an active VibeCoder session for this chat
        vibecoder_sid = getattr(self, '_active_vibecoder_session', None)
        if vibecoder_sid:
            try:
                from spaces.n8n.tools.workflow_chat import get_workflow_chat_manager
                import asyncio
                mgr = get_workflow_chat_manager()
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, mgr.send_message, vibecoder_sid, text)
                self.send_message({
                    "type": "chat_response",
                    "success": True,
                    "message": result.get("response", result.get("message", "OK")),
                    "event_type": "n8n.vibecoder",
                    "vibecoder_session_id": vibecoder_sid,
                    "has_workflow": result.get("has_workflow", False),
                })
                # Clear session when workflow is deployed or user says stop
                if text.lower() in ("stop", "abbruch", "fertig", "exit"):
                    self._active_vibecoder_session = None
                return
            except Exception as e:
                debug_log(f"VibeCoder chat error: {e}")
                self._active_vibecoder_session = None
                # Fall through to normal orchestrator

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

            response_msg = result.response_hint if result else "OK"
            event_type = result.event_type if result else None

            # Check if the tool result triggered a VibeCoder session
            tool_result = result.tool_result if result and hasattr(result, 'tool_result') else None
            if isinstance(tool_result, dict) and tool_result.get("needs_checklist"):
                vibecoder_sid = tool_result.get("vibecoder_session_id")
                if vibecoder_sid:
                    self._active_vibecoder_session = vibecoder_sid
                    debug_log(f"VibeCoder session started from chat: {vibecoder_sid}")

            self.send_message({
                "type": "chat_response",
                "success": True,
                "message": response_msg,
                "event_type": event_type,
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

    # ── Models Config Tab ──

    # Group assignment for model roles
    _ROLE_GROUPS = {
        "classifier": "Core", "rag_classifier": "Core", "response": "Core",
        "orchestrator": "Core", "analysis": "Core",
        "space_agent": "Agents & Routing", "stream_listener": "Agents & Routing",
        "space_router": "Agents & Routing",
        "summary": "Content", "rewrite": "Content", "exploration": "Content",
        "n8n_generator": "Content",
        "conversion": "Personality & Context", "personality": "Personality & Context",
        "profiling": "Personality & Context", "context": "Personality & Context",
        "summarization_worker": "Workers", "rewrite_worker": "Workers",
        "voice": "Special", "vision": "Special", "local": "Special",
        "agentfarm": "Special", "flowzen_reasoning": "Special",
    }

    def _get_yaml_path(self):
        from pathlib import Path
        return Path(__file__).parent.parent / "config" / "llm_models.yml"

    async def handle_get_models_config(self):
        """Get all LLM model roles and providers for Models tab."""
        try:
            import os
            import yaml
            yaml_path = self._get_yaml_path()
            with open(yaml_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            # Build providers list
            providers = []
            for name, prov in config.get("providers", {}).items():
                api_key_env = prov.get("api_key_env")
                has_key = bool(os.environ.get(api_key_env)) if api_key_env else False
                providers.append({
                    "name": name,
                    "base_url": prov.get("base_url"),
                    "api_key_env": api_key_env,
                    "has_key": has_key,
                })

            # Build models list
            models = []
            for role, role_cfg in config.get("models", {}).items():
                models.append({
                    "role": role,
                    "provider": role_cfg.get("provider", "openai"),
                    "model": role_cfg.get("model", ""),
                    "max_tokens": role_cfg.get("max_tokens"),
                    "description": role_cfg.get("description", ""),
                    "group": self._ROLE_GROUPS.get(role, "Other"),
                    "locked": role == "voice",
                })

            self.send_message({
                "type": "models_config",
                "providers": providers,
                "models": models,
            })
        except Exception as e:
            debug_log(f"Error getting models config: {e}")
            self.send_message({
                "type": "models_config",
                "providers": [],
                "models": [],
                "error": str(e),
            })

    async def handle_update_model_role(self, message: dict):
        """Update a single model role in llm_models.yml."""
        role = message.get("role", "")
        try:
            if role == "voice":
                self.send_message({
                    "type": "model_update_result",
                    "success": False,
                    "role": role,
                    "error": "Voice role is locked (Realtime API)",
                })
                return

            import yaml
            yaml_path = self._get_yaml_path()
            with open(yaml_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            models = config.get("models", {})
            if role not in models:
                self.send_message({
                    "type": "model_update_result",
                    "success": False,
                    "role": role,
                    "error": f"Unknown role: {role}",
                })
                return

            # Update fields
            if "provider" in message:
                models[role]["provider"] = message["provider"]
            if "model" in message:
                models[role]["model"] = message["model"]
            if "max_tokens" in message:
                models[role]["max_tokens"] = message["max_tokens"]

            # Write back
            header = (
                "# config/llm_models.yml — SINGLE SOURCE OF TRUTH for all VibeMind LLM models\n"
                "# Edit THIS file to change any model globally across the entire system.\n"
                "#\n"
                "# Override any role via environment variable:\n"
                "#   LLM_MODEL_CLASSIFIER=gpt-4o\n"
                "#   LLM_MODEL_VOICE=gpt-4o-realtime-preview-2025-06\n"
                "#\n"
                "# Legacy env vars (CLASSIFIER_MODEL, OPENAI_MODEL, etc.) also work as fallbacks.\n\n"
            )
            yaml_content = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)
            with open(yaml_path, "w", encoding="utf-8") as f:
                f.write(header)
                f.write(yaml_content)

            # Reload in-process config
            import llm_config
            llm_config.reload_config()

            debug_log(f"Updated model role '{role}': provider={message.get('provider')}, model={message.get('model')}")
            self.send_message({
                "type": "model_update_result",
                "success": True,
                "role": role,
            })
        except Exception as e:
            debug_log(f"Error updating model role '{role}': {e}")
            self.send_message({
                "type": "model_update_result",
                "success": False,
                "role": role,
                "error": str(e),
            })

    async def handle_test_model_connection(self, message: dict):
        """Test a model connection by making a minimal API call."""
        role = message.get("role", "")
        try:
            if role == "voice":
                self.send_message({
                    "type": "model_test_result",
                    "success": False,
                    "role": role,
                    "error": "Realtime API cannot be tested via chat completions",
                })
                return

            import time
            import llm_config

            client = llm_config.get_client(role)
            model = llm_config.get_model(role)
            token_kw = llm_config.token_kwargs(model, 5)

            start = time.time()
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                **token_kw,
            )
            latency_ms = int((time.time() - start) * 1000)

            self.send_message({
                "type": "model_test_result",
                "success": True,
                "role": role,
                "latency_ms": latency_ms,
            })
        except Exception as e:
            debug_log(f"Model test failed for '{role}': {e}")
            self.send_message({
                "type": "model_test_result",
                "success": False,
                "role": role,
                "error": str(e),
            })
