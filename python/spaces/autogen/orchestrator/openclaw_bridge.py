"""
OpenClaw Gateway Bridge — communicates with OpenClaw for sandboxed execution,
user channel messaging (no timeout), and Claude CLI delegation via ACP.

Requires OpenClaw Gateway running at OPENCLAW_URL (default: ws://127.0.0.1:18789).
Falls back gracefully when OpenClaw is not available.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default: coding-engine-openclaw container already running on 18789
OPENCLAW_URL = os.getenv("OPENCLAW_URL", "ws://127.0.0.1:18789")
OPENCLAW_TOKEN = os.getenv("OPENCLAW_GATEWAY_TOKEN", "vibemind-local")


class OpenClawBridge:
    """Bridge to OpenClaw Gateway for sandboxed execution and user communication."""

    def __init__(self, gateway_url: str = None):
        self._url = gateway_url or OPENCLAW_URL
        self._token = OPENCLAW_TOKEN
        self._ws = None
        self._connected = False
        self._request_id = 0
        self._pending: Dict[int, asyncio.Future] = {}

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Connect to OpenClaw Gateway via WebSocket."""
        try:
            import websockets
            self._ws = await websockets.connect(self._url)
            connect_msg = {
                "type": "connect",
                "role": "client",
                "device": {"family": "vibemind", "platform": "win32"},
            }
            if self._token:
                connect_msg["token"] = self._token
            await self._ws.send(json.dumps(connect_msg))
            resp = json.loads(await self._ws.recv())
            self._connected = resp.get("ok", False)
            if self._connected:
                logger.info(f"OpenClaw connected at {self._url}")
                asyncio.create_task(self._listen())
            return self._connected
        except Exception as e:
            logger.warning(f"OpenClaw not available: {e}")
            self._connected = False
            return False

    async def _listen(self):
        """Background listener for events and responses."""
        try:
            async for msg in self._ws:
                data = json.loads(msg)
                if data.get("type") == "res":
                    req_id = data.get("id")
                    if req_id in self._pending:
                        self._pending[req_id].set_result(data)
        except Exception as e:
            logger.warning(f"OpenClaw listener ended: {e}")
            self._connected = False

    async def _request(self, method: str, params: dict = None,
                       timeout: float = None) -> dict:
        """Send request to OpenClaw Gateway and wait for response."""
        if not self._connected:
            raise ConnectionError("OpenClaw not connected")

        self._request_id += 1
        req_id = self._request_id
        msg = {"type": "req", "id": req_id, "method": method, "params": params or {}}

        future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future
        await self._ws.send(json.dumps(msg))

        try:
            if timeout:
                result = await asyncio.wait_for(future, timeout=timeout)
            else:
                result = await future  # No timeout — waits indefinitely
            return result.get("payload", {})
        finally:
            self._pending.pop(req_id, None)

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # User Communication (NO TIMEOUT)
    # ------------------------------------------------------------------

    async def ask_user(self, question: str, channel: str = None,
                       options: List[str] = None) -> str:
        """Ask user a question via channel. NO TIMEOUT — waits until user responds."""
        if not self._connected:
            logger.warning("OpenClaw not connected, skipping user question")
            return ""

        message = question
        if options:
            message += "\n" + "\n".join(f"{i+1}. {o}" for i, o in enumerate(options))

        params = {"message": message, "waitForReply": True}
        if channel:
            params["channel"] = channel

        result = await self._request("send", params, timeout=None)
        return result.get("reply", result.get("text", ""))

    async def send_status(self, message: str, channel: str = None):
        """Send status update to user (non-blocking, best-effort)."""
        if not self._connected:
            logger.info(f"[Pipeline Status] {message}")
            return
        params = {"message": message}
        if channel:
            params["channel"] = channel
        try:
            await self._request("send", params, timeout=5.0)
        except Exception:
            logger.debug(f"Status send failed: {message[:50]}")

    # ------------------------------------------------------------------
    # Docker Sandbox Execution
    # ------------------------------------------------------------------

    async def run_in_sandbox(self, args: List[str], workdir: str = None,
                             timeout: float = None) -> Dict[str, Any]:
        """Execute command in OpenClaw Docker sandbox."""
        if not self._connected:
            return await self._local_exec(args, workdir, timeout)

        result = await self._request("agent", {
            "task": " ".join(args),
            "runtime": "sandbox",
        }, timeout=timeout)

        return {
            "success": result.get("ok", False),
            "output": result.get("output", ""),
            "exit_code": result.get("exitCode", -1),
        }

    async def docker_build(self, context_path: str,
                           timeout: float = None) -> Dict[str, Any]:
        """Run docker compose build in sandbox."""
        return await self.run_in_sandbox(
            ["docker", "compose", "-f", f"{context_path}/docker-compose.yml", "build"],
            workdir=context_path, timeout=timeout,
        )

    async def docker_run(self, context_path: str,
                         timeout: float = None) -> Dict[str, Any]:
        """Run docker compose up in sandbox."""
        return await self.run_in_sandbox(
            ["docker", "compose", "-f", f"{context_path}/docker-compose.yml",
             "up", "--abort-on-container-exit"],
            workdir=context_path, timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Claude CLI Delegation via ACP
    # ------------------------------------------------------------------

    async def delegate_to_claude_cli(self, task: str,
                                     files: List[str] = None,
                                     timeout: float = 300.0) -> Dict[str, Any]:
        """Delegate task to Claude CLI via OpenClaw ACP."""
        if not self._connected:
            return await self._local_claude_cli(task, timeout)

        result = await self._request("agent", {
            "task": task,
            "runtime": "acp",
            "agentId": "claude",
            "mode": "session",
        }, timeout=timeout)

        return {
            "success": result.get("ok", False),
            "output": result.get("output", result.get("text", "")),
            "session_id": result.get("sessionId"),
        }

    # ------------------------------------------------------------------
    # Local Fallbacks
    # ------------------------------------------------------------------

    async def _local_exec(self, args: List[str], workdir: str = None,
                          timeout: float = 300.0) -> Dict[str, Any]:
        """Fallback: run command locally via subprocess (no shell)."""
        try:
            result = subprocess.run(
                args, capture_output=True, text=True,
                cwd=workdir, timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "Timeout", "exit_code": -1}
        except Exception as e:
            return {"success": False, "output": str(e), "exit_code": -1}

    async def _local_claude_cli(self, task: str,
                                timeout: float = 300.0) -> Dict[str, Any]:
        """Fallback: run Claude CLI directly (no shell injection)."""
        claude_path = shutil.which("claude")
        if not claude_path:
            return {"success": False, "output": "Claude CLI not found"}

        try:
            result = subprocess.run(
                [claude_path, "--print", "--output-format", "text", "-p", task],
                capture_output=True, text=True, timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "session_id": None,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "Claude CLI timeout"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def disconnect(self):
        """Close WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._connected = False
            logger.info("OpenClaw disconnected")
