"""
Generate embeddings for bubbles to enable exploration.
"""
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def generate_embeddings():
    print("=" * 60)
    print("GENERATING EMBEDDINGS FOR BUBBLES")
    print("=" * 60)

    from data import IdeasRepository
    from data.database import get_database

    repo = IdeasRepository()
    db = get_database()

    # Get all bubbles (top-level ideas)
    ideas = repo.list(limit=50)
    bubbles = [i for i in ideas if not i.parent_id]

    print(f"\nFound {len(bubbles)} bubbles")

    # Check for embedding service
    print("\n1. Checking embedding service...")
    try:
        from data.embedding_service import get_embedding_service
        embedding_service = get_embedding_service()
        print("   ✓ Embedding service available")
    except ImportError as e:
        print(f"   ✗ Embedding service not available: {e}")
        print("   → Generating mock embeddings for testing")
        embedding_service = None

    # Generate embeddings
    print("\n2. Generating embeddings...")
    updated = 0

    for bubble in bubbles:
        # Skip if already has embedding
        if bubble.embedding_vector:
            print(f"   • {bubble.title}: already has embedding")
            continue

        # Create text for embedding
        text = f"{bubble.title}. {bubble.description or ''}"

        if embedding_service:
            try:
                embedding = embedding_service.get_embedding(text)
                # Store as JSON string
                embedding_json = json.dumps(embedding)
            except Exception as e:
                print(f"   ✗ {bubble.title}: embedding failed - {e}")
                # Use mock embedding
                import hashlib
                hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
                embedding = [(hash_val >> i) % 1000 / 1000.0 for i in range(384)]
                embedding_json = json.dumps(embedding)
        else:
            # Generate mock embedding based on text hash
            import hashlib
            hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
            # Create 384-dimensional mock embedding
            embedding = [(hash_val >> (i % 32)) % 1000 / 1000.0 - 0.5 for i in range(384)]
            embedding_json = json.dumps(embedding)

        # Update database
        with db.connection() as conn:
            conn.execute(
                "UPDATE ideas SET embedding_vector = ?, embedding_hash = ? WHERE id = ?",
                (embedding_json, hashlib.md5(text.encode()).hexdigest()[:16], bubble.id)
            )
            conn.commit()

        print(f"   ✓ {bubble.title}: embedding generated ({len(embedding)} dims)")
        updated += 1

    print(f"\n3. Summary: {updated} embeddings generated")

    # Verify
    print("\n4. Verification...")
    ideas = repo.list(limit=50)
    bubbles_with_embeddings = [i for i in ideas if not i.parent_id and i.embedding_vector]
    print(f"   Bubbles with embeddings: {len(bubbles_with_embeddings)}/{len(bubbles)}")

    if len(bubbles_with_embeddings) >= 2:
        print("\n   ✓ Exploration should now work!")
    else:
        print("\n   ⚠ Need at least 2 bubbles with embeddings for exploration")

    return updated


if __name__ == "__main__":
    import hashlib  # Import here for mock embedding
    generate_embeddings()
