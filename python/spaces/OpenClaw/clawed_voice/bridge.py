"""
Clawed Voice Bridge

Main entry point for VibeMind to OpenClaw integration.
Handles task execution, notification storage, and status checks.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional

from .config import get_config
from .client import OpenClawClient, get_client
from .gateway_manager import get_gateway_manager, GatewayState
from .notifications import get_notification_queue, Notification

logger = logging.getLogger(__name__)


class ClawedVoiceBridge:
    """
    Bridge between VibeMind and OpenClaw.

    Provides high-level API for executing tasks via OpenClaw
    and managing results in notification queue.
    """

    def __init__(self):
        self._client: Optional[OpenClawClient] = None
        self._queue = get_notification_queue()
        self._gateway = get_gateway_manager()

    @property
    def client(self) -> OpenClawClient:
        """Get or create OpenClaw client."""
        if self._client is None:
            self._client = get_client()
        return self._client

    async def ensure_connected(self) -> bool:
        """Ensure connected to OpenClaw Gateway."""
        if self.client.connected:
            return True
        return await self.client.connect()

    async def get_status(self) -> Dict[str, Any]:
        """
        Get bridge and gateway status.

        Returns:
            Status dict with gateway and connection info
        """
        gateway_status = self._gateway.get_status()

        connected = self.client.connected
        if connected:
            try:
                health = await self.client.health()
                gateway_health = health
            except Exception as e:
                gateway_health = {"error": str(e)}
        else:
            gateway_health = None

        unread = 0
        try:
            unread = await self._queue.count_unread()
        except Exception:
            pass

        return {
            "connected": connected,
            "gateway": gateway_status,
            "health": gateway_health,
            "notifications_pending": unread,
        }

    async def execute_task(
        self,
        task_type: str,
        params: Dict[str, Any],
        store_result: bool = True,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute task via OpenClaw.

        Args:
            task_type: Type of task (messaging.whatsapp, web.search, etc.)
            params: Task parameters
            store_result: Whether to store result in notification queue
            job_id: Optional job ID for tracking

        Returns:
            Task result dict with success, result/error, and job_id
        """
        job_id = job_id or str(uuid.uuid4())

        logger.info(f"Executing task {task_type} (job: {job_id})")

        # Ensure connected
        if not await self.ensure_connected():
            result = {
                "success": False,
                "error": "Failed to connect to OpenClaw Gateway",
                "job_id": job_id,
            }
            if store_result:
                await self._queue.add(task_type, result, status="failed", job_id=job_id)
            return result

        try:
            # Route to appropriate handler
            if task_type.startswith("messaging."):
                result = await self._handle_messaging(task_type, params)
            elif task_type == "web.search":
                result = await self._handle_web_search(params)
            elif task_type == "web.fetch":
                result = await self._handle_web_fetch(params)
            elif task_type.startswith("browser."):
                result = await self._handle_browser(task_type, params)
            elif task_type == "agent.run":
                result = await self._handle_agent(params)
            else:
                result = {"success": False, "error": f"Unknown task type: {task_type}"}

            result["job_id"] = job_id

            # Store result
            if store_result:
                status = "completed" if result.get("success") else "failed"
                await self._queue.add(task_type, result, status=status, job_id=job_id)

            return result

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            result = {
                "success": False,
                "error": str(e),
                "job_id": job_id,
            }
            if store_result:
                await self._queue.add(task_type, result, status="failed", job_id=job_id)
            return result

    async def _handle_messaging(
        self,
        task_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle messaging tasks via agent."""
        from .contacts import resolve_contact

        platform = task_type.split(".")[-1] if "." in task_type else params.get("platform", "whatsapp")
        recipient = params.get("recipient", params.get("to", ""))
        content = params.get("content", params.get("message", params.get("text", "")))

        if not recipient:
            return {"success": False, "error": "No recipient specified"}
        if not content:
            return {"success": False, "error": "No message content"}

        # Resolve contact name to phone number
        recipient_resolved = resolve_contact(recipient)

        # Build natural language task
        task = f"Send {platform.capitalize()} message to {recipient_resolved}: {content}"

        try:
            result = await self.client.run_agent(task=task)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_web_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle web search tasks via agent."""
        query = params.get("query", params.get("q", ""))
        if not query:
            return {"success": False, "error": "No search query"}

        # Build natural language task
        task = f"Search the web for: {query}"

        try:
            result = await self.client.run_agent(task=task)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_web_fetch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle web fetch tasks via agent."""
        url = params.get("url", "")
        if not url:
            return {"success": False, "error": "No URL specified"}

        # Build natural language task
        task = f"Fetch and summarize the content from: {url}"

        try:
            result = await self.client.run_agent(task=task)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_browser(
        self,
        task_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle browser tasks via agent."""
        action = task_type.split(".")[-1] if "." in task_type else params.get("action", "navigate")

        try:
            # Build natural language task based on action
            if action == "navigate":
                url = params.get("url", "")
                if not url:
                    return {"success": False, "error": "No URL specified"}
                task = f"Navigate to {url}"
            elif action == "screenshot":
                task = "Take a screenshot of the current page"
            else:
                return {"success": False, "error": f"Unknown browser action: {action}"}

            result = await self.client.run_agent(task=task)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_agent(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle agent run tasks."""
        task = params.get("task", "")
        agent_id = params.get("agent_id", "default")
        context = params.get("context", {})

        if not task:
            return {"success": False, "error": "No task specified"}

        try:
            result = await self.client.run_agent(
                task=task,
                agent_id=agent_id,
            )
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_notifications(self, limit: int = 5) -> Dict[str, Any]:
        """
        Get pending notifications.

        Returns:
            Dict with count, notifications list, and summaries
        """
        notifications = await self._queue.get_pending(limit=limit)

        results = []
        for notif in notifications:
            results.append({
                "job_id": notif.job_id,
                "task_type": notif.task_type,
                "status": notif.status,
                "summary": notif.summary(),
                "timestamp": notif.timestamp,
            })

        return {
            "count": len(results),
            "notifications": results,
        }

    async def mark_notification_read(self, job_id: str) -> bool:
        """Mark notification as read."""
        return await self._queue.mark_read(job_id)

    async def shutdown(self):
        """Graceful shutdown."""
        if self._client:
            await self._client.disconnect()

        # Stop gateway if we started it
        await self._gateway.stop()


# Singleton
_bridge: Optional[ClawedVoiceBridge] = None


def get_bridge() -> ClawedVoiceBridge:
    """Get or create ClawedVoiceBridge singleton."""
    global _bridge
    if _bridge is None:
        _bridge = ClawedVoiceBridge()
    return _bridge


# === Convenience functions for sync/async usage ===

def _run_async(coro):
    """Run async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create new event loop in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=60)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def execute_task_sync(
    task_type: str,
    params: Dict[str, Any],
    store_result: bool = True,
) -> Dict[str, Any]:
    """Synchronous wrapper for execute_task."""
    return _run_async(get_bridge().execute_task(task_type, params, store_result))


def get_status_sync() -> Dict[str, Any]:
    """Synchronous wrapper for get_status."""
    return _run_async(get_bridge().get_status())


def get_notifications_sync(limit: int = 5) -> Dict[str, Any]:
    """Synchronous wrapper for get_notifications."""
    return _run_async(get_bridge().get_notifications(limit))


# === CLI interface ===

async def _test_bridge():
    """Test bridge functionality."""
    print("Testing Clawed Voice Bridge...")

    bridge = get_bridge()

    # Get status
    print("\n1. Checking status...")
    status = await bridge.get_status()
    print(f"   Gateway state: {status['gateway']['state']}")
    print(f"   Connected: {status['connected']}")

    # Test connection
    print("\n2. Connecting to Gateway...")
    connected = await bridge.ensure_connected()
    print(f"   Connected: {connected}")

    if connected:
        # Get health
        print("\n3. Checking health...")
        status = await bridge.get_status()
        print(f"   Health: {status.get('health', 'N/A')}")

        # Test web search
        print("\n4. Testing web search...")
        result = await bridge.execute_task(
            "web.search",
            {"query": "OpenClaw AI documentation"},
            store_result=True,
        )
        print(f"   Success: {result.get('success')}")
        if result.get("error"):
            print(f"   Error: {result['error']}")

        # Check notifications
        print("\n5. Checking notifications...")
        notifications = await bridge.get_notifications()
        print(f"   Pending: {notifications['count']}")

    # Shutdown
    print("\n6. Shutting down...")
    await bridge.shutdown()
    print("   Done!")


def main():
    """CLI entry point."""
    import sys

    if "--test" in sys.argv:
        asyncio.run(_test_bridge())
    else:
        print("Clawed Voice Bridge")
        print("Usage: python -m clawed_voice.bridge --test")


if __name__ == "__main__":
    main()


__all__ = [
    "ClawedVoiceBridge",
    "get_bridge",
    "execute_task_sync",
    "get_status_sync",
    "get_notifications_sync",
]
