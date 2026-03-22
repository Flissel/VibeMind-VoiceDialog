"""N8N Workflow Builder IPC handlers."""

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
        """Generate an n8n workflow from natural language description."""
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
            result = generate_workflow(description=description)
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
