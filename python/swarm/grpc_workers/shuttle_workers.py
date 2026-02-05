"""
Shuttle Worker Agents - gRPC Workers for Shuttle Domain

Provides specialized worker agents for:
- Requirements Analyst
- Pipeline Manager
- Validator
- Exporter

Each worker is a gRPC worker agent with GrpcWorkerAgentRuntime.
"""

import logging
from typing import Dict, Callable, Any

from swarm.grpc_worker_runtime import RoutedAgent

logger = logging.getLogger(__name__)


class RequirementsAnalystWorker(RoutedAgent):
    """
    Worker agent for requirements analysis and validation.
    
    Analyzes bubble content and generates requirements using LLM.
    """
    
    def __init__(self):
        super().__init__("requirements_analyst")
        self._register_handlers()
    
    def _register_handlers(self):
        """Register message handlers for this worker."""
        self.register_handler("analyze_requirements", self._handle_analyze_requirements)
        self.register_handler("validate_requirements", self._handle_validate_requirements)
    
    async def _handle_analyze_requirements(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle requirements analysis request.
        
        Args:
            payload: Analysis request with bubble_id
            
        Returns:
            Analysis result
        """
        bubble_id = payload.get("bubble_id")
        logger.info(f"Analyzing requirements for bubble {bubble_id}")
        
        # Import shuttle tools
        try:
            from tools.bubble_requirements_tool import process_bubble_requirements
            
            # Process bubble requirements
            result = await process_bubble_requirements(bubble_id)
            
            return {
                "status": "completed",
                "bubble_id": bubble_id,
                "requirements": result,
            }
        except Exception as e:
            logger.error(f"Error analyzing requirements: {e}")
            return {
                "status": "error",
                "error": str(e),
            }
    
    async def _handle_validate_requirements(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle requirements validation request.
        
        Args:
            payload: Validation request with requirements
            
        Returns:
            Validation result
        """
        requirements = payload.get("requirements", [])
        logger.info(f"Validating {len(requirements)} requirements")
        
        # Simple validation logic
        validation_errors = []
        for i, req in enumerate(requirements):
            if not req.get("title"):
                validation_errors.append(f"Requirement {i+1}: Missing title")
            if not req.get("description"):
                validation_errors.append(f"Requirement {i+1}: Missing description")
        
        if validation_errors:
            return {
                "status": "failed",
                "errors": validation_errors,
            }
        else:
            return {
                "status": "completed",
                "valid": True,
            }


class PipelineManagerWorker(RoutedAgent):
    """
    Worker agent for pipeline management and coordination.
    
    Manages pipeline stages and coordinates execution across workers.
    """
    
    def __init__(self):
        super().__init__("pipeline_manager")
        self._register_handlers()
    
    def _register_handlers(self):
        """Register message handlers for this worker."""
        self.register_handler("create_pipeline", self._handle_create_pipeline)
        self.register_handler("update_pipeline", self._handle_update_pipeline)
        self.register_handler("execute_pipeline", self._handle_execute_pipeline)
    
    async def _handle_create_pipeline(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle pipeline creation request.
        
        Args:
            payload: Pipeline creation request
            
        Returns:
            Pipeline creation result
        """
        pipeline_name = payload.get("pipeline_name")
        stages = payload.get("stages", [])
        logger.info(f"Creating pipeline {pipeline_name} with {len(stages)} stages")
        
        return {
            "status": "completed",
            "pipeline_id": f"pipeline_{pipeline_name}",
            "stages": stages,
        }
    
    async def _handle_update_pipeline(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle pipeline update request.
        
        Args:
            payload: Pipeline update request
            
        Returns:
            Pipeline update result
        """
        pipeline_id = payload.get("pipeline_id")
        stage = payload.get("stage")
        status = payload.get("status")
        logger.info(f"Updating pipeline {pipeline_id} stage {stage} to {status}")
        
        return {
            "status": "completed",
            "pipeline_id": pipeline_id,
            "stage": stage,
            "pipeline_status": status,
        }
    
    async def _handle_execute_pipeline(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle pipeline execution request.
        
        Args:
            payload: Pipeline execution request
            
        Returns:
            Pipeline execution result
        """
        pipeline_id = payload.get("pipeline_id")
        logger.info(f"Executing pipeline {pipeline_id}")
        
        return {
            "status": "completed",
            "pipeline_id": pipeline_id,
            "execution_status": "started",
        }


class ValidatorWorker(RoutedAgent):
    """
    Worker agent for requirements validation against specifications.
    
    Validates generated requirements against project specifications.
    """
    
    def __init__(self):
        super().__init__("validator")
        self._register_handlers()
    
    def _register_handlers(self):
        """Register message handlers for this worker."""
        self.register_handler("validate_against_spec", self._handle_validate_against_spec)
        self.register_handler("check_completeness", self._handle_check_completeness)
    
    async def _handle_validate_against_spec(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle validation against specifications request.
        
        Args:
            payload: Validation request with requirements and specifications
            
        Returns:
            Validation result
        """
        requirements = payload.get("requirements", [])
        specifications = payload.get("specifications", {})
        logger.info(f"Validating {len(requirements)} requirements against specifications")
        
        # Simple validation logic
        validation_results = []
        for req in requirements:
            req_id = req.get("id")
            title = req.get("title", "")
            
            # Check if requirement meets specifications
            meets_spec = True
            if specifications.get("min_length") and len(title) < specifications["min_length"]:
                meets_spec = False
            if specifications.get("required_keywords"):
                required_keywords = specifications["required_keywords"]
                if not any(kw in title.lower() for kw in required_keywords):
                    meets_spec = False
            
            validation_results.append({
                "id": req_id,
                "title": title,
                "meets_specification": meets_spec,
            })
        
        return {
            "status": "completed",
            "validation_results": validation_results,
        }
    
    async def _handle_check_completeness(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle completeness check request.
        
        Args:
            payload: Completeness check request with requirements
            
        Returns:
            Completeness check result
        """
        requirements = payload.get("requirements", [])
        logger.info(f"Checking completeness of {len(requirements)} requirements")
        
        # Simple completeness check
        missing_fields = []
        for req in requirements:
            if not req.get("title"):
                missing_fields.append(f"Requirement {req.get('id')}: Missing title")
            if not req.get("description"):
                missing_fields.append(f"Requirement {req.get('id')}: Missing description")
            if not req.get("priority"):
                missing_fields.append(f"Requirement {req.get('id')}: Missing priority")
        
        return {
            "status": "completed",
            "complete": len(missing_fields) == 0,
            "missing_fields": missing_fields,
        }


class ExporterWorker(RoutedAgent):
    """
    Worker agent for exporting requirements in various formats.
    
    Exports requirements to different formats like JSON, CSV, Markdown.
    """
    
    def __init__(self):
        super().__init__("exporter")
        self._register_handlers()
    
    def _register_handlers(self):
        """Register message handlers for this worker."""
        self.register_handler("export_json", self._handle_export_json)
        self.register_handler("export_csv", self._handle_export_csv)
        self.register_handler("export_markdown", self._handle_export_markdown)
    
    async def _handle_export_json(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle JSON export request.
        
        Args:
            payload: Export request with requirements
            
        Returns:
            Export result
        """
        requirements = payload.get("requirements", [])
        logger.info(f"Exporting {len(requirements)} requirements to JSON")
        
        return {
            "status": "completed",
            "format": "json",
            "data": requirements,
        }
    
    async def _handle_export_csv(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle CSV export request.
        
        Args:
            payload: Export request with requirements
            
        Returns:
            Export result
        """
        requirements = payload.get("requirements", [])
        logger.info(f"Exporting {len(requirements)} requirements to CSV")
        
        return {
            "status": "completed",
            "format": "csv",
            "data": requirements,
        }
    
    async def _handle_export_markdown(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle Markdown export request.
        
        Args:
            payload: Export request with requirements
            
        Returns:
            Export result
        """
        requirements = payload.get("requirements", [])
        logger.info(f"Exporting {len(requirements)} requirements to Markdown")
        
        return {
            "status": "completed",
            "format": "markdown",
            "data": requirements,
        }


def create_requirements_analyst_worker() -> RequirementsAnalystWorker:
    """Create Requirements Analyst Worker."""
    return RequirementsAnalystWorker()


def create_pipeline_manager_worker() -> PipelineManagerWorker:
    """Create Pipeline Manager Worker."""
    return PipelineManagerWorker()


def create_validator_worker() -> ValidatorWorker:
    """Create Validator Worker."""
    return ValidatorWorker()


def create_exporter_worker() -> ExporterWorker:
    """Create Exporter Worker."""
    return ExporterWorker()


__all__ = [
    "RequirementsAnalystWorker",
    "PipelineManagerWorker",
    "ValidatorWorker",
    "ExporterWorker",
    "create_requirements_analyst_worker",
    "create_pipeline_manager_worker",
    "create_validator_worker",
    "create_exporter_worker",
]
