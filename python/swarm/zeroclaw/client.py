"""
ZeroClaw HTTP Client

Async client for communicating with ZeroClaw's gateway API.
Sends messages and receives agent responses.
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ZeroClawClient:
    """
    Async HTTP client for ZeroClaw gateway.

    Communicates via the /webhook endpoint to send messages
    and receive agent responses with tool results.
    """

    def __init__(self, base_url: str = None, timeout: float = 60.0):
        self._base_url = base_url or os.getenv(
            "ZEROCLAW_URL", f"http://127.0.0.1:{os.getenv('ZEROCLAW_PORT', '42618')}"
        )
        self._timeout = timeout
        self._pairing_token: Optional[str] = None

    @property
    def base_url(self) -> str:
        return self._base_url

    async def send_message(
        self,
        content: str,
        metadata: Dict[str, Any] = None,
        sender: str = "vibemind",
    ) -> Dict[str, Any]:
        """
        Send a message to ZeroClaw agent.

        Args:
            content: Message text (the research query)
            metadata: Optional metadata (event_type, payload, etc.)
            sender: Sender identifier

        Returns:
            Dict with 'success', 'response', and optional 'tool_results'
        """
        try:
            import aiohttp
        except ImportError:
            logger.error("aiohttp not installed. Run: pip install aiohttp")
            return {"success": False, "response": "aiohttp not installed"}

        payload = {
            "sender": sender,
            "content": content,
            "channel": "api",
        }
        if metadata:
            payload["metadata"] = metadata

        headers = {"Content-Type": "application/json"}
        if self._pairing_token:
            headers["Authorization"] = f"Bearer {self._pairing_token}"

        last_error = None
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self._base_url}/webhook",
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=self._timeout),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return {
                                "success": True,
                                "response": data.get("response", data.get("message", "")),
                                "tool_results": data.get("tool_results", []),
                                "raw": data,
                            }
                        else:
                            body = await resp.text()
                            logger.warning(
                                f"ZeroClaw returned {resp.status}: {body[:200]}"
                            )
                            return {
                                "success": False,
                                "response": f"ZeroClaw error {resp.status}: {body[:200]}",
                            }

            except aiohttp.ClientConnectorError as e:
                last_error = e
                logger.warning(
                    f"ZeroClaw connection failed (attempt {attempt + 1}/3): {e}"
                )
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(1.0 * (attempt + 1))

            except Exception as e:
                last_error = e
                logger.error(f"ZeroClaw request failed: {e}")
                break

        return {
            "success": False,
            "response": f"ZeroClaw unavailable: {last_error}",
        }

    async def health_check(self) -> bool:
        """Check if ZeroClaw is responding."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/v1/models",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False


# Singleton
_client: Optional[ZeroClawClient] = None


def get_zeroclaw_client() -> ZeroClawClient:
    """Get or create ZeroClawClient singleton."""
    global _client
    if _client is None:
        _client = ZeroClawClient()
    return _client
