"""Quick script to check ideas in Debug information space."""
from data.supabase_database import get_database
from data.repository import IdeasRepository, CanvasRepository

db = get_database()
ideas_repo = IdeasRepository(db)
canvas_repo = CanvasRepository(db)

# Find Debug information bubble (top-level idea/space)
all_ideas = ideas_repo.list(limit=200)
print(f"Found {len(all_ideas)} ideas total")
debug_bubbles = []
for idea in all_ideas:
    if 'debug' in idea.title.lower():
        debug_bubbles.append(idea)
        print(f'Found bubble: "{idea.title}" (id={idea.id})')

debug_bubble = debug_bubbles[-1] if debug_bubbles else None  # Take the last one

if debug_bubble:
    # Get canvas nodes linked to this bubble
    all_nodes = canvas_repo.list_nodes(limit=500)
    nodes_in_bubble = [n for n in all_nodes if n.linked_idea_id == debug_bubble.id]
    print(f'\nCanvas nodes in "{debug_bubble.title}": {len(nodes_in_bubble)}')
    for i, node in enumerate(nodes_in_bubble[:20]):
        title = node.title[:55] + '...' if len(node.title) > 55 else node.title
        print(f'  {i+1}. [{node.node_type}] {title}')
else:
    print('No debug bubble found')
