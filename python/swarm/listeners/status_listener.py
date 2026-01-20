"""
Status Listener - Listens for backend status updates

The StatusListener:
1. Subscribes to the events:status Redis stream
2. Receives status updates from backend swarm (progress, completion, errors)
3. Pushes COMPLETED tasks to NotificationQueue for deferred voice feedback
4. Updates JobManager with status changes

Deferred Feedback Pattern:
- Completed tasks go to NotificationQueue
- Rachel checks the queue on next user input
- User gets informed about completed tasks naturally
"""

import logging
import sys
from typing import Callable, Optional, Any

logger = logging.getLogger(__name__)


def _debug_print(msg: str):
    """Print debug message to stderr for visibility in Electron."""
    print(f"[Python DEBUG] [StatusListener] {msg}", file=sys.stderr)


class StatusListener:
    """
    Listens for backend status and routes to NotificationQueue.

    Uses deferred feedback pattern:
    - Completed tasks → NotificationQueue → Rachel speaks on next input
    - This is 100% compatible with ElevenLabs Conversational AI
    """

    # Status messages for optional TTS callback (mostly unused with deferred pattern)
    STATUS_MESSAGES = {
        "task.started": "Ich starte die Aufgabe...",
        "task.progress": "{stage}... {progress}% fertig",
        "task.complete": "Fertig! {result}",
        "task.complete_with_preview": "Fertig! Die Preview ist bereit.",
        "task.error": "Es gab ein Problem: {error}",
        "task.timeout": "Die Aufgabe hat zu lange gedauert. Bitte versuche es erneut.",
        "task.cancelled": "Aufgabe abgebrochen.",
    }

    def __init__(
        self,
        notification_queue: Any = None,
        tts_callback: Optional[Callable[[str], Any]] = None
    ):
        """
        Initialize StatusListener.

        Args:
            notification_queue: NotificationQueue for deferred feedback
            tts_callback: Optional TTS callback (for legacy/debugging)
        """
        self._notification_queue = notification_queue
        self.tts_callback = tts_callback
        self._bus = None
        self._job_manager = None
        self._running = False

    @property
    def bus(self):
        """Lazy-load EventBus."""
        if self._bus is None:
            from swarm.event_bus import get_event_bus
            self._bus = get_event_bus()
        return self._bus

    @property
    def job_manager(self):
        """Lazy-load JobManager."""
        if self._job_manager is None:
            from swarm.event_team.job_manager import get_job_manager
            self._job_manager = get_job_manager()
        return self._job_manager

    @property
    def notification_queue(self):
        """Lazy-load NotificationQueue."""
        if self._notification_queue is None:
            from swarm.orchestrator import get_notification_queue
            self._notification_queue = get_notification_queue()
        return self._notification_queue

    def set_notification_queue(self, queue):
        """Set the notification queue instance."""
        self._notification_queue = queue

    def set_tts_callback(self, callback: Callable[[str], Any]):
        """Set the TTS callback function (legacy/debugging)."""
        self.tts_callback = callback

    async def start(self):
        """Start listening for status updates."""
        if self._running:
            logger.warning("StatusListener already running")
            return

        self._running = True
        logger.info("StatusListener: Starting to listen on events:status")
        _debug_print("STARTED - listening on events:status (Redis async mode)")

        await self.bus.subscribe("events:status", self._handle_status)

    async def stop(self):
        """Stop listening."""
        self._running = False
        logger.info("StatusListener: Stopped")

    async def _handle_status(self, event):
        """
        Handle incoming status event.

        Completed/failed tasks are pushed to NotificationQueue for deferred feedback.
        This allows Rachel to inform the user on their next voice input.

        Args:
            event: SwarmEvent from the status stream
        """
        try:
            event_type = event.event_type
            payload = event.payload
            job_id = event.job_id

            # Log all received events to stderr for debugging
            _debug_print(f"RECEIVED: {event_type} (job={job_id[:8] if job_id else 'none'})")
            logger.debug(f"StatusListener: Received {event_type} for job {job_id}")

            # Update JobManager
            await self._update_job_manager(event_type, payload, job_id)

            # Push completed/failed tasks to NotificationQueue (deferred feedback)
            if event_type in ["task.complete", "task.completed"]:
                original_event = payload.get("original_event_type", "task")
                self._queue_notification(
                    job_id=job_id,
                    event_type=original_event,
                    result=payload.get("result", "Fertig"),
                    metadata=payload
                )
                _debug_print(f"QUEUED to NotificationQueue: {original_event} (job={job_id[:8] if job_id else 'none'})")
                logger.info(f"StatusListener: Queued notification for {job_id}")

            elif event_type == "task.error":
                original_event = payload.get("original_event_type", "task")
                self._queue_notification(
                    job_id=job_id,
                    event_type=original_event,
                    result=f"Fehler: {payload.get('error', 'Unbekannter Fehler')}",
                    metadata=payload
                )
                _debug_print(f"QUEUED ERROR to NotificationQueue: {original_event} (job={job_id[:8] if job_id else 'none'})")
                logger.info(f"StatusListener: Queued error notification for {job_id}")

            # Optional TTS callback for real-time feedback (legacy/debugging)
            if self.tts_callback:
                message = self._format_message(event_type, payload)
                if message:
                    logger.debug(f"StatusListener: TTS (legacy): {message}")
                    try:
                        result = self.tts_callback(message)
                        if hasattr(result, '__await__'):
                            await result
                    except Exception as e:
                        logger.error(f"TTS callback error: {e}")

        except Exception as e:
            logger.error(f"StatusListener error: {e}")

    def _queue_notification(
        self,
        job_id: str,
        event_type: str,
        result: Any,
        metadata: dict = None
    ):
        """
        Add notification to the queue for deferred feedback.

        Args:
            job_id: The job ID
            event_type: Original event type
            result: Task result
            metadata: Additional metadata
        """
        self.notification_queue.add_notification(
            job_id=job_id,
            event_type=event_type,
            result=result,
            metadata=metadata or {}
        )

    async def _update_job_manager(self, event_type: str, payload: dict, job_id: str):
        """Update JobManager with status from event."""
        from swarm.event_team.job_manager import JobStatus

        status_map = {
            "task.started": JobStatus.RUNNING,
            "task.progress": JobStatus.RUNNING,
            "task.complete": JobStatus.COMPLETED,
            "task.completed": JobStatus.COMPLETED,  # base_agent publishes "task.completed"
            "task.error": JobStatus.FAILED,
            "task.timeout": JobStatus.TIMEOUT,
            "task.cancelled": JobStatus.CANCELLED,
        }

        status = status_map.get(event_type)
        if status and job_id:
            await self.job_manager.update_status(
                job_id=job_id,
                status=status,
                result=payload.get("result"),
                error=payload.get("error"),
                progress=payload.get("progress", 0),
                stage=payload.get("stage", ""),
            )

    def _format_message(self, event_type: str, payload: dict) -> Optional[str]:
        """
        Format a voice message for the event.

        Args:
            event_type: Type of event
            payload: Event payload

        Returns:
            Formatted message or None if no message needed
        """
        # Handle task.complete with preview URL
        if event_type == "task.complete":
            vnc_url = payload.get("vnc_url")
            if vnc_url:
                return self.STATUS_MESSAGES["task.complete_with_preview"]

        template = self.STATUS_MESSAGES.get(event_type)
        if not template:
            return None

        # Format template with payload values
        try:
            return template.format(**payload)
        except KeyError:
            # Some values might be missing, return a generic message
            return template.replace("{", "").replace("}", "")

    async def speak(self, message: str):
        """
        Manually trigger TTS to speak a message.

        Args:
            message: Text to speak
        """
        if self.tts_callback:
            try:
                result = self.tts_callback(message)
                if hasattr(result, '__await__'):
                    await result
            except Exception as e:
                logger.error(f"TTS error: {e}")


# Singleton instance
_status_listener: Optional[StatusListener] = None


def get_status_listener(
    notification_queue: Any = None,
    tts_callback: Callable = None
) -> StatusListener:
    """
    Get or create StatusListener singleton.

    Args:
        notification_queue: NotificationQueue for deferred feedback
        tts_callback: Optional TTS callback (legacy/debugging)

    Returns:
        StatusListener instance
    """
    global _status_listener
    if _status_listener is None:
        _status_listener = StatusListener(
            notification_queue=notification_queue,
            tts_callback=tts_callback
        )
    else:
        if notification_queue:
            _status_listener.set_notification_queue(notification_queue)
        if tts_callback:
            _status_listener.set_tts_callback(tts_callback)
    return _status_listener


__all__ = [
    "StatusListener",
    "get_status_listener",
]
