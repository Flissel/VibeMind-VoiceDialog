"""
Transcript Manager for VibeMind Swarm

Manages conversation transcripts for context-aware planning and analysis.
Provides memory and context for intelligent task planning.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


class TranscriptManager:
    """
    Manages conversation transcripts and provides context for planning.

    Stores conversation history and provides intelligent analysis
    for task planning and execution.
    """

    def __init__(self, max_entries: int = 1000, retention_hours: int = 24):
        self.transcript: List[Dict[str, Any]] = []
        self.max_entries = max_entries
        self.retention_hours = retention_hours
        self._initialized = False

    async def initialize(self):
        """Initialize the transcript manager."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("Transcript manager initialized")

    def add_entry(self, entry_type: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add an entry to the transcript.

        Args:
            entry_type: Type of entry ('user_input', 'agent_response', 'system_event', etc.)
            content: The content of the entry
            metadata: Optional metadata (agent_name, timestamp, etc.)
        """
        entry = {
            'id': len(self.transcript),
            'timestamp': datetime.now().isoformat(),
            'type': entry_type,
            'content': content,
            'metadata': metadata or {}
        }

        self.transcript.append(entry)

        # Maintain size limit
        if len(self.transcript) > self.max_entries:
            self.transcript = self.transcript[-self.max_entries:]

        # Clean old entries
        self._cleanup_old_entries()

        logger.debug(f"Added transcript entry: {entry_type} ({len(content)} chars)")

    def _cleanup_old_entries(self):
        """Remove entries older than retention period."""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        self.transcript = [
            entry for entry in self.transcript
            if datetime.fromisoformat(entry['timestamp']) > cutoff_time
        ]

    def get_recent_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent transcript entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent entries (newest first)
        """
        return self.transcript[-limit:]

    def get_entries_by_type(self, entry_type: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get entries of a specific type.

        Args:
            entry_type: Type of entries to retrieve
            limit: Maximum number of entries

        Returns:
            Filtered entries
        """
        filtered = [entry for entry in self.transcript if entry['type'] == entry_type]
        return filtered[-limit:]

    def get_conversation_context(self, current_topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Get conversation context for planning.

        Args:
            current_topic: Optional current topic for context filtering

        Returns:
            Context dictionary with relevant information
        """
        context = {
            'total_entries': len(self.transcript),
            'time_range': self._get_time_range(),
            'recent_activity': self.get_recent_entries(10),
            'user_inputs': self.get_entries_by_type('user_input', 20),
            'agent_responses': self.get_entries_by_type('agent_response', 20),
            'system_events': self.get_entries_by_type('system_event', 10),
            'current_topic': current_topic,
            'conversation_summary': self._generate_conversation_summary()
        }

        return context

    def _get_time_range(self) -> Dict[str, str]:
        """Get the time range of the transcript."""
        if not self.transcript:
            return {'start': None, 'end': None}

        timestamps = [datetime.fromisoformat(entry['timestamp']) for entry in self.transcript]
        return {
            'start': min(timestamps).isoformat(),
            'end': max(timestamps).isoformat()
        }

    def _generate_conversation_summary(self) -> str:
        """Generate a summary of the conversation."""
        if not self.transcript:
            return "No conversation history available."

        # Count different types
        type_counts = {}
        for entry in self.transcript:
            entry_type = entry['type']
            type_counts[entry_type] = type_counts.get(entry_type, 0) + 1

        # Get recent activity
        recent = self.get_recent_entries(5)
        recent_summary = []
        for entry in recent:
            if entry['type'] in ['user_input', 'agent_response']:
                content_preview = entry['content'][:50] + "..." if len(entry['content']) > 50 else entry['content']
                recent_summary.append(f"{entry['type']}: {content_preview}")

        summary = f"Conversation with {type_counts.get('user_input', 0)} user inputs, "
        summary += f"{type_counts.get('agent_response', 0)} agent responses. "
        summary += f"Recent activity: {'; '.join(recent_summary)}"

        return summary

    def search_transcript(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search the transcript for specific content.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Matching entries
        """
        query_lower = query.lower()
        matches = []

        for entry in reversed(self.transcript):  # Search from most recent
            content_lower = entry['content'].lower()
            if query_lower in content_lower:
                matches.append(entry)
                if len(matches) >= limit:
                    break

        return matches

    def get_topic_context(self, topic: str) -> Dict[str, Any]:
        """
        Get context specifically about a topic.

        Args:
            topic: Topic to analyze

        Returns:
            Topic-specific context
        """
        # Search for topic-related entries
        topic_entries = self.search_transcript(topic, 50)

        # Analyze topic mentions
        topic_context = {
            'topic': topic,
            'total_mentions': len(topic_entries),
            'first_mention': topic_entries[0]['timestamp'] if topic_entries else None,
            'last_mention': topic_entries[-1]['timestamp'] if topic_entries else None,
            'related_entries': topic_entries,
            'topic_evolution': self._analyze_topic_evolution(topic_entries)
        }

        return topic_context

    def _analyze_topic_evolution(self, topic_entries: List[Dict[str, Any]]) -> List[str]:
        """
        Analyze how a topic has evolved in the conversation.

        Args:
            topic_entries: Entries related to the topic

        Returns:
            List of evolution insights
        """
        if len(topic_entries) < 2:
            return ["Topic mentioned but limited evolution data"]

        insights = []

        # Check for progression in understanding
        user_inputs = [e for e in topic_entries if e['type'] == 'user_input']
        agent_responses = [e for e in topic_entries if e['type'] == 'agent_response']

        if len(user_inputs) > 1:
            insights.append(f"User has refined understanding from {len(user_inputs)} inputs")

        if len(agent_responses) > 1:
            insights.append(f"System has provided {len(agent_responses)} responses on this topic")

        # Check for time progression
        if len(topic_entries) > 1:
            time_span = datetime.fromisoformat(topic_entries[-1]['timestamp']) - datetime.fromisoformat(topic_entries[0]['timestamp'])
            insights.append(f"Topic discussed over {time_span.total_seconds()/60:.1f} minutes")

        return insights

    def export_transcript(self, format: str = 'json') -> str:
        """
        Export the transcript in different formats.

        Args:
            format: Export format ('json', 'text', 'markdown')

        Returns:
            Formatted transcript
        """
        if format == 'json':
            return json.dumps(self.transcript, indent=2, ensure_ascii=False)
        elif format == 'text':
            lines = []
            for entry in self.transcript:
                timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%H:%M:%S')
                lines.append(f"[{timestamp}] {entry['type'].upper()}: {entry['content']}")
            return '\n'.join(lines)
        elif format == 'markdown':
            lines = ['# Conversation Transcript\n']
            for entry in self.transcript:
                timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                lines.append(f"## {entry['type'].title()} ({timestamp})\n")
                lines.append(f"{entry['content']}\n")
            return '\n'.join(lines)
        else:
            return "Unsupported format"

    def clear_transcript(self):
        """Clear all transcript entries."""
        self.transcript.clear()
        logger.info("Transcript cleared")


# Global transcript manager instance
_transcript_manager = None

async def get_transcript_manager() -> TranscriptManager:
    """Get the global transcript manager instance."""
    global _transcript_manager
    if _transcript_manager is None:
        _transcript_manager = TranscriptManager()
        await _transcript_manager.initialize()
    return _transcript_manager

# Convenience functions for easy integration
async def add_transcript_entry(entry_type: str, content: str, metadata: Optional[Dict[str, Any]] = None):
    """Add an entry to the transcript."""
    manager = await get_transcript_manager()
    manager.add_entry(entry_type, content, metadata)

async def get_conversation_context(current_topic: Optional[str] = None) -> Dict[str, Any]:
    """Get conversation context for planning."""
    manager = await get_transcript_manager()
    return manager.get_conversation_context(current_topic)

async def search_transcript(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search the transcript."""
    manager = await get_transcript_manager()
    return manager.search_transcript(query, limit)


__all__ = [
    "TranscriptManager",
    "get_transcript_manager",
    "add_transcript_entry",
    "get_conversation_context",
    "search_transcript",
]