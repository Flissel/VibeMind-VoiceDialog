#!/usr/bin/env python3
"""
Scan VibeMind codebase for vibe coding tool integrations.

Detects CLI tools (Claude CLI, Kilo CLI, Codex CLI), SDKs (Anthropic, OpenAI),
agent frameworks (AutoGen, LangChain, CrewAI), MCP servers, IDE integrations
(Cursor, Windsurf, Continue, Copilot, Cline/Roo Code), and deployment tools.

Usage:
    python scan_coding_tools.py [--root /path/to/project]
    python scan_coding_tools.py --json
    python scan_coding_tools.py --configs-dir configs
"""

import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------------------------------
# Tool Definitions — each tool has detection patterns
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = {
    # --- CLI Tools ---
    "claude-cli": {
        "category": "CLI Tools",
        "display": "Claude CLI / Claude Code",
        "patterns": {
            "subprocess": [
                re.compile(r"""subprocess\.\w+\s*\([^)]*['"]claude['"\s,\]]"""),
                re.compile(r"""subprocess\.\w+\s*\(\s*\[['"]claude['"]"""),
                re.compile(r"""shutil\.which\s*\(\s*['"]claude['"]"""),
            ],
            "import": [
                re.compile(r"""from\s+claude_agent_sdk\s+import"""),
                re.compile(r"""import\s+claude_agent_sdk"""),
            ],
            "config": [
                re.compile(r"""claude\s*(?:--model|--print|--output|--verbose|--dangerously)"""),
                re.compile(r"""CLAUDE_(?:API_KEY|MODEL|CLI_PATH|PLUGIN_ROOT)"""),
            ],
            "file_marker": ["CLAUDE.md", ".claude-plugin"],
        },
    },
    "kilo-cli": {
        "category": "CLI Tools",
        "display": "Kilo Code CLI",
        "patterns": {
            "subprocess": [
                re.compile(r"""subprocess\.\w+\s*\([^)]*['"]kilocode['"\s,\]]"""),
                re.compile(r"""subprocess\.\w+\s*\(\s*\[['"]kilocode['"]"""),
                re.compile(r"""shutil\.which\s*\(\s*['"]kilocode['"]"""),
            ],
            "import": [],
            "config": [
                re.compile(r"""kilocode\s+(?:--model|--mode|--output|--yolo)"""),
                re.compile(r"""KILO_(?:CLI_PATH|MODEL|MODE)"""),
            ],
            "file_marker": [".kilocode", "kilo_cli_wrapper"],
        },
    },
    "codex-cli": {
        "category": "CLI Tools",
        "display": "OpenAI Codex CLI",
        "patterns": {
            "subprocess": [
                re.compile(r"""subprocess\.\w+\s*\([^)]*['"]codex['"\s,\]]"""),
                re.compile(r"""subprocess\.\w+\s*\(\s*\[['"]codex['"]"""),
            ],
            "import": [],
            "config": [
                re.compile(r"""codex\s+(?:--model|--full-auto|--quiet)"""),
            ],
            "file_marker": ["codex-cli", "AGENTS.md"],
        },
    },
    "aider": {
        "category": "CLI Tools",
        "display": "Aider (AI Pair Programming)",
        "patterns": {
            "subprocess": [
                re.compile(r"""subprocess\.\w+\s*\([^)]*['"]aider['"\s,\]]"""),
                re.compile(r"""subprocess\.\w+\s*\(\s*\[['"]aider['"]"""),
            ],
            "import": [
                re.compile(r"""from\s+aider"""),
                re.compile(r"""import\s+aider"""),
            ],
            "config": [
                re.compile(r"""aider\s+--"""),
                re.compile(r"""AIDER_"""),
            ],
            "file_marker": [".aider", "aider-chat"],
        },
    },

    # --- SDKs ---
    "anthropic-sdk": {
        "category": "SDKs",
        "display": "Anthropic SDK (Python/JS)",
        "patterns": {
            "subprocess": [],
            "import": [
                re.compile(r"""from\s+anthropic\s+import"""),
                re.compile(r"""import\s+anthropic"""),
                re.compile(r"""require\s*\(\s*['"]@anthropic-ai/sdk['"]"""),
                re.compile(r"""from\s+['"]@anthropic-ai/sdk['"]"""),
            ],
            "config": [
                re.compile(r"""anthropic\.(?:Anthropic|Client|AsyncClient|AsyncAnthropic)\s*\("""),
                re.compile(r"""ANTHROPIC_API_KEY"""),
            ],
            "file_marker": [],
        },
    },
    "openai-sdk": {
        "category": "SDKs",
        "display": "OpenAI SDK (Python/JS)",
        "patterns": {
            "subprocess": [],
            "import": [
                re.compile(r"""from\s+openai\s+import"""),
                re.compile(r"""import\s+openai"""),
                re.compile(r"""require\s*\(\s*['"]openai['"]"""),
                re.compile(r"""from\s+['"]openai['"]"""),
            ],
            "config": [
                re.compile(r"""openai\.(?:OpenAI|AsyncOpenAI|Client)\s*\("""),
                re.compile(r"""OPENAI_API_KEY"""),
            ],
            "file_marker": [],
        },
    },
    "google-ai-sdk": {
        "category": "SDKs",
        "display": "Google AI SDK (Gemini)",
        "patterns": {
            "subprocess": [],
            "import": [
                re.compile(r"""from\s+google\.generativeai"""),
                re.compile(r"""import\s+google\.generativeai"""),
                re.compile(r"""from\s+google\.ai"""),
                re.compile(r"""require\s*\(\s*['"]@google/generative-ai['"]"""),
            ],
            "config": [
                re.compile(r"""GOOGLE_(?:API_KEY|AI_KEY|MODEL)"""),
                re.compile(r"""genai\.(?:GenerativeModel|configure)"""),
            ],
            "file_marker": [],
        },
    },

    # --- Agent Frameworks ---
    "autogen": {
        "category": "Agent Frameworks",
        "display": "Microsoft AutoGen 0.4+",
        "patterns": {
            "subprocess": [],
            "import": [
                re.compile(r"""from\s+autogen_agentchat"""),
                re.compile(r"""from\s+autogen_core"""),
                re.compile(r"""from\s+autogen_ext"""),
                re.compile(r"""import\s+autogen"""),
            ],
            "config": [
                re.compile(r"""(?:RoundRobinGroupChat|SelectorGroupChat|Swarm)\s*\("""),
                re.compile(r"""(?:AssistantAgent|UserProxyAgent|AutonomousAgent)\s*\("""),
                re.compile(r"""autogen[-_](?:agentchat|core|ext)"""),
            ],
            "file_marker": ["autogen"],
        },
    },
    "langchain": {
        "category": "Agent Frameworks",
        "display": "LangChain / LangGraph",
        "patterns": {
            "subprocess": [],
            "import": [
                re.compile(r"""from\s+langchain"""),
                re.compile(r"""from\s+langgraph"""),
                re.compile(r"""import\s+langchain"""),
                re.compile(r"""import\s+langgraph"""),
            ],
            "config": [
                re.compile(r"""langchain[-_]"""),
                re.compile(r"""LANGCHAIN_"""),
            ],
            "file_marker": [],
        },
    },
    "crewai": {
        "category": "Agent Frameworks",
        "display": "CrewAI",
        "patterns": {
            "subprocess": [],
            "import": [
                re.compile(r"""from\s+crewai"""),
                re.compile(r"""import\s+crewai"""),
            ],
            "config": [
                re.compile(r"""(?:Agent|Task|Crew)\s*\(.*role="""),
            ],
            "file_marker": [],
        },
    },

    # --- MCP ---
    "mcp": {
        "category": "Protocols",
        "display": "Model Context Protocol (MCP)",
        "patterns": {
            "subprocess": [],
            "import": [
                re.compile(r"""from\s+mcp"""),
                re.compile(r"""import\s+mcp"""),
                re.compile(r"""require\s*\(\s*['"]@modelcontextprotocol"""),
            ],
            "config": [
                re.compile(r"""mcp[-_](?:server|plugin|client|registry)"""),
                re.compile(r"""MCP_(?:SERVER|PLUGIN|HOST|PORT)"""),
                re.compile(r"""mcpServers"""),
            ],
            "file_marker": [".mcp.json", "mcp_plugins/", "mcp-server"],
        },
    },

    # --- Services/Providers ---
    "openrouter": {
        "category": "Services",
        "display": "OpenRouter (Multi-LLM Gateway)",
        "patterns": {
            "subprocess": [],
            "import": [],
            "config": [
                re.compile(r"""OPENROUTER_(?:API_KEY|BASE_URL|MODEL)"""),
                re.compile(r"""openrouter\.ai/api"""),
            ],
            "file_marker": [],
        },
    },
    "supermemory": {
        "category": "Services",
        "display": "Supermemory (Semantic Memory)",
        "patterns": {
            "subprocess": [],
            "import": [
                re.compile(r"""from\s+supermemory"""),
                re.compile(r"""import\s+supermemory"""),
            ],
            "config": [
                re.compile(r"""SUPERMEMORY_(?:API_KEY|URL|HOST)"""),
                re.compile(r"""supermemory\["""),
            ],
            "file_marker": [],
        },
    },
    "n8n": {
        "category": "Services",
        "display": "n8n (Workflow Automation)",
        "patterns": {
            "subprocess": [],
            "import": [],
            "config": [
                re.compile(r"""N8N_(?:URL|HOST|API_KEY|WEBHOOK)"""),
                re.compile(r"""n8n[-_](?:workflow|webhook|server)"""),
            ],
            "file_marker": ["n8n", "docker-compose.n8n"],
        },
    },
}

