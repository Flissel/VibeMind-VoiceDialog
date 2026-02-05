#!/usr/bin/env python3
"""Simulate Tavily MCP Agent with a realistic task.

NOTE: Requires TAVILY_API_KEY environment variable
"""
import subprocess
import sys
import os

def main():
    """Run tavily agent simulation."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 60)
    print("Tavily Agent Simulation")
    print("=" * 60)
    print("Task: Search for 'React hooks best practices'")
    print()

    if not os.getenv("TAVILY_API_KEY"):
        print("[SKIP] TAVILY_API_KEY not set")
        return 2  # Skip exit code

    try:
        result = subprocess.run(
            [sys.executable, os.path.join(script_dir, "agent.py"),
             "--task", "Search for 'React hooks best practices'",
             "--session-id", "sim_tavily_test"],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=script_dir,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}
        )

        if "SESSION_ANNOUNCE" in result.stdout:
            print("[OK] Agent started successfully")
            print()
            print("Output (last 500 chars):")
            print("-" * 40)
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)

            if "TASK_COMPLETE" in result.stdout:
                print()
                print("[OK] Task completed successfully")
                return 0
            else:
                print()
                print("[WARN] Task may not have completed")
                return 1
        else:
            print("[FAIL] Agent failed to start")
            print("stderr:", result.stderr[:500] if result.stderr else "None")
            return 1

    except subprocess.TimeoutExpired:
        print("[FAIL] Agent timed out after 90s")
        return 1
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
