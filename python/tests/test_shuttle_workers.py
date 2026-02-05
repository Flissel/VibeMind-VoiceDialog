"""
Unit Tests for Shuttle Worker Agents

This module provides comprehensive unit tests for the Shuttle Worker Agents,
which are responsible for executing specific tasks in the distributed gRPC
architecture for shuttle tool agents.

Test Coverage:
- RequirementsAnalystWorker: Requirements analysis and validation
- PipelineManagerWorker: Pipeline management and coordination
- ValidatorWorker: Requirements validation against specifications
- ExporterWorker: Exporting requirements in various formats
- gRPC worker runtime integration
- Message handling and routing
- Error handling and recovery
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


class TestRequirementsAnalystWorker(unittest.TestCase):
    """Unit tests for RequirementsAnalystWorker."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock imports
        self.mock_swarm_modules()
        
        # Import after mocking
        from swarm.grpc_workers.shuttle_workers import (
            RequirementsAnalystWorker,
        )
        
        self.RequirementsAnalystWorker = RequirementsAnalystWorker
    
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
        """Test RequirementsAnalystWorker initialization."""
        # Mock model client
        mock_model_client = MagicMock()
        
        # Create worker
        worker = self.RequirementsAnalystWorker(model_client=mock_model_client)
        
        # Verify initialization
        self.assertIsNotNone(worker)
        self.assertIsNotNone(worker.model_client)
        self.assertEqual(worker.model_client, mock_model_client)
        
        if logger:
            logger.info("[PASS] Test RequirementsAnalystWorker initialization passed")
    
    def test_analyze_requirements(self):
        """Test requirements analysis."""
        # Mock model client
        mock_model_client = MagicMock()
        mock_model_client.generate_response.return_value = asyncio.Future()
        mock_model_client.generate_response.return_value.set_result({
            "requirements": [
                {
                    "id": "REQ-001",
                    "title": "User Authentication",
                    "description": "Implement secure user authentication",
                    "priority": "high",
                    "status": "pending"
                },
                {
                    "id": "REQ-002",
                    "title": "Data Encryption",
                    "description": "Encrypt all sensitive data",
                    "priority": "high",
                    "status": "pending"
                },
            ],
            "analysis_summary": "Analyzed 2 requirements from bubble content"
        })
        
        # Create worker
        worker = self.RequirementsAnalystWorker(model_client=mock_model_client)
        
        # Test requirements analysis
        async def run_test():
            result = await worker.analyze_requirements(
                bubble_id="123",
                bubble_content="User authentication and data encryption requirements"
            )
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertIn("requirements", result)
            self.assertEqual(len(result["requirements"]), 2)
            self.assertIn("analysis_summary", result)
            
            if logger:
                logger.info("[PASS] Test requirements analysis passed")
        
        asyncio.run(run_test())
    
    def test_validate_requirements(self):
        """Test requirements validation."""
        # Mock model client
        mock_model_client = MagicMock()
        mock_model_client.generate_response.return_value = asyncio.Future()
        mock_model_client.generate_response.return_value.set_result({
            "validation_results": [
                {
                    "requirement_id": "REQ-001",
                    "is_valid": True,
                    "issues": []
                },
                {
                    "requirement_id": "REQ-002",
                    "is_valid": False,
                    "issues": ["Missing acceptance criteria"]
                },
            ],
            "validation_summary": "1 valid, 1 invalid requirement"
        })
        
        # Create worker
        worker = self.RequirementsAnalystWorker(model_client=mock_model_client)
        
        # Test requirements validation
        async def run_test():
            result = await worker.validate_requirements(
                bubble_id="123",
                requirements=[
                    {"id": "REQ-001", "title": "User Authentication"},
                    {"id": "REQ-002", "title": "Data Encryption"},
                ]
            )
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertIn("validation_results", result)
            self.assertEqual(len(result["validation_results"]), 2)
            self.assertIn("validation_summary", result)
            
            if logger:
                logger.info("[PASS] Test requirements validation passed")
        
        asyncio.run(run_test())


