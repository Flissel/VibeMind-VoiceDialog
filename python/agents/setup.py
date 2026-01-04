"""
Agent Setup Script

Wird beim App-Start ausgeführt um:
1. Feste Spaces für Adam und Antoni zu erstellen (falls nicht vorhanden)
2. ElevenLabs Agenten mit den richtigen Tools zu konfigurieren
"""

import os
import sys
from pathlib import Path
from typing import Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Füge parent directory zu path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import get_registry, AgentInfo
from data import IdeasRepository


def create_fixed_spaces():
    """
    Erstelle feste Spaces für Agenten die welche benötigen.
    (Adam Desktop, Antoni Workshop)
    """
    registry = get_registry()
    ideas_repo = IdeasRepository()
    
    agents_with_spaces = registry.get_agents_with_fixed_space()
    
    for agent in agents_with_spaces:
        space_name = agent.space_name
        if not space_name:
            continue
        
        # Prüfe ob Space bereits existiert
        existing = ideas_repo.get_by_title(space_name)
        if existing:
            logger.info(f"Space '{space_name}' für {agent.name} existiert bereits (ID: {existing.id})")
            continue
        
        # Erstelle neuen Space
        idea = ideas_repo.create(
            title=space_name,
            description=f"Fester Arbeitsbereich für {agent.name}",
            source="system"
        )
        
        # Verknüpfe mit Agent-ID falls vorhanden
        agent_id = registry.get_agent_id(agent.slug)
        if agent_id:
            idea.agent_id = agent_id
            ideas_repo.update(idea)
        
        logger.info(f"Space '{space_name}' für {agent.name} erstellt (ID: {idea.id})")
    
    return True


def setup_agents():
    """
    Hauptsetup-Funktion - wird beim App-Start aufgerufen.
    """
    logger.info("="*50)
    logger.info("Agent Setup gestartet")
    logger.info("="*50)
    
    # 1. Feste Spaces erstellen
    logger.info("\n1. Erstelle feste Spaces...")
    create_fixed_spaces()
    
    # 2. Agent-Registry laden und prüfen
    logger.info("\n2. Prüfe Agent-Konfiguration...")
    registry = get_registry()
    
    for agent in registry.get_all():
        agent_id = registry.get_agent_id(agent.slug)
        status = "✓ OK" if agent_id else "✗ FEHLT"
        logger.info(f"   {agent.name}: {status}")
        if not agent_id:
            env_var = f"{agent.slug.upper()}_AGENT_ID"
            logger.warning(f"      → Setze {env_var} in .env")
    
    # 3. Entry-Agent prüfen
    entry = registry.get_entry_agent()
    if entry:
        logger.info(f"\n3. Entry-Agent: {entry.name}")
    else:
        logger.error("\n3. FEHLER: Kein Entry-Agent gefunden!")
    
    logger.info("\n" + "="*50)
    logger.info("Agent Setup abgeschlossen")
    logger.info("="*50)
    
    return True


if __name__ == "__main__":
    setup_agents()