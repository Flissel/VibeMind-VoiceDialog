"""Exploration (AI-Scientist Tree Search) IPC handlers."""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


def debug_log(msg):
    from electron_backend import debug_log as _debug_log
    _debug_log(msg)


class ExplorationHandlers:
    """Handles Exploration IPC messages."""

    def __init__(self, backend):
        self.backend = backend
        self.send_message = backend.send_message

    async def handle_exploration_start(self, bubble_id, depth, mode, context):
        """Handle exploration start from Electron."""
        try:
            from spaces.ideas.tools.exploration_tools import start_exploration
            result = await start_exploration(
                bubble_id=bubble_id,
                depth=depth,
                mode=mode,
                context=context,
            )
            self.send_message({
                "type": "exploration_started",
                **result
            })
        except Exception as e:
            logger.error(f"Exploration start error: {e}")
            self.send_message({
                "type": "exploration_error",
                "error": str(e)
            })

    async def handle_exploration_stop(self):
        """Handle exploration stop."""
        try:
            from spaces.ideas.tools.exploration_tools import stop_exploration
            result = await stop_exploration()
            self.send_message({
                "type": "exploration_stopped",
                **result
            })
        except Exception as e:
            logger.error(f"Exploration stop error: {e}")
            self.send_message({
                "type": "exploration_error",
                "error": str(e)
            })

    async def handle_exploration_respond(self, question_id, response_type, selected_option, custom_text):
        """Handle response to exploration question."""
        try:
            from spaces.ideas.tools.exploration_tools import respond_to_exploration_question
            result = await respond_to_exploration_question(
                question_id=question_id,
                response_type=response_type,
                selected_option=selected_option,
                custom_text=custom_text,
            )
            debug_log(f"Exploration response processed: {result}")
            # The exploration will continue automatically after response
        except Exception as e:
            logger.error(f"Exploration respond error: {e}")
            self.send_message({
                "type": "exploration_error",
                "error": str(e)
            })

    async def handle_exploration_direction(self, direction, bubble_id):
        """Handle exploration direction setting."""
        try:
            from spaces.ideas.tools.exploration_tools import set_exploration_direction
            result = await set_exploration_direction(
                direction=direction,
                bubble_id=bubble_id,
            )
            self.send_message({
                "type": "exploration_direction_set",
                **result
            })
        except Exception as e:
            logger.error(f"Exploration direction error: {e}")
            self.send_message({
                "type": "exploration_error",
                "error": str(e)
            })

    async def handle_exploration_status(self):
        """Get current exploration status."""
        try:
            from spaces.ideas.tools.exploration_tools import get_exploration_status
            result = await get_exploration_status()
            self.send_message({
                "type": "exploration_status",
                **result
            })
        except Exception as e:
            logger.error(f"Exploration status error: {e}")
            self.send_message({
                "type": "exploration_error",
                "error": str(e)
            })
