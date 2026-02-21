"""
Agent Transfer Handler

Manages agent switching in the VibeMind voice system.
Monitors for pending agent switch signals and coordinates session transitions.

Flow:
1. User requests agent switch (e.g., "connect me to Alice")
2. ElevenLabs calls transfer_to_AGENT client tool
3. Python handler sets _pending_agent_switch signal
4. TransferHandler detects signal and:
   a. Ends current voice session
   b. Starts new session with target agent
   c. Updates UI via Electron IPC
"""

import os
import sys
import time
import threading
import logging
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)


class TransferHandler:
    """
    Coordinates agent transfers between voice sessions.
    
    Runs as a background monitor that:
    - Watches for pending agent switch signals
    - Orchestrates smooth session transitions
    - Notifies UI of agent changes
    """
    
    def __init__(
        self,
        get_pending_switch: Callable[[], Optional[Dict[str, Any]]],
        end_session: Callable[[], None],
        start_session: Callable[[str], None],
        send_to_electron: Callable[[dict], None]
    ):
        """
        Initialize transfer handler.
        
        Args:
            get_pending_switch: Function to get pending switch signal (from bubble_tools)
            end_session: Function to end current voice session
            start_session: Function to start voice session with agent_id
            send_to_electron: Function to send IPC messages to Electron
        """
        self.get_pending_switch = get_pending_switch
        self.end_session = end_session
        self.start_session = start_session
        self.send_to_electron = send_to_electron
        
        self._running = False
        self._watcher_thread: Optional[threading.Thread] = None
        self._current_agent_id: Optional[str] = None
        self._current_agent_name: str = "Rachel"
        
        # Agent ID -> Name mapping
        self._agent_names = self._load_agent_names()
    
    def _load_agent_names(self) -> Dict[str, str]:
        """Load agent ID to name mapping from environment."""
        mapping = {}
        
        # Load from env
        agent_vars = {
            "AGENT_MULTIVERSE": "Rachel",
            "AGENT_RACHEL": "Rachel",
        }
        
        for env_var, name in agent_vars.items():
            agent_id = os.getenv(env_var)
            if agent_id:
                mapping[agent_id] = name
        
        return mapping
    
    def get_agent_name(self, agent_id: str) -> str:
        """Get human-readable name for agent ID."""
        return self._agent_names.get(agent_id, "Agent")
    
    def start(self, initial_agent_id: str):
        """
        Start the transfer handler.
        
        Args:
            initial_agent_id: ID of the initially active agent
        """
        self._current_agent_id = initial_agent_id
        self._current_agent_name = self.get_agent_name(initial_agent_id)
        self._running = True
        
        self._watcher_thread = threading.Thread(
            target=self._watch_for_transfers,
            daemon=True
        )
        self._watcher_thread.start()
        
        logger.info(f"TransferHandler started with {self._current_agent_name}")
    
    def stop(self):
        """Stop the transfer handler."""
        self._running = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=1.0)
        logger.info("TransferHandler stopped")
    
    def _watch_for_transfers(self):
        """Background thread watching for agent switch signals."""
        while self._running:
            try:
                switch_info = self.get_pending_switch()
                
                if switch_info:
                    self._handle_transfer(switch_info)
                
            except Exception as e:
                logger.error(f"Error in transfer watcher: {e}")
            
            time.sleep(0.1)  # Poll every 100ms
    
    def _handle_transfer(self, switch_info: Dict[str, Any]):
        """
        Handle an agent transfer request.
        
        Args:
            switch_info: Transfer details from bubble_tools
                - agent_id: Target agent ID
                - bubble_id: Target bubble (if entering one)
                - bubble_title: Human-readable name
        """
        target_agent_id = switch_info.get("agent_id")
        target_name = switch_info.get("bubble_title", "Agent")
        
        if not target_agent_id:
            logger.warning("Transfer request missing agent_id")
            return
        
        # Same agent? Skip
        if target_agent_id == self._current_agent_id:
            logger.info(f"Already on {target_name}, skipping transfer")
            return
        
        logger.info(f"Transferring: {self._current_agent_name} -> {target_name}")
        
        # Notify UI of transfer start
        self.send_to_electron({
            "type": "agent_transfer_start",
            "from_agent": self._current_agent_name,
            "to_agent": target_name,
            "target_agent_id": target_agent_id
        })
        
        try:
            # End current session
            logger.info("Ending current voice session...")
            self.end_session()
            
            # Brief pause for clean transition
            time.sleep(0.3)
            
            # Start new session with target agent
            logger.info(f"Starting session with {target_name}...")
            self.start_session(target_agent_id)
            
            # Update tracking vars
            from_agent_name = self._current_agent_name
            self._current_agent_id = target_agent_id
            self._current_agent_name = target_name
            
            # Notify UI of successful transfer
            self.send_to_electron({
                "type": "agent_transfer_complete",
                "from_agent": from_agent_name,
                "to_agent": target_name,
                "target_agent_id": target_agent_id
            })
            
            logger.info(f"Transfer complete: Now talking to {target_name}")
            
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            
            # Notify UI of failure
            self.send_to_electron({
                "type": "agent_transfer_error",
                "error": str(e),
                "attempted_agent": target_name
            })
    
    @property
    def current_agent(self) -> str:
        """Get current agent name."""
        return self._current_agent_name
    
    @property
    def current_agent_id(self) -> Optional[str]:
        """Get current agent ID."""
        return self._current_agent_id


# Singleton instance for global access
_transfer_handler: Optional[TransferHandler] = None


def get_transfer_handler() -> Optional[TransferHandler]:
    """Get the global transfer handler instance."""
    return _transfer_handler


def init_transfer_handler(
    get_pending_switch: Callable,
    end_session: Callable,
    start_session: Callable,
    send_to_electron: Callable
) -> TransferHandler:
    """
    Initialize the global transfer handler.
    
    Should be called once during app startup.
    """
    global _transfer_handler
    
    _transfer_handler = TransferHandler(
        get_pending_switch=get_pending_switch,
        end_session=end_session,
        start_session=start_session,
        send_to_electron=send_to_electron
    )
    
    return _transfer_handler


__all__ = [
    "TransferHandler",
    "get_transfer_handler",
    "init_transfer_handler",
]