# ---------------------------------------------------------------------------
# Skip dirs & extensions
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv", ".venv312",
    "dist", "build", ".eggs", "dashboard", "worktrees",
}

# Skip files that are this scanner itself (avoid self-references)
SELF_SKIP = {"scan_coding_tools.py", "SKILL.md"}

SCAN_EXTENSIONS = {
    ".py", ".js", ".ts", ".json", ".yml", ".yaml", ".toml", ".bat", ".sh",
    ".cfg", ".md", ".txt",
}

# Domain classification (same as scan-llm)
PATH_TO_DOMAIN = [
    ("spaces/ideas",        "Ideas"),
    ("spaces/coding",       "Coding"),
    ("spaces/desktop",      "Desktop"),
    ("spaces/rowboat",      "Rowboat"),
    ("spaces/research",     "Research"),
    ("spaces/minibook",     "Minibook"),
    ("spaces/schedule",     "Schedule"),
    ("spaces/shuttles",     "Shuttles"),
    ("spaces/roarboot",     "Rowboat"),
    ("spaces/brain",        "Brain"),
    ("spaces/config",       "Config"),
    ("voice/",              "Voice"),
    ("swarm/orchestrator",  "Orchestrator"),
    ("swarm/",              "Swarm"),
    ("workers/",            "Workers"),
    ("publishing/",         "Publishing"),
    ("tools/",              "SharedTools"),
    ("config.py",           "Core"),
    ("data/",               "Data"),
    ("electron_backend.py", "Core"),
    ("electron-app/",       "Electron"),
    ("external/",           "External"),
    ("tests/",              "Tests"),
    (".claude/",            "PluginConfig"),
    ("configs/",            "Configs"),
    ("docker",              "Docker"),
]


