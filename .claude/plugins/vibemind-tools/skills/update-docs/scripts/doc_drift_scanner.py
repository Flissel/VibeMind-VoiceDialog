#!/usr/bin/env python3
"""
VibeMind Documentation Drift Scanner

Scans the codebase for current state (spaces, agents, tools, event types,
DB schema, IPC messages, env vars) and compares against existing documentation
to identify drift — outdated, missing, or inaccurate doc sections.

Usage:
    python doc_drift_scanner.py --root /path/to/VibeMind-VoiceDialog
    python doc_drift_scanner.py --root /path/to/VibeMind-VoiceDialog --json
    python doc_drift_scanner.py --root /path/to/VibeMind-VoiceDialog --section spaces
    python doc_drift_scanner.py --root /path/to/VibeMind-VoiceDialog --section tools,events,db
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# ── Helpers ──────────────────────────────────────────────────────────────────

def find_py_files(root: Path, subdirs: list[str] | None = None) -> list[Path]:
    """Find all .py files under root, optionally limited to subdirs."""
    targets = [root / s for s in subdirs] if subdirs else [root]
    files = []
    skip = {"__pycache__", "node_modules", ".git", ".venv", "Coding_engine",
            "Automation_ui", "swe_desgine", "rowboat", ".claude"}
    for target in targets:
        if not target.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for f in filenames:
                if f.endswith(".py"):
                    files.append(Path(dirpath) / f)
    return files


def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def extract_md_table_col(md_text: str, col_index: int) -> set[str]:
    """Extract values from a specific column in markdown tables."""
    values = set()
    for line in md_text.splitlines():
        line = line.strip()
        if line.startswith("|") and not re.match(r"\|[\s\-:]+\|", line):
            cells = [c.strip().strip("`") for c in line.split("|")]
            cells = [c for c in cells if c]
            if len(cells) > col_index and cells[col_index] not in ("—", "--", ""):
                val = cells[col_index]
                if not re.match(r"^[A-Z]", val) or "." in val or "_" in val:
                    values.add(val)
    return values


# ── Scanners ─────────────────────────────────────────────────────────────────

def scan_spaces(root: Path) -> dict[str, Any]:
    """Scan python/spaces/ for actual space directories and their agents/tools."""
    spaces_dir = root / "python" / "spaces"
    if not spaces_dir.exists():
        return {"spaces": [], "error": "python/spaces/ not found"}

    # Directories that are not real spaces (empty, config-only, or submodule-only)
    skip_dirs = {"__pycache__", "config", "autogen"}

    spaces = {}
    for d in sorted(spaces_dir.iterdir()):
        if not d.is_dir() or d.name.startswith(("_", ".")) or d.name in skip_dirs:
            continue
        space = {
            "name": d.name,
            "has_agents": (d / "agents").is_dir(),
            "has_tools": (d / "tools").is_dir(),
            "has_readme": (d / "README.md").is_file(),
            "agents": [],
            "tools_files": [],
            "tool_functions": [],
        }
        # Find agent files
        if space["has_agents"]:
            for f in (d / "agents").glob("*.py"):
                if f.name.startswith("_"):
                    continue
                space["agents"].append(f.name)
                # Extract class names
                content = read_file(f)
                for m in re.finditer(r"class\s+(\w+(?:Agent|Backend)\w*)", content):
                    space["agents"].append(f"class:{m.group(1)}")
        # Find tool files and functions
        if space["has_tools"]:
            for f in (d / "tools").glob("*.py"):
                if f.name.startswith("_"):
                    continue
                space["tools_files"].append(f.name)
                content = read_file(f)
                for m in re.finditer(r"^def\s+(\w+)\s*\(", content, re.MULTILINE):
                    fn = m.group(1)
                    if not fn.startswith("_"):
                        space["tool_functions"].append(fn)
        spaces[d.name] = space
    return {"spaces": spaces}


def scan_event_types(root: Path) -> dict[str, Any]:
    """Scan event_router.py for STREAM_MAPPING entries."""
    router_file = root / "python" / "swarm" / "event_team" / "event_router.py"
    if not router_file.exists():
        return {"event_types": {}, "error": "event_router.py not found"}

    content = read_file(router_file)
    events = {}
    # Match "event.type": STREAM_CONSTANT patterns
    for m in re.finditer(r'"([a-z][a-z0-9_]*\.[a-z_]+)"\s*:\s*(\w+)', content):
        event_type = m.group(1)
        stream_const = m.group(2)
        events[event_type] = stream_const
    return {"event_types": events}


def scan_tool_maps(root: Path) -> dict[str, Any]:
    """Scan backend agents for TOOL_MAP definitions."""
    agents_dir = root / "python" / "spaces"
    if not agents_dir.exists():
        return {"tool_maps": {}}

    tool_maps = {}
    for py_file in find_py_files(root, ["python/spaces", "python/swarm/backend_agents"]):
        content = read_file(py_file)
        if "TOOL_MAP" not in content:
            continue
        # Extract TOOL_MAP dict entries
        agent_name = py_file.stem
        mappings = {}
        for m in re.finditer(r'"([a-z][a-z0-9_]*\.[a-z_]+)"\s*:\s*"(\w+)"', content):
            mappings[m.group(1)] = m.group(2)
        if mappings:
            rel = str(py_file.relative_to(root))
            tool_maps[rel] = {"agent": agent_name, "mappings": mappings}
    return {"tool_maps": tool_maps}


def scan_db_schema(root: Path) -> dict[str, Any]:
    """Scan database.py and migrations for CREATE TABLE statements."""
    tables = {}

    # Scan database.py
    db_file = root / "python" / "data" / "database.py"
    if db_file.exists():
        content = read_file(db_file)
        for m in re.finditer(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\)",
            content, re.DOTALL | re.IGNORECASE
        ):
            table_name = m.group(1)
            columns = []
            for col_m in re.finditer(r"(\w+)\s+(TEXT|INTEGER|REAL|BLOB|BOOLEAN|TIMESTAMP)", m.group(2), re.IGNORECASE):
                columns.append(col_m.group(1))
            tables[table_name] = {"columns": columns, "source": "database.py"}

    # Scan migrations
    migrations_dir = root / "python" / "data" / "migrations"
    if migrations_dir.exists():
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            content = read_file(sql_file)
            for m in re.finditer(
                r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\)",
                content, re.DOTALL | re.IGNORECASE
            ):
                table_name = m.group(1)
                columns = []
                for col_m in re.finditer(r"(\w+)\s+(TEXT|INTEGER|REAL|BLOB|BOOLEAN|TIMESTAMP)", m.group(2), re.IGNORECASE):
                    columns.append(col_m.group(1))
                tables[table_name] = {"columns": columns, "source": sql_file.name}

        # Check for ALTER TABLE in migrations
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            content = read_file(sql_file)
            for m in re.finditer(
                r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+(?:COLUMN\s+)?(\w+)\s+(TEXT|INTEGER|REAL|BLOB)",
                content, re.IGNORECASE
            ):
                table_name = m.group(1)
                col_name = m.group(2)
                if table_name in tables and col_name not in tables[table_name]["columns"]:
                    tables[table_name]["columns"].append(col_name)
                    tables[table_name]["source"] += f"+{sql_file.name}"

    return {"tables": tables}


def scan_ipc_messages(root: Path) -> dict[str, Any]:
    """Scan for _broadcast_to_electron message types."""
    msg_types = set()

    for py_file in find_py_files(root, ["python"]):
        content = read_file(py_file)
        # Match _broadcast_to_electron({"type": "xxx", ...})
        for m in re.finditer(r'_broadcast_to_electron\s*\(\s*\{[^}]*"type"\s*:\s*"(\w+)"', content):
            msg_types.add(m.group(1))
        # Match broadcast_message("type", ...)
        for m in re.finditer(r'broadcast_message\s*\(\s*"(\w+)"', content):
            msg_types.add(m.group(1))
        # Match {"type": "xxx"} in broadcast contexts
        for m in re.finditer(r'"type"\s*:\s*"(\w+)".*?broadcast|broadcast.*?"type"\s*:\s*"(\w+)"', content):
            val = m.group(1) or m.group(2)
            if val:
                msg_types.add(val)

    # Also scan electron main.js for handled message types
    main_js = root / "electron-app" / "main.js"
    if main_js.exists():
        content = read_file(main_js)
        for m in re.finditer(r"case\s+['\"](\w+)['\"]", content):
            msg_types.add(m.group(1))
        for m in re.finditer(r"ipcMain\.handle\s*\(\s*['\"]([^'\"]+)['\"]", content):
            msg_types.add(m.group(1))

    return {"ipc_messages": sorted(msg_types)}


def scan_backend_agents(root: Path) -> dict[str, Any]:
    """Scan backend agent registry."""
    registry_file = root / "python" / "swarm" / "backend_agents" / "__init__.py"
    agents = {}

    if registry_file.exists():
        content = read_file(registry_file)
        # Match lazy imports: "AgentName": ("module.path", "ClassName")
        for m in re.finditer(r'"(\w+)"\s*:\s*\(\s*"([^"]+)"\s*,\s*"(\w+)"\s*\)', content):
            agents[m.group(1)] = {"module": m.group(2), "class": m.group(3)}
        # Match direct imports
        for m in re.finditer(r'from\s+(\S+)\s+import\s+(\w+Agent\w*)', content):
            agents[m.group(2)] = {"module": m.group(1), "class": m.group(2)}

    return {"backend_agents": agents}


def scan_classifier_events(root: Path) -> dict[str, Any]:
    """Scan intent_classifier.py for documented event types."""
    classifier = root / "python" / "swarm" / "orchestrator" / "intent_classifier.py"
    if not classifier.exists():
        return {"classifier_events": []}

    content = read_file(classifier)
    events = set()
    for m in re.finditer(r"['\"]([a-z][a-z0-9_]*\.[a-z_]+)['\"]", content):
        events.add(m.group(1))
    return {"classifier_events": sorted(events)}


def scan_shared_tools(root: Path) -> dict[str, Any]:
    """Scan python/tools/ for tool modules and public functions."""
    tools_dir = root / "python" / "tools"
    if not tools_dir.exists():
        return {"shared_tools": {}}

    tools = {}
    for f in sorted(tools_dir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        content = read_file(f)
        functions = []
        for m in re.finditer(r"^def\s+(\w+)\s*\(", content, re.MULTILINE):
            fn = m.group(1)
            if not fn.startswith("_"):
                functions.append(fn)
        if functions:
            tools[f.name] = functions
    return {"shared_tools": tools}


# ── Doc Comparison ───────────────────────────────────────────────────────────

def compare_spaces(code_data: dict, root: Path) -> list[dict]:
    """Compare space code state against documentation."""
    drifts = []
    code_spaces = set(code_data["spaces"].keys())

    # Check docs/python/spaces/README.md
    spaces_readme = root / "docs" / "python" / "spaces" / "README.md"
    if spaces_readme.exists():
        content = read_file(spaces_readme)
        for space_name in code_spaces:
            if space_name not in content:
                drifts.append({
                    "type": "missing_in_docs",
                    "section": "spaces",
                    "item": space_name,
                    "doc_file": "docs/python/spaces/README.md",
                    "detail": f"Space '{space_name}' exists in code but not documented in spaces overview"
                })
    else:
        drifts.append({
            "type": "missing_doc_file",
            "section": "spaces",
            "doc_file": "docs/python/spaces/README.md",
            "detail": "Spaces overview README does not exist"
        })

    # Check per-space READMEs
    for name, space in code_data["spaces"].items():
        space_readme = root / "docs" / "python" / "spaces" / name / "README.md"
        if not space_readme.exists():
            drifts.append({
                "type": "missing_doc_file",
                "section": "spaces",
                "item": name,
                "doc_file": f"docs/python/spaces/{name}/README.md",
                "detail": f"No doc README for space '{name}'"
            })
        else:
            content = read_file(space_readme)
            # Check if agent classes are documented
            for agent in space.get("agents", []):
                if agent.startswith("class:"):
                    cls = agent[6:]
                    if cls not in content:
                        drifts.append({
                            "type": "missing_in_docs",
                            "section": "spaces",
                            "item": f"{name}/{cls}",
                            "doc_file": f"docs/python/spaces/{name}/README.md",
                            "detail": f"Agent class '{cls}' not mentioned in space docs"
                        })
            # Check if tool files are documented
            for tf in space.get("tools_files", []):
                if tf.replace(".py", "") not in content and tf not in content:
                    drifts.append({
                        "type": "missing_in_docs",
                        "section": "spaces",
                        "item": f"{name}/tools/{tf}",
                        "doc_file": f"docs/python/spaces/{name}/README.md",
                        "detail": f"Tool file '{tf}' not documented in space README"
                    })

    # Check CLAUDE.md spaces table
    claude_md = root / "CLAUDE.md"
    if claude_md.exists():
        content = read_file(claude_md)
        for space_name in code_spaces:
            # Spaces should appear in the "Eight Spaces" section
            if space_name not in content.lower():
                drifts.append({
                    "type": "missing_in_docs",
                    "section": "spaces",
                    "item": space_name,
                    "doc_file": "CLAUDE.md",
                    "detail": f"Space '{space_name}' not mentioned in CLAUDE.md"
                })

    return drifts


def compare_events(code_data: dict, root: Path) -> list[dict]:
    """Compare event types in code vs docs."""
    drifts = []
    code_events = set(code_data["event_types"].keys())

    event_doc = root / "docs" / "api" / "event-types.md"
    if not event_doc.exists():
        drifts.append({
            "type": "missing_doc_file",
            "section": "events",
            "doc_file": "docs/api/event-types.md",
            "detail": "Event types reference doc does not exist"
        })
        return drifts

    content = read_file(event_doc)
    doc_events = set()
    for m in re.finditer(r"`([a-z][a-z0-9_]*\.[a-z_]+)`", content):
        doc_events.add(m.group(1))

    missing_in_docs = code_events - doc_events
    extra_in_docs = doc_events - code_events

    for ev in sorted(missing_in_docs):
        drifts.append({
            "type": "missing_in_docs",
            "section": "events",
            "item": ev,
            "doc_file": "docs/api/event-types.md",
            "detail": f"Event '{ev}' in STREAM_MAPPING but not documented"
        })

    for ev in sorted(extra_in_docs):
        # Only flag if not in classifier either
        if ev not in code_data.get("classifier_events", []):
            drifts.append({
                "type": "extra_in_docs",
                "section": "events",
                "item": ev,
                "doc_file": "docs/api/event-types.md",
                "detail": f"Event '{ev}' documented but not in STREAM_MAPPING (may be removed)"
            })

    return drifts


def compare_db_schema(code_data: dict, root: Path) -> list[dict]:
    """Compare DB tables in code vs docs."""
    drifts = []
    code_tables = set(code_data["tables"].keys())

    schema_doc = root / "docs" / "api" / "database-schema.md"
    if not schema_doc.exists():
        drifts.append({
            "type": "missing_doc_file",
            "section": "database",
            "doc_file": "docs/api/database-schema.md",
            "detail": "Database schema reference doc does not exist"
        })
        return drifts

    content = read_file(schema_doc)
    doc_tables = set()
    for m in re.finditer(r"###\s+(\w+)", content):
        doc_tables.add(m.group(1))

    missing = code_tables - doc_tables
    extra = doc_tables - code_tables

    for t in sorted(missing):
        drifts.append({
            "type": "missing_in_docs",
            "section": "database",
            "item": t,
            "doc_file": "docs/api/database-schema.md",
            "detail": f"Table '{t}' exists in schema but not documented"
        })

    for t in sorted(extra):
        drifts.append({
            "type": "extra_in_docs",
            "section": "database",
            "item": t,
            "doc_file": "docs/api/database-schema.md",
            "detail": f"Table '{t}' documented but not found in schema code"
        })

    # Check columns for documented tables
    for table_name, table_data in code_data["tables"].items():
        if table_name not in doc_tables:
            continue
        # Find the table section in docs
        section_pattern = rf"###\s+{re.escape(table_name)}\s*\n(.*?)(?=###|\Z)"
        section_match = re.search(section_pattern, content, re.DOTALL)
        if section_match:
            section_text = section_match.group(1)
            for col in table_data["columns"]:
                if col not in section_text:
                    drifts.append({
                        "type": "missing_in_docs",
                        "section": "database",
                        "item": f"{table_name}.{col}",
                        "doc_file": "docs/api/database-schema.md",
                        "detail": f"Column '{col}' in table '{table_name}' not documented"
                    })

    return drifts


def compare_tools(code_data: dict, root: Path) -> list[dict]:
    """Compare tool functions in code vs docs."""
    drifts = []

    tool_doc = root / "docs" / "api" / "tool-functions.md"
    if not tool_doc.exists():
        drifts.append({
            "type": "missing_doc_file",
            "section": "tools",
            "doc_file": "docs/api/tool-functions.md",
            "detail": "Tool functions reference doc does not exist"
        })
        return drifts

    content = read_file(tool_doc)
    doc_functions = set()
    for m in re.finditer(r"`(\w+)\(", content):
        doc_functions.add(m.group(1))

    # Check shared tools
    for module, functions in code_data.get("shared_tools", {}).items():
        for fn in functions:
            if fn not in doc_functions and fn not in content:
                drifts.append({
                    "type": "missing_in_docs",
                    "section": "tools",
                    "item": f"python/tools/{module}::{fn}",
                    "doc_file": "docs/api/tool-functions.md",
                    "detail": f"Shared tool function '{fn}' from {module} not documented"
                })

    # Check space-specific tools
    for space_name, space in code_data.get("spaces", {}).items():
        for fn in space.get("tool_functions", []):
            if fn not in doc_functions and fn not in content:
                drifts.append({
                    "type": "missing_in_docs",
                    "section": "tools",
                    "item": f"spaces/{space_name}::{fn}",
                    "doc_file": "docs/api/tool-functions.md",
                    "detail": f"Space tool '{fn}' from {space_name} not documented"
                })

    return drifts


def compare_ipc(code_data: dict, root: Path) -> list[dict]:
    """Compare IPC message types in code vs docs."""
    drifts = []
    code_msgs = set(code_data["ipc_messages"])

    ipc_doc = root / "docs" / "api" / "ipc-messages.md"
    if not ipc_doc.exists():
        drifts.append({
            "type": "missing_doc_file",
            "section": "ipc",
            "doc_file": "docs/api/ipc-messages.md",
            "detail": "IPC messages reference doc does not exist"
        })
        return drifts

    content = read_file(ipc_doc)
    doc_msgs = set()
    # Match backtick-wrapped names
    for m in re.finditer(r"`(\w+)`", content):
        doc_msgs.add(m.group(1))
    # Match #### heading names (ipc-messages.md uses this format)
    for m in re.finditer(r"^#{3,4}\s+(\w+)", content, re.MULTILINE):
        doc_msgs.add(m.group(1))
    # Match "type": "xxx" in JSON examples
    for m in re.finditer(r'"type"\s*:\s*"(\w+)"', content):
        doc_msgs.add(m.group(1))
    # Match heading with / separator (e.g. "#### enter_shuttle / enter_shuttle_by_name")
    for m in re.finditer(r"^#{3,4}\s+(.+)$", content, re.MULTILINE):
        for part in m.group(1).split("/"):
            word = part.strip()
            if re.match(r"^\w+$", word):
                doc_msgs.add(word)

    missing = code_msgs - doc_msgs
    for msg in sorted(missing):
        # Filter noise — skip very generic words
        if len(msg) > 3 and "_" in msg or msg.endswith("_update") or msg.endswith("_added"):
            drifts.append({
                "type": "missing_in_docs",
                "section": "ipc",
                "item": msg,
                "doc_file": "docs/api/ipc-messages.md",
                "detail": f"IPC message type '{msg}' found in code but not documented"
            })

    return drifts


def compare_agents(code_data: dict, root: Path) -> list[dict]:
    """Compare backend agent registry vs docs."""
    drifts = []
    code_agents = code_data.get("backend_agents", {})

    agents_doc = root / "docs" / "python" / "swarm" / "backend-agents" / "README.md"
    claude_md = root / "CLAUDE.md"

    for doc_file in [agents_doc, claude_md]:
        if not doc_file.exists():
            continue
        content = read_file(doc_file)
        for agent_key, agent_info in code_agents.items():
            cls = agent_info.get("class", agent_key)
            if cls not in content and agent_key not in content:
                rel = str(doc_file.relative_to(root))
                drifts.append({
                    "type": "missing_in_docs",
                    "section": "agents",
                    "item": cls,
                    "doc_file": rel,
                    "detail": f"Backend agent '{cls}' registered but not documented"
                })

    return drifts


# ── Main Report ──────────────────────────────────────────────────────────────

def run_full_scan(root: Path, sections: list[str] | None = None) -> dict[str, Any]:
    """Run all scanners and comparisons."""
    all_sections = ["spaces", "events", "tools", "db", "ipc", "agents"]
    active = sections or all_sections

    # Phase 1: Scan code
    code_data = {}
    if "spaces" in active or "tools" in active:
        code_data.update(scan_spaces(root))
    if "events" in active:
        code_data.update(scan_event_types(root))
        code_data.update(scan_classifier_events(root))
    if "tools" in active:
        code_data.update(scan_tool_maps(root))
        code_data.update(scan_shared_tools(root))
    if "db" in active:
        code_data.update(scan_db_schema(root))
    if "ipc" in active:
        code_data.update(scan_ipc_messages(root))
    if "agents" in active:
        code_data.update(scan_backend_agents(root))

    # Phase 2: Compare against docs
    drifts = []
    if "spaces" in active:
        drifts.extend(compare_spaces(code_data, root))
    if "events" in active:
        drifts.extend(compare_events(code_data, root))
    if "db" in active:
        drifts.extend(compare_db_schema(code_data, root))
    if "tools" in active:
        drifts.extend(compare_tools(code_data, root))
    if "ipc" in active:
        drifts.extend(compare_ipc(code_data, root))
    if "agents" in active:
        drifts.extend(compare_agents(code_data, root))

    # Phase 3: Build summary
    summary = {
        "total_drifts": len(drifts),
        "by_type": defaultdict(int),
        "by_section": defaultdict(int),
        "affected_docs": set(),
    }
    for d in drifts:
        summary["by_type"][d["type"]] += 1
        summary["by_section"][d["section"]] += 1
        summary["affected_docs"].add(d["doc_file"])

    summary["by_type"] = dict(summary["by_type"])
    summary["by_section"] = dict(summary["by_section"])
    summary["affected_docs"] = sorted(summary["affected_docs"])

    return {
        "code_state": {
            "spaces": list(code_data.get("spaces", {}).keys()),
            "event_types_count": len(code_data.get("event_types", {})),
            "tables_count": len(code_data.get("tables", {})),
            "shared_tool_modules": len(code_data.get("shared_tools", {})),
            "backend_agents_count": len(code_data.get("backend_agents", {})),
            "ipc_message_types": len(code_data.get("ipc_messages", [])),
        },
        "summary": summary,
        "drifts": drifts,
        "code_data": code_data,  # full data for detailed analysis
    }


def print_report(result: dict):
    """Print human-readable drift report."""
    summary = result["summary"]
    code = result["code_state"]

    print("=" * 70)
    print("  VibeMind Documentation Drift Report")
    print("=" * 70)
    print()
    print("Code State:")
    print(f"  Spaces:          {len(code['spaces'])}  ({', '.join(code['spaces'])})")
    print(f"  Event types:     {code['event_types_count']}")
    print(f"  DB tables:       {code['tables_count']}")
    print(f"  Shared tools:    {code['shared_tool_modules']} modules")
    print(f"  Backend agents:  {code['backend_agents_count']}")
    print(f"  IPC msg types:   {code['ipc_message_types']}")
    print()

    if summary["total_drifts"] == 0:
        print("No documentation drift detected. Docs are up to date!")
        return

    print(f"Total drifts found: {summary['total_drifts']}")
    print()
    print("By type:")
    for t, count in sorted(summary["by_type"].items()):
        label = {
            "missing_in_docs": "Missing from docs",
            "extra_in_docs": "Extra in docs (possibly removed from code)",
            "missing_doc_file": "Missing doc file entirely",
        }.get(t, t)
        print(f"  {label}: {count}")
    print()
    print("By section:")
    for s, count in sorted(summary["by_section"].items()):
        print(f"  {s}: {count}")
    print()
    print("Affected doc files:")
    for f in summary["affected_docs"]:
        print(f"  {f}")
    print()

    # Group drifts by section
    by_section = defaultdict(list)
    for d in result["drifts"]:
        by_section[d["section"]].append(d)

    for section, items in sorted(by_section.items()):
        print(f"\n{'-' * 50}")
        print(f"  {section.upper()} ({len(items)} issues)")
        print(f"{'-' * 50}")
        for d in items:
            icon = {"missing_in_docs": "+", "extra_in_docs": "-", "missing_doc_file": "!"}
            print(f"  [{icon.get(d['type'], '?')}] {d['detail']}")
            print(f"      -> {d['doc_file']}")


def main():
    parser = argparse.ArgumentParser(description="VibeMind Documentation Drift Scanner")
    parser.add_argument("--root", required=True, help="Project root directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--section", help="Comma-separated sections: spaces,events,tools,db,ipc,agents")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Error: Root directory not found: {root}", file=sys.stderr)
        sys.exit(1)

    sections = args.section.split(",") if args.section else None
    result = run_full_scan(root, sections)

    if args.json:
        # Remove non-serializable code_data for JSON output
        output = {k: v for k, v in result.items() if k != "code_data"}
        print(json.dumps(output, indent=2, default=str))
    else:
        print_report(result)


if __name__ == "__main__":
    main()