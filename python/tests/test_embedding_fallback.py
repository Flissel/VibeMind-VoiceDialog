"""Test the embedding service fallback."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from data.embedding_service import get_embedding_service

print("=" * 60)
print("EMBEDDING SERVICE FALLBACK TEST")
print("=" * 60)

service = get_embedding_service()
print(f"\nService available: {service.is_available}")
print(f"Using fallback: {service.is_using_fallback}")

# Test embedding
print("\n1. Testing single embedding...")
text = "Marketing Strategie für B2B SaaS"
embedding = service.embed(text)
if embedding:
    print(f"   ✓ Embedding dim: {len(embedding)}")
    print(f"   First 5 values: {[f'{v:.4f}' for v in embedding[:5]]}")
else:
    print("   ✗ Embedding failed")

# Test similarity between related texts
print("\n2. Testing similarity (related texts)...")
texts = [
    ("Marketing Strategie für B2B SaaS", "Social Media Kampagnen für Unternehmen"),
    ("Marketing Strategie für B2B SaaS", "Produktentwicklung und Features"),
    ("KI Machine Learning Integration", "AI und automatische Analyse"),
]

for text1, text2 in texts:
    emb1 = service.embed(text1)
    emb2 = service.embed(text2)
    if emb1 and emb2:
        sim = service.similarity(emb1, emb2)
        print(f"   '{text1[:30]}...' vs '{text2[:30]}...'")
        print(f"   Similarity: {sim:.4f}")
        print()

print("=" * 60)
if service.is_using_fallback:
    print("NOTE: Using hash-based fallback (not semantic embeddings)")
    print("      Results are based on text similarity, not meaning")
else:
    print("Using real sentence-transformer embeddings")