def classify_domain(filepath: str) -> str:
    normalized = filepath.replace("\\", "/")
    for fragment, domain in PATH_TO_DOMAIN:
        if fragment in normalized:
            return domain
    return "Root"


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_file_for_tools(filepath: Path, root: Path) -> list:
    """Scan a file for coding tool references. Returns list of match dicts."""
    matches = []
    rel = str(filepath.relative_to(root))
    rel_unix = rel.replace("\\", "/")

    # Skip self-references
    if filepath.name in SELF_SKIP and "scan-tools" in rel_unix:
        return matches

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return matches

    # Precompute lines for regex scanning
    file_lines = content.splitlines()
    is_python = filepath.suffix == ".py"

    for tool_id, tool_def in TOOL_DEFINITIONS.items():
        # Check file_marker patterns (path-based)
        for marker in tool_def["patterns"].get("file_marker", []):
            if marker in rel_unix:
                matches.append({
                    "tool": tool_id,
                    "category": tool_def["category"],
                    "display": tool_def["display"],
                    "match_type": "file_marker",
                    "file": rel,
                    "line": 0,
                    "context": f"File path contains '{marker}'",
                })
                break  # one file_marker match per tool per file

        # Check regex patterns against file content
        for match_type in ("subprocess", "import", "config"):
            for pattern in tool_def["patterns"].get(match_type, []):
                for line_num, line_text in enumerate(file_lines, 1):
                    stripped = line_text.strip()
                    if is_python and stripped.startswith("#"):
                        continue
                    if pattern.search(line_text):
                        matches.append({
                            "tool": tool_id,
                            "category": tool_def["category"],
                            "display": tool_def["display"],
                            "match_type": match_type,
                            "file": rel,
                            "line": line_num,
                            "context": stripped[:140],
                        })

    return matches


