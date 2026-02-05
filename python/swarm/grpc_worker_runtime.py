"""
gRPC Worker Runtime - Distributed Agent Infrastructure

Provides GrpcWorkerAgentRuntime and GrpcWorkerAgentRuntimeHost for
distributed agent communication across process boundaries.
"""

import asyncio
import logging
from typing import Dict, Callable, Optional, Any, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class RoutedAgent(ABC):
    """
    Base class for gRPC routed agents.
    
    Agents inherit from this class to receive messages through
    the gRPC worker runtime and handle them with message handlers.
    """
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._message_handlers: Dict[str, Callable] = {}
    
    def register_handler(self, message_type: str, handler: Callable):
        """
        Register a message handler for a specific message type.
        
        Args:
            message_type: The type of message to handle
            handler: The handler function to call
        """
        self._message_handlers[message_type] = handler
        logger.info(f"{self.agent_name}: Registered handler for {message_type}")
    
    @abstractmethod
    async def handle_message(self, message_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an incoming message.
        
        Args:
            message_type: The type of message
            payload: The message payload
            
        Returns:
            Response dictionary
        """
        pass
    
    async def process_message(self, message_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a message by routing to the appropriate handler.
        
        Args:
            message_type: The type of message
            payload: The message payload
            
        Returns:
            Response dictionary
        """
        handler = self._message_handlers.get(message_type)
        if not handler:
            logger.warning(f"{self.agent_name}: No handler for {message_type}")
            return {"error": f"No handler for {message_type}"}
        
        try:
            response = await handler(payload)
            logger.info(f"{self.agent_name}: Processed {message_type}")
            return response
        except Exception as e:
            logger.error(f"{self.agent_name}: Error processing {message_type}: {e}")
            return {"error": str(e)}


class GrpcWorkerAgentRuntime:
    """
    Runtime for gRPC worker agents.
    
    Manages agent lifecycle, message routing, and communication
    with the gRPC host.
    """
    
    def __init__(self, agent: RoutedAgent):
        """
        Initialize the runtime with a routed agent.
        
        Args:
            agent: The routed agent to manage
        """
        self.agent = agent
        self._running = False
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the worker runtime."""
        if self._running:
            logger.warning(f"{self.agent.agent_name} runtime already running")
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info(f"{self.agent.agent_name} runtime started")
    
    async def stop(self):
        """Stop the worker runtime."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"{self.agent.agent_name} runtime stopped")
    
    async def _worker_loop(self):
        """Main worker loop for processing messages."""
        while self._running:
            try:
                # Wait for message with timeout
                message_type, payload = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                
                # Process message
                response = await self.agent.process_message(message_type, payload)
                
                # Handle response (could be sent back via gRPC)
                logger.debug(f"{self.agent.agent_name}: Response: {response}")
                
            except asyncio.TimeoutError:
                # No message, continue loop
                continue
            except Exception as e:
                logger.error(f"{self.agent.agent_name}: Error in worker loop: {e}")
                await asyncio.sleep(1)  # Avoid tight error loop
    
    async def send_message(self, message_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message to the agent.
        
        Args:
            message_type: The type of message
            payload: The message payload
            
        Returns:
            Response dictionary
        """
        await self._message_queue.put((message_type, payload))
        
        # Wait for response (simplified - in real gRPC would be async)
        await asyncio.sleep(0.1)
        
        # Return a placeholder response
        return {"status": "queued"}


class GrpcWorkerAgentRuntimeHost:
    """
    Host for managing multiple gRPC worker agent runtimes.
    
    Provides centralized lifecycle management and communication
    for distributed agents.
    """
    
    def __init__(self):
        self._runtimes: Dict[str, GrpcWorkerAgentRuntime] = {}
        self._running = False
    
    def register_runtime(self, agent_name: str, runtime: GrpcWorkerAgentRuntime):
        """
        Register a worker runtime.
        
        Args:
            agent_name: Unique name for the agent
            runtime: The runtime instance
        """
        self._runtimes[agent_name] = runtime
        logger.info(f"Registered runtime for {agent_name}")
    
    def get_runtime(self, agent_name: str) -> Optional[GrpcWorkerAgentRuntime]:
        """
        Get a registered runtime.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Runtime instance or None
        """
        return self._runtimes.get(agent_name)
    
    async def start_all(self):
        """Start all registered runtimes."""
        self._running = True
        for name, runtime in self._runtimes.items():
            await runtime.start()
        logger.info(f"Started {len(self._runtimes)} runtimes")
    
    async def stop_all(self):
        """Stop all registered runtimes."""
        self._running = False
        for name, runtime in self._runtimes.items():
            await runtime.stop()
        logger.info(f"Stopped {len(self._runtimes)} runtimes")
    
    async def send_to_agent(self, agent_name: str, message_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message to a specific agent.
        
        Args:
            agent_name: Name of the target agent
            message_type: The type of message
            payload: The message payload
            
        Returns:
            Response dictionary or error
        """
        runtime = self.get_runtime(agent_name)
        if not runtime:
            return {"error": f"Agent {agent_name} not found"}
        
        return await runtime.send_message(message_type, payload)
    
    def list_agents(self) -> List[str]:
        """List all registered agent names."""
        return list(self._runtimes.keys())


# Singleton instance
_runtime_host: Optional[GrpcWorkerAgentRuntimeHost] = None


def get_runtime_host() -> GrpcWorkerAgentRuntimeHost:
    """Get or create the runtime host singleton."""
    global _runtime_host
    if _runtime_host is None:
        _runtime_host = GrpcWorkerAgentRuntimeHost()
    return _runtime_host


__all__ = [
    "RoutedAgent",
    "GrpcWorkerAgentRuntime",
    "GrpcWorkerAgentRuntimeHost",
    "get_runtime_host",
]
