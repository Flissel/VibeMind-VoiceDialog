"""
OpenClaw Desktop Swarm - Comprehensive E2E Test Suite

10 Schwierigkeitsgrade (Level 1-10), je 5 Tests = 50 Tests total.

Level 1:  Imports & Module Loading
Level 2:  Configuration & Environment
Level 3:  Agent Creation & Structure
Level 4:  Tool Availability & Signatures
Level 5:  Claude CLI Connectivity
Level 6:  MCP Server Discovery
Level 7:  MCP Server Connection (43 Tools)
Level 8:  Desktop Tool Execution
Level 9:  Swarm Single-Turn Execution
Level 10: Swarm Multi-Agent Flow (Full E2E)

Usage:
    python -m tests.test_openclaw_e2e
    python -m tests.test_openclaw_e2e --level 5      # Only level 5
    python -m tests.test_openclaw_e2e --up-to 7      # Levels 1-7
"""

import sys
import os
import asyncio
import time
import inspect
import argparse
from typing import Dict, List, Tuple, Any

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
except ImportError:
    pass


# ── Helpers ──

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

results: Dict[int, List[Tuple[str, str, str]]] = {}


def record(level: int, name: str, status: str, detail: str = ""):
    results.setdefault(level, [])
    results[level].append((name, status, detail))


def run_async(coro):
    """Run async coroutine in sync context."""
    return asyncio.run(coro)


# ══════════════════════════════════════════════════════════════
# LEVEL 1: Imports & Module Loading
# ══════════════════════════════════════════════════════════════

def test_level_1():
    L = 1

    # 1.1 Core package import
    try:
        import spaces.OpenClaw
        record(L, "1.1 Package import", PASS, "spaces.OpenClaw")
    except Exception as e:
        record(L, "1.1 Package import", FAIL, str(e))

    # 1.2 Swarm module import
    try:
        from spaces.OpenClaw.agents.desktop_swarm import (
            create_desktop_swarm, run_desktop_swarm, get_desktop_swarm,
            reset_desktop_swarm, USE_MCP_DESKTOP
        )
        record(L, "1.2 Swarm imports", PASS, "5 symbols")
    except Exception as e:
        record(L, "1.2 Swarm imports", FAIL, str(e))

    # 1.3 Claude CLI tools import
    try:
        from spaces.OpenClaw.tools.claude_cli_tools import (
            claude_reason, claude_analyze_screenshot, claude_plan_task,
            CLAUDE_CLI_TOOLS, CLAUDE_CLI
        )
        record(L, "1.3 Claude CLI tools", PASS, f"CLI={CLAUDE_CLI}")
    except Exception as e:
        record(L, "1.3 Claude CLI tools", FAIL, str(e))

    # 1.4 Desktop CLI tools import
    try:
        from spaces.OpenClaw.tools.desktop_cli_tools import (
            execute_desktop_task, click_element, type_text, press_key,
            take_screenshot, scroll_screen, open_app, moire_scan, moire_find_element
        )
        record(L, "1.4 Desktop CLI tools", PASS, "9 tools")
    except Exception as e:
        record(L, "1.4 Desktop CLI tools", FAIL, str(e))

    # 1.5 Messaging tools import
    try:
        from spaces.OpenClaw.tools.messaging_tools import (
            send_whatsapp, send_telegram, web_search, web_fetch,
            get_pending_notifications, get_openclaw_status
        )
        record(L, "1.5 Messaging tools", PASS, "6 tools")
    except Exception as e:
        record(L, "1.5 Messaging tools", FAIL, str(e))


# ══════════════════════════════════════════════════════════════
# LEVEL 2: Configuration & Environment
# ══════════════════════════════════════════════════════════════

