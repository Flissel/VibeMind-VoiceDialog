#!/usr/bin/env python3
"""
Test-Skript für AutoGen-basiertes Multi-Agenten-Research-System

Testet die AutoGen-Funktionen:
1. conduct_autogen_research - Führe komplette Forschung durch
2. start_autogen_host - Starte den Host Service
3. stop_autogen_host - Stoppe den Host Service
"""

import asyncio
import sys
import os
from pathlib import Path

# Füge python zum Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Lade .env Datei (aus Projekt-Root-Verzeichnis)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
    print(f".env Datei geladen von: {env_path}")
else:
    print(f"Warnung: .env Datei nicht gefunden unter: {env_path}")

from spaces.ideas.tools.autogen_research import (
    conduct_autogen_research,
    start_autogen_host,
    stop_autogen_host,
)


async def test_conduct_research():
    """Teste die conduct_autogen_research Funktion."""
    print("=" * 80)
    print("TEST: conduct_autogen_research")
    print("=" * 80)
    
    topic = "Multiversum: Advanced AI Agent Orchestration Framework"
    requirements = [
        "Event-Bus Architektur",
        "Agenten-Kommunikation",
        "Koordinations-Mechanismen",
        "Performance-Anforderungen (< 50ms Latenz)",
        "Skalierbarkeit (bis zu 10 Agenten)",
    ]
    
    try:
        result = await conduct_autogen_research(
            topic=topic,
            requirements=requirements,
            language="de",
            max_concurrent_workers=3,
        )
        
        print(f"\nResult: {result.get('success')}")
        print(f"Message: {result.get('message')}")
        
        if result.get("success"):
            print(f"\nAgent Count: {result.get('agent_count')}")
            print(f"Requirements: {result.get('requirements', {}).get('title', 'N/A')}")
            print(f"Paper: {result.get('paper', {}).get('title', 'N/A')}")
            print(f"Quality: {result.get('quality_report', {}).get('overall_score', 'N/A')}")
        else:
            print(f"\nError: {result.get('message')}")
        
        return result.get("success", False)
    
    except Exception as e:
        print(f"\nException: {e}")
        return False


async def test_host_operations():
    """Teste Host-Operationen."""
    print("\n" + "=" * 80)
    print("TEST: Host-Operationen")
    print("=" * 80)
    
    # Teste Start
    print("\n[TEST 1] Starte Host...")
    start_result = await start_autogen_host(address="localhost:50052")
    print(f"Start Result: {start_result}")
    
    # Warte kurz
    await asyncio.sleep(2)
    
    # Teste Stop
    print("\n[TEST 2] Stoppe Host...")
    stop_result = await stop_autogen_host()
    print(f"Stop Result: {stop_result}")
    
    return start_result.get("success", False) and stop_result.get("success", False)


async def main():
    """Hauptfunktion."""
    print("\n" + "=" * 80)
    print("AutoGen Research-System Test")
    print("=" * 80)
    print()
    
    # Teste Forschung
    print("\n[TEST 1] conduct_autogen_research...")
    research_success = await test_conduct_research()
    
    # Teste Host-Operationen
    print("\n[TEST 2] Host-Operationen...")
    host_success = await test_host_operations()
    
    # Zusammenfassung
    print("\n" + "=" * 80)
    print("TEST-ZUSAMMENFASSUNG")
    print("=" * 80)
    
    if research_success and host_success:
        print("\n[OK] Alle Tests erfolgreich!")
        print("\nDas AutoGen-System ist bereit für die Integration.")
    else:
        print("\n[FAIL] Einige Tests fehlgeschlagen.")
        print("\nBitte überprüfen Sie:")
        print("  1. AutoGen ist installiert?")
        print("  2. OPENROUTER_API_KEY ist gesetzt?")
        print("  3. TAVILY_API_KEY ist gesetzt (optional)?")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())
