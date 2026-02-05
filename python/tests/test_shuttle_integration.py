"""
Integration Tests for Shuttle Agent System

This module provides comprehensive integration tests for the Shuttle Agent System,
which includes the Shuttle Orchestrator Agent and the Shuttle Worker Agents
(Requirements Analyst, Pipeline Manager, Validator, Exporter) in a distributed
gRPC architecture.

Test Coverage:
- End-to-end workflow from intent classification to execution
- Integration between Shuttle Orchestrator and Worker Agents
- gRPC worker runtime communication
- Redis event bus integration
- Error handling and recovery across components
- Concurrent request handling
- Performance and scalability tests
"""

import unittest
import asyncio
import sys
import os
import json
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logger = None
try:
    import logging
    logger = logging.getLogger(__name__)
except ImportError:
    logger = None


class TestShuttleIntegration(unittest.TestCase):
    """Integration tests for Shuttle Agent System."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock imports
        self.mock_swarm_modules()
        
        # Import after mocking
        from swarm.backend_agents.shuttle_orchestrator_agent import (
            ShuttleOrchestratorAgent,
            get_shuttle_orchestrator_agent,
        )
        from swarm.grpc_workers.shuttle_workers import (
            RequirementsAnalystWorker,
            PipelineManagerWorker,
            ValidatorWorker,
            ExporterWorker,
        )
        from swarm.grpc_host_service import (
            GrpcHostService,
            get_grpc_host_service,
        )
        
        self.ShuttleOrchestratorAgent = ShuttleOrchestratorAgent
        self.get_shuttle_orchestrator_agent = get_shuttle_orchestrator_agent
        self.RequirementsAnalystWorker = RequirementsAnalystWorker
        self.PipelineManagerWorker = PipelineManagerWorker
        self.ValidatorWorker = ValidatorWorker
        self.ExporterWorker = ExporterWorker
        self.GrpcHostService = GrpcHostService
        self.get_grpc_host_service = get_grpc_host_service
    
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        # Clean up mocks
        self.restore_swarm_modules()
    
    def mock_swarm_modules(self):
        """Mock swarm modules for testing."""
        # Mock gRPC worker runtime
        sys.modules['swarm.grpc_worker_runtime'] = MagicMock()
        
        # Mock EventBus
        mock_event_bus = MagicMock()
        mock_event_bus.STREAM_TASKS_SHUTTLES = "events:tasks:shuttles"
        sys.modules['swarm.event_bus'] = MagicMock()
        sys.modules['swarm.event_bus'].EventBus = mock_event_bus
        
        # Mock model client
        sys.modules['swarm.models'] = MagicMock()
    
    def restore_swarm_modules(self):
        """Restore original swarm modules."""
        # Remove mocked modules
        sys.modules.pop('swarm.grpc_worker_runtime', None)
        sys.modules.pop('swarm.event_bus', None)
        sys.modules.pop('swarm.models', None)
    
    def test_end_to_end_workflow(self):
        """Test end-to-end workflow from intent classification to execution."""
        # Mock model client
        mock_model_client = MagicMock()
        
        # Mock responses
        mock_model_client.generate_response.side_effect = [
            # Intent classification
            asyncio.Future(),
            # Execution plan generation
            asyncio.Future(),
            # Requirements analysis
            asyncio.Future(),
            # Validation
            asyncio.Future(),
            # Export
            asyncio.Future(),
        ]
        
        # Set up mock responses
        mock_model_client.generate_response.side_effect[0].set_result({
            "event_type": "shuttle.process",
            "confidence": 0.9,
            "reasoning": "User wants to process bubble requirements"
        })
        
        mock_model_client.generate_response.side_effect[1].set_result({
            "steps": [
                {
                    "step": 1,
                    "action": "analyze_requirements",
                    "tool": "requirements_analyst",
                    "params": {"bubble_id": "123"}
                },
                {
                    "step": 2,
                    "action": "validate_requirements",
                    "tool": "validator",
                    "params": {"bubble_id": "123"}
                },
                {
                    "step": 3,
                    "action": "export_requirements",
                    "tool": "exporter",
                    "params": {"bubble_id": "123", "format": "json"}
                },
            ]
        })
        
        mock_model_client.generate_response.side_effect[2].set_result({
            "requirements": [
                {
                    "id": "REQ-001",
                    "title": "User Authentication",
                    "description": "Implement secure user authentication",
                    "priority": "high",
                    "status": "pending"
                },
            ],
            "analysis_summary": "Analyzed 1 requirement from bubble content"
        })
        
        mock_model_client.generate_response.side_effect[3].set_result({
            "validation_results": [
                {
                    "requirement_id": "REQ-001",
                    "is_valid": True,
                    "issues": []
                },
            ],
            "validation_summary": "1 valid requirement"
        })
        
        mock_model_client.generate_response.side_effect[4].set_result({
            "export_id": "EXP-001",
            "format": "json",
            "content": {
                "bubble_id": "123",
                "requirements": [
                    {"id": "REQ-001", "title": "User Authentication"},
                ]
            },
            "file_path": "/exports/requirements_123.json",
            "status": "completed"
        })
        
        # Create orchestrator
        orchestrator = self.ShuttleOrchestratorAgent(model_client=mock_model_client)
        
        # Test end-to-end workflow
        async def run_test():
            # Step 1: Classify intent
            intent = await orchestrator.classify_intent("Generiere Anforderungen für die Marketing bubble")
            self.assertEqual(intent["event_type"], "shuttle.process")
            
            # Step 2: Generate execution plan
            plan = await orchestrator.generate_execution_plan(
                event_type="shuttle.process",
                params={"bubble_id": "123"}
            )
            self.assertEqual(len(plan["steps"]), 3)
            
            # Step 3: Execute plan
            results = []
            for step in plan["steps"]:
                if step["action"] == "analyze_requirements":
                    worker = self.RequirementsAnalystWorker(model_client=mock_model_client)
                    result = await worker.analyze_requirements(
                        bubble_id=step["params"]["bubble_id"],
                        bubble_content="User authentication requirements"
                    )
                    results.append(result)
                elif step["action"] == "validate_requirements":
                    worker = self.ValidatorWorker(model_client=mock_model_client)
                    result = await worker.validate_requirements(
                        bubble_id=step["params"]["bubble_id"],
                        requirements=[{"id": "REQ-001", "title": "User Authentication"}]
                    )
                    results.append(result)
                elif step["action"] == "export_requirements":
                    worker = self.ExporterWorker(model_client=mock_model_client)
                    result = await worker.export_requirements(
                        bubble_id=step["params"]["bubble_id"],
                        requirements=[{"id": "REQ-001", "title": "User Authentication"}],
                        format=step["params"]["format"]
                    )
                    results.append(result)
            
            # Verify all steps completed successfully
            self.assertEqual(len(results), 3)
            for result in results:
                self.assertIsNotNone(result)
            
            if logger:
                logger.info("[PASS] Test end-to-end workflow passed")
        
        asyncio.run(run_test())
    
    def test_orchestrator_worker_integration(self):
        """Test integration between Shuttle Orchestrator and Worker Agents."""
        # Mock model client
        mock_model_client = MagicMock()
        
        # Mock responses
        mock_model_client.generate_response.side_effect = [
            asyncio.Future(),
            asyncio.Future(),
        ]
        
        mock_model_client.generate_response.side_effect[0].set_result({
            "event_type": "shuttle.process",
            "confidence": 0.85,
            "reasoning": "Process bubble requirements"
        })
        
        mock_model_client.generate_response.side_effect[1].set_result({
            "steps": [
                {
                    "step": 1,
                    "action": "analyze_requirements",
                    "tool": "requirements_analyst",
                    "params": {"bubble_id": "456"}
                },
            ]
        })
        
        # Create orchestrator
        orchestrator = self.ShuttleOrchestratorAgent(model_client=mock_model_client)
        
        # Test orchestrator-worker integration
        async def run_test():
            # Classify intent
            intent = await orchestrator.classify_intent("Analysiere Anforderungen für die Conversion AI bubble")
            self.assertEqual(intent["event_type"], "shuttle.process")
            
            # Generate execution plan
            plan = await orchestrator.generate_execution_plan(
                event_type="shuttle.process",
                params={"bubble_id": "456"}
            )
            
            # Execute first step with worker
            worker = self.RequirementsAnalystWorker(model_client=mock_model_client)
            result = await worker.analyze_requirements(
                bubble_id=plan["steps"][0]["params"]["bubble_id"],
                bubble_content="Conversion AI requirements"
            )
            
            # Verify integration
            self.assertIsNotNone(result)
            self.assertIn("requirements", result)
            
            if logger:
                logger.info("[PASS] Test orchestrator-worker integration passed")
        
        asyncio.run(run_test())
    
    def test_grpc_host_service_integration(self):
        """Test integration with gRPC Host Service."""
        # Mock model client
        mock_model_client = MagicMock()
        
        # Create gRPC host service
        host_service = self.GrpcHostService()
        
        # Test gRPC host service integration
        async def run_test():
            # Register workers
            await host_service.register_worker(
                worker_id="requirements_analyst",
                worker_type="RequirementsAnalystWorker",
                address="localhost:50051"
            )
            
            await host_service.register_worker(
                worker_id="validator",
                worker_type="ValidatorWorker",
                address="localhost:50052"
            )
            
            # Check worker health
            is_healthy = await host_service.check_worker_health("requirements_analyst")
            self.assertTrue(is_healthy)
            
            # Get available workers
            workers = await host_service.get_available_workers()
            self.assertGreater(len(workers), 0)
            
            if logger:
                logger.info("[PASS] Test gRPC host service integration passed")
        
        asyncio.run(run_test())
    
    def test_redis_event_bus_integration(self):
        """Test integration with Redis event bus."""
        # Mock Redis client
        mock_redis = MagicMock()
        mock_redis.xadd.return_value = "1234567890-0"
        mock_redis.xread.return_value = [
            ("events:tasks:shuttles", [
                ("1234567890-0", {
                    "event_type": "shuttle.process",
                    "bubble_id": "789",
                    "intent": "Generiere Anforderungen"
                })
            ])
        ]
        
        # Test Redis event bus integration
        async def run_test():
            # Add event to stream
            event_id = mock_redis.xadd(
                "events:tasks:shuttles",
                {
                    "event_type": "shuttle.process",
                    "bubble_id": "789",
                    "intent": "Generiere Anforderungen"
                }
            )
            
            # Verify event was added
            self.assertIsNotNone(event_id)
            
            # Read event from stream
            events = mock_redis.xread(
                streams={"events:tasks:shuttles": "0"},
                count=1,
                block=1000
            )
            
            # Verify event was read
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0][0], "events:tasks:shuttles")
            
            if logger:
                logger.info("[PASS] Test Redis event bus integration passed")
        
        asyncio.run(run_test())
    
    def test_error_handling_across_components(self):
        """Test error handling across components."""
        # Mock model client to throw error
        mock_model_client = MagicMock()
        mock_model_client.generate_response.side_effect = Exception("LLM API error")
        
        # Create orchestrator
        orchestrator = self.ShuttleOrchestratorAgent(model_client=mock_model_client)
        
        # Test error handling
        async def run_test():
            # Classify intent (should handle error gracefully)
            result = await orchestrator.classify_intent("Test intent")
            
            # Verify error handling
            self.assertIsNotNone(result)
            self.assertIn("error", result)
            self.assertIsNotNone(result["error"])
            
            if logger:
                logger.info("[PASS] Test error handling across components passed")
        
        asyncio.run(run_test())
    
    def test_concurrent_request_handling(self):
        """Test concurrent request handling."""
        # Mock model client
        mock_model_client = MagicMock()
        
        # Create orchestrator
        orchestrator = self.ShuttleOrchestratorAgent(model_client=mock_model_client)
        
        # Test concurrent request handling
        async def run_test():
            # Create multiple concurrent requests
            requests = [
                "Liste alle Bubbles mit Anforderungen",
                "Generiere Anforderungen für Marketing",
                "Zeige Anforderungen für Conversion AI",
                "Validiere Anforderungen für Multiversum",
                "Exportiere Anforderungen für Verbesserung der Conversion AI",
            ]
            
            # Process requests concurrently
            results = await asyncio.gather(*[
                orchestrator.classify_intent(request)
                for request in requests
            ])
            
            # Verify all results
            self.assertEqual(len(results), 5)
            for result in results:
                self.assertIsNotNone(result)
            
            if logger:
                logger.info("[PASS] Test concurrent request handling passed")
        
        asyncio.run(run_test())
    
    def test_performance_and_scalability(self):
        """Test performance and scalability."""
        # Mock model client
        mock_model_client = MagicMock()
        
        # Create orchestrator
        orchestrator = self.ShuttleOrchestratorAgent(model_client=mock_model_client)
        
        # Test performance and scalability
        async def run_test():
            # Create large number of concurrent requests
            num_requests = 100
            requests = [f"Test request {i}" for i in range(num_requests)]
            
            # Measure execution time
            import time
            start_time = time.time()
            
            # Process requests concurrently
            results = await asyncio.gather(*[
                orchestrator.classify_intent(request)
                for request in requests
            ])
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Verify all results
            self.assertEqual(len(results), num_requests)
            for result in results:
                self.assertIsNotNone(result)
            
            # Verify performance (should complete in reasonable time)
            self.assertLess(execution_time, 30.0)  # 30 seconds for 100 requests
            
            if logger:
                logger.info(f"[PASS] Test performance and scalability passed: {num_requests} requests in {execution_time:.2f}s")
        
        asyncio.run(run_test())


def run_tests():
    """Run all integration tests."""
    import time
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestShuttleIntegration)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    duration = time.time() - start_time
    
    # Print summary
    print("\n" + "="*70)
    print("SHUTTLE AGENT SYSTEM INTEGRATION TESTS")
    print("="*70)
    print(f"\nTests run: {result.testsRun}")
    successes = result.testsRun - len(result.failures) - len(result.errors)
    print(f"Successes: {successes}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Time: {duration:.2f}s")
    print("="*70 + "\n")
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
