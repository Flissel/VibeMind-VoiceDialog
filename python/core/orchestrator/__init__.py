"""
VibeMind Core Orchestrator Module

Intent classification, orchestration, and response generation.
Re-exports from legacy swarm/orchestrator/ module for backward compatibility.
"""

# Re-export from legacy swarm.orchestrator module
from swarm.orchestrator import (
    IntentClassifier,
    IntentOrchestrator,
    get_orchestrator,
    NotificationQueue,
    Notification,
    get_notification_queue,
    ResponseGenerator,
    get_response_generator,
    SystemContextStore,
    get_system_context_store,
)

__all__ = [
    # Intent Classification
    "IntentClassifier",
    # Orchestration
    "IntentOrchestrator",
    "get_orchestrator",
    # Notifications
    "NotificationQueue",
    "Notification",
    "get_notification_queue",
    # Response Generation
    "ResponseGenerator",
    "get_response_generator",
    # System Context
    "SystemContextStore",
    "get_system_context_store",
]
