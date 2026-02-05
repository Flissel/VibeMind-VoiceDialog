"""
Bubble Requirements Tool

Dieses Tool verarbeitet die Inhalte einer Bubble und generiert Requirements für die Vorverarbeitung in einer Multi-Agenten-Anwendung.
"""

import json
import sys
import os
from typing import Dict, Any, List, Optional

# Füge das python Verzeichnis zum Pfad hinzu
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data import IdeasRepository, CanvasRepository


def process_bubble_requirements(bubble_id: str) -> Dict[str, Any]:
    """
    Verarbeite die Inhalte einer Bubble und generiere Requirements für die Vorverarbeitung.
    
    Args:
        bubble_id: ID der Bubble
        
    Returns:
        Dict mit den verarbeiteten Requirements und Metadaten
    """
    try:
        # Hole die Bubble
        ideas_repo = IdeasRepository()
        canvas_repo = CanvasRepository()
        
        bubble = ideas_repo.get(bubble_id)
        if not bubble:
            return {
                "error": f"Bubble {bubble_id} nicht gefunden",
                "status": "error"
            }
        
        # Hole alle Nodes für diese Bubble
        nodes = canvas_repo.list_nodes(limit=1000)
        bubble_nodes = [n for n in nodes if n.linked_idea_id == bubble_id]
        
        # Hole alle Edges für diese Bubble
        edges = canvas_repo.list_edges(limit=5000)
        bubble_edges = [e for e in edges if any([
            canvas_repo.get_node(e.from_node_id) and canvas_repo.get_node(e.from_node_id).linked_idea_id == bubble_id,
            canvas_repo.get_node(e.to_node_id) and canvas_repo.get_node(e.to_node_id).linked_idea_id == bubble_id
        ])]
        
        # Analysiere die Nodes
        node_data = []
        total_words = 0
        total_chars = 0
        
        for node in bubble_nodes:
            content = node.content or ""
            title = node.title or ""
            
            # Extrahiere verschiedene Elemente
            urls = [line.strip() for line in content.split('\n') if 'http' in line.lower()]
            images = [line.strip() for line in content.split('\n') if 'image' in line.lower() or 'img' in line.lower()]
            code_blocks = [line.strip() for line in content.split('\n') if '```' in line]
            
            # Extrahiere Konzepte
            concepts = []
            for word in (title + " " + content).split():
                if len(word) > 5 and word.isalpha():
                    concepts.append(word.lower())
            
            # Statistiken
            word_count = len(content.split())
            char_count = len(content)
            
            total_words += word_count
            total_chars += char_count
            
            node_data.append({
                "id": node.id,
                "node_type": node.node_type,
                "title": title,
                "word_count": word_count,
                "char_count": char_count,
                "url_count": len(urls),
                "image_count": len(images),
                "code_block_count": len(code_blocks),
                "concept_count": len(concepts),
                "urls": urls[:5],  # Top 5 URLs
                "images": images[:5],  # Top 5 Bilder
                "concepts": concepts[:10]  # Top 10 Konzepte
            })
        
        # Kategorisiere die Nodes
        categories = {}
        for node in bubble_nodes:
            node_type = node.node_type
            if node_type not in categories:
                categories[node_type] = []
            categories[node_type].append({
                "id": node.id,
                "title": node.title
            })
        
        # Top-Konzepte
        all_concepts = []
        for node in bubble_nodes:
            content = node.content or ""
            title = node.title or ""
            for word in (title + " " + content).split():
                if len(word) > 5 and word.isalpha():
                    all_concepts.append(word.lower())
        
        from collections import Counter
        concept_counts = Counter(all_concepts)
        top_concepts = [concept for concept, count in concept_counts.most_common(20)]
        
        # Top-URLs
        all_urls = []
        for node in bubble_nodes:
            content = node.content or ""
            for line in content.split('\n'):
                if 'http' in line.lower():
                    all_urls.append(line.strip())
        
        top_urls = all_urls[:10]
        
        # Top-Bilder
        all_images = []
        for node in bubble_nodes:
            content = node.content or ""
            for line in content.split('\n'):
                if 'image' in line.lower() or 'img' in line.lower():
                    all_images.append(line.strip())
        
        top_images = all_images[:10]
        
        # Generiere Requirements basierend auf den Nodes
        requirements = []
        for i, node in enumerate(bubble_nodes):
            content = node.content or ""
            title = node.title or ""
            word_count = len(content.split())
            char_count = len(content)
            
            req_id = f"REQ-{i+1:03d}"
            
            requirement = {
                "id": req_id,
                "title": title,
                "description": content[:500] if content else "",
                "details": {
                    "word_count": word_count,
                    "char_count": char_count,
                    "node_type": node.node_type,
                    "url_count": len([line for line in content.split('\n') if 'http' in line.lower()]),
                    "image_count": len([line for line in content.split('\n') if 'image' in line.lower() or 'img' in line.lower()]),
                    "code_block_count": len([line for line in content.split('\n') if '```' in line]),
                    "concept_count": len([word for word in (title + " " + content).split() if len(word) > 5 and word.isalpha()])
                },
                "acceptance_criteria": [
                    f"Das System muss {title.lower()} unterstützen",
                    f"Die Implementierung muss auf den Inhalten des Nodes basieren",
                    f"Die Funktionalität muss getestet und validiert werden"
                ],
                "user_stories": [
                    f"Als Benutzer möchte ich {title.lower()} nutzen, um meine Ziele zu erreichen",
                    f"Als Administrator möchte ich {title.lower()} konfigurieren können"
                ],
                "priority": "medium",
                "status": "pending"
            }
            
            requirements.append(requirement)
        
        # Generiere das Ergebnis
        result = {
            "metadata": {
                "bubble_id": bubble.id,
                "bubble_title": bubble.title,
                "bubble_description": bubble.description,
                "node_count": len(bubble_nodes),
                "edge_count": len(bubble_edges),
                "total_words": total_words,
                "total_chars": total_chars,
                "processed_at": None  # Wird von der Pipeline gesetzt
            },
            "nodes": node_data,
            "edges": [
                {
                    "id": edge.id,
                    "from_node_id": edge.from_node_id,
                    "to_node_id": edge.to_node_id,
                    "from_node_title": canvas_repo.get_node(edge.from_node_id).title if canvas_repo.get_node(edge.from_node_id) else "",
                    "to_node_title": canvas_repo.get_node(edge.to_node_id).title if canvas_repo.get_node(edge.to_node_id) else "",
                    "edge_type": edge.edge_type
                }
                for edge in bubble_edges
            ],
            "categories": categories,
            "statistics": {
                "total_words": total_words,
                "total_chars": total_chars,
                "avg_words_per_node": total_words / len(bubble_nodes) if bubble_nodes else 0,
                "avg_chars_per_node": total_chars / len(bubble_nodes) if bubble_nodes else 0
            },
            "top_concepts": top_concepts,
            "top_urls": top_urls,
            "top_images": top_images,
            "requirements": requirements
        }
        
        return result
    except Exception as e:
        return {
            "error": str(e),
            "status": "error"
        }


