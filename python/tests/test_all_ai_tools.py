"""
Test all AI-powered tools independently.

Tests format_dispatcher format agents (11 formats) and AI enrichment tools.
Each test runs independently with sample data - no DB required.
"""

import os
import sys
import json
import time
import traceback

# Ensure python/ is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


def test_format_agent(name, func, source_content, **kwargs):
    """Run a single format agent test."""
    print(f"\n{'='*60}")
    print(f"  TEST: {name}")
    print(f"{'='*60}")
    start = time.time()
    try:
        result = func(source_content, **kwargs)
        elapsed = time.time() - start

        if isinstance(result, dict):
            rtype = result.get("type", "?")
            has_content = bool(result.get("title") or result.get("text") or
                            result.get("columns") or result.get("branches") or
                            result.get("strengths") or result.get("stories") or
                            result.get("nodes") or result.get("items") or
                            result.get("pros") or result.get("levels") or
                            result.get("specifications") or result.get("headers"))
            metadata = result.get("metadata", {})
            agent = metadata.get("formatted_by", "?")

            print(f"  OK  type={rtype}  has_content={has_content}  agent={agent}  ({elapsed:.1f}s)")

            # Print structure summary
            keys = [k for k in result.keys() if k not in ("type", "metadata")]
            print(f"       keys: {keys}")

            # Print first-level sizes
            for k in keys:
                v = result[k]
                if isinstance(v, list):
                    print(f"       {k}: {len(v)} items")
                elif isinstance(v, dict):
                    print(f"       {k}: {list(v.keys())}")
                elif isinstance(v, str) and len(v) > 80:
                    print(f"       {k}: \"{v[:77]}...\"")
                else:
                    print(f"       {k}: {v!r}")

            return True, elapsed
        else:
            elapsed = time.time() - start
            print(f"  WARN  returned non-dict: {type(result).__name__} ({elapsed:.1f}s)")
            print(f"       {str(result)[:200]}")
            return False, elapsed

    except Exception as e:
        elapsed = time.time() - start
        print(f"  FAIL  {type(e).__name__}: {e} ({elapsed:.1f}s)")
        traceback.print_exc(limit=3)
        return False, elapsed


