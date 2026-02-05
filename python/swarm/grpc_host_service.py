"""
gRPC Host Service - Central coordination for distributed gRPC worker agents

This module provides the GrpcWorkerAgentRuntimeHost for managing
distributed gRPC worker agents across process boundaries.

The host service:
1. Manages gRPC worker agent lifecycle (registration, deregistration)
2. Facilitates communication between orchestrator and workers
3. Provides health monitoring and status tracking
4. Handles graceful shutdown and cleanup

Usage:
    from swarm.grpc_host_service import get_grpc_host_service, start_grpc_host_service
    
    # Get the host service singleton
    host = get_grpc_host_service()
    
    # Start the host service (blocking call)
    start_grpc_host_service(host_port=50051)
"""

import logging
import asyncio
import signal
import sys
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Import gRPC worker runtime
try:
    from swarm.grpc_worker_runtime import (
        GrpcWorkerAgentRuntime,
        GrpcWorkerAgentRuntimeHost,
        RoutedAgent,
        get_grpc_worker_runtime,
    )
    HAS_GRPC_RUNTIME = True
except ImportError as e:
    logger.warning(f"gRPC worker runtime not available: {e}")
    HAS_GRPC_RUNTIME = False
    GrpcWorkerAgentRuntime = None
    GrpcWorkerAgentRuntimeHost = None
    RoutedAgent = None
    get_grpc_worker_runtime = None

# Import Shuttle Orchestrator Agent
try:
    from swarm.backend_agents.shuttle_orchestrator_agent import (
        ShuttleOrchestratorAgent,
        get_shuttle_orchestrator_agent,
    )
    HAS_SHUTTLE_ORCHESTRATOR = True
except ImportError as e:
    logger.warning(f"Shuttle orchestrator agent not available: {e}")
    HAS_SHUTTLE_ORCHESTRATOR = False
    ShuttleOrchestratorAgent = None
    get_shuttle_orchestrator_agent = None

# Import Shuttle Worker Agents
try:
    from swarm.grpc_workers.shuttle_workers import (
        RequirementsAnalystWorker,
        PipelineManagerWorker,
        ValidatorWorker,
        ExporterWorker,
        get_requirements_analyst_worker,
        get_pipeline_manager_worker,
        get_validator_worker,
        get_exporter_worker,
    )
    HAS_SHUTTLE_WORKERS = True
except ImportError as e:
    logger.warning(f"Shuttle worker agents not available: {e}")
    HAS_SHUTTLE_WORKERS = False
    RequirementsAnalystWorker = None
    PipelineManagerWorker = None
    ValidatorWorker = None
    ExporterWorker = None
    get_requirements_analyst_worker = None
    get_pipeline_manager_worker = None
    get_validator_worker = None
    get_exporter_worker = None


@dataclass
class WorkerRegistration:
    """Registration info for a worker agent."""
    agent_id: str
    agent_name: str
    agent_type: str
    runtime: Optional[GrpcWorkerAgentRuntime] = None
    status: str = "registered"  # registered, active, stopped, error


