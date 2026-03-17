"""Auto-generates SPACE_BINDINGS from registered backend agents."""

import logging
import re
from typing import Dict, Optional

from .types import SpaceBinding

logger = logging.getLogger(__name__)

# Tier 2: Keyword patterns -> Space (German + English)
KEYWORD_BINDINGS: Dict[str, SpaceBinding] = {
    r"screenshot|bildschirm|klick|browser|click": SpaceBinding(
        space="desktop", agent="DesktopAgent", pattern="keyword:desktop"
    ),
    r"workflow|automatisierung|n8n|automation": SpaceBinding(
        space="n8n", agent="N8nBackendAgent", pattern="keyword:n8n"
    ),
    r"termin|erinnerung|wecker|timer|schedule|reminder": SpaceBinding(
        space="schedule", agent="ScheduleBackendAgent", pattern="keyword:schedule"
    ),
}

# Compiled keyword regexes (built once)
_COMPILED_KEYWORDS: Dict[re.Pattern, SpaceBinding] = {}


def _compile_keywords():
    """Compile keyword patterns once."""
    global _COMPILED_KEYWORDS
    if not _COMPILED_KEYWORDS:
        _COMPILED_KEYWORDS = {
            re.compile(pattern, re.IGNORECASE): binding
            for pattern, binding in KEYWORD_BINDINGS.items()
        }


def build_prefix_bindings() -> Dict[str, SpaceBinding]:
    """
    Scan all registered backend agents and extract prefix -> space mappings
    from their EVENT_TO_TOOL dicts.

    Returns dict like {"bubble.": SpaceBinding(space="ideas", ...), ...}
    """
    bindings: Dict[str, SpaceBinding] = {}

    # Map of agent_key -> (space_name, agent_name, stream)
    agent_registry = {
        "bubbles": ("ideas", "BubblesAgent", "events:tasks:bubbles"),
        "ideas": ("ideas", "IdeasAgent", "events:tasks:ideas"),
        "desktop": ("desktop", "DesktopAgent", "events:tasks:desktop"),
        "coding": ("coding", "CodingAgent", "events:tasks:coding"),
        "roarboot": ("rowboat", "RoarbootBackendAgent", "events:tasks:roarboot"),
        "n8n": ("n8n", "N8nBackendAgent", "events:tasks:n8n"),
        "schedule": ("schedule", "ScheduleBackendAgent", "events:tasks:schedule"),
        "minibook": ("minibook", "MinibookBackendAgent", "events:tasks:minibook"),
        "zeroclaw_research": ("research", "ZeroClawResearchAgent", "events:tasks:zeroclaw"),
        "video": ("video", "VideoBackendAgent", "events:tasks:video"),
    }

    for agent_key, (space, agent_name, stream) in agent_registry.items():
        try:
            module = __import__("swarm.backend_agents", fromlist=[f"get_{agent_key}_agent"])
            getter = getattr(module, f"get_{agent_key}_agent", None)
            if not getter:
                continue
            agent_instance = getter()
            if not agent_instance:
                continue

            event_to_tool = getattr(agent_instance, "EVENT_TO_TOOL", {})

            # Extract unique prefixes
            prefixes = set()
            for event_type in event_to_tool.keys():
                prefix = event_type.split(".")[0] + "."
                prefixes.add(prefix)

            for prefix in prefixes:
                bindings[prefix] = SpaceBinding(
                    space=space, agent=agent_name,
                    stream=stream, pattern=f"prefix:{prefix}*"
                )
        except Exception as e:
            logger.debug(f"Could not load agent {agent_key}: {e}")
            continue

    # Static fallback is authoritative for prefix->space mapping.
    # Dynamic extraction can produce wrong mappings when agents share event prefixes
    # (e.g. CodingAgent has "idea.to_project" but Ideas owns the "idea." prefix).
    # Static takes priority; dynamic only adds genuinely new prefixes.
    static = _get_static_fallback()
    merged = dict(static)
    for prefix, binding in bindings.items():
        if prefix not in merged:
            merged[prefix] = binding

    logger.info(f"Built {len(merged)} prefix bindings ({len(merged) - len(static)} dynamic additions)")
    return merged


def _get_static_fallback() -> Dict[str, SpaceBinding]:
    """Static fallback bindings if agent introspection fails."""
    return {
        "bubble.": SpaceBinding(space="ideas", agent="BubblesAgent", stream="events:tasks:bubbles", pattern="prefix:bubble.*"),
        "idea.": SpaceBinding(space="ideas", agent="IdeasAgent", stream="events:tasks:ideas", pattern="prefix:idea.*"),
        "code.": SpaceBinding(space="coding", agent="CodingAgent", stream="events:tasks:coding", pattern="prefix:code.*"),
        "desktop.": SpaceBinding(space="desktop", agent="DesktopAgent", stream="events:tasks:desktop", pattern="prefix:desktop.*"),
        "web.": SpaceBinding(space="desktop", agent="DesktopAgent", stream="events:tasks:desktop", pattern="prefix:web.*"),
        "messaging.": SpaceBinding(space="desktop", agent="DesktopAgent", stream="events:tasks:desktop", pattern="prefix:messaging.*"),
        "openclaw.": SpaceBinding(space="desktop", agent="DesktopAgent", stream="events:tasks:desktop", pattern="prefix:openclaw.*"),
        "roarboot.": SpaceBinding(space="rowboat", agent="RoarbootBackendAgent", stream="events:tasks:roarboot", pattern="prefix:roarboot.*"),
        "research.": SpaceBinding(space="research", agent="ZeroClawResearchAgent", stream="events:tasks:zeroclaw", pattern="prefix:research.*"),
        "minibook.": SpaceBinding(space="minibook", agent="MinibookBackendAgent", stream="events:tasks:minibook", pattern="prefix:minibook.*"),
        "schedule.": SpaceBinding(space="schedule", agent="ScheduleBackendAgent", stream="events:tasks:schedule", pattern="prefix:schedule.*"),
        "n8n.": SpaceBinding(space="n8n", agent="N8nBackendAgent", stream="events:tasks:n8n", pattern="prefix:n8n.*"),
        "video.": SpaceBinding(space="video", agent="VideoBackendAgent", stream="events:tasks:video", pattern="prefix:video.*"),
    }


def match_keyword(user_input: str) -> Optional[SpaceBinding]:
    """Tier 2: Match user input against keyword patterns."""
    _compile_keywords()
    normalized = user_input.lower().strip()
    for pattern, binding in _COMPILED_KEYWORDS.items():
        if pattern.search(normalized):
            return binding
    return None
