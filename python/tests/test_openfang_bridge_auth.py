"""BrainOpenFangBridge schickt den OpenFang-Bearer-Key mit.

Seit OpenFang 0.6.9 (23.09.2026) verlangt :4200 den Key auch von
Loopback-Aufrufern. Die Bridge (aktiv mit USE_BRAIN_BRIDGE /
USE_OPENFANG_DIRECT) schickte keinen Header: Nachricht senden und Agent
anlegen scheiterten mit 401, nur die oeffentliche Agentenliste ging noch.
Die Tests fahren die echte aiohttp-Strecke gegen einen lokalen HTTP-Server.
"""
import asyncio
import http.server
import json
import threading

import pytest

from swarm.routing.brain_openfang_bridge import BrainOpenFangBridge


@pytest.fixture()
def openfang(monkeypatch):
    seen: list = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def _reply(self, body) -> None:
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            seen.append(("GET", self.path, self.headers.get("Authorization")))
            self._reply([])

        def do_POST(self) -> None:  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            seen.append(("POST", self.path, self.headers.get("Authorization")))
            self._reply({"id": "neu-123", "response": "bereit"})

        def log_message(self, *args) -> None:
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("OPENFANG_API_KEY", "test-schluessel-123")
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", seen
    finally:
        httpd.shutdown()


def test_send_to_agent_carries_bearer_key(openfang):
    url, seen = openfang
    bridge = BrainOpenFangBridge(openfang_url=url)

    asyncio.run(bridge.send_to_agent("agent-1", "hallo"))

    assert ("POST", "/api/agents/agent-1/message", "Bearer test-schluessel-123") in seen


def test_spawning_a_missing_agent_carries_bearer_key(openfang):
    url, seen = openfang
    bridge = BrainOpenFangBridge(openfang_url=url)

    agent_id = asyncio.run(bridge.ensure_agent("gibt-es-noch-nicht"))

    assert agent_id == "neu-123"
    assert ("POST", "/api/agents", "Bearer test-schluessel-123") in seen
