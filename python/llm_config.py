"""
Global LLM Configuration — Single Source of Truth for all VibeMind model selection.

Usage:
    from llm_config import get_model, get_model_config

    model = get_model("classifier")           # -> "gpt-5.4"
    config = get_model_config("classifier")   # -> {"model": "gpt-5.4", "provider": "openai", ...}

Override via environment:
    LLM_MODEL_CLASSIFIER=gpt-4o              # New-style override
    CLASSIFIER_MODEL=gpt-4o                   # Legacy compat

Config file: python/config/llm_models.yml
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_config_cache: Optional[Dict[str, Any]] = None

# Legacy env var mapping: old_env_var -> role
_LEGACY_ENV_MAP = {
    "CLASSIFIER_MODEL": "classifier",
    "RAG_CLASSIFIER_MODEL": "rag_classifier",
    "RESPONSE_MODEL": "response",
    "OPENROUTER_MODEL": "orchestrator",
    "ANALYSIS_MODEL": "analysis",
    "SPACE_AGENT_MODEL": "space_agent",
    "STREAM_LISTENER_MODEL": "stream_listener",
    "MINIBOOK_ENRICHMENT_MODEL": "space_router",
    "OPENROUTER_SUMMARY_MODEL": "summary",
    "OPENROUTER_REWRITE_MODEL": "rewrite",
    "OPENROUTER_EVAL_MODEL": "exploration",
    "N8N_GENERATOR_MODEL": "n8n_generator",
    "CONVERSION_MODEL": "conversion",
    "PERSONALITY_MODEL": "personality",
    "PROFILING_MODEL": "profiling",
    "CONTEXT_MODEL": "context",
    "OPENAI_VISION_MODEL": "vision",
    "OPENAI_REALTIME_MODEL": "voice",
    "OLLAMA_MODEL": "local",
    "OPENAI_SUMMARIZATION_MODEL": "summarization_worker",
    "GEMINI_MODEL": "rewrite_worker",
    "OPENAI_MODEL": "orchestrator",  # Generic fallback
    # --- New roles ---
    "ORCHESTRATOR_MODEL": "tool_orchestrator",
    "DROPE_MODEL": "drope_resolver",
    "FORMAT_DISPATCHER_MODEL": "format_dispatcher",
    "IDEA_ENRICHMENT_MODEL": "idea_enrichment",
    "OPENROUTER_WHITEPAPER_MODEL": "whitepaper",
    "OPENROUTER_STRUCTURE_MODEL": "structure_analysis",
    "OPENROUTER_FEATURE_MODEL": "feature_extraction",
    "OPENROUTER_DOC_MODEL": "doc_generation",
    "DESKTOP_REASONING_MODEL": "desktop_reasoning",
    "DESKTOP_VISION_MODEL": "desktop_vision",
    "DESKTOP_VISION_FAST_MODEL": "desktop_vision_fast",
    "DESKTOP_QUICK_MODEL": "desktop_quick",
    "DESKTOP_ORCHESTRATOR_MODEL": "desktop_orchestrator",
    "DESKTOP_STT_MODEL": "desktop_stt",
    "DESKTOP_TTS_MODEL": "desktop_tts",
    "DESKTOP_WORKER_MODEL": "desktop_worker",
    "N8N_SELECTOR_MODEL": "n8n_selector",
    "ANTHROPIC_MODEL": "agentfarm_anthropic",
    "MIROFISH_LLM_MODEL": "mirofish",
    "MIROFISH_EVAL_MODEL": "mirofish_eval",
    "MIROFISH_OPENROUTER_MODEL": "mirofish_openrouter",
    "CLAUDE_WORKER_MODEL": "claude_worker",
    "MESSAGING_OLLAMA_MODEL": "messaging_relevance",
    # --- Runde 2 ---
    "IDEAS_RESEARCH_MODEL": "ideas_research",
    "CONNECTION_EVAL_MODEL": "connection_eval",
    "MIROFISH_EMBEDDING_MODEL": "mirofish_embedding",
    "TRANSCRIPTION_MODEL": "transcription",
    "WIZARD_OLLAMA_MODEL": "wizard_ollama",
    "WIZARD_OPENROUTER_MODEL": "wizard_openrouter",
    "WIZARD_OPENAI_MODEL": "wizard_openai",
    "ROWBOAT_MODEL": "rowboat_model",
}

# Reverse map: role -> legacy env var (for fallback reads)
_ROLE_TO_LEGACY = {}
for _env, _role in _LEGACY_ENV_MAP.items():
    if _role not in _ROLE_TO_LEGACY:
        _ROLE_TO_LEGACY[_role] = _env


def _load_config() -> Dict[str, Any]:
    """Load and cache the YAML config."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    config_path = Path(__file__).parent / "config" / "llm_models.yml"

    if not config_path.exists():
        logger.warning(f"LLM config not found at {config_path}, using empty config")
        _config_cache = {"providers": {}, "models": {}}
        return _config_cache

    try:
        import yaml
    except ImportError:
        # Fallback: simple YAML parser for basic key-value structure
        logger.warning("PyYAML not installed, using basic parser")
        _config_cache = _parse_yaml_basic(config_path)
        return _config_cache

    with open(config_path, "r", encoding="utf-8") as f:
        _config_cache = yaml.safe_load(f) or {"providers": {}, "models": {}}

    return _config_cache


