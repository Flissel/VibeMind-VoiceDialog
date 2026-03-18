"""
Benchmark: Minibook-Route vs Direct-Async for format tools.

Measures:
  A) Direct LLM call (what format_dispatcher does today)
  B) Minibook round-trip: POST task → Poll for response → get result

Run from python/:
    python -m tests.benchmark_format_routes
"""

import asyncio
import json
import os
import sys
import time

# Add python/ to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

# Load .env
from dotenv import load_dotenv
# Load .env from project root (two levels up from tests/)
_base = os.path.dirname(os.path.abspath(__file__))
_root = os.path.normpath(os.path.join(_base, "..", ".."))
load_dotenv(os.path.join(_root, ".env"))
# Also try python/.env as fallback
load_dotenv(os.path.join(_base, "..", ".env"))


SAMPLE_CONTENT = {
    "type": "note",
    "title": "API Design Ideas",
    "text": (
        "We need a REST API with authentication via JWT tokens. "
        "Endpoints: GET /users, POST /users, PUT /users/:id, DELETE /users/:id. "
        "Rate limiting at 100 req/min. Database: PostgreSQL with connection pooling. "
        "Caching layer with Redis for frequently accessed user profiles. "
        "WebSocket support for real-time notifications."
    ),
}

SAMPLE_TITLE = "API Design Ideas"


def benchmark_direct_llm():
    """A) Direct LLM call — same as format_dispatcher._call_format_agent."""
    from openai import OpenAI

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None, "OPENROUTER_API_KEY not set"

    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    prompt = f"""Convert this content into a table:

TITLE: {SAMPLE_TITLE}
CONTENT:
{SAMPLE_CONTENT['text']}

Format as JSON:
{{
  "type": "table",
  "title": "Table Title",
  "headers": ["Column1", "Column2", "Column3"],
  "rows": [
    ["Value1", "Value2", "Value3"]
  ]
}}

IMPORTANT:
- Extract structured information
- Each row must have exactly as many values as headers
- Use "" for empty fields
"""

    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model="anthropic/claude-sonnet-4-5",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=3000,
    )
    elapsed = time.perf_counter() - t0

    content = response.choices[0].message.content.strip()
    # Extract JSON
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(content)
        return elapsed, result
    except json.JSONDecodeError as e:
        return elapsed, f"JSON parse error: {e}"


def benchmark_minibook_roundtrip():
    """B) Minibook POST → Poll for comment → get result."""
    try:
        import requests
    except ImportError:
        return None, "requests not installed"

    minibook_url = os.getenv("MINIBOOK_URL", "http://localhost:3480").rstrip("/")

    # Step 1: Check if we have an orchestrator agent registered
    t0 = time.perf_counter()

    # Time each hop separately
    timings = {}

    # Hop 1: Create POST
    t_hop1 = time.perf_counter()
    try:
        # Get or create agent
        agents_resp = requests.get(f"{minibook_url}/api/v1/agents", timeout=5)
        agents = agents_resp.json() if agents_resp.ok else []

        agent_key = None
        for a in agents:
            if a.get("name") == "vibemind_orchestrator":
                agent_key = a.get("api_key", "")
                break

        if not agent_key:
            # Register
            reg_resp = requests.post(
                f"{minibook_url}/api/v1/agents",
                json={"name": "benchmark_agent"},
                timeout=5,
            )
            if reg_resp.ok:
                agent_key = reg_resp.json().get("api_key", "")

        # Get project
        projects_resp = requests.get(
            f"{minibook_url}/api/v1/projects",
            headers={"Authorization": f"Bearer {agent_key}"} if agent_key else {},
            timeout=5,
        )
        projects = projects_resp.json() if projects_resp.ok else []
        project_id = projects[0]["id"] if projects else None

        if not project_id:
            timings["hop1_get_project"] = time.perf_counter() - t_hop1
            return time.perf_counter() - t0, {"error": "No Minibook project found", "timings": timings}

        timings["hop1_setup"] = time.perf_counter() - t_hop1

        # Hop 2: POST the task
        t_hop2 = time.perf_counter()
        post_content = json.dumps({
            "version": "2",
            "event_type": "idea.format_table",
            "tasks": [{
                "space_key": "ideas",
                "event_type": "idea.format_table",
                "payload": {"idea_name": SAMPLE_TITLE, "target_format": "table"},
                "context": {},
                "priority": "normal",
            }],
            "original_text": f"Format '{SAMPLE_TITLE}' as table",
        }, ensure_ascii=False)

        post_resp = requests.post(
            f"{minibook_url}/api/v1/projects/{project_id}/posts",
            json={
                "content": f"```enriched\n{post_content}\n```\n\nTask: Format as table @vibemind_ideas",
                "agent_name": "benchmark_agent",
                "post_type": "task",
                "title": f"[benchmark] format_table",
            },
            headers={"Authorization": f"Bearer {agent_key}"} if agent_key else {},
            timeout=10,
        )
        timings["hop2_post"] = time.perf_counter() - t_hop2

        if not post_resp.ok:
            return time.perf_counter() - t0, {
                "error": f"POST failed: {post_resp.status_code} {post_resp.text[:200]}",
                "timings": timings,
            }

        post_id = post_resp.json().get("id", "")
        timings["post_id"] = post_id

        # Hop 3: Poll for response (simulate what DiscussionPollerWorker does)
        t_hop3 = time.perf_counter()
        max_polls = 30  # 30 * 2s = 60s max
        poll_count = 0
        result_text = None

        for i in range(max_polls):
            time.sleep(2)
            poll_count += 1

            comments_resp = requests.get(
                f"{minibook_url}/api/v1/posts/{post_id}/comments",
                headers={"Authorization": f"Bearer {agent_key}"} if agent_key else {},
                timeout=5,
            )

            if comments_resp.ok:
                comments = comments_resp.json()
                for c in comments:
                    if c.get("agent_name") in ("vibemind_ideas", "ideas"):
                        result_text = c.get("content", "")
                        break
                if result_text:
                    break

        timings["hop3_poll"] = time.perf_counter() - t_hop3
        timings["poll_count"] = poll_count

        total = time.perf_counter() - t0
        return total, {
            "result": result_text[:200] if result_text else "NO RESPONSE (timeout)",
            "timings": timings,
        }

    except Exception as e:
        return time.perf_counter() - t0, {"error": str(e)}