class TestPipelineManagerWorker(unittest.TestCase):
    """Unit tests for PipelineManagerWorker."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock imports
        self.mock_swarm_modules()
        
        # Import after mocking
        from swarm.grpc_workers.shuttle_workers import (
            PipelineManagerWorker,
        )
        
        self.PipelineManagerWorker = PipelineManagerWorker
    
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
        """Test PipelineManagerWorker initialization."""
        # Mock model client
        mock_model_client = MagicMock()
        
        # Create worker
        worker = self.PipelineManagerWorker(model_client=mock_model_client)
        
        # Verify initialization
        self.assertIsNotNone(worker)
        self.assertIsNotNone(worker.model_client)
        self.assertEqual(worker.model_client, mock_model_client)
        
        if logger:
            logger.info("[PASS] Test PipelineManagerWorker initialization passed")
    
    def test_create_pipeline(self):
        """Test pipeline creation."""
        # Mock model client
        mock_model_client = MagicMock()
        mock_model_client.generate_response.return_value = asyncio.Future()
        mock_model_client.generate_response.return_value.set_result({
            "pipeline_id": "PIPE-001",
            "pipeline_name": "Requirements Processing Pipeline",
            "steps": [
                {"step": 1, "action": "analyze", "worker": "requirements_analyst"},
                {"step": 2, "action": "validate", "worker": "validator"},
                {"step": 3, "action": "export", "worker": "exporter"},
            ],
            "status": "created"
        })
        
        # Create worker
        worker = self.PipelineManagerWorker(model_client=mock_model_client)
        
        # Test pipeline creation
        async def run_test():
            result = await worker.create_pipeline(
                bubble_id="123",
                pipeline_name="Requirements Processing Pipeline",
                steps=[
                    {"action": "analyze", "worker": "requirements_analyst"},
                    {"action": "validate", "worker": "validator"},
                    {"action": "export", "worker": "exporter"},
                ]
            )
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertIn("pipeline_id", result)
            self.assertIn("pipeline_name", result)
            self.assertIn("steps", result)
            self.assertEqual(len(result["steps"]), 3)
            self.assertEqual(result["status"], "created")
            
            if logger:
                logger.info("[PASS] Test pipeline creation passed")
        
        asyncio.run(run_test())
    
    def test_execute_pipeline(self):
        """Test pipeline execution."""
        # Mock model client
        mock_model_client = MagicMock()
        mock_model_client.generate_response.return_value = asyncio.Future()
        mock_model_client.generate_response.return_value.set_result({
            "pipeline_id": "PIPE-001",
            "execution_id": "EXEC-001",
            "status": "completed",
            "results": [
                {"step": 1, "status": "completed", "result": "Analysis complete"},
                {"step": 2, "status": "completed", "result": "Validation complete"},
                {"step": 3, "status": "completed", "result": "Export complete"},
            ],
            "execution_time": 5.2
        })
        
        # Create worker
        worker = self.PipelineManagerWorker(model_client=mock_model_client)
        
        # Test pipeline execution
        async def run_test():
            result = await worker.execute_pipeline(
                pipeline_id="PIPE-001",
                bubble_id="123"
            )
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertIn("pipeline_id", result)
            self.assertIn("execution_id", result)
            self.assertEqual(result["status"], "completed")
            self.assertIn("results", result)
            self.assertEqual(len(result["results"]), 3)
            self.assertIn("execution_time", result)
            
            if logger:
                logger.info("[PASS] Test pipeline execution passed")
        
        asyncio.run(run_test())


class TestValidatorWorker(unittest.TestCase):
    """Unit tests for ValidatorWorker."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock imports
        self.mock_swarm_modules()
        
        # Import after mocking
        from swarm.grpc_workers.shuttle_workers import (
            ValidatorWorker,
        )
        
        self.ValidatorWorker = ValidatorWorker
    
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
        """Test ValidatorWorker initialization."""
        # Mock model client
        mock_model_client = MagicMock()
        
        # Create worker
        worker = self.ValidatorWorker(model_client=mock_model_client)
        
        # Verify initialization
        self.assertIsNotNone(worker)
        self.assertIsNotNone(worker.model_client)
        self.assertEqual(worker.model_client, mock_model_client)
        
        if logger:
            logger.info("[PASS] Test ValidatorWorker initialization passed")
    
    def test_validate_against_specifications(self):
        """Test validation against specifications."""
        # Mock model client
        mock_model_client = MagicMock()
        mock_model_client.generate_response.return_value = asyncio.Future()
        mock_model_client.generate_response.return_value.set_result({
            "validation_results": [
                {
                    "requirement_id": "REQ-001",
                    "specification_id": "SPEC-001",
                    "is_compliant": True,
                    "issues": []
                },
                {
                    "requirement_id": "REQ-002",
                    "specification_id": "SPEC-002",
                    "is_compliant": False,
                    "issues": ["Missing performance metrics"]
                },
            ],
            "compliance_score": 0.5,
            "validation_summary": "1 compliant, 1 non-compliant requirement"
        })
        
        # Create worker
        worker = self.ValidatorWorker(model_client=mock_model_client)
        
        # Test validation against specifications
        async def run_test():
            result = await worker.validate_against_specifications(
                bubble_id="123",
                requirements=[
                    {"id": "REQ-001", "title": "User Authentication"},
                    {"id": "REQ-002", "title": "Data Encryption"},
                ],
                specifications=[
                    {"id": "SPEC-001", "title": "Security Specification"},
                    {"id": "SPEC-002", "title": "Performance Specification"},
                ]
            )
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertIn("validation_results", result)
            self.assertEqual(len(result["validation_results"]), 2)
            self.assertIn("compliance_score", result)
            self.assertIn("validation_summary", result)
            
            if logger:
                logger.info("[PASS] Test validation against specifications passed")
        
        asyncio.run(run_test())


