"""
VibeMind Routing Module

Domain-first routing for intent processing.
"""

from .domain_router import (
    Domain,
    DomainMatch,
    DomainRouter,
    get_domain_router,
)

__all__ = [
    "Domain",
    "DomainMatch",
    "DomainRouter",
    "get_domain_router",
]