def _parse_yaml_basic(path: Path) -> Dict[str, Any]:
    """Minimal YAML parser for when PyYAML is not installed."""
    import re
    config = {"providers": {}, "models": {}}
    current_section = None
    current_key = None

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        if indent == 0 and stripped.endswith(":"):
            current_section = stripped[:-1]
            continue

        if current_section == "models" and indent == 2 and stripped.endswith(":"):
            current_key = stripped[:-1]
            config["models"][current_key] = {}
            continue

        if current_section == "models" and current_key and indent == 4:
            m = re.match(r'(\w+):\s*"?([^"]*)"?', stripped)
            if m:
                key, val = m.group(1), m.group(2).strip()
                if val == "null":
                    val = None
                config["models"][current_key][key] = val

        if current_section == "providers" and indent == 2 and stripped.endswith(":"):
            current_key = stripped[:-1]
            config["providers"][current_key] = {}
            continue

        if current_section == "providers" and current_key and indent == 4:
            m = re.match(r'(\w+):\s*"?([^"]*)"?', stripped)
            if m:
                key, val = m.group(1), m.group(2).strip()
                if val == "null":
                    val = None
                config["providers"][current_key][key] = val

    return config


def get_model(role: str) -> str:
    """
    Get model ID for a role.

    Priority: LLM_MODEL_{ROLE} env > legacy env var > YAML config > fallback.
    """
    # 1. New-style env override: LLM_MODEL_CLASSIFIER
    env_key = f"LLM_MODEL_{role.upper()}"
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val

    # 2. Legacy env var fallback: CLASSIFIER_MODEL
    legacy_key = _ROLE_TO_LEGACY.get(role)
    if legacy_key:
        legacy_val = os.environ.get(legacy_key)
        if legacy_val:
            return legacy_val

    # 3. YAML config
    config = _load_config()
    model_config = config.get("models", {}).get(role, {})
    model = model_config.get("model")
    if model:
        return model

    # 4. Fallback
    logger.warning(f"No model configured for role '{role}', falling back to gpt-5.4")
    return "gpt-5.4"


def get_provider(role: str) -> str:
    """Get provider name for a role."""
    config = _load_config()
    return config.get("models", {}).get(role, {}).get("provider", "openai")


def get_api_key(role: str) -> Optional[str]:
    """Get API key for a role's provider."""
    provider = get_provider(role)
    config = _load_config()
    provider_config = config.get("providers", {}).get(provider, {})
    env_var = provider_config.get("api_key_env")
    if env_var:
        return os.environ.get(env_var)
    return None


