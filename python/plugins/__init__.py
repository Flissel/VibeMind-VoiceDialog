"""
VibeMind Plugin System

Provides dynamic discovery, loading, and management of space plugins.
"""

from plugins.plugin_manager import PluginManager, get_plugin_manager
from plugins.plugin_manifest import PluginManifest

__all__ = ["PluginManager", "PluginManifest", "get_plugin_manager"]