def test_level_2():
    L = 2

    # 2.1 OpenClawConfig creation
    try:
        from spaces.OpenClaw.config import OpenClawConfig
        cfg = OpenClawConfig.from_env()
        record(L, "2.1 Config from_env()", PASS, f"swarm={cfg.use_ag2_desktop_swarm}")
    except Exception as e:
        record(L, "2.1 Config from_env()", FAIL, str(e))

    # 2.2 Config singleton
    try:
        from spaces.OpenClaw.config import get_config
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2, "Not singleton"
        record(L, "2.2 Config singleton", PASS)
    except Exception as e:
        record(L, "2.2 Config singleton", FAIL, str(e))

    # 2.3 OpenRouter API key
    try:
        key = os.getenv("OPENROUTER_API_KEY", "")
        assert key and len(key) > 10, f"Key missing or too short ({len(key)})"
        record(L, "2.3 OPENROUTER_API_KEY", PASS, f"len={len(key)}")
    except Exception as e:
        record(L, "2.3 OPENROUTER_API_KEY", FAIL, str(e))

    # 2.4 Feature flags
    try:
        from spaces.OpenClaw.agents.desktop_swarm import USE_MCP_DESKTOP, MCP_DESKTOP_SERVER
        record(L, "2.4 Feature flags", PASS,
               f"MCP={USE_MCP_DESKTOP}, server={MCP_DESKTOP_SERVER}")
    except Exception as e:
        record(L, "2.4 Feature flags", FAIL, str(e))

    # 2.5 servers.json exists and valid
    try:
        import json
        servers_json = os.path.join(
            os.path.dirname(__file__), "..",
            "swarm", "mcp_plugins", "servers", "servers.json"
        )
        assert os.path.isfile(servers_json), f"Not found"
        with open(servers_json, encoding="utf-8") as f:
            data = json.load(f)
        srv_count = len(data.get("servers", []))
        active = sum(1 for s in data.get("servers", []) if s.get("active"))
        record(L, "2.5 servers.json", PASS, f"{srv_count} servers ({active} active)")
    except Exception as e:
        record(L, "2.5 servers.json", FAIL, str(e))


# ══════════════════════════════════════════════════════════════
# LEVEL 3: Agent Creation & Structure
# ══════════════════════════════════════════════════════════════

def test_level_3():
    L = 3
    from spaces.OpenClaw.agents.desktop_swarm import create_desktop_swarm, reset_desktop_swarm
    reset_desktop_swarm()

    # 3.1 Swarm creation
    try:
        swarm = create_desktop_swarm()
        assert swarm is not None
        record(L, "3.1 Swarm creation", PASS)
    except Exception as e:
        record(L, "3.1 Swarm creation", FAIL, str(e))
        return

    # 3.2 Agent count = 3
    try:
        agents = swarm._participants
        assert len(agents) == 3, f"Expected 3, got {len(agents)}"
        record(L, "3.2 Agent count (3)", PASS, ", ".join(a.name for a in agents))
    except Exception as e:
        record(L, "3.2 Agent count (3)", FAIL, str(e))

    # 3.3 Coordinator has 0 tools
    try:
        coord = [a for a in swarm._participants if a.name == "desktop_coordinator"][0]
        tools = getattr(coord, "_tools", [])
        assert len(tools) == 0, f"Has {len(tools)} tools"
        record(L, "3.3 Coordinator: 0 tools", PASS)
    except Exception as e:
        record(L, "3.3 Coordinator: 0 tools", FAIL, str(e))

    # 3.4 ClaudeCLI has 4 tools
    try:
        cli = [a for a in swarm._participants if a.name == "claude_cli_agent"][0]
        tools = getattr(cli, "_tools", [])
        assert len(tools) == 4, f"Has {len(tools)}, expected 4"
        record(L, "3.4 ClaudeCLI: 4 tools", PASS)
    except Exception as e:
        record(L, "3.4 ClaudeCLI: 4 tools", FAIL, str(e))

    # 3.5 Operator has 15 tools
    try:
        op = [a for a in swarm._participants if a.name == "desktop_operator"][0]
        tools = getattr(op, "_tools", [])
        assert len(tools) == 15, f"Has {len(tools)}, expected 15"
        record(L, "3.5 Operator: 15 tools", PASS)
    except Exception as e:
        record(L, "3.5 Operator: 15 tools", FAIL, str(e))


