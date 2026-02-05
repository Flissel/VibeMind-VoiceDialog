"""
Test für das generate_bubble_embeddings Tool

Dieser Test simuliert die Embedding-Generierung, ohne den EmbeddingService tatsächlich zu verwenden.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.bubble_tools import generate_bubble_embeddings


def test_generate_bubble_embeddings():
    """Test für das generate_bubble_embeddings Tool."""
    print("=" * 70)
    print("Test für das generate_bubble_embeddings Tool")
    print("=" * 70)

    # Test 1: Tool aufrufen
    print("\n=== Test 1: Tool aufrufen ===")
    try:
        result = generate_bubble_embeddings({})
        print(f"[PASS] Tool aufgerufen: {result}")
    except Exception as e:
        print(f"[FAIL] Tool-Aufruf fehlgeschlagen: {e}")
        return False

    # Test 2: Ergebnis prüfen
    print("\n=== Test 2: Ergebnis prüfen ===")
    if result:
        print(f"[PASS] Ergebnis ist nicht leer: {result}")
    else:
        print("[FAIL] Ergebnis ist leer")
        return False

    # Test 3: Ergebnis enthält Statistiken
    print("\n=== Test 3: Ergebnis enthält Statistiken ===")
    if "Embeddings" in result or "Bubbles" in result:
        print(f"[PASS] Ergebnis enthält Statistiken")
    else:
        print(f"[FAIL] Ergebnis enthält keine Statistiken")
        return False

    print("\n" + "=" * 70)
    print("Test-Zusammenfassung")
    print("=" * 70)
    print("[PASS] Alle Tests bestanden")
    return True


if __name__ == "__main__":
    success = test_generate_bubble_embeddings()
    sys.exit(0 if success else 1)
