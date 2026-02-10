"""
OpenClaw Gateway Protocol

Defines message types and helpers for communicating with OpenClaw Gateway.
Based on OpenClaw Gateway WebSocket protocol documentation.

Protocol:
- Requests: {type:"req", id, method, params} -> {type:"res", id, ok, payload|error}
- Events: {type:"event", event, payload}
"""

import json
import uuid
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List


class MessageType(str, Enum):
    """OpenClaw message types."""
    REQUEST = "req"
    RESPONSE = "res"
    EVENT = "event"


class GatewayMethod(str, Enum):
    """Known Gateway RPC methods."""
    # Connection
    CONNECT = "connect"

    # Health & Status
    HEALTH = "health"
    STATUS = "status"

    # Messaging
    MESSAGE_SEND = "message.send"

    # Agent
    AGENT_RUN = "agent"

    # Web
    WEB_SEARCH = "web.search"
    WEB_FETCH = "web.fetch"

    # Browser
    BROWSER_NAVIGATE = "browser.navigate"
    BROWSER_SCREENSHOT = "browser.screenshot"
    BROWSER_CLICK = "browser.click"
    BROWSER_TYPE = "browser.type"
    BROWSER_SNAPSHOT = "browser.snapshot"

    # Nodes
    NODE_INVOKE = "node.invoke"

    # Sessions
    SESSION_LIST = "session.list"


class GatewayEvent(str, Enum):
    """Known Gateway events."""
    HELLO_OK = "hello-ok"
    MESSAGE = "message"
    AGENT_UPDATE = "agent.update"
    AGENT_COMPLETE = "agent.complete"
    SHUTDOWN = "shutdown"
    ERROR = "error"


