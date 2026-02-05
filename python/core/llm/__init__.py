"""
VibeMind Core LLM Module

LLM clients for OpenRouter (cloud) and Ollama (local fallback).
Re-exports from legacy swarm/ module for backward compatibility.
"""

# Re-export from legacy swarm module
from swarm.cloud_client import get_model_client
from swarm.ollama_client import get_ollama_client

__all__ = [
    "get_model_client",
    "get_ollama_client",
]
