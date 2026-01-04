"""
Memory Tools für Desktop Automation

Speichert und ruft Befehlshistorie und häufige Kommandos ab.
Nutzt Supermemory für persistente Speicherung.

Tools:
1. store_command_history - Speichert einen Befehl mit Kontext
2. get_frequent_commands - Ruft häufig verwendete Befehle ab
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from collections import Counter
import os

logger = logging.getLogger(__name__)

# Module-level command store (Fallback wenn Supermemory nicht verfügbar)
_command_history: List[Dict[str, Any]] = []
_command_counter: Counter = Counter()


@dataclass
class CommandRecord:
    """Ein gespeicherter Befehl."""
    command: str
    app_context: str
    timestamp: float
    success: bool
    tags: List[str]
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "app_context": self.app_context,
            "timestamp": self.timestamp,
            "success": self.success,
            "tags": self.tags,
            "metadata": self.metadata
        }


def _get_supermemory_client():
    """Versucht den SupermemoryClient zu importieren."""
    try:
        from memory.supermemory_client import SupermemoryClient
        api_key = os.getenv("SUPERMEMORY_API_KEY")
        if api_key:
            return SupermemoryClient(api_key)
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Supermemory init failed: {e}")
    return None


async def store_command_history(
    command: str,
    app_context: str = "desktop",
    success: bool = True,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Speichert einen ausgeführten Befehl in der Historie.
    
    Wird verwendet um häufige Befehle zu lernen und 
    Vorschläge zu verbessern.
    
    Args:
        command: Der ausgeführte Befehl (z.B. "Öffne Chrome")
        app_context: App-Kontext (z.B. "chrome", "word", "desktop")
        success: War der Befehl erfolgreich?
        tags: Optional - Tags für Kategorisierung
        metadata: Optional - Zusätzliche Daten
    
    Returns:
        Dict mit Bestätigung
    """
    try:
        record = CommandRecord(
            command=command,
            app_context=app_context.lower(),
            timestamp=time.time(),
            success=success,
            tags=tags or [],
            metadata=metadata
        )
        
        # In lokalen Store
        _command_history.append(record.to_dict())
        if success:
            _command_counter[command.lower()] += 1
        
        # Versuche Supermemory
        client = _get_supermemory_client()
        if client:
            try:
                # Als Memory speichern
                memory_content = f"Desktop Command: {command}\nApp: {app_context}\nSuccess: {success}"
                if tags:
                    memory_content += f"\nTags: {', '.join(tags)}"
                
                await client.add_memory(
                    content=memory_content,
                    metadata={
                        "type": "command_history",
                        "command": command,
                        "app": app_context,
                        "success": success,
                        "tags": tags or [],
                        **( metadata or {})
                    }
                )
                storage = "supermemory"
            except Exception as e:
                logger.warning(f"Supermemory store failed: {e}")
                storage = "local"
        else:
            storage = "local"
        
        # Historie trimmen wenn zu groß
        if len(_command_history) > 1000:
            _command_history[:] = _command_history[-500:]
        
        logger.info(f"Command stored ({storage}): {command[:50]}...")
        
        return {
            "success": True,
            "message": f"Befehl gespeichert in {storage}",
            "command": command,
            "storage": storage,
            "history_size": len(_command_history)
        }
        
    except Exception as e:
        logger.error(f"store_command_history failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def get_frequent_commands(
    app_context: Optional[str] = None,
    limit: int = 10,
    include_recent: bool = True
) -> Dict[str, Any]:
    """
    Ruft häufig verwendete Befehle ab.
    
    Nützlich für Vorschläge und Autocompletion.
    
    Args:
        app_context: Optional - Filter für bestimmte App
        limit: Maximale Anzahl (default: 10)
        include_recent: Die letzten 5 Befehle einschließen?
    
    Returns:
        Dict mit Befehlsliste
    """
    try:
        frequent = []
        recent = []
        
        # Versuche Supermemory
        client = _get_supermemory_client()
        if client:
            try:
                # Query für häufige Commands
                query = "desktop commands"
                if app_context:
                    query = f"{app_context} commands"
                
                results = await client.search_memories(
                    query=query,
                    limit=limit * 2,
                    metadata_filter={"type": "command_history"}
                )
                
                # Parse results
                if results:
                    for r in results:
                        if hasattr(r, 'metadata') and r.metadata:
                            cmd = r.metadata.get('command', '')
                            if cmd and (not app_context or 
                                       r.metadata.get('app', '').lower() == app_context.lower()):
                                frequent.append({
                                    "command": cmd,
                                    "app": r.metadata.get('app', ''),
                                    "success": r.metadata.get('success', True),
                                    "source": "supermemory"
                                })
            except Exception as e:
                logger.warning(f"Supermemory search failed: {e}")
        
        # Lokale Daten ergänzen
        if len(frequent) < limit:
            # Häufigste aus Counter
            for cmd, count in _command_counter.most_common(limit):
                if not any(f['command'].lower() == cmd for f in frequent):
                    frequent.append({
                        "command": cmd,
                        "count": count,
                        "source": "local"
                    })
        
        # Nach App filtern wenn gewünscht
        if app_context:
            app_lower = app_context.lower()
            filtered_history = [
                h for h in _command_history 
                if h.get('app_context', '').lower() == app_lower
            ]
        else:
            filtered_history = _command_history
        
        # Letzte Befehle
        if include_recent and filtered_history:
            recent = filtered_history[-5:][::-1]  # Neueste zuerst
        
        # Limits anwenden
        frequent = frequent[:limit]
        
        return {
            "success": True,
            "frequent": frequent,
            "recent": recent if include_recent else [],
            "total_commands": len(_command_history),
            "unique_commands": len(_command_counter),
            "app_filter": app_context
        }
        
    except Exception as e:
        logger.error(f"get_frequent_commands failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "frequent": [],
            "recent": []
        }


