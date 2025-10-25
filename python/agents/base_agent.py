"""
Base Agent Class
Abstract base class for all specialized agents in the system
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAgent(ABC):
    """
    Abstract base class for all specialized agents.
    Each agent implements specific functionality (research, code, data, system).
    """

    def __init__(self, name: str):
        """
        Initialize the base agent

        Args:
            name: Agent name for identification
        """
        self.name = name

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent action with given parameters

        Args:
            params: Dictionary of parameters from the tool call

        Returns:
            Dictionary with results (structure depends on agent implementation)

        Raises:
            NotImplementedError: If not overridden by subclass
        """
        pass

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"