def scan_dependencies(root: Path) -> list:
    """Scan dependency files (requirements.txt, package.json, pyproject.toml)."""
    matches = []

    dep_patterns = {
        "anthropic-sdk": [r"anthropic(?:\[|>=|==|~=|>|\s)", r"@anthropic-ai/sdk"],
        "openai-sdk": [r"openai(?:>=|==|~=|>|\s)", r'"openai"'],
        "autogen": [r"autogen[-_](?:agentchat|core|ext)", r"pyautogen"],
        "langchain": [r"langchain", r"langgraph"],
        "crewai": [r"crewai"],
        "supermemory": [r"supermemory"],
        "mcp": [r"@modelcontextprotocol", r"mcp[-_]server"],
        "aider": [r"aider[-_]chat"],
        "google-ai-sdk": [r"google[-_]generativeai", r"@google/generative-ai"],
    }

    dep_files = [
        root / "requirements.txt",
        root / "electron-app" / "package.json",
    ]
    # Also check submodule requirements
    for req in root.rglob("requirements.txt"):
        if any(skip in req.parts for skip in SKIP_DIRS):
            continue
        if req not in dep_files:
            dep_files.append(req)
    for pkg in root.rglob("package.json"):
        if any(skip in pkg.parts for skip in SKIP_DIRS):
            continue
        if pkg not in dep_files:
            dep_files.append(pkg)

    for dep_file in dep_files:
        if not dep_file.exists():
            continue
        rel = str(dep_file.relative_to(root))
        try:
            content = dep_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for tool_id, patterns in dep_patterns.items():
            tool_def = TOOL_DEFINITIONS.get(tool_id, {})
            for pat in patterns:
                for i, line in enumerate(content.splitlines(), 1):
                    if re.search(pat, line):
                        matches.append({
                            "tool": tool_id,
                            "category": tool_def.get("category", "Unknown"),
                            "display": tool_def.get("display", tool_id),
                            "match_type": "dependency",
                            "file": rel,
                            "line": i,
                            "context": line.strip()[:140],
                        })

    return matches


def scan_mcp_servers(root: Path) -> list:
    """Detect individual MCP server directories."""
    matches = []
    mcp_dirs = list(root.rglob("mcp_plugins/servers"))

    for mcp_dir in mcp_dirs:
        if any(skip in mcp_dir.parts for skip in SKIP_DIRS):
            continue
        if not mcp_dir.is_dir():
            continue
        for server_dir in sorted(mcp_dir.iterdir()):
            if not server_dir.is_dir() or server_dir.name.startswith("."):
                continue
            if server_dir.name == "__pycache__":
                continue
            rel = str(server_dir.relative_to(root))
            agent_file = server_dir / "agent.py"
            server_id = f"mcp-{server_dir.name}"
            matches.append({
                "tool": server_id,
                "category": "MCP Servers",
                "display": f"MCP: {server_dir.name}",
                "match_type": "mcp_server",
                "file": rel,
                "line": 0,
                "context": f"MCP server '{server_dir.name}'"
                           + (" (has agent.py)" if agent_file.exists() else ""),
            })

    # Also check .mcp.json files
    for mcp_json in root.rglob(".mcp.json"):
        if any(skip in mcp_json.parts for skip in SKIP_DIRS):
            continue
        rel = str(mcp_json.relative_to(root))
        # Name based on parent dir
        parent_name = mcp_json.parent.name or "root"
        matches.append({
            "tool": f"mcp-config-{parent_name}",
            "category": "MCP Servers",
            "display": f"MCP: .mcp.json ({parent_name})",
            "match_type": "mcp_config",
            "file": rel,
            "line": 0,
            "context": f".mcp.json server configuration in {parent_name}/",
        })

    return matches


