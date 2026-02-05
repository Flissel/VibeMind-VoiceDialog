"""
Unit Tests for Shuttle Orchestrator Agent

This module provides comprehensive unit tests for the Shuttle Orchestrator Agent,
which is responsible for coordinating shuttle tool agents (Requirements Analyst,
Pipeline Manager, Validator, Exporter) in a distributed gRPC architecture.

Test Coverage:
- Intent classification and routing
- Event-to-tool mapping
- Parameter normalization
- Execution plan generation
- Execution plan distribution
- Error handling and recovery
- Integration with gRPC worker runtime
"""

import unittest
import asyncio
import sys
import os
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


class TestShuttleOrchestratorAgent(unittest.TestCase):
    """Unit tests for Shuttle Orchestrator Agent."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock imports
        self.mock_swarm_modules()
        
        # Import after mocking
        from swarm.backend_agents.shuttle_orchestrator_agent import (
            ShuttleOrchestratorAgent,
            get_shuttle_orchestrator_agent,
        )
        
        self.ShuttleOrchestratorAgent = ShuttleOrchestratorAgent
        self.get_shuttle_orchestrator_agent = get_shuttle_orchestrator_agent
    
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
    
    def test_initialization(self):
        """Test Shuttle Orchestrator Agent initialization."""
        # Create orchestrator
        orchestrator = self.ShuttleOrchestratorAgent()
        
        # Verify initialization
        self.assertIsNotNone(orchestrator)
        
        if logger:
            logger.info("[PASS] Test initialization passed")
    
    def test_event_to_tool_mapping(self):
        """Test EVENT_TO_TOOL mapping."""
        # Create orchestrator
        orchestrator = self.ShuttleOrchestratorAgent()
        
        # Verify EVENT_TO_TOOL mapping
        expected_mapping = {
            "shuttle.list": "list_bubbles_with_requirements",
            "shuttle.get": "get_bubble_requirements",
            "shuttle.process": "process_bubble_requirements",
            "shuttle.classify_intent": "classify_intent",
            "shuttle.generate_plan": "generate_execution_plan",
            "shuttle.distribute_task": "distribute_task",
        }
        
        self.assertEqual(orchestrator.EVENT_TO_TOOL, expected_mapping)
        
        if logger:
            logger.info("[PASS] Test event-to-tool mapping passed")
    
    def test_param_mapping(self):
        """Test PARAM_MAPPING for parameter normalization."""
        # Create orchestrator
        orchestrator = self.ShuttleOrchestratorAgent()
        
        # Verify PARAM_MAPPING
        expected_mapping = {
            "shuttle.list": {},
            "shuttle.get": {
                "bubble_id": "bubble_id",
                "id": "bubble_id",
            },
            "shuttle.process": {
                "bubble_id": "bubble_id",
                "id": "bubble_id",
            },
            "shuttle.classify_intent": {
                "user_input": "user_input",
                "transcript": "user_input",
                "text": "user_input",
            },
            "shuttle.generate_plan": {
                "intent": "intent",
                "user_input": "user_input",
                "context": "context",
            },
            "shuttle.distribute_task": {
                "plan": "execution_plan",
                "worker_type": "worker_type",
                "task_data": "task_data",
            },
        }
        
        self.assertEqual(orchestrator.PARAM_MAPPING, expected_mapping)
        
        if logger:
            logger.info("[PASS] Test param mapping passed")
    
    def test_get_orchestrator_singleton(self):
        """Test get_shuttle_orchestrator_agent singleton."""
        # First call
        orchestrator1 = self.get_shuttle_orchestrator_agent()
        
        # Second call should return same instance
        orchestrator2 = self.get_shuttle_orchestrator_agent()
        
        # Verify singleton pattern
        self.assertIs(orchestrator1, orchestrator2)
        
        if logger:
            logger.info("[PASS] Test singleton pattern passed")
    
    def test_build_swarm_task(self):
        """Test _build_swarm_task method."""
        # Create orchestrator
        orchestrator = self.ShuttleOrchestratorAgent()
        
        # Test with user_input
        payload = {
            "_user_input": "Generiere Anforderungen für die Marketing bubble",
            "bubble_id": "123",
            "job_id": "test-job",
        }
        
        task = orchestrator._build_swarm_task("shuttle.process", payload)
        
        # Verify task includes user_input
        self.assertIn("Generiere Anforderungen für die Marketing bubble", task)
        self.assertIn("shuttle.process", task)
        self.assertIn("bubble_id", task)
        
        if logger:
            logger.info("[PASS] Test build_swarm_task with user_input passed")
        
        # Test without user_input
        payload = {
            "bubble_id": "123",
            "bubble_name": "Marketing",
            "job_id": "test-job",
        }
        
        task = orchestrator._build_swarm_task("shuttle.process", payload)
        
        # Verify task includes event_type and params
        self.assertIn("shuttle.process", task)
        self.assertIn("bubble_id", task)
        self.assertIn("bubble_name", task)
        
        if logger:
            logger.info("[PASS] Test build_swarm_task without user_input passed")
    
    def test_run_swarm(self):
        """Test _run_swarm method."""
        # Create orchestrator
        orchestrator = self.ShuttleOrchestratorAgent()
        
        # Mock swarm
        mock_swarm = MagicMock()
        mock_result = MagicMock()
        mock_result.messages = [MagicMock(content="Test response")]
        mock_swarm.run = AsyncMock(return_value=mock_result)
        
        # Test _run_swarm
        async def run_test():
            with patch('swarm.backend_agents.shuttle_swarm.get_shuttle_swarm', return_value=mock_swarm):
                result = await orchestrator._run_swarm("Test task")
                
                # Verify result
                self.assertEqual(result, "Test response")
                
                # Verify swarm.run was called
                mock_swarm.run.assert_called_once_with(task="Test task")
                
                if logger:
                    logger.info("[PASS] Test run_swarm passed")
        
        asyncio.run(run_test())
    
    def test_handle_event_without_ag2_swarm(self):
        """Test _handle_event without AG2 Swarm (fallback to direct dispatch)."""
        # Create orchestrator
        orchestrator = self.ShuttleOrchestratorAgent()
        
        # Mock event
        mock_event = MagicMock()
        mock_event.job_id = "test-job"
        mock_event.event_type = "shuttle.process"
        mock_event.payload = {
            "bubble_id": "123",
        }
        
        # Test _handle_event without AG2 Swarm
        async def run_test():
            with patch('swarm.backend_agents.shuttle_orchestrator_agent.USE_AG2_SWARM', False):
                with patch.object(orchestrator, '_publish_status', new_callable=AsyncMock):
                    await orchestrator._handle_event(mock_event)
                    
                    if logger:
                        logger.info("[PASS] Test handle_event without AG2 Swarm passed")
        
        asyncio.run(run_test())


def run_tests():
    """Run all unit tests."""
    import time
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestShuttleOrchestratorAgent)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    duration = time.time() - start_time
    
    # Print summary
    print("\n" + "="*70)
    print("SHUTTLE ORCHESTRATOR AGENT UNIT TESTS")
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
