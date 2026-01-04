"""
AutoGen Workers Package

This package contains AutoGen gRPC worker agents that provide
specialized capabilities to ElevenLabs conversational agents.

Available Workers:
- KnowledgeWorker: URL fetching, web search, document processing
- ClaudeWorker: Desktop automation via Claude Opus 4.5 + OpenRouter

Adapters:
- mcp_tools_adapter: MCP tools wrapper for Claude worker
"""

__version__ = "0.2.0"

# Lazy imports to avoid circular dependencies
def get_claude_worker():
    """Get ClaudeWorker class."""
    from .claude_worker import ClaudeWorker
    return ClaudeWorker

def get_mcp_tools():
    """Get MCP tools adapter functions."""
    from .mcp_tools_adapter import execute_tool, get_tools_for_llm, get_status
    return {
        "execute_tool": execute_tool,
        "get_tools_for_llm": get_tools_for_llm,
        "get_status": get_status
    }
