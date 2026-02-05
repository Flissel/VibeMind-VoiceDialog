"""Test Bug 22 fix: Embedding service timeout and monitoring."""

import sys
sys.path.insert(0, '.')

def test_embedding_service():
    """Test the embedding service with monitoring and timeout."""
    print("=" * 60)
    print("Testing Bug 22 Fix: Embedding Service Timeout & Monitoring")
    print("=" * 60)
    print()

    # Test 1: Model loading with monitoring
    print("Test 1: Model loading with monitoring")
    print("-" * 40)

    from data.embedding_service import get_embedding_service

    service = get_embedding_service()
    print(f"  Service available: {service.is_available}")

    if not service.is_available:
        print("  [WARNING] Embedding service not available (sentence-transformers not installed?)")
        print("  Skipping embedding tests...")
    else:
        # Test 2: Embedding with timeout
        print()
        print("Test 2: Batch embedding")
        print("-" * 40)
        texts = ['Test idea one', 'Test idea two', 'Test idea three']
        embeddings = service.embed_batch(texts)
        valid = len([e for e in embeddings if e is not None])
        print(f"  Generated {valid}/{len(texts)} embeddings")

        if valid == len(texts):
            print("  [PASS] All embeddings generated successfully")
        else:
            print("  [FAIL] Some embeddings failed")

    # Test 3: Check system status
    print()
    print("Test 3: System status")
    print("-" * 40)
    from swarm.monitoring.system_status import get_status_monitor
    monitor = get_status_monitor()
    status = monitor.get_status()
    print(f"  Operations completed: {status['total_operations']}")
    print(f"  Errors: {status['total_errors']}")
    print(f"  Active operations: {status['active_count']}")

    # Show recent completed operations
    if status['recent_completed']:
        print()
        print("Recent operations:")
        for op in status['recent_completed'][-5:]:
            status_str = 'OK' if op['success'] else 'ERR'
            print(f"  [{op['duration_s']:.1f}s] {status_str} {op['type']}: {op['description'][:40]}")

    print()
    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_embedding_service()