def get_base_url(role: str) -> Optional[str]:
    """Get base URL for a role's provider."""
    provider = get_provider(role)
    config = _load_config()
    return config.get("providers", {}).get(provider, {}).get("base_url")


def get_max_tokens(role: str) -> Optional[int]:
    """Get max tokens for a role."""
    config = _load_config()
    val = config.get("models", {}).get(role, {}).get("max_tokens")
    if val is not None and val != "null":
        try:
            return int(val)
        except (ValueError, TypeError):
            return None
    return None


def get_model_config(role: str) -> Dict[str, Any]:
    """Get full config dict for a role."""
    return {
        "model": get_model(role),
        "provider": get_provider(role),
        "api_key": get_api_key(role),
        "base_url": get_base_url(role),
        "max_tokens": get_max_tokens(role),
    }


def get_openrouter_model(role: str) -> str:
    """Get model in OpenRouter format (auto-prefix anthropic/ for Claude models)."""
    model = get_model(role)
    if "/" in model:
        return model
    if model.startswith("claude-"):
        return f"anthropic/{model}"
    if model.startswith("gpt-") or model.startswith("o1-"):
        return f"openai/{model}"
    if model.startswith("gemini"):
        return f"google/{model}"
    return model


def list_roles() -> List[str]:
    """List all configured roles."""
    config = _load_config()
    return sorted(config.get("models", {}).keys())


def _resolve_credentials(role: str):
    """Resolve api_key, base_url for a role (shared by sync and async clients)."""
    api_key = get_api_key(role)
    base_url = get_base_url(role)

    if not api_key and get_provider(role) != "ollama":
        # Fallback: try OpenRouter if primary provider key missing
        fallback_key = os.environ.get("OPENROUTER_API_KEY")
        if fallback_key:
            api_key = fallback_key
            base_url = "https://openrouter.ai/api/v1"
            logger.debug(f"Role '{role}': falling back to OpenRouter (primary API key missing)")

    if not api_key and get_provider(role) == "ollama":
        # Ollama doesn't need API key
        api_key = "ollama"

    if not api_key:
        raise ValueError(f"No API key for role '{role}'. Set {_get_api_key_env(role)} or OPENROUTER_API_KEY")

    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    return kwargs


def get_client(role: str):
    """
    Get a configured OpenAI-compatible client for a role.

    Returns an openai.OpenAI instance pointed at the correct provider
    (OpenAI direct, OpenRouter, or Ollama).
    """
    from openai import OpenAI
    return OpenAI(**_resolve_credentials(role))


def get_async_client(role: str):
    """
    Get a configured async OpenAI-compatible client for a role.

    Returns an openai.AsyncOpenAI instance pointed at the correct provider
    (OpenAI direct, OpenRouter, or Ollama).
    """
    from openai import AsyncOpenAI
    return AsyncOpenAI(**_resolve_credentials(role))


def _get_api_key_env(role: str) -> str:
    """Get the env var name for a role's API key."""
    provider = get_provider(role)
    config = _load_config()
    return config.get("providers", {}).get(provider, {}).get("api_key_env", "OPENAI_API_KEY")


def token_kwargs(model: str, max_tokens: int) -> Dict[str, int]:
    """
    Return the correct token-limit kwarg for a model.

    Newer OpenAI models (o1/o3/o4/gpt-5+) require 'max_completion_tokens';
    older models and OpenRouter proxied models use 'max_tokens'.
    """
    model_lower = model.lower() if model else ""
    # Models that require max_completion_tokens
    needs_completion_tokens = any(tag in model_lower for tag in (
        "o1", "o3", "o4", "gpt-5",
    ))
    key = "max_completion_tokens" if needs_completion_tokens else "max_tokens"
    return {key: max_tokens}


def reload_config():
    """Force reload of config (e.g., after editing YAML)."""
    global _config_cache
    _config_cache = None
    _load_config()