class GrpcHostService:
    """
    gRPC Host Service for managing distributed gRPC worker agents.
    
    Responsibilities:
    1. Worker lifecycle management (registration, deregistration)
    2. Communication facilitation between orchestrator and workers
    3. Health monitoring and status tracking
    4. Graceful shutdown and cleanup
    """
    
    def __init__(self, host_port: int = 50051):
        """
        Initialize gRPC host service.
        
        Args:
            host_port: Port for gRPC server (default: 50051)
        """
        self.host_port = host_port
        self.host_address = f"[::]:{host_port}"
        
        # Worker registry
        self._workers: Dict[str, WorkerRegistration] = {}
        
        # gRPC runtime host
        self._runtime_host: Optional[GrpcWorkerAgentRuntimeHost] = None
        
        # Shuttle orchestrator agent
        self._shuttle_orchestrator: Optional[ShuttleOrchestratorAgent] = None
        
        # Shutdown flag
        self._shutdown_requested = False
        
        # Health monitoring
        self._health_check_interval = 30  # seconds
        self._health_check_task: Optional[asyncio.Task] = None
        
        logger.info(f"GrpcHostService initialized on port {host_port}")
    
    def register_worker(
        self,
        agent_id: str,
        agent_name: str,
        agent_type: str,
        runtime: GrpcWorkerAgentRuntime
    ) -> bool:
        """
        Register a worker agent with the host service.
        
        Args:
            agent_id: Unique agent identifier
            agent_name: Human-readable agent name
            agent_type: Agent type (requirements_analyst, pipeline_manager, validator, exporter)
            runtime: gRPC worker runtime instance
        
        Returns:
            True if registration successful, False otherwise
        """
        if agent_id in self._workers:
            logger.warning(f"Worker {agent_id} already registered, skipping")
            return False
        
        registration = WorkerRegistration(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_type=agent_type,
            runtime=runtime,
            status="registered"
        )
        
        self._workers[agent_id] = registration
        logger.info(f"Registered worker: {agent_name} ({agent_type}) - {agent_id}")
        
        return True
    
    def deregister_worker(self, agent_id: str) -> bool:
        """
        Deregister a worker agent from the host service.
        
        Args:
            agent_id: Unique agent identifier
        
        Returns:
            True if deregistration successful, False otherwise
        """
        if agent_id not in self._workers:
            logger.warning(f"Worker {agent_id} not registered, skipping deregistration")
            return False
        
        registration = self._workers[agent_id]
        registration.status = "stopped"
        
        logger.info(f"Deregistered worker: {registration.agent_name} ({registration.agent_type}) - {agent_id}")
        
        return True
    
    def get_worker_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a registered worker.
        
        Args:
            agent_id: Unique agent identifier
        
        Returns:
            Worker status dict or None if not found
        """
        if agent_id not in self._workers:
            return None
        
        registration = self._workers[agent_id]
        return {
            "agent_id": registration.agent_id,
            "agent_name": registration.agent_name,
            "agent_type": registration.agent_type,
            "status": registration.status,
            "runtime": str(type(registration.runtime).__name__) if registration.runtime else None,
        }
    
    def get_all_workers(self) -> List[Dict[str, Any]]:
        """
        Get status of all registered workers.
        
        Returns:
            List of worker status dicts
        """
        return [
            {
                "agent_id": reg.agent_id,
                "agent_name": reg.agent_name,
                "agent_type": reg.agent_type,
                "status": reg.status,
                "runtime": str(type(reg.runtime).__name__) if reg.runtime else None,
            }
            for reg in self._workers.values()
        ]
    
    async def start(self) -> bool:
        """
        Start the gRPC host service.
        
        This method:
        1. Initializes the gRPC runtime host
        2. Registers all shuttle worker agents
        3. Starts the gRPC server
        4. Begins health monitoring
        
        Returns:
            True if startup successful, False otherwise
        """
        logger.info("Starting gRPC host service...")
        
        try:
            # Initialize gRPC runtime host
            if HAS_GRPC_RUNTIME and GrpcWorkerAgentRuntimeHost:
                self._runtime_host = GrpcWorkerAgentRuntimeHost(
                    host_address=self.host_address
                )
                logger.info(f"gRPC runtime host initialized on {self.host_address}")
            else:
                logger.error("gRPC worker runtime not available, cannot start host service")
                return False
            
            # Initialize shuttle orchestrator agent
            if HAS_SHUTTLE_ORCHESTRATOR and ShuttleOrchestratorAgent:
                self._shuttle_orchestrator = get_shuttle_orchestrator_agent()
                logger.info("Shuttle orchestrator agent initialized")
            else:
                logger.warning("Shuttle orchestrator agent not available")
            
            # Register shuttle worker agents
            if HAS_SHUTTLE_WORKERS:
                await self._register_shuttle_workers()
            else:
                logger.warning("Shuttle worker agents not available")
            
            # Start gRPC server
            await self._runtime_host.start()
            logger.info(f"gRPC server started on {self.host_address}")
            
            # Start health monitoring
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("Health monitoring started")
            
            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            logger.info("gRPC host service started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start gRPC host service: {e}")
            return False
    
    async def _register_shuttle_workers(self) -> None:
        """Register all shuttle worker agents with the host service."""
        logger.info("Registering shuttle worker agents...")
        
        # Register Requirements Analyst Worker
        if HAS_SHUTTLE_WORKERS and RequirementsAnalystWorker and get_requirements_analyst_worker:
            worker = get_requirements_analyst_worker()
            if worker:
                self.register_worker(
                    agent_id="requirements_analyst",
                    agent_name="Requirements Analyst Worker",
                    agent_type="requirements_analyst",
                    runtime=worker
                )
        
        # Register Pipeline Manager Worker
        if HAS_SHUTTLE_WORKERS and PipelineManagerWorker and get_pipeline_manager_worker:
            worker = get_pipeline_manager_worker()
            if worker:
                self.register_worker(
                    agent_id="pipeline_manager",
                    agent_name="Pipeline Manager Worker",
                    agent_type="pipeline_manager",
                    runtime=worker
                )
        
        # Register Validator Worker
        if HAS_SHUTTLE_WORKERS and ValidatorWorker and get_validator_worker:
            worker = get_validator_worker()
            if worker:
                self.register_worker(
                    agent_id="validator",
                    agent_name="Validator Worker",
                    agent_type="validator",
                    runtime=worker
                )
        
        # Register Exporter Worker
        if HAS_SHUTTLE_WORKERS and ExporterWorker and get_exporter_worker:
            worker = get_exporter_worker()
            if worker:
                self.register_worker(
                    agent_id="exporter",
                    agent_name="Exporter Worker",
                    agent_type="exporter",
                    runtime=worker
                )
        
        logger.info(f"Registered {len(self._workers)} shuttle worker agents")
    
    async def _health_check_loop(self) -> None:
        """Periodic health check for all registered workers."""
        while not self._shutdown_requested:
            try:
                await asyncio.sleep(self._health_check_interval)
                
                # Check health of all workers
                for agent_id, registration in self._workers.items():
                    if registration.runtime:
                        try:
                            # Check if worker is responsive
                            is_healthy = await registration.runtime.check_health(agent_id)
                            
                            if not is_healthy:
                                logger.warning(f"Worker {registration.agent_name} ({agent_id}) is unhealthy")
                                registration.status = "error"
                            else:
                                registration.status = "active"
                        except Exception as e:
                            logger.error(f"Health check failed for {registration.agent_name}: {e}")
                            registration.status = "error"
                
            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                break
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_requested = True
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Signal handlers registered for graceful shutdown")
    
    async def stop(self) -> None:
        """
        Stop the gRPC host service gracefully.
        
        This method:
        1. Cancels health monitoring
        2. Stops the gRPC server
        3. Deregisters all workers
        4. Cleans up resources
        """
        logger.info("Stopping gRPC host service...")
        
        # Set shutdown flag
        self._shutdown_requested = True
        
        # Cancel health monitoring
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            logger.info("Health monitoring stopped")
        
        # Stop gRPC server
        if self._runtime_host:
            await self._runtime_host.stop()
            logger.info("gRPC server stopped")
        
        # Deregister all workers
        for agent_id in list(self._workers.keys()):
            self.deregister_worker(agent_id)
        
        logger.info("gRPC host service stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get overall status of the gRPC host service.
        
        Returns:
            Status dict with host and worker information
        """
        return {
            "host_address": self.host_address,
            "host_status": "running" if self._runtime_host and self._runtime_host.is_running() else "stopped",
            "workers_count": len(self._workers),
            "workers": self.get_all_workers(),
            "shuttle_orchestrator": str(type(self._shuttle_orchestrator).__name__) if self._shuttle_orchestrator else None,
        }


