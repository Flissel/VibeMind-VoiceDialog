"""
Test-Skript: Inhalte der "Multiversum" bubble aus der Datenbank auslesen und als DataFrame anzeigen
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Import repositories
from data import IdeasRepository, CanvasRepository
import pandas as pd


def main():
    """Hauptfunktion zum Auslesen der Multiversum bubble Inhalte."""
    print("=" * 80)
    print("Multiversum Bubble Inhalte auslesen")
    print("=" * 80)
    
    # Repositories initialisieren
    ideas_repo = IdeasRepository()
    canvas_repo = CanvasRepository()
    
    # Alle Bubbles auflisten
    print("\n[INFO] Alle Bubbles auflisten...")
    all_bubbles = ideas_repo.list(limit=100)
    print(f"[OK] {len(all_bubbles)} Bubbles gefunden")
    
    # Nach "Multiversum" Bubble suchen
    print("\n[INFO] Suche nach 'Multiversum' Bubble...")
    multiverseum_bubble = None
    
    # 1. Exakte Suche
    multiverseum_bubble = ideas_repo.get_by_title("Multiversum")
    
    # 2. Fuzzy-Suche
    if not multiverseum_bubble:
        multiverseum_bubble = ideas_repo.get_by_title_fuzzy("Multiversum")
    
    if not multiverseum_bubble:
        print("[ERROR] Keine 'Multiversum' Bubble gefunden!")
        print("\n[INFO] Verfuegbare Bubbles:")
        for i, bubble in enumerate(all_bubbles[:10], 1):
            print(f"  {i}. {bubble.title} (ID: {bubble.id})")
        return
    
    print(f"[OK] 'Multiversum' Bubble gefunden: {multiverseum_bubble.title} (ID: {multiverseum_bubble.id})")
    
    # CanvasNodes fuer diese Bubble auslesen
    print(f"\n[INFO] CanvasNodes fuer Bubble '{multiverseum_bubble.title}' auslesen...")
    all_nodes = canvas_repo.list_nodes(limit=1000)
    bubble_nodes = [n for n in all_nodes if n.linked_idea_id == multiverseum_bubble.id]
    print(f"[OK] {len(bubble_nodes)} CanvasNodes gefunden")
    
    # CanvasEdges fuer diese Bubble auslesen
    print(f"\n[INFO] CanvasEdges fuer Bubble '{multiverseum_bubble.title}' auslesen...")
    all_edges = canvas_repo.list_edges(limit=1000)
    node_ids = {n.id for n in bubble_nodes}
    bubble_edges = [e for e in all_edges if e.from_node_id in node_ids or e.to_node_id in node_ids]
    print(f"[OK] {len(bubble_edges)} CanvasEdges gefunden")
    
    # DataFrame fuer Bubble erstellen
    print(f"\n[INFO] DataFrame fuer Bubble erstellen...")
    bubble_data = {
        "id": multiverseum_bubble.id,
        "title": multiverseum_bubble.title,
        "description": multiverseum_bubble.description,
        "score": multiverseum_bubble.score,
        "status": multiverseum_bubble.status,
        "created_at": multiverseum_bubble.created_at,
        "node_count": len(bubble_nodes),
        "edge_count": len(bubble_edges)
    }
    bubble_df = pd.DataFrame([bubble_data])
    print("[OK] Bubble DataFrame erstellt")
    
    # DataFrame fuer CanvasNodes erstellen
    print(f"\n[INFO] DataFrame fuer CanvasNodes erstellen...")
    nodes_data = []
    for node in bubble_nodes:
        nodes_data.append({
            "id": node.id,
            "node_type": node.node_type,
            "title": node.title,
            "content": node.content,
            "x": node.x,
            "y": node.y,
            "linked_idea_id": node.linked_idea_id,
            "linked_project_id": node.linked_project_id,
            "summary": node.summary
        })
    nodes_df = pd.DataFrame(nodes_data)
    print(f"[OK] CanvasNodes DataFrame erstellt ({len(nodes_df)} Zeilen)")
    
    # DataFrame fuer CanvasEdges erstellen
    print(f"\n[INFO] DataFrame fuer CanvasEdges erstellen...")
    edges_data = []
    for edge in bubble_edges:
        edges_data.append({
            "id": edge.id,
            "from_node_id": edge.from_node_id,
            "to_node_id": edge.to_node_id,
            "edge_type": edge.edge_type
        })
    edges_df = pd.DataFrame(edges_data)
    print(f"[OK] CanvasEdges DataFrame erstellt ({len(edges_df)} Zeilen)")
    
    # Zusammenfassung
    print("\n" + "=" * 80)
    print("Zusammenfassung")
    print("=" * 80)
    print(f"\nBubble: {multiverseum_bubble.title}")
    print(f"  - ID: {multiverseum_bubble.id}")
    print(f"  - Score: {multiverseum_bubble.score:.0f}")
    print(f"  - Status: {multiverseum_bubble.status}")
    print(f"  - Beschreibung: {multiverseum_bubble.description}")
    print(f"  - Erstellt am: {multiverseum_bubble.created_at}")
    print(f"  - Anzahl CanvasNodes: {len(bubble_nodes)}")
    print(f"  - Anzahl CanvasEdges: {len(bubble_edges)}")
    
    # DataFrames anzeigen
    print("\n" + "=" * 80)
    print("Bubble DataFrame")
    print("=" * 80)
    print(bubble_df.to_string(index=False))
    
    print("\n" + "=" * 80)
    print("CanvasNodes DataFrame")
    print("=" * 80)
    print(nodes_df.to_string(index=False))
    
    print("\n" + "=" * 80)
    print("CanvasEdges DataFrame")
    print("=" * 80)
    print(edges_df.to_string(index=False))
    
    # Statistiken
    print("\n" + "=" * 80)
    print("Statistiken")
    print("=" * 80)
    print(f"\nGesamtzahl aller Bubbles: {len(all_bubbles)}")
    print(f"Anzahl CanvasNodes in 'Multiversum': {len(bubble_nodes)}")
    print(f"Anzahl CanvasEdges in 'Multiversum': {len(bubble_edges)}")
    
    # Node-Typen
    node_types = {}
    for node in bubble_nodes:
        node_type = node.node_type or "unknown"
        node_types[node_type] = node_types.get(node_type, 0) + 1
    print(f"\nNode-Typen:")
    for node_type, count in sorted(node_types.items()):
        print(f"  - {node_type}: {count}")
    
    # Edge-Typen
    edge_types = {}
    for edge in bubble_edges:
        edge_type = edge.edge_type or "unknown"
        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
    print(f"\nEdge-Typen:")
    for edge_type, count in sorted(edge_types.items()):
        print(f"  - {edge_type}: {count}")
    
    print("\n[OK] Skript erfolgreich abgeschlossen")


if __name__ == "__main__":
    main()
