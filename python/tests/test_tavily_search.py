"""
Test-Skript für echte Web-Suche mit Tavily.

Dieses Skript testet die Tavily-Suche und zeigt, wie man echte Suchergebnisse erhält.
"""

import os
import asyncio
from dotenv import load_dotenv
from tavily import TavilyClient

# Lade Umgebungsvariablen
load_dotenv()

async def test_tavily_search():
    """Teste Tavily-Suche."""
    print("=" * 80)
    print("Test 11: Echte Web-Suche mit Tavily")
    print("=" * 80)
    
    # Hole Tavily API Key
    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_api_key:
        print("[ERROR] TAVILY_API_KEY nicht gesetzt")
        print("Bitte setze TAVILY_API_KEY in der .env Datei")
        return False
    
    print(f"[OK] TAVILY_API_KEY gefunden")
    
    # Erstelle Tavily Client
    client = TavilyClient(api_key=tavily_api_key)
    print(f"[OK] Tavily Client erstellt")
    
    # Teste einfache Suche
    print("\n" + "-" * 80)
    print("Teste einfache Suche...")
    print("-" * 80)
    
    query = "AutoGen Multi-Agenten-System"
    print(f"Query: {query}")
    
    try:
        result = client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_answer=True,
            include_raw_content=False,
        )
        
        print(f"\n[OK] Suche erfolgreich!")
        print(f"Anzahl der Ergebnisse: {len(result.get('results', []))}")
        
        # Zeige Antwort
        if 'answer' in result:
            print(f"\nAntwort: {result['answer']}")
        
        # Zeige Ergebnisse
        print("\nErgebnisse:")
        for i, item in enumerate(result.get('results', []), 1):
            print(f"\n{i}. {item.get('title', 'Kein Titel')}")
            print(f"   URL: {item.get('url', 'Keine URL')}")
            print(f"   Snippet: {item.get('content', 'Kein Inhalt')[:100]}...")
        
    except Exception as e:
        print(f"[ERROR] Suche fehlgeschlagen: {e}")
        return False
    
    # Teste erweiterte Suche
    print("\n" + "-" * 80)
    print("Teste erweiterte Suche...")
    print("-" * 80)
    
    query = "Event-Bus Architektur Microservices"
    print(f"Query: {query}")
    
    try:
        result = client.search(
            query=query,
            search_depth="advanced",
            max_results=10,
            include_answer=True,
            include_raw_content=False,
            include_domains=[],
            exclude_domains=[],
        )
        
        print(f"\n[OK] Erweiterte Suche erfolgreich!")
        print(f"Anzahl der Ergebnisse: {len(result.get('results', []))}")
        
        # Zeige Antwort
        if 'answer' in result:
            print(f"\nAntwort: {result['answer']}")
        
        # Zeige Ergebnisse
        print("\nErgebnisse:")
        for i, item in enumerate(result.get('results', []), 1):
            print(f"\n{i}. {item.get('title', 'Kein Titel')}")
            print(f"   URL: {item.get('url', 'Keine URL')}")
            print(f"   Score: {item.get('score', 'N/A')}")
            print(f"   Snippet: {item.get('content', 'Kein Inhalt')[:100]}...")
        
    except Exception as e:
        print(f"[ERROR] Erweiterte Suche fehlgeschlagen: {e}")
        return False
    
    print("\n" + "=" * 80)
    print("[OK] Test 11 abgeschlossen: Echte Web-Suche mit Tavily erfolgreich!")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_tavily_search())
    exit(0 if success else 1)