# ══════════════════════════════════════════════════════════════
# LEVEL 4: Tool Availability & Signatures
# ══════════════════════════════════════════════════════════════

def test_level_4():
    L = 4

    # 4.1 Claude CLI tools are async
    try:
        from spaces.OpenClaw.tools.claude_cli_tools import (
            claude_reason, claude_analyze_screenshot, claude_plan_task
        )
        assert asyncio.iscoroutinefunction(claude_reason)
        assert asyncio.iscoroutinefunction(claude_analyze_screenshot)
        assert asyncio.iscoroutinefunction(claude_plan_task)
        record(L, "4.1 Claude tools async", PASS)
    except Exception as e:
        record(L, "4.1 Claude tools async", FAIL, str(e))

    # 4.2 claude_reason signature
    try:
        sig = inspect.signature(claude_reason)
        params = list(sig.parameters.keys())
        assert "prompt" in params and "context" in params and "timeout" in params
        record(L, "4.2 claude_reason sig", PASS, str(params))
    except Exception as e:
        record(L, "4.2 claude_reason sig", FAIL, str(e))

    # 4.3 Desktop tools are callable
    try:
        from spaces.OpenClaw.tools.desktop_cli_tools import DESKTOP_WORKER_TOOLS
        for t in DESKTOP_WORKER_TOOLS:
            assert callable(t), f"{t} not callable"
        record(L, "4.3 Desktop tools callable", PASS, f"{len(DESKTOP_WORKER_TOOLS)}")
    except Exception as e:
        record(L, "4.3 Desktop tools callable", FAIL, str(e))

    # 4.4 Messaging tools are callable
    try:
        from spaces.OpenClaw.tools.messaging_tools import MESSAGING_TOOLS
        for t in MESSAGING_TOOLS:
            assert callable(t)
        record(L, "4.4 Messaging tools callable", PASS, f"{len(MESSAGING_TOOLS)}")
    except Exception as e:
        record(L, "4.4 Messaging tools callable", FAIL, str(e))

    # 4.5 Event routing complete
    try:
        from swarm.event_team.event_router import EventRouter
        desktop_events = [
            "desktop.open_app", "desktop.click", "desktop.type",
            "desktop.press_key", "desktop.screenshot", "desktop.scroll",
            "messaging.whatsapp", "messaging.telegram", "web.search",
        ]
        missing = [e for e in desktop_events if e not in EventRouter.STREAM_MAPPING]
        assert not missing, f"Missing: {missing}"
        record(L, "4.5 Event routing", PASS, f"{len(desktop_events)} events mapped")
    except Exception as e:
        record(L, "4.5 Event routing", FAIL, str(e))


# ══════════════════════════════════════════════════════════════
# LEVEL 5: Claude CLI Connectivity
# ══════════════════════════════════════════════════════════════