def scan_codebase(root: Path) -> list:
    """Full codebase scan for coding tools."""
    all_matches = []

    # 1. Scan dependencies
    all_matches.extend(scan_dependencies(root))

    # 2. Scan MCP servers
    all_matches.extend(scan_mcp_servers(root))

    # 3. Scan source files
    for ext in SCAN_EXTENSIONS:
        for filepath in root.rglob(f"*{ext}"):
            if any(skip in filepath.parts for skip in SKIP_DIRS):
                continue
            all_matches.extend(scan_file_for_tools(filepath, root))

    return all_matches


# ---------------------------------------------------------------------------
# Deduplication & Grouping
# ---------------------------------------------------------------------------

def deduplicate(matches: list) -> list:
    """Remove duplicate matches at same file:line for same tool."""
    seen = set()
    deduped = []
    # Prefer specific match types over generic
    priority = {"dependency": 0, "import": 1, "subprocess": 2, "config": 3,
                "mcp_server": 4, "mcp_config": 5, "file_marker": 6}

    sorted_matches = sorted(matches, key=lambda m: priority.get(m["match_type"], 99))

    for m in sorted_matches:
        key = (m["tool"], m["file"], m["line"])
        if key not in seen:
            seen.add(key)
            deduped.append(m)
    return deduped


def group_by_tool(matches: list) -> dict:
    """Group matches by tool_id, preserving category info."""
    grouped = defaultdict(list)
    for m in matches:
        grouped[m["tool"]].append(m)
    return dict(sorted(grouped.items()))


def group_by_category(matches: list) -> dict:
    """Group by category, then by tool within category."""
    cats = defaultdict(lambda: defaultdict(list))
    for m in matches:
        cats[m["category"]][m["tool"]].append(m)
    return dict(sorted(cats.items()))


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_tools_yaml(matches: list, output_path: Path):
    """Write full tool inventory YAML."""
    by_cat = group_by_category(matches)

    lines = [
        "# VibeMind Coding Tools Inventory (auto-generated)",
        "# Re-run scan-tools to update.",
        "",
    ]

    summary_lines = ["summary:"]
    for cat, tools in sorted(by_cat.items()):
        for tool_id, refs in sorted(tools.items()):
            display = refs[0]["display"]
            domains = sorted(set(classify_domain(r["file"]) for r in refs))
            summary_lines.append(f'  - tool: "{display}"')
            summary_lines.append(f'    id: "{tool_id}"')
            summary_lines.append(f'    category: "{cat}"')
            summary_lines.append(f'    references: {len(refs)}')
            summary_lines.append(f'    domains: [{", ".join(domains)}]')
            summary_lines.append("")

    lines.extend(summary_lines)
    lines.append("")
    lines.append("# --- Detailed References ---")
    lines.append("")

    for cat, tools in sorted(by_cat.items()):
        lines.append(f"# {cat}")
        for tool_id, refs in sorted(tools.items()):
            display = refs[0]["display"]
            lines.append(f"{tool_id}:")
            lines.append(f'  display: "{display}"')
            lines.append(f'  category: "{cat}"')
            lines.append(f"  references:")

            by_type = defaultdict(list)
            for r in refs:
                by_type[r["match_type"]].append(r)

            for mtype, type_refs in sorted(by_type.items()):
                lines.append(f"    {mtype}:")
                for r in type_refs[:15]:
                    loc = f"{r['file']}:{r['line']}" if r["line"] else r["file"]
                    lines.append(f'      - file: "{loc}"')
                    lines.append(f'        context: "{r["context"][:100]}"')
                if len(type_refs) > 15:
                    lines.append(f"      # +{len(type_refs)-15} more")
            lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_per_space_configs(matches: list, configs_dir: Path):
    """Write per-space tool config YAML files to configs/tools/."""
    tools_dir = configs_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    by_domain = defaultdict(list)
    for m in matches:
        domain = classify_domain(m["file"])
        by_domain[domain].append(m)

    for domain, refs in sorted(by_domain.items()):
        by_tool = defaultdict(list)
        for r in refs:
            by_tool[r["tool"]].append(r)

        lines = [
            f"# {domain} — Coding Tools",
            "# Auto-generated by scan-tools. Re-run to update.",
            "",
            "tools:",
        ]

        for tool_id in sorted(by_tool.keys()):
            tool_refs = by_tool[tool_id]
            display = tool_refs[0]["display"]
            category = tool_refs[0]["category"]

            by_type = defaultdict(list)
            for r in tool_refs:
                by_type[r["match_type"]].append(r)

            lines.append(f'  - tool: "{display}"')
            lines.append(f'    id: "{tool_id}"')
            lines.append(f'    category: "{category}"')
            lines.append(f'    match_types: [{", ".join(sorted(by_type.keys()))}]')
            lines.append(f"    locations:")
            for r in tool_refs[:10]:
                loc = f"{r['file']}:{r['line']}" if r["line"] else r["file"]
                lines.append(f'      - "{loc}"')
            if len(tool_refs) > 10:
                lines.append(f"      # +{len(tool_refs)-10} more")
            lines.append("")

        filename = domain.lower().replace(" ", "_") + ".yml"
        (tools_dir / filename).write_text("\n".join(lines), encoding="utf-8")

    return tools_dir


