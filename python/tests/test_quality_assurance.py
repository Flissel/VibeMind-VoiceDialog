#!/usr/bin/env python3
"""
Quality Assurance & Testing Suite for VibeMind Advanced Features

Phase 21: Comprehensive testing framework covering:
- Database consistency validation
- Performance benchmarking
- Integration testing
- End-to-end workflow validation
- Load testing and scalability
- Error handling and recovery

Tests all components: Super Memory, Execution Layer, Enhanced Agents, API Server
"""

import asyncio
import time
import pytest
import sqlite3
import tempfile
import shutil
import json
import statistics
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import AsyncMock, patch
import concurrent.futures

# Import all components to test
from super_memory_api import SuperMemoryAPI, MemoryQuery, MemoryEntry
from swarm.execution_layer import ExecutionEngine, WorkflowPlanner, WorkflowStep
from spaces.ideas.enhanced.enhanced_ideas_agent import EnhancedIdeasAgent
from vibemind_api import VibeMindAPI
from swarm.orchestrator.intent_orchestrator import get_orchestrator
from swarm.analysis.user_context import UserContext


class TestDatabaseConsistency:
    """Test database consistency and integrity."""

    def setup_method(self):
        """Set up test database."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.super_memory = SuperMemoryAPI(db_path=self.db_path)

    def teardown_method(self):
        """Clean up test database."""
        self.super_memory = None
        os.close(self.db_fd)
        os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_memory_storage_integrity(self):
        """Test that memory storage maintains data integrity."""
        # Store test memories
        memories = [
            {
                "content": "Test memory 1",
                "memory_type": "conversation",
                "user_id": "test_user",
                "session_id": "session1",
                "importance": 0.8,
                "tags": ["test", "memory"],
                "metadata": {"source": "test"}
            },
            {
                "content": "Test memory 2",
                "memory_type": "idea",
                "user_id": "test_user",
                "session_id": "session1",
                "importance": 0.6,
                "tags": ["idea"],
                "metadata": {"priority": "high"}
            }
        ]

        stored_ids = []
        for memory in memories:
            memory_id = await self.super_memory.store_memory(**memory)
            stored_ids.append(memory_id)
            assert memory_id is not None

        # Verify storage
        query = MemoryQuery(query_text="", user_id="test_user", limit=10)
        result = await self.super_memory.retrieve_memories(query)

        assert len(result.results) == 2
        assert result.total_found == 2

        # Verify data integrity
        for i, memory in enumerate(result.results):
            original = memories[i]
            assert memory.content == original["content"]
            assert memory.memory_type == original["memory_type"]
            assert memory.user_id == original["user_id"]
            assert memory.importance == original["importance"]
            assert memory.tags == set(original["tags"])
            assert memory.metadata == original["metadata"]

    @pytest.mark.asyncio
    async def test_database_constraints(self):
        """Test database constraints and foreign key relationships."""
        # Test invalid importance values
        with pytest.raises(Exception):
            await self.super_memory.store_memory(
                content="Test",
                memory_type="conversation",
                user_id="test_user",
                session_id="session1",
                importance=1.5  # Invalid: > 1.0
            )

        with pytest.raises(Exception):
            await self.super_memory.store_memory(
                content="Test",
                memory_type="conversation",
                user_id="test_user",
                session_id="session1",
                importance=-0.5  # Invalid: < 0.0
            )

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test database handles concurrent access properly."""
        async def store_memory_task(task_id: int):
            return await self.super_memory.store_memory(
                content=f"Concurrent memory {task_id}",
                memory_type="conversation",
                user_id="test_user",
                session_id=f"session{task_id}",
                importance=0.5
            )

        # Run multiple concurrent stores
        tasks = [store_memory_task(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert len(results) == 10
        assert all(r is not None for r in results)

        # Verify all stored
        query = MemoryQuery(query_text="", user_id="test_user", limit=20)
        result = await self.super_memory.retrieve_memories(query)
        assert len(result.results) == 10


class TestPerformanceBenchmarking:
    """Performance benchmarking tests."""

    def setup_method(self):
        """Set up performance test environment."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.super_memory = SuperMemoryAPI(db_path=self.db_path)

    def teardown_method(self):
        """Clean up performance test environment."""
        self.super_memory = None
        os.close(self.db_fd)
        os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_memory_storage_performance(self):
        """Benchmark memory storage performance."""
        # Prepare test data
        test_memories = []
        for i in range(100):
            test_memories.append({
                "content": f"Performance test memory {i} with some additional content to make it more realistic and test the storage performance under load",
                "memory_type": "conversation" if i % 2 == 0 else "idea",
                "user_id": f"user_{i % 10}",
                "session_id": f"session_{i % 5}",
                "importance": 0.1 + (i % 9) * 0.1,  # 0.1 to 0.9
                "tags": [f"tag_{j}" for j in range(i % 5)],
                "metadata": {"index": i, "batch": "performance_test"}
            })

        # Measure storage performance
        start_time = time.time()
        stored_ids = []

        for memory in test_memories:
            memory_id = await self.super_memory.store_memory(**memory)
            stored_ids.append(memory_id)

        storage_time = time.time() - start_time
        storage_rate = len(test_memories) / storage_time

        print(".2f")
        print(".1f")

        # Assert reasonable performance
        assert storage_time < 5.0, f"Storage too slow: {storage_time}s"
        assert storage_rate > 10, f"Storage rate too low: {storage_rate} memories/s"

    @pytest.mark.asyncio
    async def test_memory_query_performance(self):
        """Benchmark memory query performance."""
        # First, store test data
        for i in range(500):
            await self.super_memory.store_memory(
                content=f"Query performance test memory {i}",
                memory_type="conversation",
                user_id="perf_user",
                session_id="perf_session",
                importance=0.5,
                tags=["performance", f"batch_{i % 10}"]
            )

        # Test different query types
        queries = [
            MemoryQuery(query_text="", user_id="perf_user", limit=10),
            MemoryQuery(query_text="performance", user_id="perf_user", limit=50),
            MemoryQuery(query_text="", user_id="perf_user", memory_types=["conversation"], limit=100),
            MemoryQuery(query_text="", user_id="perf_user", tags=["batch_5"], limit=20),
        ]

        for query in queries:
            start_time = time.time()
            result = await self.super_memory.retrieve_memories(query)
            query_time = time.time() - start_time

            print(".3f")

            # Assert reasonable query performance
            assert query_time < 0.5, f"Query too slow: {query_time}s for {len(result.results)} results"
            assert len(result.results) > 0, "Query returned no results"

    @pytest.mark.asyncio
    async def test_memory_consolidation_performance(self):
        """Benchmark memory consolidation performance."""
        # Store similar memories to test consolidation
        base_content = "This is a test memory for consolidation performance testing"

        for i in range(200):
            # Create slightly different variations
            variation = f"{base_content} variation {i}"
            await self.super_memory.store_memory(
                content=variation,
                memory_type="conversation",
                user_id="consolidation_user",
                session_id="consolidation_session",
                importance=0.7
            )

        # Measure consolidation performance
        start_time = time.time()
        consolidations = await self.super_memory.consolidate_memories("consolidation_user", max_age_days=1)
        consolidation_time = time.time() - start_time

        print(f"Consolidation: {consolidations} operations in {consolidation_time:.3f}s")

        # Assert reasonable performance
        assert consolidation_time < 2.0, f"Consolidation too slow: {consolidation_time}s"


class TestIntegrationTesting:
    """Integration tests for component interaction."""

    def setup_method(self):
        """Set up integration test environment."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.super_memory = SuperMemoryAPI(db_path=self.db_path)

        # Mock components for testing
        self.orchestrator = get_orchestrator()

    def teardown_method(self):
        """Clean up integration test environment."""
        self.super_memory = None
        os.close(self.db_fd)
        os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_memory_orchestrator_integration(self):
        """Test integration between Super Memory and Intent Orchestrator."""
        # Store context in memory
        await self.super_memory.store_memory(
            content="User prefers creating ideas in German",
            memory_type="context",
            user_id="integration_user",
            session_id="integration_session",
            importance=0.9,
            tags=["preference", "language"]
        )

        # Process intent that should benefit from memory context
        from swarm.event_team import TaskContext
        context = TaskContext(
            user_id="integration_user",
            session_id="integration_session_2"
        )

        result = await self.orchestrator.process_intent(
            "Erstelle eine neue Idee",
            context
        )

        # Verify processing succeeded
        assert result.event_type != "error"
        assert result.job_id or result.is_conversational

    @pytest.mark.asyncio
    async def test_api_memory_integration(self):
        """Test API server integration with Super Memory."""
        # This would require a running API server
        # For now, test the API components directly
        from vibemind_api import get_api_server

        api_server = get_api_server()

        # Verify API has access to super memory
        assert api_server.super_memory is not None
        assert api_server.orchestrator is not None

        # Test API initialization
        assert hasattr(api_server, 'app')
        assert hasattr(api_server, 'super_memory')


class TestEndToEndWorkflows:
    """End-to-end workflow testing."""

    def setup_method(self):
        """Set up end-to-end test environment."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.super_memory = SuperMemoryAPI(db_path=self.db_path)

        # Create temporary upload directory
        self.upload_dir = Path(tempfile.mkdtemp())
        self.api_server = VibeMindAPI()
        self.api_server.upload_dir = self.upload_dir

    def teardown_method(self):
        """Clean up end-to-end test environment."""
        self.super_memory = None
        os.close(self.db_fd)
        os.unlink(self.db_path)
        shutil.rmtree(self.upload_dir)

    @pytest.mark.asyncio
    async def test_complete_memory_workflow(self):
        """Test complete memory storage and retrieval workflow."""
        user_id = "e2e_user"
        session_id = "e2e_session"

        # 1. Store memories
        memories = [
            {
                "content": "First test memory",
                "memory_type": "conversation",
                "user_id": user_id,
                "session_id": session_id,
                "importance": 0.8,
                "tags": ["test", "first"]
            },
            {
                "content": "Second test memory with different content",
                "memory_type": "idea",
                "user_id": user_id,
                "session_id": session_id,
                "importance": 0.6,
                "tags": ["test", "second"]
            }
        ]

        stored_ids = []
        for memory in memories:
            memory_id = await self.super_memory.store_memory(**memory)
            stored_ids.append(memory_id)

        # 2. Query memories
        query = MemoryQuery(
            query_text="test memory",
            user_id=user_id,
            limit=10
        )
        result = await self.super_memory.retrieve_memories(query)

        # 3. Verify results
        assert len(result.results) == 2
        assert result.total_found == 2

        # 4. Update importance
        first_memory = result.results[0]
        success = await self.super_memory.update_memory_importance(first_memory.id, 0.9)
        assert success

        # 5. Verify update
        updated_query = MemoryQuery(query_text="", user_id=user_id, limit=10)
        updated_result = await self.super_memory.retrieve_memories(updated_query)

        updated_memory = next(m for m in updated_result.results if m.id == first_memory.id)
        assert updated_memory.importance == 0.9

        # 6. Get statistics
        stats = await self.super_memory.get_memory_stats(user_id)
        assert stats["total_memories"] == 2
        assert stats["avg_importance"] > 0.7  # Average of 0.9 and 0.6

    @pytest.mark.asyncio
    async def test_agent_workflow_integration(self):
        """Test agent workflow with memory integration."""
        # Create enhanced agent
        agent = EnhancedIdeasAgent()
        await agent.start()

        try:
            # Create complex workflow
            workflow_id = "e2e_workflow_test"
            workflow_state = await agent.create_complex_idea_workflow(
                workflow_id=workflow_id,
                idea_description="End-to-end test idea",
                auto_expand=True,
                connect_similar=True
            )

            # Verify workflow creation
            assert workflow_state.workflow_id == workflow_id
            assert "create_idea" in workflow_state.pending_steps

            # Check workflow state management
            current_state = await agent.get_workflow_state(workflow_id)
            assert current_state is not None
            assert not current_state.is_complete

        finally:
            await agent.stop()


class TestLoadAndScalability:
    """Load testing and scalability validation."""

    def setup_method(self):
        """Set up load test environment."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.super_memory = SuperMemoryAPI(db_path=self.db_path)

    def teardown_method(self):
        """Clean up load test environment."""
        self.super_memory = None
        os.close(self.db_fd)
        os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_concurrent_memory_operations(self):
        """Test concurrent memory operations under load."""
        user_id = "load_test_user"

        async def memory_operation(task_id: int):
            # Mix of different operations
            operation = task_id % 4

            if operation == 0:  # Store
                return await self.super_memory.store_memory(
                    content=f"Load test memory {task_id}",
                    memory_type="conversation",
                    user_id=user_id,
                    session_id=f"session_{task_id % 10}",
                    importance=0.5
                )
            elif operation == 1:  # Query
                query = MemoryQuery(query_text="", user_id=user_id, limit=5)
                result = await self.super_memory.retrieve_memories(query)
                return len(result.results)
            elif operation == 2:  # Update
                # Try to update a memory (may not exist, that's ok)
                try:
                    success = await self.super_memory.update_memory_importance(f"mem_{task_id}", 0.8)
                    return success
                except:
                    return False
            else:  # Get stats
                stats = await self.super_memory.get_memory_stats(user_id)
                return stats.get("total_memories", 0)

        # Run concurrent operations
        num_operations = 100
        start_time = time.time()

        tasks = [memory_operation(i) for i in range(num_operations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time

        # Analyze results
        successful_operations = sum(1 for r in results if not isinstance(r, Exception))
        failed_operations = sum(1 for r in results if isinstance(r, Exception))

        print(f"Load test: {successful_operations}/{num_operations} operations successful")
        print(".2f")
        print(".1f")

        # Assert reasonable performance under load
        assert successful_operations > num_operations * 0.8, f"Too many failures: {failed_operations}"
        assert total_time < 30.0, f"Load test too slow: {total_time}s"

    @pytest.mark.asyncio
    async def test_memory_scaling(self):
        """Test memory system scaling with large datasets."""
        user_id = "scaling_user"

        # Store large number of memories
        num_memories = 1000
        start_time = time.time()

        for i in range(num_memories):
            await self.super_memory.store_memory(
                content=f"Scaling test memory {i} with substantial content to test database performance and memory usage patterns under realistic load conditions",
                memory_type="conversation" if i % 3 == 0 else "idea",
                user_id=user_id,
                session_id=f"session_{i % 20}",
                importance=0.1 + (i % 9) * 0.1,
                tags=[f"tag_{j}" for j in range(i % 5)],
                metadata={"batch": "scaling_test", "index": i}
            )

        storage_time = time.time() - start_time
        storage_rate = num_memories / storage_time

        print(f"Scaling test: Stored {num_memories} memories in {storage_time:.2f}s")
        print(".1f")

        # Test query performance on large dataset
        query_start = time.time()
        query = MemoryQuery(query_text="", user_id=user_id, limit=100)
        result = await self.super_memory.retrieve_memories(query)
        query_time = time.time() - query_start

        print(f"Query performance: {len(result.results)} results in {query_time:.3f}s")

        # Assert scaling performance
        assert storage_rate > 50, f"Storage rate too low: {storage_rate} memories/s"
        assert query_time < 1.0, f"Query too slow: {query_time}s"
        assert len(result.results) == 100, "Query returned wrong number of results"


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery mechanisms."""

    def setup_method(self):
        """Set up error handling test environment."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.super_memory = SuperMemoryAPI(db_path=self.db_path)

    def teardown_method(self):
        """Clean up error handling test environment."""
        self.super_memory = None
        os.close(self.db_fd)
        os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_database_corruption_recovery(self):
        """Test recovery from database corruption."""
        # Store some data first
        await self.super_memory.store_memory(
            content="Recovery test memory",
            memory_type="conversation",
            user_id="recovery_user",
            session_id="recovery_session",
            importance=0.8
        )

        # Simulate database corruption by directly modifying the file
        # (This is dangerous in real scenarios, but for testing...)
        try:
            # Create a backup super memory instance
            backup_memory = SuperMemoryAPI(db_path=self.db_path + ".backup")

            # Copy current data to backup
            query = MemoryQuery(query_text="", user_id="recovery_user", limit=10)
            original_data = await self.super_memory.retrieve_memories(query)

            # Simulate corruption by deleting the database file
            import os
            os.unlink(self.db_path)

            # Try to recover by recreating the database
            recovered_memory = SuperMemoryAPI(db_path=self.db_path)

            # Verify recovery (database should be recreated empty)
            recovered_query = MemoryQuery(query_text="", user_id="recovery_user", limit=10)
            recovered_data = await recovered_memory.retrieve_memories(recovered_query)

            # In a real recovery scenario, we'd restore from backup
            # For this test, we just verify the system handles missing database gracefully
            assert len(recovered_data.results) == 0

        except Exception as e:
            # If corruption simulation fails, at least verify error handling
            assert "database" in str(e).lower() or "corrupt" in str(e).lower()

    @pytest.mark.asyncio
    async def test_invalid_input_handling(self):
        """Test handling of invalid inputs."""
        # Test invalid importance values
        with pytest.raises((ValueError, Exception)):
            await self.super_memory.store_memory(
                content="Test",
                memory_type="invalid_type",
                user_id="",  # Empty user_id
                session_id="test",
                importance=1.5  # Invalid importance
            )

        # Test empty content
        with pytest.raises((ValueError, Exception)):
            await self.super_memory.store_memory(
                content="",  # Empty content
                memory_type="conversation",
                user_id="test_user",
                session_id="test",
                importance=0.5
            )

    @pytest.mark.asyncio
    async def test_concurrent_error_recovery(self):
        """Test error recovery under concurrent load."""
        async def failing_operation(task_id: int):
            try:
                if task_id % 5 == 0:  # Every 5th operation fails
                    raise Exception(f"Simulated failure in task {task_id}")

                return await self.super_memory.store_memory(
                    content=f"Concurrent test memory {task_id}",
                    memory_type="conversation",
                    user_id="concurrent_user",
                    session_id=f"session_{task_id % 10}",
                    importance=0.5
                )
            except Exception as e:
                # Log error and return failure indicator
                print(f"Task {task_id} failed: {e}")
                return None

        # Run concurrent operations with some failures
        tasks = [failing_operation(i) for i in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze results
        successful = sum(1 for r in results if r is not None and not isinstance(r, Exception))
        failed = sum(1 for r in results if r is None or isinstance(r, Exception))

        print(f"Concurrent error test: {successful} successful, {failed} failed")

        # System should handle failures gracefully
        assert successful > failed * 2, "Too many failures compared to successes"

        # Verify successful operations were actually stored
        query = MemoryQuery(query_text="", user_id="concurrent_user", limit=100)
        stored_results = await self.super_memory.retrieve_memories(query)
        assert len(stored_results.results) == successful


# =========================================================================
# UTILITY FUNCTIONS
# =========================================================================

def run_performance_benchmarks():
    """Run comprehensive performance benchmarks."""
    print("Running Performance Benchmarks...")
    print("=" * 50)

    # This would run the performance tests and generate reports
    # For now, just indicate this would be implemented
    print("Performance benchmarks would be implemented here")
    print("- Memory storage throughput")
    print("- Query response times")
    print("- Concurrent operation handling")
    print("- Memory consolidation efficiency")
    print("- Database size vs performance")


def run_load_tests():
    """Run load and stress tests."""
    print("Running Load Tests...")
    print("=" * 50)

    # This would run load tests with various scenarios
    print("Load tests would be implemented here")
    print("- Concurrent user simulation")
    print("- Memory usage monitoring")
    print("- Database connection pooling")
    print("- API endpoint stress testing")


def generate_test_report():
    """Generate comprehensive test report."""
    print("Generating Test Report...")
    print("=" * 50)

    # This would analyze all test results and generate reports
    print("Test report would include:")
    print("- Test coverage metrics")
    print("- Performance benchmarks")
    print("- Error rates and patterns")
    print("- Recommendations for improvements")


if __name__ == "__main__":
    # Run specific test categories
    import sys

    if len(sys.argv) > 1:
        test_type = sys.argv[1]

        if test_type == "performance":
            run_performance_benchmarks()
        elif test_type == "load":
            run_load_tests()
        elif test_type == "report":
            generate_test_report()
        else:
            print(f"Unknown test type: {test_type}")
            print("Available types: performance, load, report")
    else:
        print("Quality Assurance Test Suite")
        print("Usage: python test_quality_assurance.py [performance|load|report]")
        print("Or run with pytest: pytest test_quality_assurance.py")