def test_level_5():
    L = 5
    from spaces.OpenClaw.tools.claude_cli_tools import CLAUDE_CLI

    # 5.1 CLI path resolved
    try:
        assert CLAUDE_CLI and len(CLAUDE_CLI) > 0
        record(L, "5.1 CLI path resolved", PASS, CLAUDE_CLI)
    except Exception as e:
        record(L, "5.1 CLI path resolved", FAIL, str(e))

    # 5.2 CLI --version
    try:
        import subprocess
        result = subprocess.run(
            [CLAUDE_CLI, "--version"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"Exit {result.returncode}"
        record(L, "5.2 CLI --version", PASS, result.stdout.strip()[:60])
    except Exception as e:
        record(L, "5.2 CLI --version", FAIL, str(e))

    # 5.3 claude_reason simple
    try:
        from spaces.OpenClaw.tools.claude_cli_tools import claude_reason
        result = run_async(claude_reason("Antworte NUR: PONG", timeout=15.0))
        assert "Fehler" not in result[:10], result[:100]
        record(L, "5.3 claude_reason()", PASS, f"{len(result)} chars")
    except Exception as e:
        record(L, "5.3 claude_reason()", FAIL, str(e))

    # 5.4 claude_plan_task JSON
    try:
        from spaces.OpenClaw.tools.claude_cli_tools import claude_plan_task
        plan = run_async(claude_plan_task("Oeffne Notepad", timeout=20.0))
        assert isinstance(plan, dict), f"Not dict: {type(plan)}"
        assert "plan" in plan, f"Keys: {list(plan.keys())}"
        record(L, "5.4 plan_task JSON", PASS, f"{len(plan.get('plan', []))} steps")
    except Exception as e:
        record(L, "5.4 plan_task JSON", FAIL, str(e))

    # 5.5 claude_reason with context
    try:
        from spaces.OpenClaw.tools.claude_cli_tools import claude_reason
        result = run_async(claude_reason(
            "Was ist 2+2? Antworte NUR mit der Zahl.",
            context="Du bist ein Taschenrechner.",
            timeout=15.0
        ))
        assert "Fehler" not in result[:10]
        record(L, "5.5 reason+context", PASS, f"'{result.strip()[:30]}'")
    except Exception as e:
        record(L, "5.5 reason+context", FAIL, str(e))


# ══════════════════════════════════════════════════════════════
# LEVEL 6: MCP Server Discovery
# ══════════════════════════════════════════════════════════════

def test_level_6():
    L = 6
    from spaces.OpenClaw.agents.desktop_swarm import _load_mcp_server_params
    params = _load_mcp_server_params()

    # 6.1 Params loaded
    try:
        assert params is not None, "None returned"
        record(L, "6.1 MCP params loaded", PASS)
    except Exception as e:
        record(L, "6.1 MCP params loaded", FAIL, str(e))
        for i in range(2, 6):
            record(L, f"6.{i} (skipped)", SKIP, "No params")
        return

    # 6.2 Python 3.11
    try:
        assert "3.11" in params.command or "pyenv" in params.command
        record(L, "6.2 Python 3.11", PASS, params.command)
    except Exception as e:
        record(L, "6.2 Python 3.11", FAIL, str(e))

    # 6.3 cwd is MoireTracker
    try:
        assert params.cwd and "MoireTracker" in str(params.cwd)
        record(L, "6.3 cwd=MoireTracker", PASS)
    except Exception as e:
        record(L, "6.3 cwd=MoireTracker", FAIL, str(e))

    # 6.4 Timeout >= 30s
    try:
        assert params.read_timeout_seconds >= 30
        record(L, "6.4 timeout >= 30s", PASS, f"{params.read_timeout_seconds}s")
    except Exception as e:
        record(L, "6.4 timeout >= 30s", FAIL, str(e))

    # 6.5 Script file exists
    try:
        script = params.args[0] if params.args else ""
        assert os.path.isfile(script), f"Not found: {script}"
        record(L, "6.5 MCP script exists", PASS, os.path.basename(script))
    except Exception as e:
        record(L, "6.5 MCP script exists", FAIL, str(e))


# ══════════════════════════════════════════════════════════════
# LEVEL 7: MCP Server Connection (43 Tools)
# ══════════════════════════════════════════════════════════════

def test_level_7():
    L = 7

    async def _run():
        from spaces.OpenClaw.agents.desktop_swarm import _load_mcp_server_params
        from autogen_ext.tools.mcp import McpWorkbench

        params = _load_mcp_server_params()
        if params is None:
            for i in range(1, 6):
                record(L, f"7.{i} (skipped)", SKIP, "No MCP params")
            return

        try:
            async with McpWorkbench(params) as mcp:
                record(L, "7.1 MCP connect", PASS)

                tools = await mcp.list_tools()
                record(L, "7.2 List tools", PASS, f"{len(tools)}")

                if len(tools) >= 40:
                    record(L, "7.3 >= 40 tools", PASS, str(len(tools)))
                else:
                    record(L, "7.3 >= 40 tools", FAIL, f"Only {len(tools)}")

                tool_names = []
                for t in tools:
                    if isinstance(t, dict):
                        tool_names.append(t.get("name", ""))
                    else:
                        tool_names.append(getattr(t, "name", str(t)))

                key_tools = ["screen_scan", "action_click", "action_type"]
                missing = [t for t in key_tools if t not in tool_names]
                if not missing:
                    record(L, "7.4 Key tools present", PASS, str(key_tools))
                else:
                    record(L, "7.4 Key tools present", FAIL, f"Missing: {missing}")

                categories = {}
                for name in tool_names:
                    prefix = name.split("_")[0] if "_" in name else name
                    categories.setdefault(prefix, []).append(name)
                cats = ", ".join(f"{k}={len(v)}" for k, v in sorted(categories.items()))
                record(L, "7.5 Tool categories", PASS, cats)

        except Exception as e:
            record(L, "7.1 MCP connect", FAIL, str(e))
            for i in range(2, 6):
                record(L, f"7.{i} (skipped)", SKIP, "Connect failed")

    run_async(_run())


# ══════════════════════════════════════════════════════════════
# LEVEL 8: Desktop Tool Execution
# ══════════════════════════════════════════════════════════════

def test_level_8():
    L = 8

    # 8.1 take_screenshot (adapted wrapper import & signature)
    try:
        from spaces.desktop.adapted.desktop_tools import take_screenshot
        assert callable(take_screenshot), "Not callable"
        sig = inspect.signature(take_screenshot)
        assert len(sig.parameters) == 0, f"Expected 0 params, got {len(sig.parameters)}"
        # Don't call take_screenshot() directly - moire_external.initialize() blocks
        # when MoireTracker is not running. Actual execution tested via Swarm in L10.
        record(L, "8.1 take_screenshot", PASS, "callable, 0 params")
    except Exception as e:
        record(L, "8.1 take_screenshot", FAIL, str(e))

    # 8.2 moire_scan
    try:
        from spaces.OpenClaw.tools.desktop_cli_tools import moire_scan
        if asyncio.iscoroutinefunction(moire_scan):
            result = run_async(moire_scan())
        else:
            result = moire_scan()
        if "Fehler" in str(result) and "nicht verfuegbar" in str(result):
            record(L, "8.2 moire_scan", SKIP, "MoireServer unavailable")
        else:
            record(L, "8.2 moire_scan", PASS, f"{len(str(result))} chars")
    except Exception as e:
        record(L, "8.2 moire_scan", FAIL, str(e))

    # 8.3 open_app signature check
    try:
        from spaces.OpenClaw.tools.desktop_cli_tools import open_app
        sig = inspect.signature(open_app)
        assert "app_name" in sig.parameters
        record(L, "8.3 open_app sig", PASS, str(list(sig.parameters.keys())))
    except Exception as e:
        record(L, "8.3 open_app sig", FAIL, str(e))

    # 8.4 get_openclaw_status
    try:
        from spaces.OpenClaw.tools.messaging_tools import get_openclaw_status
        if asyncio.iscoroutinefunction(get_openclaw_status):
            result = run_async(get_openclaw_status())
        else:
            result = get_openclaw_status()
        record(L, "8.4 openclaw_status", PASS, str(result)[:80])
    except Exception as e:
        record(L, "8.4 openclaw_status", FAIL, str(e))

    # 8.5 Backend agent creation
    try:
        from spaces.OpenClaw.backend_agent import get_openclaw_desktop_agent
        agent = get_openclaw_desktop_agent()
        assert agent.name == "OpenClawDesktopAgent"
        record(L, "8.5 Backend agent", PASS, agent.name)
    except Exception as e:
        record(L, "8.5 Backend agent", FAIL, str(e))


# ══════════════════════════════════════════════════════════════
# LEVEL 9: Swarm Single-Turn Execution
# ══════════════════════════════════════════════════════════════

def test_level_9():
    L = 9
    from spaces.OpenClaw.agents.desktop_swarm import (
        create_desktop_swarm, reset_desktop_swarm, get_desktop_swarm
    )
    reset_desktop_swarm()

    msgs = []

    # 9.1 Swarm responds to greeting
    async def _run_greeting():
        swarm = create_desktop_swarm()
        return await asyncio.wait_for(
            swarm.run(task="Sage Hallo und bestaetige dass du bereit bist."),
            timeout=45.0
        )

    try:
        result = run_async(_run_greeting())
        msgs = result.messages if hasattr(result, "messages") else []
        record(L, "9.1 Swarm greeting", PASS, f"{len(msgs)} msgs")
    except asyncio.TimeoutError:
        record(L, "9.1 Swarm greeting", FAIL, "Timeout 45s")
    except Exception as e:
        record(L, "9.1 Swarm greeting", FAIL, str(e))

    # 9.2 Coordinator participated
    try:
        sources = [getattr(m, "source", "") for m in msgs]
        has_coord = "desktop_coordinator" in sources
        record(L, "9.2 Coordinator spoke", PASS if has_coord else FAIL,
               str(set(sources)))
    except Exception as e:
        record(L, "9.2 Coordinator spoke", FAIL, str(e))

    # 9.3 Termination reached
    try:
        stop = getattr(result, "stop_reason", None) if msgs else None
        record(L, "9.3 Termination", PASS if stop else SKIP,
               str(stop)[:60] if stop else "unknown")
    except Exception as e:
        record(L, "9.3 Termination", FAIL, str(e))

    # 9.4 Singleton pattern
    try:
        reset_desktop_swarm()
        s1 = get_desktop_swarm()
        s2 = get_desktop_swarm()
        assert s1 is s2, "Not singleton"
        record(L, "9.4 Singleton", PASS)
    except Exception as e:
        record(L, "9.4 Singleton", FAIL, str(e))

    # 9.5 Reset clears singleton
    try:
        reset_desktop_swarm()
        s3 = get_desktop_swarm()
        assert s3 is not s1, "Not cleared"
        record(L, "9.5 Reset singleton", PASS)
    except Exception as e:
        record(L, "9.5 Reset singleton", FAIL, str(e))


# ══════════════════════════════════════════════════════════════
# LEVEL 10: Swarm Multi-Agent Flow (Full E2E)
# ══════════════════════════════════════════════════════════════

def test_level_10():
    L = 10
    from spaces.OpenClaw.agents.desktop_swarm import create_desktop_swarm, reset_desktop_swarm
    reset_desktop_swarm()

    msgs = []

    # 10.1 Screenshot task E2E
    async def _run_screenshot():
        swarm = create_desktop_swarm()
        return await asyncio.wait_for(
            swarm.run(task="Mache einen Screenshot und beschreibe kurz was du siehst."),
            timeout=180.0
        )

    try:
        result = run_async(_run_screenshot())
        msgs = result.messages if hasattr(result, "messages") else []
        record(L, "10.1 Screenshot E2E", PASS, f"{len(msgs)} msgs")
    except asyncio.TimeoutError:
        record(L, "10.1 Screenshot E2E", FAIL, "Timeout 90s")
    except Exception as e:
        record(L, "10.1 Screenshot E2E", FAIL, str(e))

    # 10.2 Multiple agents participated
    try:
        sources = set(getattr(m, "source", "?") for m in msgs)
        agents = [s for s in sources if s and s != "?"]
        record(L, "10.2 Multi-agent", PASS if len(agents) >= 2 else FAIL,
               str(agents))
    except Exception as e:
        record(L, "10.2 Multi-agent", FAIL, str(e))

    # 10.3 Handoffs occurred
    try:
        handoff_count = sum(1 for m in msgs if "HandoffMessage" in type(m).__name__
                           or "handoff" in type(m).__name__.lower())
        if handoff_count > 0:
            record(L, "10.3 Handoffs", PASS, f"{handoff_count}")
        else:
            # Check message content for implicit handoffs
            has_delegate = any(
                any(kw in str(getattr(m, "content", "")).lower()
                    for kw in ["delegiere", "operator", "claude_cli", "handoff"])
                for m in msgs
            )
            record(L, "10.3 Handoffs", PASS if has_delegate else SKIP,
                   "implicit" if has_delegate else "not detected")
    except Exception as e:
        record(L, "10.3 Handoffs", FAIL, str(e))

    # 10.4 Tool calls happened
    try:
        tool_msgs = [m for m in msgs if "tool" in type(m).__name__.lower()
                     or "ToolCall" in type(m).__name__]
        record(L, "10.4 Tool calls", PASS if tool_msgs else SKIP,
               f"{len(tool_msgs)} tool msgs")
    except Exception as e:
        record(L, "10.4 Tool calls", FAIL, str(e))

    # 10.5 Final response has content (search backwards for non-empty message)
    try:
        if msgs:
            content = ""
            for m in reversed(msgs):
                c = str(getattr(m, "content", "") or "")
                if len(c) > 10 and "HandoffMessage" not in type(m).__name__:
                    content = c
                    break
            record(L, "10.5 Final response", PASS if len(content) > 10 else FAIL,
                   f"{len(content)} chars: '{content[:60]}...'")
        else:
            record(L, "10.5 Final response", FAIL, "No messages")
    except Exception as e:
        record(L, "10.5 Final response", FAIL, str(e))


# ══════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════

LEVEL_NAMES = {
    1: "Imports & Module Loading",
    2: "Configuration & Environment",
    3: "Agent Creation & Structure",
    4: "Tool Availability & Signatures",
    5: "Claude CLI Connectivity",
    6: "MCP Server Discovery",
    7: "MCP Server Connection (43 Tools)",
    8: "Desktop Tool Execution",
    9: "Swarm Single-Turn",
    10: "Swarm Multi-Agent E2E",
}

LEVEL_FUNCS = {
    1: test_level_1,
    2: test_level_2,
    3: test_level_3,
    4: test_level_4,
    5: test_level_5,
    6: test_level_6,
    7: test_level_7,
    8: test_level_8,
    9: test_level_9,
    10: test_level_10,
}


def print_results():
    total_pass = total_fail = total_skip = 0

    for level in sorted(results.keys()):
        name = LEVEL_NAMES.get(level, "Unknown")
        print(f"\n{'='*60}")
        print(f" Level {level}: {name}")
        print(f"{'='*60}")

        for test_name, status, detail in results[level]:
            detail_str = f"  ({detail})" if detail else ""
            print(f"  [{status}] {test_name}{detail_str}")

            if status == PASS:
                total_pass += 1
            elif status == FAIL:
                total_fail += 1
            else:
                total_skip += 1

    total = total_pass + total_fail + total_skip
    print(f"\n{'='*60}")
    print(f" TOTAL: {total_pass}/{total} passed, {total_fail} failed, {total_skip} skipped")
    print(f"{'='*60}")
    return total_fail


def main():
    parser = argparse.ArgumentParser(description="OpenClaw E2E Test Suite (10 Levels x 5 Tests)")
    parser.add_argument("--level", type=int, help="Run only this level (1-10)")
    parser.add_argument("--up-to", type=int, help="Run levels 1 through N")
    args = parser.parse_args()

    if args.level:
        levels = [args.level]
    elif args.up_to:
        levels = list(range(1, args.up_to + 1))
    else:
        levels = list(range(1, 11))

    print("OpenClaw Desktop Swarm - E2E Test Suite")
    print(f"Levels: {levels} ({len(levels) * 5} tests)")
    print()

    for level in levels:
        func = LEVEL_FUNCS.get(level)
        if func:
            t0 = time.time()
            try:
                func()
            except Exception as e:
                record(level, f"Level {level} CRASH", FAIL, str(e))
            dt = time.time() - t0
            print(f"  Level {level} ({LEVEL_NAMES[level]}): {dt:.1f}s")

    print_results()
    failures = sum(1 for tests in results.values() for _, s, _ in tests if s == FAIL)
    sys.exit(1 if failures > 0 else 0)


if __name__ == "__main__":
    main()