def print_report(matches: list):
    """Print human-readable report."""
    by_cat = group_by_category(matches)
    sep = "=" * 60

    total_tools = sum(len(tools) for tools in by_cat.values())
    total_refs = len(matches)

    print(f"\n{sep}")
    print(f"  VIBE CODING TOOLS SCAN REPORT")
    print(f"{sep}")
    print(f"  Total tool integrations found: {total_tools}")
    print(f"  Total references: {total_refs}")
    print(f"  Categories: {len(by_cat)}")

    for cat, tools in sorted(by_cat.items()):
        print(f"\n  [{cat.upper()}]")
        print(f"  {'-'*40}")
        for _, refs in sorted(tools.items()):
            display = refs[0]["display"]
            domains = sorted(set(classify_domain(r["file"]) for r in refs))
            types = sorted(set(r["match_type"] for r in refs))
            print(f"    {display}")
            print(f"      refs: {len(refs)} | types: {', '.join(types)}")
            print(f"      domains: {', '.join(domains)}")
            for r in refs[:3]:
                loc = f"{r['file']}:{r['line']}" if r["line"] else r["file"]
                print(f"        -> {loc}")
            if len(refs) > 3:
                print(f"        -> ... +{len(refs)-3} more")

    # Not found
    found_tools = set()
    for tools in by_cat.values():
        found_tools.update(tools.keys())
    not_found = [
        tid for tid in TOOL_DEFINITIONS
        if tid not in found_tools
    ]
    if not_found:
        print(f"\n  [NOT DETECTED]")
        print(f"  {'-'*40}")
        for tid in sorted(not_found):
            print(f"    {TOOL_DEFINITIONS[tid]['display']}")

    print(f"\n{sep}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scan for vibe coding tool integrations")
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--yaml", type=str, default=None,
                        help="Write YAML inventory to file")
    parser.add_argument("--configs-dir", type=str, default=None,
                        help="Write per-space tool configs to dir")
    args = parser.parse_args()

    root = Path(args.root).resolve()

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    matches = scan_codebase(root)
    matches = deduplicate(matches)

    if args.configs_dir:
        configs_path = root / args.configs_dir
        tools_dir = write_per_space_configs(matches, configs_path)
        files = list(tools_dir.glob("*.yml"))
        print(f"Written {len(files)} tool config files to {tools_dir}")
        for f in sorted(files):
            print(f"  {f.name}")
    elif args.json:
        by_tool = group_by_tool(matches)
        print(json.dumps({
            "total_references": len(matches),
            "tools_found": len(by_tool),
            "by_tool": {k: [dict(m) for m in v] for k, v in by_tool.items()},
        }, indent=2, default=str))
    elif args.yaml:
        yaml_path = root / args.yaml
        write_tools_yaml(matches, yaml_path)
        by_tool = group_by_tool(matches)
        print(f"Written {len(by_tool)} tool inventories ({len(matches)} refs) to {yaml_path}")
    else:
        print_report(matches)


if __name__ == "__main__":
    main()