def main():
    print("=" * 70)
    print("FORMAT TOOL BENCHMARK: Direct LLM vs Minibook Round-Trip")
    print("=" * 70)
    print()

    # --- Benchmark A: Direct LLM ---
    print("[A] Direct LLM call (OpenRouter -> Claude Sonnet 4.5)...")
    print("    This is what format_dispatcher does today.")
    print()

    times_a = []
    for run_num in range(3):
        try:
            elapsed, result = benchmark_direct_llm()
        except Exception as e:
            print(f"    Run {run_num+1}: ERROR - {e}")
            continue
        if elapsed is None:
            print(f"    Run {run_num+1}: FAILED - {result}")
            continue
        times_a.append(elapsed)
        success = isinstance(result, dict) and "headers" in result
        print(f"    Run {run_num+1}: {elapsed:.2f}s {'OK' if success else 'PARSE_ERR'}")
        if success:
            print(f"           Headers: {result.get('headers', [])}")
            print(f"           Rows: {len(result.get('rows', []))}")

    if times_a:
        avg_a = sum(times_a) / len(times_a)
        print(f"\n    AVG: {avg_a:.2f}s  (min={min(times_a):.2f}s, max={max(times_a):.2f}s)")
    else:
        avg_a = None
        print("\n    ALL FAILED")

    print()
    print("-" * 70)
    print()

    # --- Benchmark B: Minibook Round-Trip ---
    print("[B] Minibook Round-Trip (POST → Poll → Comment)...")
    print("    This is what MinibookHub.dispatch() does.")
    print("    NOTE: Requires SpaceMinibookResponder to be running!")
    print()

    elapsed_b, result_b = benchmark_minibook_roundtrip()
    if elapsed_b is not None:
        print(f"    Total: {elapsed_b:.2f}s")
        if isinstance(result_b, dict):
            for k, v in result_b.get("timings", {}).items():
                if isinstance(v, float):
                    print(f"      {k}: {v:.3f}s")
                else:
                    print(f"      {k}: {v}")
            if result_b.get("error"):
                print(f"    ERROR: {result_b['error']}")
            if result_b.get("result"):
                print(f"    Result preview: {result_b['result'][:100]}...")
    else:
        print(f"    FAILED: {result_b}")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    if avg_a:
        print(f"  Direct LLM avg:      {avg_a:.2f}s  (pure LLM latency)")
    if elapsed_b:
        timings = result_b.get("timings", {}) if isinstance(result_b, dict) else {}
        overhead = elapsed_b - (avg_a or 0)
        print(f"  Minibook round-trip: {elapsed_b:.2f}s  (LLM + network hops + polling)")
        print(f"  Minibook overhead:   {overhead:.2f}s")
        poll_wait = timings.get("hop3_poll", 0)
        if poll_wait:
            print(f"    of which polling:  {poll_wait:.2f}s ({timings.get('poll_count', '?')} polls)")
    print()
    print("Conclusion:")
    if avg_a and elapsed_b:
        ratio = elapsed_b / avg_a if avg_a > 0 else 0
        print(f"  Minibook route is {ratio:.1f}x slower than direct LLM")
        if ratio > 2:
            print("  -> Minibook adds significant overhead (polling interval dominates)")
            print("  -> Recommendation: Direct async + optional Minibook audit post")
        else:
            print("  -> Minibook overhead is acceptable")
            print("  -> Can use Minibook as execution engine")
    elif avg_a:
        print("  Minibook route failed — direct LLM is the only working path")
    print()


if __name__ == "__main__":
    main()
