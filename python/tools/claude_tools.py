"""
Claude Orchestrator Tools for VibeMind Voice Dialog

Integration with Claude Orchestrator via Redis for spawning and managing
Claude Code instances from voice commands.

Tools:
- spawn_claude - Create new Claude instance with a task
- send_to_claude - Send follow-up message to running instance
- list_claude_instances - Get list of active instances
- close_claude - Terminate a Claude instance

Prerequisites:
- Redis server running on localhost:6379
- Claude Orchestrator running and connected to Redis
"""

import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4

logger = logging.getLogger(__name__)

# Import Redis
try:
    import redis
    HAS_REDIS = True
except ImportError:
    logger.warning("redis not available. Install with: pip install redis")
    HAS_REDIS = False


class ClaudeOrchestratorClient:
    """
    Client for communicating with Claude Orchestrator via Redis.

    The Claude Orchestrator is an Electron app that manages multiple Claude Code
    instances. It uses Redis for task queue and event streaming.

    Redis Channels:
    - orchestrator:tasks - Task queue (LPUSH/RPUSH for priority)
    - orchestrator:events - Event stream (XADD/XREAD)
    - orchestrator:instances - Hash of active instances
    """

    def __init__(self, host: str = "localhost", port: int = 6379):
        self.host = host
        self.port = port
        self.redis: Optional[redis.Redis] = None
        self.is_connected = False

        # Redis keys
        self.task_queue = "orchestrator:tasks"
        self.event_stream = "orchestrator:events"
        self.instances_key = "orchestrator:instances"
        self.response_prefix = "orchestrator:response:"

    def connect(self) -> bool:
        """Connect to Redis."""
        if not HAS_REDIS:
            logger.error("redis not installed")
            return False

        try:
            self.redis = redis.Redis(
                host=self.host,
                port=self.port,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis.ping()
            self.is_connected = True
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            self.redis.close()
            self.redis = None
        self.is_connected = False

    def ensure_connected(self) -> bool:
        """Ensure Redis connection is active."""
        if self.is_connected and self.redis:
            try:
                self.redis.ping()
                return True
            except Exception:
                self.is_connected = False

        return self.connect()

    def spawn_instance(
        self,
        task: str,
        working_dir: str = "C:\\Users\\User\\Desktop\\ClaudeWorkspace",
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Spawn a new Claude instance with a task.

        Args:
            task: The task/prompt for Claude to work on
            working_dir: Directory for Claude to work in
            priority: 'high' or 'normal' - high goes to front of queue

        Returns:
            Dict with task_id and status
        """
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to Redis"}

        try:
            task_id = f"vibemind-{uuid4().hex[:8]}"

            task_obj = {
                "id": task_id,
                "task": task,
                "workingDir": working_dir,
                "priority": priority,
                "submittedAt": datetime.now().isoformat(),
                "submittedBy": "vibemind-voice",
                "status": "pending"
            }

            task_json = json.dumps(task_obj)

            # Add to queue (LPUSH for high priority, RPUSH for normal)
            if priority == "high":
                self.redis.lpush(self.task_queue, task_json)
            else:
                self.redis.rpush(self.task_queue, task_json)

            # Also publish event
            self.redis.xadd(self.event_stream, {
                "type": "task_submitted",
                "task_id": task_id,
                "task": task[:100],
                "source": "vibemind"
            })

            logger.info(f"Spawned Claude task {task_id}: {task[:50]}...")

            return {
                "success": True,
                "task_id": task_id,
                "message": f"Task submitted to Claude Orchestrator",
                "priority": priority,
                "working_dir": working_dir
            }
        except Exception as e:
            logger.error(f"spawn_instance failed: {e}")
            return {"success": False, "error": str(e)}

    def send_message(self, instance_id: str, message: str) -> Dict[str, Any]:
        """
        Send a follow-up message to a running Claude instance.

        Args:
            instance_id: The instance/task ID
            message: Message to send

        Returns:
            Dict with status
        """
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to Redis"}

        try:
            msg_obj = {
                "type": "user_message",
                "instance_id": instance_id,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "source": "vibemind"
            }

            # Publish to instance-specific channel
            channel = f"orchestrator:instance:{instance_id}:input"
            self.redis.publish(channel, json.dumps(msg_obj))

            # Also add to event stream
            self.redis.xadd(self.event_stream, {
                "type": "message_sent",
                "instance_id": instance_id,
                "message": message[:100],
                "source": "vibemind"
            })

            return {
                "success": True,
                "instance_id": instance_id,
                "message": f"Message sent to Claude instance {instance_id}"
            }
        except Exception as e:
            logger.error(f"send_message failed: {e}")
            return {"success": False, "error": str(e)}

    def list_instances(self) -> Dict[str, Any]:
        """
        List all active Claude instances.

        Returns:
            Dict with list of instances
        """
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to Redis", "instances": []}

        try:
            instances = []

            # Get from instances hash
            instance_data = self.redis.hgetall(self.instances_key)

            for instance_id, data_json in instance_data.items():
                try:
                    data = json.loads(data_json)
                    instances.append({
                        "id": instance_id,
                        "status": data.get("status", "unknown"),
                        "working_dir": data.get("workingDir", ""),
                        "task": data.get("task", "")[:50],
                        "started_at": data.get("startedAt", "")
                    })
                except json.JSONDecodeError:
                    continue

            # Also check queue for pending tasks
            queue_length = self.redis.llen(self.task_queue)

            return {
                "success": True,
                "instances": instances,
                "active_count": len(instances),
                "queue_length": queue_length,
                "message": f"{len(instances)} active instances, {queue_length} in queue"
            }
        except Exception as e:
            logger.error(f"list_instances failed: {e}")
            return {"success": False, "error": str(e), "instances": []}

    def close_instance(self, instance_id: str) -> Dict[str, Any]:
        """
        Close/terminate a Claude instance.

        Args:
            instance_id: The instance ID to close

        Returns:
            Dict with status
        """
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to Redis"}

        try:
            # Send close command
            cmd = {
                "type": "close_instance",
                "instance_id": instance_id,
                "timestamp": datetime.now().isoformat(),
                "source": "vibemind"
            }

            # Publish to orchestrator commands channel
            self.redis.publish("orchestrator:commands", json.dumps(cmd))

            # Also add to event stream
            self.redis.xadd(self.event_stream, {
                "type": "close_requested",
                "instance_id": instance_id,
                "source": "vibemind"
            })

            return {
                "success": True,
                "instance_id": instance_id,
                "message": f"Close request sent for instance {instance_id}"
            }
        except Exception as e:
            logger.error(f"close_instance failed: {e}")
            return {"success": False, "error": str(e)}

    def get_instance_status(self, instance_id: str) -> Dict[str, Any]:
        """
        Get status of a specific instance.

        Args:
            instance_id: The instance ID

        Returns:
            Dict with instance details
        """
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to Redis"}

        try:
            data_json = self.redis.hget(self.instances_key, instance_id)

            if data_json:
                data = json.loads(data_json)
                return {
                    "success": True,
                    "found": True,
                    "instance": {
                        "id": instance_id,
                        "status": data.get("status", "unknown"),
                        "working_dir": data.get("workingDir", ""),
                        "task": data.get("task", ""),
                        "started_at": data.get("startedAt", ""),
                        "last_activity": data.get("lastActivity", "")
                    }
                }
            else:
                return {
                    "success": True,
                    "found": False,
                    "message": f"Instance {instance_id} not found"
                }
        except Exception as e:
            logger.error(f"get_instance_status failed: {e}")
            return {"success": False, "error": str(e)}

    def get_claude_notifications(self, count: int = 10, instance_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get recent notifications/events from Claude instances.

        Args:
            count: Number of recent events to retrieve
            instance_id: Optional - filter by specific instance

        Returns:
            Dict with notifications list
        """
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to Redis", "notifications": []}

        try:
            notifications = []

            # Read from event stream (most recent first)
            # XREVRANGE returns newest first
            events = self.redis.xrevrange(self.event_stream, count=count)

            for event_id, event_data in events:
                # Filter by instance if specified
                if instance_id and event_data.get("instance_id") != instance_id:
                    if event_data.get("task_id") != instance_id:
                        continue

                notification = {
                    "id": event_id,
                    "type": event_data.get("type", "unknown"),
                    "instance_id": event_data.get("instance_id") or event_data.get("task_id"),
                    "message": event_data.get("message", ""),
                    "source": event_data.get("source", ""),
                    "timestamp": event_id.split("-")[0]  # Extract timestamp from event ID
                }

                # Add type-specific details
                if event_data.get("status"):
                    notification["status"] = event_data["status"]
                if event_data.get("output"):
                    notification["output"] = event_data["output"][:500]  # Truncate long output
                if event_data.get("error"):
                    notification["error"] = event_data["error"]

                notifications.append(notification)

            # Summarize by type
            type_counts = {}
            for n in notifications:
                t = n["type"]
                type_counts[t] = type_counts.get(t, 0) + 1

            return {
                "success": True,
                "notifications": notifications,
                "count": len(notifications),
                "type_summary": type_counts,
                "message": f"Retrieved {len(notifications)} notifications"
            }
        except Exception as e:
            logger.error(f"get_claude_notifications failed: {e}")
            return {"success": False, "error": str(e), "notifications": []}

    def get_claude_output(self, instance_id: str) -> Dict[str, Any]:
        """
        Get the output/result from a Claude instance.

        Args:
            instance_id: The instance ID

        Returns:
            Dict with instance output
        """
        if not self.ensure_connected():
            return {"success": False, "error": "Not connected to Redis"}

        try:
            # Check for output in response key
            output_key = f"{self.response_prefix}{instance_id}"
            output_data = self.redis.get(output_key)

            # Also check instance status
            instance_json = self.redis.hget(self.instances_key, instance_id)
            instance_data = json.loads(instance_json) if instance_json else {}

            result = {
                "success": True,
                "instance_id": instance_id,
                "status": instance_data.get("status", "unknown"),
                "task": instance_data.get("task", ""),
            }

            if output_data:
                try:
                    output = json.loads(output_data)
                    result["output"] = output.get("result", output_data)
                    result["completed_at"] = output.get("completedAt")
                    result["has_output"] = True
                except json.JSONDecodeError:
                    result["output"] = output_data
                    result["has_output"] = True
            else:
                result["has_output"] = False
                result["message"] = "No output available yet"

            # Get recent events for this instance
            events = self.redis.xrevrange(self.event_stream, count=5)
            instance_events = []
            for event_id, event_data in events:
                if event_data.get("instance_id") == instance_id or event_data.get("task_id") == instance_id:
                    instance_events.append({
                        "type": event_data.get("type"),
                        "message": event_data.get("message", "")[:100]
                    })
            result["recent_events"] = instance_events

            return result
        except Exception as e:
            logger.error(f"get_claude_output failed: {e}")
            return {"success": False, "error": str(e)}


# Singleton client
_claude_client: Optional[ClaudeOrchestratorClient] = None


def get_claude_client() -> ClaudeOrchestratorClient:
    """Get singleton Claude Orchestrator client."""
    global _claude_client
    if _claude_client is None:
        _claude_client = ClaudeOrchestratorClient()
    return _claude_client


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

async def spawn_claude(
    task: str,
    working_dir: str = "C:\\Users\\User\\Desktop\\ClaudeWorkspace",
    priority: str = "normal"
) -> Dict[str, Any]:
    """
    Spawn a new Claude Code instance with a task.

    Args:
        task: Description of what Claude should do
        working_dir: Directory for Claude to work in
        priority: 'high' or 'normal'

    Returns:
        Dict with task ID and status
    """
    client = get_claude_client()
    return client.spawn_instance(task, working_dir, priority)


async def send_to_claude(instance_id: str, message: str) -> Dict[str, Any]:
    """
    Send a follow-up message to a running Claude instance.

    Args:
        instance_id: The Claude instance ID
        message: Message to send

    Returns:
        Dict with status
    """
    client = get_claude_client()
    return client.send_message(instance_id, message)


async def list_claude_instances() -> Dict[str, Any]:
    """
    List all active Claude Code instances.

    Returns:
        Dict with list of instances and queue status
    """
    client = get_claude_client()
    return client.list_instances()


async def close_claude(instance_id: str) -> Dict[str, Any]:
    """
    Close/terminate a Claude Code instance.

    Args:
        instance_id: The instance ID to close

    Returns:
        Dict with status
    """
    client = get_claude_client()
    return client.close_instance(instance_id)


async def get_claude_status(instance_id: str) -> Dict[str, Any]:
    """
    Get status of a specific Claude instance.

    Args:
        instance_id: The instance ID

    Returns:
        Dict with instance details
    """
    client = get_claude_client()
    return client.get_instance_status(instance_id)


async def get_claude_notifications(count: int = 10, instance_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get recent notifications/events from Claude instances.

    Use this to check what Claude instances have been doing,
    see completed tasks, errors, or progress updates.

    Args:
        count: Number of recent notifications to retrieve (default 10)
        instance_id: Optional - filter by specific instance ID

    Returns:
        Dict with notifications list and summary
    """
    client = get_claude_client()
    return client.get_claude_notifications(count, instance_id)


async def get_claude_output(instance_id: str) -> Dict[str, Any]:
    """
    Get the output/result from a Claude instance.

    Use this to retrieve what a Claude instance has produced,
    including code output, completed work, or error details.

    Args:
        instance_id: The instance ID to get output from

    Returns:
        Dict with output, status, and recent events
    """
    client = get_claude_client()
    return client.get_claude_output(instance_id)


# =============================================================================
# TOOL DEFINITIONS FOR ELEVENLABS
# =============================================================================

CLAUDE_TOOLS = [
    {
        "name": "spawn_claude",
        "description": "Create a new Claude Code instance to work on a task. Claude can write code, fix bugs, build features.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "What Claude should work on. Be specific about the task."
                },
                "working_dir": {
                    "type": "string",
                    "description": "Directory for Claude to work in",
                    "default": "C:\\Users\\User\\Desktop\\ClaudeWorkspace"
                },
                "priority": {
                    "type": "string",
                    "enum": ["normal", "high"],
                    "default": "normal"
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "send_to_claude",
        "description": "Send a follow-up message to a running Claude instance.",
        "parameters": {
            "type": "object",
            "properties": {
                "instance_id": {"type": "string", "description": "The Claude instance ID"},
                "message": {"type": "string", "description": "Message to send"}
            },
            "required": ["instance_id", "message"]
        }
    },
    {
        "name": "list_claude_instances",
        "description": "List all active Claude Code instances and queue status.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "close_claude",
        "description": "Close/terminate a Claude Code instance.",
        "parameters": {
            "type": "object",
            "properties": {
                "instance_id": {"type": "string", "description": "The instance ID to close"}
            },
            "required": ["instance_id"]
        }
    },
    {
        "name": "get_claude_status",
        "description": "Get status of a specific Claude instance.",
        "parameters": {
            "type": "object",
            "properties": {
                "instance_id": {"type": "string", "description": "The instance ID"}
            },
            "required": ["instance_id"]
        }
    },
    {
        "name": "get_claude_notifications",
        "description": "Get recent notifications from Claude instances. Shows completed tasks, errors, progress. Use to check what Claude has been doing.",
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of notifications to retrieve",
                    "default": 10
                },
                "instance_id": {
                    "type": "string",
                    "description": "Optional - filter by specific instance ID"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_claude_output",
        "description": "Get the output/result from a Claude instance. Retrieves what Claude produced - code, completed work, or errors.",
        "parameters": {
            "type": "object",
            "properties": {
                "instance_id": {"type": "string", "description": "The instance ID to get output from"}
            },
            "required": ["instance_id"]
        }
    }
]


# =============================================================================
# REGISTRATION
# =============================================================================

def register_claude_tools(tools_manager) -> None:
    """
    Register Claude Orchestrator tools with the ClientToolsManager.

    Args:
        tools_manager: ClientToolsManager instance
    """
    print("Registering Claude Orchestrator tools...")

    def create_wrapper(async_func):
        def wrapper(params):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, async_func(**params))
                        return future.result()
                else:
                    return asyncio.run(async_func(**params))
            except Exception as e:
                return {"success": False, "error": str(e)}
        return wrapper

    tools_manager.register_with_observer("spawn_claude", create_wrapper(
        lambda task, working_dir="C:\\Users\\User\\Desktop\\ClaudeWorkspace", priority="normal":
            spawn_claude(task, working_dir, priority)
    ))
    print("  - spawn_claude")

    tools_manager.register_with_observer("send_to_claude", create_wrapper(
        lambda instance_id, message: send_to_claude(instance_id, message)
    ))
    print("  - send_to_claude")

    tools_manager.register_with_observer("list_claude_instances", create_wrapper(
        lambda: list_claude_instances()
    ))
    print("  - list_claude_instances")

    tools_manager.register_with_observer("close_claude", create_wrapper(
        lambda instance_id: close_claude(instance_id)
    ))
    print("  - close_claude")

    tools_manager.register_with_observer("get_claude_status", create_wrapper(
        lambda instance_id: get_claude_status(instance_id)
    ))
    print("  - get_claude_status")

    tools_manager.register_with_observer("get_claude_notifications", create_wrapper(
        lambda count=10, instance_id=None: get_claude_notifications(count, instance_id)
    ))
    print("  - get_claude_notifications")

    tools_manager.register_with_observer("get_claude_output", create_wrapper(
        lambda instance_id: get_claude_output(instance_id)
    ))
    print("  - get_claude_output")

    print(f"Claude Orchestrator tools registered ({len(CLAUDE_TOOLS)} tools)")


# =============================================================================
# TEST
# =============================================================================

async def test_claude_tools():
    """Test Claude Orchestrator tools."""
    print("Testing Claude Orchestrator Tools...")
    print(f"  redis available: {HAS_REDIS}")

    client = get_claude_client()
    connected = client.connect()
    print(f"  Redis connected: {connected}")

    if connected:
        # List instances
        print("\nListing Claude instances...")
        result = await list_claude_instances()
        print(f"  Result: {result}")

        # Test spawn (without actually running)
        print("\nTest spawn_claude (dry run)...")
        # Uncomment to actually spawn:
        # result = await spawn_claude("Write a hello world script", priority="normal")
        # print(f"  Result: {result}")

    print("\nClaude tools test completed")


if __name__ == "__main__":
    asyncio.run(test_claude_tools())
