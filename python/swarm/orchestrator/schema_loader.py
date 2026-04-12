"""
Schema Loader — loads tool_schemas.yml and exposes helpers for prompt generation.

The YAML schema is the single source of truth for:
- Event descriptions (human-readable)
- Few-shot examples (natural language → structured output)
- Parameter requirements
- Triggers/anti-triggers (disambiguation hints)

This module is used by:
- YamlClassifier (orchestrator/yaml_classifier.py) — builds compact prompts
- train_brain_from_schemas.py — training data source
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parents[2] / "config" / "tool_schemas.yml"
_CACHE: Optional[Dict[str, Any]] = None


def _load() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        if not _SCHEMA_PATH.exists():
            logger.warning(f"Schema file missing: {_SCHEMA_PATH}")
            _CACHE = {}
        else:
            with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
                _CACHE = yaml.safe_load(f) or {}
            logger.info(f"Loaded {len(_CACHE)} event schemas from {_SCHEMA_PATH.name}")
    return _CACHE


def get_all_events() -> Dict[str, Any]:
    """Return all event schemas as {event_type: schema_dict}."""
    return dict(_load())


def get_events_for_prefix(prefix: str) -> Dict[str, Any]:
    """Return event schemas whose type starts with `prefix` (e.g. 'bubble', 'idea')."""
    schemas = _load()
    return {evt: s for evt, s in schemas.items() if evt.startswith(f"{prefix}.") or evt == prefix}


def render_event_block(event_type: str, schema: Dict[str, Any], max_examples: int = 3) -> str:
    """Render a single event as a compact prompt block."""
    lines = [f"- {event_type}: {schema.get('description', '').strip()}"]

    params = schema.get("params") or {}
    required = [name for name, spec in params.items() if isinstance(spec, dict) and spec.get("required")]
    if required:
        lines.append(f"  required params: {', '.join(required)}")

    examples = (schema.get("examples") or [])[:max_examples]
    for ex in examples:
        if not isinstance(ex, dict):
            continue
        user_text = ex.get("input", "").strip()
        output = ex.get("output") or {}
        if user_text:
            lines.append(f'  ex: "{user_text}" -> {output}')

    return "\n".join(lines)


def render_events_block(event_types: List[str], max_examples: int = 3) -> str:
    """Render multiple events as a prompt block, separated by blank lines."""
    schemas = _load()
    blocks = []
    for evt in event_types:
        if evt in schemas:
            blocks.append(render_event_block(evt, schemas[evt], max_examples))
    return "\n\n".join(blocks)


def render_prefix_block(prefix: str, max_examples: int = 3) -> str:
    """Render all events for a prefix (e.g. 'bubble' → all bubble.* events)."""
    events = get_events_for_prefix(prefix)
    return render_events_block(sorted(events.keys()), max_examples)


def render_ideas_space_block(max_examples: int = 3) -> str:
    """Render all Ideas-Space events (bubble.* + idea.*) for classifier prompt."""
    schemas = _load()
    event_types = sorted(
        e for e in schemas.keys()
        if e.startswith("bubble.") or e.startswith("idea.")
    )
    return render_events_block(event_types, max_examples)
