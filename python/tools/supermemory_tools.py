"""
SuperMemory Tools for Voice Integration

Provides voice-callable tools for storing and retrieving context
from SuperMemory AI. Used for persistent memory across sessions.

Tools:
- search_memory: Semantic search in stored memories
- store_to_supermemory: Store important information for later recall
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.supermemory_client import SupermemoryClient

# Singleton client instance
_supermemory_client: Optional[SupermemoryClient] = None

# Session ID for current conversation (set externally)
_current_session_id: Optional[str] = None


def _get_client() -> Optional[SupermemoryClient]:
    """Get or create SuperMemory client."""
    global _supermemory_client
    
    if _supermemory_client is None:
        try:
            _supermemory_client = SupermemoryClient()
            logger.info("SuperMemory client initialized")
        except ValueError as e:
            logger.warning(f"SuperMemory not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize SuperMemory: {e}")
            return None
    
    return _supermemory_client


def get_session_id() -> str:
    """Get current session ID, creating one if needed."""
    global _current_session_id
    
    if _current_session_id is None:
        import uuid
        _current_session_id = str(uuid.uuid4())
        logger.info(f"Created new session ID: {_current_session_id}")
    
    return _current_session_id


def set_session_id(session_id: str):
    """Set the current session ID (called by voice_dialog_main)."""
    global _current_session_id
    _current_session_id = session_id
    logger.info(f"Session ID set to: {session_id}")


# =============================================================================
# SUPERMEMORY TOOLS
# =============================================================================

def search_memory(params: Dict[str, Any]) -> str:
    """
    Search SuperMemory for relevant context based on a query.
    
    Uses semantic search to find memories related to the query.
    Returns relevant information from past conversations.
    
    Voice triggers: 
    - "Was weißt du noch über...?"
    - "Erinnere dich an..."
    - "Was haben wir über ... besprochen?"
    - "Suche nach Informationen über..."
    
    Args (via params):
        query: What to search for (required)
        limit: Maximum results to return (default: 5)
    
    Returns:
        str: Formatted search results or error message
    """
    query = params.get("query", "").strip()
    limit = params.get("limit", 5)
    
    logger.info(f"search_memory called with query: '{query}', limit: {limit}")
    
    if not query:
        return "What should I search for in my memories?"
    
    client = _get_client()
    if not client:
        return "SuperMemory not configured. Set SUPERMEMORY_API_KEY in .env."
    
    session_id = get_session_id()
    
    try:
        results = client.retrieve_context(
            session_id=session_id,
            query=query,
            limit=limit
        )
        
        if not results:
            logger.info(f"No memories found for query: '{query}'")
            return f"No memories found for '{query}'."
        
        # Format results for voice response
        memories = []
        for i, result in enumerate(results[:limit], 1):
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            
            # Truncate long content for voice
            if len(content) > 200:
                content = content[:200] + "..."
            
            memory_type = metadata.get("type", "memory")
            memories.append(f"{i}. {content}")
        
        result_text = f"I found {len(memories)} memories: " + " ".join(memories)
        logger.info(f"Found {len(memories)} memories for query: '{query}'")
        
        return result_text
        
    except Exception as e:
        logger.error(f"Error searching memory: {e}")
        return f"Search error: {str(e)}"


def store_to_supermemory(params: Dict[str, Any]) -> str:
    """
    Store important information in SuperMemory for later recall.
    
    Use this to remember facts, preferences, or important context
    that should persist across conversations.
    
    Voice triggers:
    - "Merke dir dass..."
    - "Speichere dass..."
    - "Erinnere dich dass ich..."
    - "Notiere für später..."
    
    Args (via params):
        content: The information to store (required)
        category: Optional category (preference, fact, project, note)
    
    Returns:
        str: Confirmation message
    """
    content = params.get("content", "").strip()
    category = params.get("category", "note").strip()
    
    logger.info(f"store_to_supermemory called with content: '{content[:50]}...', category: '{category}'")
    
    if not content:
        return "What should I remember?"
    
    client = _get_client()
    if not client:
        return "SuperMemory not configured. Set SUPERMEMORY_API_KEY in .env."
    
    session_id = get_session_id()
    
    try:
        # Build metadata
        metadata = {
            "type": category,
            "session_id": session_id,
            "source": "voice"
        }
        
        # Add category-specific handling
        if category == "preference":
            metadata["type"] = "user_preference"
        elif category == "project":
            metadata["type"] = "project"
        elif category == "fact":
            metadata["type"] = "fact"
        
        result = client.store_memory(
            content=content,
            metadata=metadata
        )
        
        memory_id = result.get("id", "unknown")
        logger.info(f"Stored memory: {memory_id}")
        
        return f"I remembered: {content[:100]}{'...' if len(content) > 100 else ''}"
        
    except Exception as e:
        logger.error(f"Error storing memory: {e}")
        return f"Error saving: {str(e)}"


def recall_conversation(params: Dict[str, Any]) -> str:
    """
    Recall the conversation history from the current session.
    
    Voice triggers:
    - "Was haben wir bisher besprochen?"
    - "Zusammenfassung unseres Gesprächs"
    - "Worüber haben wir geredet?"
    
    Returns:
        str: Summary of conversation history
    """
    client = _get_client()
    if not client:
        return "SuperMemory not configured."
    
    session_id = get_session_id()
    
    try:
        history = client.get_conversation_history(session_id)
        
        if not history:
            return "We haven't discussed much in this session yet."
        
        # Summarize history
        topics = []
        for item in history[:5]:
            metadata = item.get("metadata", {})
            agent = metadata.get("agent", "")
            if agent:
                topics.append(f"With {agent}")

        if topics:
            return f"In this session: {', '.join(set(topics))}. Total {len(history)} interactions."
        else:
            return f"We have {len(history)} interactions in this session."
            
    except Exception as e:
        logger.error(f"Error recalling conversation: {e}")
        return f"Error fetching history: {str(e)}"


def clear_session_memory(params: Dict[str, Any]) -> str:
    """
    Start a fresh session (creates new session ID).
    
    Voice triggers:
    - "Vergiss diese Session"
    - "Starte neue Session"
    - "Reset Kontext"
    
    Returns:
        str: Confirmation message
    """
    global _current_session_id
    
    old_session = _current_session_id
    _current_session_id = None
    
    # Get new session ID
    new_session = get_session_id()
    
    logger.info(f"Cleared session {old_session}, new session: {new_session}")
    
    return "New session started. Local context has been reset."


# =============================================================================
# TOOL REGISTRY
# =============================================================================

SUPERMEMORY_TOOLS = {
    "search_memory": search_memory,
    "store_to_supermemory": store_to_supermemory,
    "recall_conversation": recall_conversation,
    "clear_session_memory": clear_session_memory,
}


def register_supermemory_tools(tools_manager) -> None:
    """Register all SuperMemory tools with the tools manager."""
    print("Registering SuperMemory tools...")
    for tool_name, tool_func in SUPERMEMORY_TOOLS.items():
        tools_manager.register_with_observer(tool_name, tool_func)
        print(f"  - {tool_name}")


__all__ = [
    "search_memory",
    "store_to_supermemory", 
    "recall_conversation",
    "clear_session_memory",
    "set_session_id",
    "get_session_id",
    "SUPERMEMORY_TOOLS",
    "register_supermemory_tools",
]