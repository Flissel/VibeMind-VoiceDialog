#!/usr/bin/env python3
"""
Test-Skript für AutoGen-basiertes Multi-Agenten-Research-System
mit Multiversum-Content

Testet die AutoGen-Funktionen mit dem Multiversum-Content:
1. conduct_autogen_research - Führe komplette Forschung durch
2. Zeige die generierten Ergebnisse an
"""

import asyncio
import sys
import os
import json
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

from swarm.tools.autogen_research import (
    conduct_autogen_research,
    start_autogen_host,
    stop_autogen_host,
)


async def test_multiversum_research():
    """Teste die conduct_autogen_research Funktion mit Multiversum-Content."""
    print("=" * 80)
    print("TEST: Multiversum Research mit AutoGen")
    print("=" * 80)
    
    topic = "Multiversum: Advanced AI Agent Orchestration Framework"
    requirements = [
        "Event-Bus Architektur",
        "Agenten-Kommunikation",
        "Koordinations-Mechanismen",
        "Performance-Anforderungen (< 50ms Latenz)",
        "Skalierbarkeit (bis zu 10 Agenten)",
        "Multi-Agenten-Workflow",
        "State Management",
        "Error Handling und Recovery",
    ]
    
    try:
        print(f"\nTopic: {topic}")
        print(f"\nRequirements ({len(requirements)}):")
        for i, req in enumerate(requirements, 1):
            print(f"  {i}. {req}")
        
        print("\n" + "-" * 80)
        print("Starte AutoGen Research...")
        print("-" * 80)
        
        result = await conduct_autogen_research(
            topic=topic,
            requirements=requirements,
            language="de",
            max_concurrent_workers=5,
        )
        
        print("\n" + "-" * 80)
        print("Research-Ergebnisse:")
        print("-" * 80)
        
        print(f"\nSuccess: {result.get('success')}")
        print(f"Message: {result.get('message')}")
        
        if result.get("success"):
            print(f"\nAgent Count: {result.get('agent_count')}")
            
            # Requirements
            requirements_data = result.get('requirements', {})
            if requirements_data:
                print(f"\n{'=' * 80}")
                print("REQUIREMENTS")
                print('=' * 80)
                print(f"Title: {requirements_data.get('title', 'N/A')}")
                print(f"Content: {requirements_data.get('content', 'N/A')}")
                if 'features' in requirements_data:
                    print(f"\nFeatures ({len(requirements_data['features'])}):")
                    for i, feature in enumerate(requirements_data['features'], 1):
                        print(f"  {i}. {feature}")
            
            # Paper
            paper_data = result.get('paper', {})
            if paper_data:
                print(f"\n{'=' * 80}")
                print("RESEARCH PAPER")
                print('=' * 80)
                print(f"Title: {paper_data.get('title', 'N/A')}")
                print(f"Abstract: {paper_data.get('abstract', 'N/A')}")
                print(f"Content: {paper_data.get('content', 'N/A')}")
            
            # Quality Report
            quality_data = result.get('quality_report', {})
            if quality_data:
                print(f"\n{'=' * 80}")
                print("QUALITY REPORT")
                print('=' * 80)
                print(f"Overall Score: {quality_data.get('overall_score', 'N/A')}")
                print(f"Content: {quality_data.get('content', 'N/A')}")
                if 'criteria' in quality_data:
                    print(f"\nCriteria:")
                    for criterion, score in quality_data['criteria'].items():
                        print(f"  {criterion}: {score}")
            
            # Speichere Ergebnisse als JSON
            output_file = Path(__file__).parent / "multiversum_research_results.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n{'=' * 80}")
            print(f"Ergebnisse gespeichert in: {output_file}")
            print('=' * 80)
            
            return True
        else:
            print(f"\nError: {result.get('message')}")
            return False
    
    except Exception as e:
        print(f"\nException: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Hauptfunktion."""
    print("\n" + "=" * 80)
    print("Multiversum Research Test mit AutoGen")
    print("=" * 80)
    print()
    
    # Teste Forschung
    print("\n[TEST] conduct_autogen_research mit Multiversum-Content...")
    research_success = await test_multiversum_research()
    
    # Zusammenfassung
    print("\n" + "=" * 80)
    print("TEST-ZUSAMMENFASSUNG")
    print("=" * 80)
    
    if research_success:
        print("\n[OK] Multiversum Research erfolgreich!")
        print("\nDas AutoGen-System hat erfolgreich Forschungsergebnisse generiert.")
        print("Die Ergebnisse wurden in 'multiversum_research_results.json' gespeichert.")
    else:
        print("\n[FAIL] Multiversum Research fehlgeschlagen.")
        print("\nBitte überprüfen Sie:")
        print("  1. AutoGen ist installiert?")
        print("  2. OPENROUTER_API_KEY ist gesetzt?")
        print("  3. TAVILY_API_KEY ist gesetzt (optional)?")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())
