"""
Liste alle Bubbles und finde context-reiche Bubbles.
"""

import sys
import os

# Füge das python Verzeichnis zum Pfad hinzu
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data import IdeasRepository, CanvasRepository

def main():
    ideas_repo = IdeasRepository()
    canvas_repo = CanvasRepository()
    
    # Hole alle Bubbles (top-level ideas)
    bubbles = ideas_repo.list(limit=1000)
    
    print(f'Anzahl der Bubbles: {len(bubbles)}')
    print()
    
    # Analysiere jede Bubble
    context_rich_bubbles = []
    
    for bubble in bubbles:
        # Hole alle Nodes für diese Bubble
        nodes = canvas_repo.list_nodes(limit=1000)
        bubble_nodes = [n for n in nodes if n.linked_idea_id == bubble.id]
        
        # Berechne Statistiken
        total_words = sum(len((n.content or '').split()) for n in bubble_nodes)
        total_chars = sum(len(n.content or '') for n in bubble_nodes)
        total_urls = sum(len([line for line in (n.content or '').split('\n') if 'http' in line.lower()]) for n in bubble_nodes)
        total_images = sum(len([line for line in (n.content or '').split('\n') if 'image' in line.lower() or 'img' in line.lower()]) for n in bubble_nodes)
        
        # Prüfe, ob die Bubble context-reich ist
        is_context_rich = (
            len(bubble_nodes) >= 5 or  # Mindestens 5 Nodes
            total_words >= 1000 or  # Mindestens 1000 Wörter
            total_urls >= 3 or  # Mindestens 3 URLs
            total_images >= 3  # Mindestens 3 Bilder
        )
        
        bubble_info = {
            'id': bubble.id,
            'title': bubble.title,
            'description': bubble.description[:100] if bubble.description else '',
            'node_count': len(bubble_nodes),
            'total_words': total_words,
            'total_chars': total_chars,
            'total_urls': total_urls,
            'total_images': total_images,
            'is_context_rich': is_context_rich
        }
        
        if is_context_rich:
            context_rich_bubbles.append(bubble_info)
        
        # Zeige alle Bubbles
        print(f'ID: {bubble.id}')
        print(f'Title: {bubble.title}')
        print(f'Description: {bubble.description[:100] if bubble.description else ""}...')
        print(f'Nodes: {len(bubble_nodes)}')
        print(f'Words: {total_words}')
        print(f'Chars: {total_chars}')
        print(f'URLs: {total_urls}')
        print(f'Images: {total_images}')
        print(f'Context-Rich: {"YES" if is_context_rich else "NO"}')
        print()
    
    # Zeige context-reiche Bubbles
    print('=' * 80)
    print('CONTEXT-REICHE BUBBLES:')
    print('=' * 80)
    print()
    
    for bubble in context_rich_bubbles:
        print(f'ID: {bubble["id"]}')
        print(f'Title: {bubble["title"]}')
        print(f'Description: {bubble["description"]}...')
        print(f'Nodes: {bubble["node_count"]}')
        print(f'Words: {bubble["total_words"]}')
        print(f'Chars: {bubble["total_chars"]}')
        print(f'URLs: {bubble["total_urls"]}')
        print(f'Images: {bubble["total_images"]}')
        print()

if __name__ == '__main__':
    main()
