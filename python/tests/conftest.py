"""Shared conftest for voice/python/tests — makes `swarm.*` importable.

Mirrors the flat voice/python test convention (sys.path insert of voice/python)
so tests in this directory can `from swarm.routing... import ...` without
package installs. Phase-0 (2026-07-02): first structured test dir for the
CASCADE Phase-0 workstreams (GATE-1, REG-1, …).
"""
import sys
from pathlib import Path

# voice/python — parent of this tests/ dir
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