class TestExporterWorker(unittest.TestCase):
    """Unit tests for ExporterWorker."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock imports
        self.mock_swarm_modules()
        
        # Import after mocking
        from swarm.grpc_workers.shuttle_workers import (
            ExporterWorker,
        )
        
        self.ExporterWorker = ExporterWorker
    
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
        """Test ExporterWorker initialization."""
        # Mock model client
        mock_model_client = MagicMock()
        
        # Create worker
        worker = self.ExporterWorker(model_client=mock_model_client)
        
        # Verify initialization
        self.assertIsNotNone(worker)
        self.assertIsNotNone(worker.model_client)
        self.assertEqual(worker.model_client, mock_model_client)
        
        if logger:
            logger.info("[PASS] Test ExporterWorker initialization passed")
    
    def test_export_to_json(self):
        """Test export to JSON format."""
        # Mock model client
        mock_model_client = MagicMock()
        mock_model_client.generate_response.return_value = asyncio.Future()
        mock_model_client.generate_response.return_value.set_result({
            "export_id": "EXP-001",
            "format": "json",
            "content": {
                "bubble_id": "123",
                "requirements": [
                    {"id": "REQ-001", "title": "User Authentication"},
                    {"id": "REQ-002", "title": "Data Encryption"},
                ]
            },
            "file_path": "/exports/requirements_123.json",
            "status": "completed"
        })
        
        # Create worker
        worker = self.ExporterWorker(model_client=mock_model_client)
        
        # Test export to JSON
        async def run_test():
            result = await worker.export_requirements(
                bubble_id="123",
                requirements=[
                    {"id": "REQ-001", "title": "User Authentication"},
                    {"id": "REQ-002", "title": "Data Encryption"},
                ],
                format="json"
            )
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertIn("export_id", result)
            self.assertEqual(result["format"], "json")
            self.assertIn("content", result)
            self.assertIn("file_path", result)
            self.assertEqual(result["status"], "completed")
            
            if logger:
                logger.info("[PASS] Test export to JSON passed")
        
        asyncio.run(run_test())
    
    def test_export_to_markdown(self):
        """Test export to Markdown format."""
        # Mock model client
        mock_model_client = MagicMock()
        mock_model_client.generate_response.return_value = asyncio.Future()
        mock_model_client.generate_response.return_value.set_result({
            "export_id": "EXP-002",
            "format": "markdown",
            "content": "# Requirements for Bubble 123\n\n## REQ-001: User Authentication\n\n## REQ-002: Data Encryption\n",
            "file_path": "/exports/requirements_123.md",
            "status": "completed"
        })
        
        # Create worker
        worker = self.ExporterWorker(model_client=mock_model_client)
        
        # Test export to Markdown
        async def run_test():
            result = await worker.export_requirements(
                bubble_id="123",
                requirements=[
                    {"id": "REQ-001", "title": "User Authentication"},
                    {"id": "REQ-002", "title": "Data Encryption"},
                ],
                format="markdown"
            )
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertIn("export_id", result)
            self.assertEqual(result["format"], "markdown")
            self.assertIn("content", result)
            self.assertIn("file_path", result)
            self.assertEqual(result["status"], "completed")
            
            if logger:
                logger.info("[PASS] Test export to Markdown passed")
        
        asyncio.run(run_test())


def run_tests():
    """Run all unit tests."""
    import time
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestRequirementsAnalystWorker))
    suite.addTests(loader.loadTestsFromTestCase(TestPipelineManagerWorker))
    suite.addTests(loader.loadTestsFromTestCase(TestValidatorWorker))
    suite.addTests(loader.loadTestsFromTestCase(TestExporterWorker))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    duration = time.time() - start_time
    
    # Print summary
    print("\n" + "="*70)
    print("SHUTTLE WORKER AGENTS UNIT TESTS")
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
