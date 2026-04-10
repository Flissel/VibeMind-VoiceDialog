"""Claude Code CLI provider — routes LLM calls through claude --print.

Uses the user's Max subscription OAuth, not an API key. Works by spawning
a `claude --print` subprocess for each request. The CLAUDECODE env var must
be unset to avoid the nesting protection.

Usage:
    from claude_code_provider import claude_code_chat
    response = claude_code_chat("Classify this intent: list bubbles", model="claude-haiku-4-5-20251001")
    # response = "bubble.list"
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# On Windows, npm installs a .cmd shim. Python's subprocess needs the .cmd
# extension explicitly, or we call via cmd.exe.
_CLAUDE_CLI = shutil.which("claude.cmd") or shutil.which("claude")


def claude_code_chat(
    prompt: str,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 2048,
    timeout: float = 30.0,
) -> Optional[str]:
    """Send a prompt to Claude via the CLI and return the text response.

    Returns None on any error (timeout, CLI not found, auth issue).
    """
    if not _CLAUDE_CLI:
        logger.warning("claude CLI not found on PATH")
        return None

    # Build clean env without ALL Claude Code nesting-protection vars.
    # If any of these remain, the CLI detects a nested session and refuses.
    env = os.environ.copy()
    for key in list(env.keys()):
        if key.startswith("CLAUDE") or key == "CLAUDECODE":
            env.pop(key)

    cmd = [
        _CLAUDE_CLI,
        "--print",
        "--model", model,
    ]

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            logger.warning(
                f"claude --print failed (rc={result.returncode}): "
                f"stderr={stderr[:300]} stdout={stdout[:100]}"
            )
            # Sometimes the response is in stdout despite non-zero exit
            if stdout and len(stdout) > 2:
                return stdout
            return None
        return (result.stdout or "").strip()
    except subprocess.TimeoutExpired:
        logger.warning(f"claude --print timed out after {timeout}s")
        return None
    except Exception as e:
        logger.warning(f"claude --print error: {e}")
        return None


def is_available() -> bool:
    """Check if the claude CLI is available."""
    return _CLAUDE_CLI is not None
