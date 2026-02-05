"""
Memory Sub-Agent Tools - Voice-callable tools for user profiling queries.

These tools allow agents to query and manage user profiling data
stored by MemorySubAgents across all domains.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def get_domain_profile(domain: str = "ideas") -> str:
    """
    Retrieve the accumulated user profile for a specific domain.

    Args:
        domain: Domain to query (ideas, coding, desktop)

    Returns:
        Formatted profile insights string
    """
    api_key = os.getenv("SUPERMEMORY_API_KEY", "")
    if not api_key:
        return f"Kein {domain}-Profil verfuegbar (Supermemory nicht konfiguriert)."

    try:
        from supermemory import AsyncSupermemory
        client = AsyncSupermemory(api_key=api_key)

        container_tag = f"vibemind-profile-{domain}"
        response = await client.search.execute(
            q=f"user behavior {domain}",
            container_tags=[container_tag],
            limit=10,
        )

        if not response.results:
            return f"Noch keine {domain}-Profil-Daten gespeichert."

        lines = [f"[{domain.upper()} Profil] {len(response.results)} Insights:"]
        for r in response.results:
            lines.append(f"  - {r.content[:150]}")

        return "\n".join(lines)

    except Exception as e:
        logger.debug(f"get_domain_profile failed: {e}")
        return f"{domain}-Profil konnte nicht abgerufen werden: {e}"


async def get_all_profiles() -> str:
    """
    Retrieve user profiles across all domains.

    Returns:
        Combined profile insights from ideas, coding, and desktop domains
    """
    domains = ["ideas", "coding", "desktop"]
    results = []

    for domain in domains:
        profile = await get_domain_profile(domain)
        results.append(profile)

    return "\n\n".join(results)


async def search_user_insights(query: str, domain: str = "") -> str:
    """
    Search for specific user insights across domains.

    Args:
        query: Search query (e.g., "preferred format", "work pattern")
        domain: Optional domain filter (ideas, coding, desktop). Empty = all domains.

    Returns:
        Matching insights
    """
    api_key = os.getenv("SUPERMEMORY_API_KEY", "")
    if not api_key:
        return "Supermemory nicht konfiguriert."

    try:
        from supermemory import AsyncSupermemory
        client = AsyncSupermemory(api_key=api_key)

        tags = []
        if domain:
            tags = [f"vibemind-profile-{domain}"]
        else:
            tags = [
                "vibemind-profile-ideas",
                "vibemind-profile-coding",
                "vibemind-profile-desktop",
            ]

        response = await client.search.execute(
            q=query,
            container_tags=tags,
            limit=10,
        )

        if not response.results:
            return f"Keine Insights gefunden fuer: {query}"

        lines = [f"Gefundene Insights ({len(response.results)}):"]
        for r in response.results:
            meta = getattr(r, "metadata", {}) or {}
            agent = meta.get("agent", "unknown")
            lines.append(f"  [{agent}] {r.content[:150]}")

        return "\n".join(lines)

    except Exception as e:
        logger.debug(f"search_user_insights failed: {e}")
        return f"Suche fehlgeschlagen: {e}"


# Tools list for AutoGen agent registration
MEMORY_SUB_AGENT_TOOLS = [
    get_domain_profile,
    get_all_profiles,
    search_user_insights,
]

__all__ = [
    "get_domain_profile",
    "get_all_profiles",
    "search_user_insights",
    "MEMORY_SUB_AGENT_TOOLS",
]