async def get_command_suggestions(
    partial_command: str,
    app_context: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Gibt Befehlsvorschläge basierend auf Teileingabe.
    
    Args:
        partial_command: Beginn des Befehls
        app_context: Optional - App-Kontext
        limit: Max Vorschläge
    
    Returns:
        Dict mit Vorschlägen
    """
    try:
        partial_lower = partial_command.lower()
        suggestions = []
        
        # Aus Counter
        for cmd, count in _command_counter.most_common(100):
            if cmd.startswith(partial_lower) or partial_lower in cmd:
                suggestions.append({
                    "command": cmd,
                    "count": count,
                    "match_type": "prefix" if cmd.startswith(partial_lower) else "contains"
                })
                if len(suggestions) >= limit:
                    break
        
        # Sortieren: Prefix-Matches zuerst, dann nach Count
        suggestions.sort(key=lambda x: (x['match_type'] != 'prefix', -x['count']))
        
        return {
            "success": True,
            "suggestions": suggestions[:limit],
            "partial": partial_command
        }
        
    except Exception as e:
        logger.error(f"get_command_suggestions failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "suggestions": []
        }


# =============================================================================
# TOOL DEFINITIONS for ElevenLabs
# =============================================================================

MEMORY_TOOLS = [
    {
        "name": "store_command_history",
        "description": "Speichert einen ausgeführten Desktop-Befehl für spätere Vorschläge. Hilft zu lernen welche Befehle der Nutzer häufig verwendet.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Der ausgeführte Befehl (z.B. 'Öffne Chrome')"
                },
                "app_context": {
                    "type": "string",
                    "description": "App-Kontext: desktop, chrome, word, excel, etc.",
                    "default": "desktop"
                },
                "success": {
                    "type": "boolean",
                    "description": "War der Befehl erfolgreich?",
                    "default": True
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags für Kategorisierung"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "get_frequent_commands",
        "description": "Ruft häufig verwendete Befehle ab. Nützlich um dem Nutzer Vorschläge zu machen.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_context": {
                    "type": "string",
                    "description": "Filter für bestimmte App (optional)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximale Anzahl",
                    "default": 10
                },
                "include_recent": {
                    "type": "boolean",
                    "description": "Die letzten 5 Befehle einschließen?",
                    "default": True
                }
            },
            "required": []
        }
    }
]


# =============================================================================
# REGISTRATION
# =============================================================================

def register_memory_tools(tools_manager) -> None:
    """Registriert Memory Tools im ClientToolsManager."""
    print("Registering memory tools...")
    
    def store_history_wrapper(params):
        return _run_async(store_command_history(
            params.get("command", ""),
            params.get("app_context", "desktop"),
            params.get("success", True),
            params.get("tags"),
            params.get("metadata")
        ))
    
    def get_frequent_wrapper(params):
        return _run_async(get_frequent_commands(
            params.get("app_context"),
            params.get("limit", 10),
            params.get("include_recent", True)
        ))
    
    def get_suggestions_wrapper(params):
        return _run_async(get_command_suggestions(
            params.get("partial_command", ""),
            params.get("app_context"),
            params.get("limit", 5)
        ))
    
    tools_manager.register_with_observer("store_command_history", store_history_wrapper)
    tools_manager.register_with_observer("get_frequent_commands", get_frequent_wrapper)
    tools_manager.register_with_observer("get_command_suggestions", get_suggestions_wrapper)
    
    print("Memory tools registered (3 tools)")


def _run_async(coro):
    """Helper um async functions synchron auszuführen."""
    import concurrent.futures
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return asyncio.run(coro)
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "store_command_history",
    "get_frequent_commands",
    "get_command_suggestions",
    "MEMORY_TOOLS",
    "register_memory_tools",
    "CommandRecord"
]
