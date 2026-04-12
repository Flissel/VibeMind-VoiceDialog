"""N8N Workflow Builder IPC handlers.

Includes both traditional one-shot generation and the VibeCoder
iterative chat interface for workflow building.
"""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


def debug_log(msg):
    from electron_backend import debug_log as _debug_log
    _debug_log(msg)


class N8nHandlers:
    """Handles N8N workflow IPC messages."""

    def __init__(self, backend):
        self.backend = backend
        self.send_message = backend.send_message

    # ------------------------------------------------------------------
    # VibeCoder Chat (iterative workflow builder)
    # ------------------------------------------------------------------

    async def handle_n8n_chat_start(self, message: dict):
        """Start a new VibeCoder chat session (returns checklist)."""
        description = message.get("description", "").strip()
        try:
            from spaces.n8n.tools.workflow_chat import get_workflow_chat_manager
            mgr = get_workflow_chat_manager()
            result = mgr.create_session(description)
            self.send_message({"type": "n8n_chat_start_result", **result})
        except Exception as e:
            debug_log(f"n8n chat start error: {e}")
            self.send_message({
                "type": "n8n_chat_start_result",
                "success": False,
                "message": str(e),
            })

    async def handle_n8n_chat_checklist(self, message: dict):
        """Answer a checklist item or complete the checklist."""
        session_id = message.get("session_id", "")
        action = message.get("action", "answer")  # "answer" or "complete"
        item_id = message.get("item_id", "")
        value = message.get("value", "")

        if not session_id:
            self.send_message({
                "type": "n8n_chat_checklist_result",
                "success": False,
                "message": "session_id required.",
            })
            return
        try:
            from spaces.n8n.tools.workflow_chat import get_workflow_chat_manager
            mgr = get_workflow_chat_manager()

            if action == "complete":
                result = mgr.complete_checklist(session_id)
            else:
                result = mgr.answer_checklist(session_id, item_id, value)

            self.send_message({"type": "n8n_chat_checklist_result", **result})
        except Exception as e:
            debug_log(f"n8n chat checklist error: {e}")
            self.send_message({
                "type": "n8n_chat_checklist_result",
                "success": False,
                "message": str(e),
            })

    async def handle_n8n_chat_message(self, message: dict):
        """Send a message in an existing VibeCoder session."""
        session_id = message.get("session_id", "")
        text = message.get("text", "").strip()
        if not session_id or not text:
            self.send_message({
                "type": "n8n_chat_message_result",
                "success": False,
                "message": "session_id and text required.",
            })
            return
        try:
            from spaces.n8n.tools.workflow_chat import get_workflow_chat_manager
            mgr = get_workflow_chat_manager()

            # Run in thread to avoid blocking (LLM call)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, mgr.send_message, session_id, text)
            self.send_message({"type": "n8n_chat_message_result", **result})
        except Exception as e:
            debug_log(f"n8n chat message error: {e}")
            self.send_message({
                "type": "n8n_chat_message_result",
                "success": False,
                "message": str(e),
            })

    async def handle_n8n_chat_deploy(self, message: dict):
        """Deploy the current session's workflow to n8n."""
        session_id = message.get("session_id", "")
        if not session_id:
            self.send_message({
                "type": "n8n_chat_deploy_result",
                "success": False,
                "message": "session_id required.",
            })
            return
        try:
            from spaces.n8n.tools.workflow_chat import get_workflow_chat_manager
            mgr = get_workflow_chat_manager()
            result = mgr.deploy_workflow(session_id)
            self.send_message({"type": "n8n_chat_deploy_result", **result})
        except Exception as e:
            debug_log(f"n8n chat deploy error: {e}")
            self.send_message({
                "type": "n8n_chat_deploy_result",
                "success": False,
                "message": str(e),
            })

    async def handle_n8n_claude_build(self, message: dict):
        """Delegate workflow build to Claude CLI with n8n-MCP."""
        session_id = message.get("session_id", "")
        if not session_id:
            self.send_message({
                "type": "n8n_claude_build_result",
                "success": False,
                "message": "session_id required.",
            })
            return
        try:
            from spaces.n8n.tools.workflow_chat import get_workflow_chat_manager
            mgr = get_workflow_chat_manager()
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, mgr.claude_build, session_id)
            self.send_message({"type": "n8n_claude_build_result", **result})
        except Exception as e:
            debug_log(f"n8n claude build error: {e}")
            self.send_message({
                "type": "n8n_claude_build_result",
                "success": False,
                "message": str(e),
            })

    async def handle_n8n_chat_history(self, message: dict):
        """Get chat history for a session."""
        session_id = message.get("session_id", "")
        if not session_id:
            self.send_message({
                "type": "n8n_chat_history_result",
                "success": False,
                "message": "session_id required.",
            })
            return
        try:
            from spaces.n8n.tools.workflow_chat import get_workflow_chat_manager
            mgr = get_workflow_chat_manager()
            result = mgr.get_session(session_id)
            self.send_message({"type": "n8n_chat_history_result", **result})
        except Exception as e:
            debug_log(f"n8n chat history error: {e}")
            self.send_message({
                "type": "n8n_chat_history_result",
                "success": False,
                "message": str(e),
            })

    async def handle_n8n_chat_sessions(self):
        """List all VibeCoder sessions."""
        try:
            from spaces.n8n.tools.workflow_chat import get_workflow_chat_manager
            mgr = get_workflow_chat_manager()
            result = mgr.list_sessions()
            self.send_message({"type": "n8n_chat_sessions_result", **result})
        except Exception as e:
            debug_log(f"n8n chat sessions error: {e}")
            self.send_message({
                "type": "n8n_chat_sessions_result",
                "success": False,
                "message": str(e),
                "sessions": [],
            })

    async def handle_n8n_status(self):
        """Check n8n instance status."""
        try:
            from spaces.n8n.tools.n8n_workflow_tools import get_n8n_status
            result = get_n8n_status()
            self.send_message({
                "type": "n8n_status_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n status error: {e}")
            self.send_message({
                "type": "n8n_status_result",
                "success": False,
                "message": str(e),
                "online": False,
            })

    async def handle_n8n_list(self):
        """List all n8n workflows."""
        try:
            from spaces.n8n.tools.n8n_workflow_tools import list_workflows
            result = list_workflows()
            self.send_message({
                "type": "n8n_list_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n list error: {e}")
            self.send_message({
                "type": "n8n_list_result",
                "success": False,
                "message": str(e),
                "workflows": [],
            })

    async def handle_n8n_generate(self, message: dict):
        """Generate an n8n workflow from natural language description.

        Accepts optional checklist data from VibeCoder for enriched generation.
        """
        description = message.get("description", "").strip()
        if not description:
            self.send_message({
                "type": "n8n_generate_result",
                "success": False,
                "message": "No description provided.",
            })
            return
        try:
            from spaces.n8n.tools.n8n_workflow_tools import generate_workflow
            # Pass through checklist and session_id if present
            checklist = message.get("checklist")
            session_id = message.get("session_id")
            result = generate_workflow(
                description=description,
                checklist=checklist,
                session_id=session_id,
            )
            self.send_message({
                "type": "n8n_generate_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n generate error: {e}")
            self.send_message({
                "type": "n8n_generate_result",
                "success": False,
                "message": str(e),
            })

    async def handle_n8n_activate(self, message: dict):
        """Activate an n8n workflow."""
        workflow_id = message.get("workflow_id")
        if not workflow_id:
            self.send_message({
                "type": "n8n_activate_result",
                "success": False,
                "message": "workflow_id required",
            })
            return
        try:
            from spaces.n8n.tools.n8n_workflow_tools import activate_workflow
            result = activate_workflow(workflow_id=workflow_id)
            self.send_message({
                "type": "n8n_activate_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n activate error: {e}")
            self.send_message({
                "type": "n8n_activate_result",
                "success": False,
                "message": str(e),
            })

    async def handle_n8n_deactivate(self, message: dict):
        """Deactivate an n8n workflow."""
        workflow_id = message.get("workflow_id")
        if not workflow_id:
            self.send_message({
                "type": "n8n_deactivate_result",
                "success": False,
                "message": "workflow_id required",
            })
            return
        try:
            from spaces.n8n.tools.n8n_workflow_tools import deactivate_workflow
            result = deactivate_workflow(workflow_id=workflow_id)
            self.send_message({
                "type": "n8n_deactivate_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n deactivate error: {e}")
            self.send_message({
                "type": "n8n_deactivate_result",
                "success": False,
                "message": str(e),
            })

    async def handle_n8n_delete(self, message: dict):
        """Delete an n8n workflow."""
        workflow_id = message.get("workflow_id")
        if not workflow_id:
            self.send_message({
                "type": "n8n_delete_result",
                "success": False,
                "message": "workflow_id required",
            })
            return
        try:
            from spaces.n8n.tools.n8n_workflow_tools import delete_workflow
            result = delete_workflow(workflow_id=workflow_id)
            self.send_message({
                "type": "n8n_delete_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n delete error: {e}")
            self.send_message({
                "type": "n8n_delete_result",
                "success": False,
                "message": str(e),
            })