def main():
    print("=" * 60)
    print("  AI TOOLS INDEPENDENT TEST")
    print("  Model: anthropic/claude-sonnet-4.5 via OpenRouter")
    print("=" * 60)

    # Check API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("\nERROR: OPENROUTER_API_KEY not set in .env")
        sys.exit(1)
    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")

    # --- Sample source content (a note about API Design) ---
    sample_note = {
        "type": "note",
        "title": "API Design Konzept",
        "text": (
            "Wir brauchen eine REST API fuer VibeMind mit folgenden Endpunkten: "
            "GET /ideas (alle Ideen auflisten), POST /ideas (neue Idee erstellen), "
            "PUT /ideas/:id (Idee aktualisieren), DELETE /ideas/:id (Idee loeschen). "
            "Authentifizierung ueber JWT Tokens. Rate Limiting auf 100 req/min. "
            "Datenbank ist SQLite lokal, spaeter PostgreSQL. "
            "Frontend kommuniziert ueber Electron IPC, nicht direkt HTTP. "
            "Brauchen auch WebSocket fuer Echtzeit-Updates. "
            "Prioritaet: REST Endpunkte zuerst, dann WebSocket, dann Auth."
        ),
    }

    # --- Import format agents ---
    from tools.format_dispatcher import (
        format_as_note,
        format_as_table,
        format_as_action_list,
        format_as_pros_cons,
        format_as_hierarchy,
        format_as_specs,
        format_as_kanban,
        format_as_mindmap,
        format_as_swot,
        format_as_user_story,
        format_as_flowchart,
    )

    results = []

    # =====================================================================
    # PART 1: FORMAT AGENTS (11 formats)
    # =====================================================================
    print("\n\n" + "#" * 60)
    print("  PART 1: FORMAT AGENTS (LLM-powered)")
    print("#" * 60)

    format_tests = [
        ("format_as_note", format_as_note, sample_note),
        ("format_as_table", format_as_table, sample_note),
        ("format_as_action_list", format_as_action_list, sample_note),
        ("format_as_pros_cons", format_as_pros_cons, sample_note),
        ("format_as_hierarchy", format_as_hierarchy, sample_note),
        ("format_as_specs", format_as_specs, sample_note),
        ("format_as_kanban", format_as_kanban, sample_note),
        ("format_as_mindmap", format_as_mindmap, sample_note),
        ("format_as_swot", format_as_swot, sample_note),
        ("format_as_user_story", format_as_user_story, sample_note),
        ("format_as_flowchart", format_as_flowchart, sample_note),
    ]

    for name, func, source in format_tests:
        ok, elapsed = test_format_agent(name, func, source)
        results.append((name, ok, elapsed))

    # =====================================================================
    # PART 2: AI ENRICHMENT TOOLS (need DB for full test, test import only)
    # =====================================================================
    print("\n\n" + "#" * 60)
    print("  PART 2: AI ENRICHMENT TOOLS (import check)")
    print("#" * 60)

    enrichment_tools = [
        ("classify_idea", "idea_tools"),
        ("expand_ideas", "idea_tools"),
        ("explain_idea", "idea_tools"),
        ("summarize_idea", "summary_tools"),
        ("generate_white_paper", "summary_tools"),
    ]

    for tool_name, module_name in enrichment_tools:
        print(f"\n  Checking import: {tool_name} (from {module_name})...", end=" ")
        try:
            module = __import__(f"tools.{module_name}", fromlist=[tool_name])
            func = getattr(module, tool_name, None)
            if func:
                print(f"OK (callable)")
                results.append((f"import:{tool_name}", True, 0))
            else:
                print(f"NOT FOUND in {module_name}")
                results.append((f"import:{tool_name}", False, 0))
        except Exception as e:
            print(f"FAIL: {e}")
            results.append((f"import:{tool_name}", False, 0))

    # =====================================================================
    # PART 3: TYPED WRAPPERS (adapted_idea_tools)
    # =====================================================================
    print("\n\n" + "#" * 60)
    print("  PART 3: TYPED WRAPPERS (adapted_idea_tools)")
    print("#" * 60)

    wrapper_tools = [
        "count_ideas",
        "move_idea",
        "connect_ideas_multi",
        "link_idea_to_root",
        "classify_idea",
        "list_ideas",
        "create_idea",
        "find_idea",
        "update_idea",
        "delete_idea",
        "connect_ideas",
        "disconnect_ideas",
        "get_current_space",
        "auto_link_ideas",
        "format_idea_as_table",
        "summarize_idea",
        "generate_white_paper",
        "expand_ideas",
        "analyze_and_suggest_links",
        "explain_idea",
    ]

    for tool_name in wrapper_tools:
        print(f"\n  Checking: {tool_name}...", end=" ")
        try:
            from swarm.tools import adapted_idea_tools
            func = getattr(adapted_idea_tools, tool_name, None)
            if func and callable(func):
                # Check signature
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                print(f"OK  params={params}  return={sig.return_annotation}")
                results.append((f"wrapper:{tool_name}", True, 0))
            else:
                print(f"NOT FOUND")
                results.append((f"wrapper:{tool_name}", False, 0))
        except Exception as e:
            print(f"FAIL: {e}")
            results.append((f"wrapper:{tool_name}", False, 0))

    # =====================================================================
    # PART 4: IDEAS SWARM (import check)
    # =====================================================================
    print("\n\n" + "#" * 60)
    print("  PART 4: IDEAS SWARM IMPORT")
    print("#" * 60)

    print(f"\n  Checking ideas_swarm...", end=" ")
    try:
        from swarm.backend_agents.ideas_swarm import create_ideas_swarm, get_ideas_swarm
        print(f"OK (create_ideas_swarm, get_ideas_swarm)")
        results.append(("swarm:import", True, 0))
    except Exception as e:
        print(f"FAIL: {e}")
        traceback.print_exc(limit=3)
        results.append(("swarm:import", False, 0))

    # =====================================================================
    # SUMMARY
    # =====================================================================
    print("\n\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    total_time = sum(t for _, _, t in results)

    print(f"\n  Total: {len(results)} tests")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Total LLM time: {total_time:.1f}s")

    if failed > 0:
        print(f"\n  FAILED TESTS:")
        for name, ok, _ in results:
            if not ok:
                print(f"    - {name}")

    print(f"\n{'='*60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