# Singleton instance
_host_service: Optional[GrpcHostService] = None


def get_grpc_host_service(host_port: int = 50051) -> GrpcHostService:
    """
    Get or create gRPC host service singleton.
    
    Args:
        host_port: Port for gRPC server (default: 50051)
    
    Returns:
        GrpcHostService instance
    """
    global _host_service
    if _host_service is None:
        _host_service = GrpcHostService(host_port=host_port)
        logger.info(f"Created gRPC host service singleton on port {host_port}")
    return _host_service


async def start_grpc_host_service(host_port: int = 50051) -> None:
    """
    Start the gRPC host service (blocking call).
    
    This is a convenience function that:
    1. Gets the host service singleton
    2. Starts the host service
    3. Runs until shutdown signal received
    
    Args:
        host_port: Port for gRPC server (default: 50051)
    """
    host = get_grpc_host_service(host_port=host_port)
    
    try:
        success = await host.start()
        if not success:
            logger.error("Failed to start gRPC host service")
            sys.exit(1)
        
        logger.info("gRPC host service running. Press Ctrl+C to stop.")
        
        # Keep the event loop running
        while not host._shutdown_requested:
            await asyncio.sleep(1)
        
        # Graceful shutdown
        await host.stop()
        logger.info("gRPC host service shutdown complete")
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        await host.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await host.stop()
        sys.exit(1)


def run_grpc_host_service(host_port: int = 50051) -> None:
    """
    Run the gRPC host service synchronously.
    
    This is a convenience function for running the host service
    from synchronous code (e.g., in a script).
    
    Args:
        host_port: Port for gRPC server (default: 50051)
    """
    try:
        asyncio.run(start_grpc_host_service(host_port=host_port))
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


__all__ = [
    "GrpcHostService",
    "get_grpc_host_service",
    "start_grpc_host_service",
    "run_grpc_host_service",
]