@dataclass
class GatewayRequest:
    """
    Request message to Gateway.

    Example:
        req = GatewayRequest(method="health")
        ws.send(req.to_json())
    """
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = field(default=MessageType.REQUEST.value, init=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "type": self.type,
            "id": self.id,
            "method": self.method,
            "params": self.params,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class GatewayResponse:
    """
    Response message from Gateway.

    Attributes:
        id: Request ID this responds to
        ok: True if successful
        payload: Result data (if ok=True)
        error: Error message (if ok=False)
    """
    id: str
    ok: bool
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    type: str = field(default=MessageType.RESPONSE.value, init=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GatewayResponse":
        """Create from parsed JSON dict."""
        return cls(
            id=data.get("id", ""),
            ok=data.get("ok", False),
            payload=data.get("payload"),
            error=data.get("error"),
        )

    @classmethod
    def from_json(cls, raw: str) -> "GatewayResponse":
        """Create from JSON string."""
        return cls.from_dict(json.loads(raw))

    def raise_for_error(self):
        """Raise exception if response is an error."""
        if not self.ok:
            raise GatewayError(self.error or "Unknown error", response=self)


@dataclass
class GatewayEventMessage:
    """
    Event message from Gateway.

    Attributes:
        event: Event name
        payload: Event data
        seq: Optional sequence number
    """
    event: str
    payload: Dict[str, Any] = field(default_factory=dict)
    seq: Optional[int] = None
    type: str = field(default=MessageType.EVENT.value, init=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GatewayEventMessage":
        """Create from parsed JSON dict."""
        return cls(
            event=data.get("event", ""),
            payload=data.get("payload", {}),
            seq=data.get("seq"),
        )


class GatewayError(Exception):
    """Error from Gateway."""

    def __init__(self, message: str, response: Optional[GatewayResponse] = None):
        super().__init__(message)
        self.response = response


def parse_message(raw: str) -> "GatewayRequest | GatewayResponse | GatewayEventMessage":
    """
    Parse raw JSON message from Gateway.

    Returns appropriate message type based on 'type' field.
    """
    data = json.loads(raw)
    msg_type = data.get("type")

    if msg_type == MessageType.RESPONSE.value:
        return GatewayResponse.from_dict(data)
    elif msg_type == MessageType.EVENT.value:
        return GatewayEventMessage.from_dict(data)
    elif msg_type == MessageType.REQUEST.value:
        return GatewayRequest(
            method=data.get("method", ""),
            params=data.get("params", {}),
            id=data.get("id", ""),
        )
    else:
        raise ValueError(f"Unknown message type: {msg_type}")


# === Helper functions for building requests ===

def connect_request(
    token: Optional[str] = None,
    role: str = "operator",
    scopes: Optional[List[str]] = None,
) -> GatewayRequest:
    """Create connection handshake request with OpenClaw protocol v3."""
    params = {
        "role": role,
        "minProtocol": 3,
        "maxProtocol": 3,
        "scopes": scopes or ["operator.read", "operator.write", "operator.admin"],
        "client": {
            "id": "cli",  # Use CLI mode
            "platform": "node",
            "mode": "cli",
            "version": "0.1.0",
        },
    }

    if token:
        params["auth"] = {"token": token}

    return GatewayRequest(method=GatewayMethod.CONNECT.value, params=params)


def health_request() -> GatewayRequest:
    """Create health check request."""
    return GatewayRequest(method=GatewayMethod.HEALTH.value)


def status_request() -> GatewayRequest:
    """Create status request."""
    return GatewayRequest(method=GatewayMethod.STATUS.value)


def message_send_request(
    platform: str,
    recipient: str,
    content: str,
    channel: str = "default",
    media: Optional[List[Dict]] = None,
) -> GatewayRequest:
    """Create message send request."""
    return GatewayRequest(
        method=GatewayMethod.MESSAGE_SEND.value,
        params={
            "channel": channel,
            "platform": platform,
            "recipient": recipient,
            "content": content,
            "media": media or [],
        },
    )


def web_search_request(query: str, max_results: int = 5) -> GatewayRequest:
    """Create web search request."""
    return GatewayRequest(
        method=GatewayMethod.WEB_SEARCH.value,
        params={"query": query, "maxResults": max_results},
    )


def web_fetch_request(url: str) -> GatewayRequest:
    """Create web fetch request."""
    return GatewayRequest(
        method=GatewayMethod.WEB_FETCH.value,
        params={"url": url},
    )


def browser_navigate_request(url: str) -> GatewayRequest:
    """Create browser navigate request."""
    return GatewayRequest(
        method=GatewayMethod.BROWSER_NAVIGATE.value,
        params={"url": url},
    )


def browser_screenshot_request() -> GatewayRequest:
    """Create browser screenshot request."""
    return GatewayRequest(method=GatewayMethod.BROWSER_SCREENSHOT.value)


def agent_run_request(
    task: str,
    to: Optional[str] = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> GatewayRequest:
    """
    Create agent run request.

    Args:
        task: The message/task for the agent
        to: Phone number in E.164 format (e.g., +491749708452) to route the response
        agent_id: Optional agent ID to use
        session_id: Optional session ID
        idempotency_key: Required idempotency key (auto-generated if not provided)
    """
    import uuid
    params = {
        "message": task,
        "idempotencyKey": idempotency_key or str(uuid.uuid4()),
    }
    if to:
        params["to"] = to
    if agent_id:
        params["agent"] = agent_id
    if session_id:
        params["sessionId"] = session_id

    return GatewayRequest(
        method=GatewayMethod.AGENT_RUN.value,
        params=params,
    )


__all__ = [
    "MessageType",
    "GatewayMethod",
    "GatewayEvent",
    "GatewayRequest",
    "GatewayResponse",
    "GatewayEventMessage",
    "GatewayError",
    "parse_message",
    "connect_request",
    "health_request",
    "status_request",
    "message_send_request",
    "web_search_request",
    "web_fetch_request",
    "browser_navigate_request",
    "browser_screenshot_request",
    "agent_run_request",
]
