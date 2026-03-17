"""
n8n REST API Client

Communicates with a running n8n instance via the v1 REST API.
Handles workflow CRUD, activation, execution, and health checks.

Auth: X-N8N-API-KEY header
Docs: https://docs.n8n.io/api/
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Optional async support — falls back to sync requests
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class N8nApiClient:
    """REST API client for n8n workflow automation platform."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("N8N_API_URL", "http://localhost:5678")).rstrip("/")
        self.api_key = api_key or os.getenv("N8N_API_KEY", "")
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            self._headers["X-N8N-API-KEY"] = self.api_key

    # ── Sync Methods (used by backend agent tools) ──────────────────────

    def _get(self, path: str) -> Dict[str, Any]:
        """GET request to n8n API."""
        url = f"{self.base_url}/api/v1{path}"
        try:
            resp = requests.get(url, headers=self._headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"n8n API GET {path} failed: {e}")
            return {"error": str(e)}

    def _post(self, path: str, data: Dict = None) -> Dict[str, Any]:
        """POST request to n8n API."""
        url = f"{self.base_url}/api/v1{path}"
        try:
            resp = requests.post(url, headers=self._headers, json=data or {}, timeout=30)
            if not resp.ok:
                body = resp.text[:500]
                logger.error(f"n8n API POST {path} failed ({resp.status_code}): {body}")
                return {"error": f"{resp.status_code}: {body}"}
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"n8n API POST {path} failed: {e}")
            return {"error": str(e)}

    def _patch(self, path: str, data: Dict = None) -> Dict[str, Any]:
        """PATCH request to n8n API."""
        url = f"{self.base_url}/api/v1{path}"
        try:
            resp = requests.patch(url, headers=self._headers, json=data or {}, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"n8n API PATCH {path} failed: {e}")
            return {"error": str(e)}

    def _delete(self, path: str) -> Dict[str, Any]:
        """DELETE request to n8n API."""
        url = f"{self.base_url}/api/v1{path}"
        try:
            resp = requests.delete(url, headers=self._headers, timeout=10)
            resp.raise_for_status()
            return resp.json() if resp.text else {"success": True}
        except requests.RequestException as e:
            logger.error(f"n8n API DELETE {path} failed: {e}")
            return {"error": str(e)}

    # ── Workflow Operations ─────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """Check if n8n instance is reachable."""
        try:
            url = f"{self.base_url}/healthz"
            resp = requests.get(url, timeout=5)
            return {
                "online": resp.status_code == 200,
                "url": self.base_url,
                "status_code": resp.status_code,
            }
        except requests.RequestException as e:
            return {"online": False, "url": self.base_url, "error": str(e)}

    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all workflows."""
        result = self._get("/workflows")
        if "error" in result:
            return []
        return result.get("data", result if isinstance(result, list) else [])

    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get a single workflow by ID."""
        return self._get(f"/workflows/{workflow_id}")

    def create_workflow(self, workflow_json: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new workflow from JSON definition."""
        return self._post("/workflows", workflow_json)

    def update_workflow(self, workflow_id: str, workflow_json: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing workflow."""
        return self._patch(f"/workflows/{workflow_id}", workflow_json)

    def delete_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Delete a workflow."""
        return self._delete(f"/workflows/{workflow_id}")

    def activate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Activate a workflow."""
        return self._patch(f"/workflows/{workflow_id}", {"active": True})

    def deactivate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Deactivate a workflow."""
        return self._patch(f"/workflows/{workflow_id}", {"active": False})

    def execute_workflow(self, workflow_id: str, data: Dict = None) -> Dict[str, Any]:
        """Execute a workflow manually with optional input data."""
        return self._post(f"/workflows/{workflow_id}/run", data or {})

    def get_executions(self, workflow_id: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Get recent workflow executions."""
        logger.debug("get_executions called: workflow_id=%s, limit=%s", workflow_id, limit)
        path = "/executions"
        if workflow_id:
            path += f"?workflowId={workflow_id}&limit={limit}"
        else:
            path += f"?limit={limit}"
        result = self._get(path)
        if "error" in result:
            return []
        return result.get("data", result if isinstance(result, list) else [])


# Singleton
_client: Optional[N8nApiClient] = None


def get_n8n_client() -> N8nApiClient:
    """Get or create the N8nApiClient singleton."""
    global _client
    if _client is None:
        _client = N8nApiClient()
    return _client


__all__ = ["N8nApiClient", "get_n8n_client"]
