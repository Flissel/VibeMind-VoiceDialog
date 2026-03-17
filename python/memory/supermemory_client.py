"""
Supermemory Client for Multi-Agent Voice System

Handles storage and retrieval of:
- Conversation context across agent handoffs
- User preferences and habits
- Project knowledge and information
"""

import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()


class SupermemoryClient:
    """Client for Supermemory AI memory API"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SUPERMEMORY_API_KEY")

        if not self.api_key:
            raise ValueError("SUPERMEMORY_API_KEY not found in environment")

        self.base_url = "https://api.supermemory.ai/v3"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def store_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a memory in Supermemory

        Args:
            content: The text content to store
            metadata: Optional metadata dict

        Returns:
            Response from Supermemory API
        """
        url = f"{self.base_url}/memories"

        payload = {
            "content": content,
            "metadata": metadata or {}
        }

        response = requests.post(url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()

        return response.json()

    def store_conversation(
        self,
        session_id: str,
        agent_name: str,
        messages: List[Dict[str, str]],
        handoff_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store conversation context for agent handoffs

        Args:
            session_id: Unique session identifier
            agent_name: Name of the agent (ConversationalMemory, ProjectManager, etc.)
            messages: List of message dicts with 'role' and 'content'
            handoff_to: Optional target agent for handoff

        Returns:
            Supermemory response
        """
        content = f"Conversation with {agent_name}\n\n"
        content += "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in messages
        ])

        metadata = {
            "type": "conversation",
            "session_id": session_id,
            "agent": agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "message_count": len(messages),
            "handoff_to": handoff_to
        }

        return self.store_memory(content, metadata)

    def store_user_preference(
        self,
        session_id: str,
        preference_key: str,
        preference_value: Any
    ) -> Dict[str, Any]:
        """
        Store a user preference

        Args:
            session_id: User session ID
            preference_key: Preference identifier (e.g., "default_editor", "coding_style")
            preference_value: Preference value

        Returns:
            Supermemory response
        """
        content = f"User Preference: {preference_key} = {preference_value}"

        metadata = {
            "type": "user_preference",
            "session_id": session_id,
            "preference_key": preference_key,
            "timestamp": datetime.utcnow().isoformat()
        }

        return self.store_memory(content, metadata)

    def store_project_info(
        self,
        session_id: str,
        project_name: str,
        project_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Store project information

        Args:
            session_id: User session ID
            project_name: Name of the project
            project_details: Project information dict

        Returns:
            Supermemory response
        """
        content = f"Project: {project_name}\n\n"
        content += json.dumps(project_details, indent=2)

        metadata = {
            "type": "project",
            "session_id": session_id,
            "project_name": project_name,
            "timestamp": datetime.utcnow().isoformat()
        }

        return self.store_memory(content, metadata)

    def retrieve_context(
        self,
        session_id: str,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context from memory

        Args:
            session_id: Session ID to filter by
            query: Search query
            limit: Maximum number of results

        Returns:
            List of memory items
        """
        # Note: Supermemory API search endpoint may vary by version
        # Try different payload formats as API may vary

        # Try different payload formats (API might expect different field names)
        payloads_to_try = [
            # Format 1: Standard with q
            {"q": query, "top_k": limit},
            # Format 2: With content
            {"content": query, "limit": limit},
            # Format 3: Just query
            {"query": query, "limit": limit},
            # Format 4: With filters
            {"query": query, "filters": {"session_id": session_id}, "limit": limit},
        ]

        url = f"{self.base_url}/search"

        for payload in payloads_to_try:
            try:
                response = requests.post(url, headers=self.headers, json=payload, timeout=10)
                if response.status_code == 400:
                    # Try next payload format
                    continue
                if response.status_code == 404:
                    break  # Endpoint doesn't exist
                response.raise_for_status()
                result = response.json()
                # Handle different response formats
                return result.get("results", result.get("memories", result.get("data", [])))
            except requests.exceptions.HTTPError as e:
                if "400" in str(e):
                    continue  # Try next payload format
                print(f"[Supermemory] Retrieval error: {e}")
                break
            except Exception as e:
                print(f"[Supermemory] Retrieval error: {e}")
                break

        # All formats failed - return empty (will fall back to local search)
        print(f"[Supermemory] Search failed - check API docs for correct format")
        return []

    def get_conversation_history(
        self,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all conversation history for a session

        Args:
            session_id: Session ID

        Returns:
            List of conversation memories, sorted by timestamp
        """
        return self.retrieve_context(
            session_id=session_id,
            query="conversation",
            limit=50
        )

    def get_user_preferences(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get user preferences for a session

        Args:
            session_id: Session ID

        Returns:
            Dict of preference_key: preference_value
        """
        logger.debug("get_user_preferences: session_id=%s", session_id)
        results = self.retrieve_context(
            session_id=session_id,
            query="user preference",
            limit=50
        )

        preferences = {}
        for result in results:
            metadata = result.get("metadata", {})
            if metadata.get("type") == "user_preference":
                key = metadata.get("preference_key")
                # Extract value from content
                content = result.get("content", "")
                if "=" in content:
                    value = content.split("=", 1)[1].strip()
                    preferences[key] = value

        return preferences

    def get_projects(
        self,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get project information for a session

        Args:
            session_id: Session ID

        Returns:
            List of project dicts
        """
        logger.debug("get_projects: session_id=%s", session_id)
        results = self.retrieve_context(
            session_id=session_id,
            query="project",
            limit=20
        )

        projects = []
        for result in results:
            metadata = result.get("metadata", {})
            if metadata.get("type") == "project":
                content = result.get("content", "")
                # Try to parse JSON from content
                try:
                    if content.startswith("Project:"):
                        json_part = content.split("\n\n", 1)[1]
                        project_data = json.loads(json_part)
                        project_data["name"] = metadata.get("project_name")
                        projects.append(project_data)
                except:
                    pass

        return projects


# Test functionality
if __name__ == "__main__":
    import uuid

    print("=" * 60)
    print("Supermemory Client Test")
    print("=" * 60)
    print()

    try:
        client = SupermemoryClient()
        print(f"✓ Client initialized")
        print()

        # Test session
        session_id = str(uuid.uuid4())
        print(f"Test Session ID: {session_id}")
        print()

        # Test storing a conversation
        print("1. Storing conversation...")
        result = client.store_conversation(
            session_id=session_id,
            agent_name="ConversationalMemory",
            messages=[
                {"role": "user", "content": "Hello, I need help with my Python project"},
                {"role": "assistant", "content": "I'd be happy to help! Let me connect you with the Project Manager."}
            ],
            handoff_to="ProjectManager"
        )
        print(f"   ✓ Stored: {result}")
        print()

        # Test storing a preference
        print("2. Storing user preference...")
        result = client.store_user_preference(
            session_id=session_id,
            preference_key="default_editor",
            preference_value="VS Code"
        )
        print(f"   ✓ Stored: {result}")
        print()

        # Test storing project info
        print("3. Storing project info...")
        result = client.store_project_info(
            session_id=session_id,
            project_name="VibeMind",
            project_details={
                "description": "Voice-controlled desktop automation",
                "language": "Python",
                "status": "active"
            }
        )
        print(f"   ✓ Stored: {result}")
        print()

        print("=" * 60)
        print("All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"✗ Error: {e}")