def get_bubble_requirements(bubble_id: str) -> Dict[str, Any]:
    """
    Hole die Requirements für eine Bubble.
    
    Args:
        bubble_id: ID der Bubble
        
    Returns:
        Dict mit den Requirements
    """
    return process_bubble_requirements(bubble_id)


def list_bubbles_with_requirements() -> Dict[str, Any]:
    """
    Liste alle Bubbles und generiere Requirements für jede.
    
    Returns:
        Dict mit allen Bubbles und ihren Requirements
    """
    ideas_repo = IdeasRepository()
    bubbles = ideas_repo.list(limit=1000)
    
    bubbles_with_requirements = []
    
    for bubble in bubbles:
        requirements = process_bubble_requirements(bubble.id)
        
        if "error" not in requirements:
            bubbles_with_requirements.append({
                "bubble_id": bubble.id,
                "bubble_title": bubble.title,
                "bubble_description": bubble.description,
                "requirements": requirements
            })
    
    return {
        "bubbles": bubbles_with_requirements,
        "total_bubbles": len(bubbles_with_requirements),
        "total_requirements": sum(len(b.get("requirements", {}).get("requirements", [])) for b in bubbles_with_requirements)
    }


if __name__ == "__main__":
    # Teste das Tool
    import sys
    
    if len(sys.argv) > 1:
        bubble_id = sys.argv[1]
        result = process_bubble_requirements(bubble_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Liste alle Bubbles
        result = list_bubbles_with_requirements()
        print(json.dumps(result, indent=2, ensure_ascii=False))
