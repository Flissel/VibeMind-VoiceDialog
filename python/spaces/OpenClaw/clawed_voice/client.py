"""
OpenClaw Gateway WebSocket Client

Handles WebSocket communication with OpenClaw Gateway.
Supports request/response patterns and event subscriptions.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, Awaitable

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
    _HAS_WEBSOCKETS = True
except ImportError:
    _HAS_WEBSOCKETS = False
    WebSocketClientProtocol = Any

from .config import get_config
from .protocol import (
    GatewayRequest,
    GatewayResponse,
    GatewayEventMessage,
    GatewayError,
    parse_message,
    connect_request,
    health_request,
    status_request,
    message_send_request,
    web_search_request,
    web_fetch_request,
    browser_navigate_request,
    browser_screenshot_request,
    agent_run_request,
)
from .gateway_manager import get_gateway_manager

logger = logging.getLogger(__name__)

# Type alias for event handlers
EventHandler = Callable[[Dict[str, Any]], Awaitable[None]]


class OpenClawClient:
    """
    WebSocket client for OpenClaw Gateway.

    Features:
    - Auto-start gateway on connect (on-demand)
    - Request/response with async futures
    - Event subscription
    - Auto-reconnection
    - Activity tracking for idle timeout
    """

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        auto_start_gateway: bool = True,
    ):
        if not _HAS_WEBSOCKETS:
            raise ImportError("websockets package required: pip install websockets")

        config = get_config()
        self.url = url or config.gateway_url
        self.token = token or config.gateway_token
        self.auto_start_gateway = auto_start_gateway

        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._pending: Dict[str, asyncio.Future] = {}
        self._event_handlers: Dict[str, list[EventHandler]] = {}
        self._receive_task: Optional[asyncio.Task] = None
        self._gateway_manager = get_gateway_manager()

    @property
    def connected(self) -> bool:
        """Check if connected to gateway."""
        return self._connected and self._ws is not None

    async def connect(self, timeout: float = 30.0) -> bool:
        """
        Connect to OpenClaw Gateway.

        Will start gateway if auto_start_gateway=True and not running.

        Returns:
            True if connected successfully
        """
        if self._connected:
            return True

        # Ensure gateway is running
        if self.auto_start_gateway:
            if not await self._gateway_manager.ensure_running():
                logger.error("Failed to start gateway")
                return False

        try:
            logger.info(f"Connecting to Gateway at {self.url}...")

            # Connect WebSocket with ping/pong keep-alive
            self._ws = await asyncio.wait_for(
                websockets.connect(
                    self.url,
                    ping_interval=20,  # Send ping every 20 seconds
                    ping_timeout=10,   # Wait 10 seconds for pong
                ),
                timeout=timeout,
            )

            # Send handshake
            handshake = connect_request(token=self.token)
            await self._ws.send(handshake.to_json())

            # Wait for events/response (OpenClaw sends challenge then hello-ok)
            connected = False
            for _ in range(3):  # Try up to 3 messages
                raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
                msg = parse_message(raw)

                if isinstance(msg, GatewayEventMessage):
                    if msg.event == "hello-ok":
                        # Successfully connected!
                        connected = True
                        break
                    elif msg.event == "connect.challenge":
                        # Challenge - continue waiting for hello-ok
                        continue
                elif isinstance(msg, GatewayResponse):
                    if msg.ok:
                        connected = True
                        break
                    else:
                        logger.error(f"Handshake failed: {msg.error}")
                        await self._ws.close()
                        return False

            if not connected:
                logger.error("Handshake failed: No hello-ok event received")
                await self._ws.close()
                return False

            self._connected = True
            self._gateway_manager.touch_activity()

            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())

            logger.info("Connected to OpenClaw Gateway")
            return True

        except asyncio.TimeoutError:
            logger.error("Connection timed out")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from gateway."""
        self._connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        # Fail pending requests
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionError("Disconnected"))
        self._pending.clear()

        logger.info("Disconnected from Gateway")

    async def _receive_loop(self):
        """Background task to receive messages."""
        while self._connected and self._ws:
            try:
                raw = await self._ws.recv()
                msg = parse_message(raw)

                if isinstance(msg, GatewayResponse):
                    # Match to pending request
                    future = self._pending.pop(msg.id, None)
                    if future and not future.done():
                        if msg.ok:
                            future.set_result(msg.payload)
                        else:
                            future.set_exception(GatewayError(msg.error or "Unknown error", msg))

                elif isinstance(msg, GatewayEventMessage):
                    # Dispatch to handlers
                    await self._dispatch_event(msg.event, msg.payload)

            except asyncio.CancelledError:
                break
            except websockets.ConnectionClosed:
                logger.warning("Connection closed by gateway")
                self._connected = False
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")

    async def _dispatch_event(self, event: str, payload: Dict[str, Any]):
        """Dispatch event to registered handlers."""
        # Debug: log all incoming events
        logger.debug(f"Received event: {event} -> {payload}")

        # Auto-archive all message events
        if event == "message":
            try:
                from .archive import archive_message
                archive_message(payload)
            except Exception as e:
                logger.debug(f"Archive error (non-critical): {e}")

        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                await handler(payload)
            except Exception as e:
                logger.error(f"Event handler error for {event}: {e}")

    def on_event(self, event: str, handler: EventHandler):
        """Register event handler."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    async def call(
        self,
        request: GatewayRequest,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Make RPC call to gateway.

        Args:
            request: Request to send
            timeout: Response timeout

        Returns:
            Response payload

        Raises:
            GatewayError: If request fails
            ConnectionError: If not connected
            TimeoutError: If response times out
        """
        if not self._connected:
            raise ConnectionError("Not connected to gateway")

        self._gateway_manager.touch_activity()

        # Create future for response
        future: asyncio.Future = asyncio.Future()
        self._pending[request.id] = future

        try:
            await self._ws.send(request.to_json())
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(request.id, None)
            raise TimeoutError(f"Request {request.method} timed out")

    # === High-Level API Methods ===

    async def health(self) -> Dict[str, Any]:
        """Check gateway health."""
        return await self.call(health_request())

    async def status(self) -> Dict[str, Any]:
        """Get gateway status."""
        return await self.call(status_request())

    async def send_message(
        self,
        platform: str,
        recipient: str,
        content: str,
        channel: str = "default",
    ) -> Dict[str, Any]:
        """
        Send message via OpenClaw.

        Args:
            platform: whatsapp, telegram, discord, slack
            recipient: Phone number, chat ID, or username
            content: Message text
            channel: Channel identifier

        Returns:
            Send result
        """
        req = message_send_request(
            platform=platform,
            recipient=recipient,
            content=content,
            channel=channel,
        )
        return await self.call(req)

    async def web_search(self, query: str) -> Dict[str, Any]:
        """Perform web search."""
        return await self.call(web_search_request(query))

    async def web_fetch(self, url: str) -> Dict[str, Any]:
        """Fetch web page content."""
        return await self.call(web_fetch_request(url))

    async def browser_navigate(self, url: str) -> Dict[str, Any]:
        """Navigate browser to URL."""
        return await self.call(browser_navigate_request(url))

    async def browser_screenshot(self) -> Dict[str, Any]:
        """Take browser screenshot."""
        return await self.call(browser_screenshot_request())

    async def run_agent(
        self,
        task: str,
        to: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        wait_for_completion: bool = False,
        completion_timeout: float = 120.0,
    ) -> Dict[str, Any]:
        """
        Run OpenClaw agent.

        Args:
            task: Task description (the message for the agent)
            to: Phone number in E.164 format to route response (defaults to config OPENCLAW_DEFAULT_RECIPIENT)
            agent_id: Optional agent ID to use
            session_id: Optional session ID for conversation continuity
            wait_for_completion: If True, wait for agent.complete event instead of just acceptance
            completion_timeout: Timeout for waiting for completion

        Returns:
            Agent result (acceptance if wait_for_completion=False, actual result if True)
        """
        # Use default recipient from config if not specified
        if not to and not session_id:
            from .config import get_config
            cfg = get_config()
            to = cfg.openclaw_default_recipient

        req = agent_run_request(
            task=task,
            to=to,
            agent_id=agent_id,
            session_id=session_id,
        )

        # Send request and get initial acceptance
        acceptance = await self.call(req, timeout=30.0)

        # If not waiting for completion, return acceptance immediately
        if not wait_for_completion:
            return acceptance

        # Wait for agent.complete event
        run_id = acceptance.get("runId")
        if not run_id:
            logger.warning("No runId in acceptance response, returning acceptance")
            return acceptance

        logger.info(f"Waiting for agent completion (runId: {run_id})...")

        # Create future for completion event
        completion_future: asyncio.Future = asyncio.Future()

        async def completion_handler(payload: Dict[str, Any]):
            """Handle agent.complete event."""
            logger.debug(f"agent.complete payload: {payload}")
            # Try multiple possible keys for runId
            payload_run_id = payload.get("runId") or payload.get("run_id") or payload.get("id")
            if payload_run_id == run_id:
                if not completion_future.done():
                    completion_future.set_result(payload)

        async def update_handler(payload: Dict[str, Any]):
            """Handle agent.update event - check if it contains completion."""
            logger.debug(f"agent.update payload: {payload}")
            payload_run_id = payload.get("runId") or payload.get("run_id") or payload.get("id")
            status = payload.get("status", "")
            if payload_run_id == run_id and status in ("completed", "done", "finished"):
                if not completion_future.done():
                    completion_future.set_result(payload)

        # Register event handlers for both complete and update events
        self.on_event("agent.complete", completion_handler)
        self.on_event("agent.update", update_handler)

        try:
            # Wait for completion
            completion_result = await asyncio.wait_for(
                completion_future,
                timeout=completion_timeout,
            )
            logger.info(f"Agent completed (runId: {run_id})")
            return completion_result
        except asyncio.TimeoutError:
            logger.error(f"Agent completion timeout (runId: {run_id})")
            return {
                "status": "timeout",
                "runId": run_id,
                "error": "Agent execution timed out",
            }
        finally:
            # Clean up handler (note: we can't easily remove specific handlers,
            # but they'll be cleaned up on disconnect)
            pass


# Singleton
_client: Optional[OpenClawClient] = None


def get_client() -> OpenClawClient:
    """Get or create OpenClawClient singleton."""
    global _client
    if _client is None:
        _client = OpenClawClient()
    return _client


async def connect() -> bool:
    """Convenience: connect to gateway."""
    return await get_client().connect()


async def disconnect():
    """Convenience: disconnect from gateway."""
    await get_client().disconnect()


__all__ = [
    "OpenClawClient",
    "get_client",
    "connect",
    "disconnect",
]
