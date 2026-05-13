"""Haiku-augmented variant generator.

For each event_type, queries fungus-search for related code chunks, then
spawns Claude CLI (Haiku) to generate realistic user phrases based on the
real docstrings and voice triggers found in the codebase.

Output: augmented training_variants.yml with ~50 variants per event.

Flow per event:
  1. Build a fungus query from event_type (e.g. "bubble.delete" -> "delete
     bubble space remove voice command").
  2. Fetch top-8 code chunks — includes docstrings like
     'Voice triggers: "Lösche Bubble X", "Delete this space"'.
  3. Send to Haiku with prompt: "generate 40 natural user phrases
     (DE + EN, umlaut variants, casual/formal) that would trigger this event".
  4. Merge with existing YAML variants (dedup).

Assumes claude CLI on PATH and fungus-search MCP running locally OR
la-fungus-search Python lib importable.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[4]
VARIANTS_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "training_variants.yml"
)


HAIKU_PROMPT_TEMPLATE = """You are generating diverse user phrases that should trigger the intent "{event_type}" in a German+English voice-controlled AI assistant called VibeMind.

Based on these real code snippets from the VibeMind codebase (look for existing voice triggers and docstrings):

---
{code_context}
---

Task: Produce {count} natural user phrases that would trigger "{event_type}".

Rules:
- Mix German (ca. 60%) and English (ca. 40%)
- Include umlaut variants (Lösche + Loesche, öffne + oeffne)
- Mix casual ("mach weg") and formal ("entferne bitte")
- Vary sentence structure: imperative, question-form, statement-form
- Use placeholder "{{name}}" for objects like bubble names (not real names)
- Keep each phrase under 12 words
- No numbering, no quotes around phrases
- One phrase per line, plain text only

Output ONLY the phrases, one per line. No explanations, no markdown."""


def fungus_query_for_event(event_type: str) -> str:
    """Translate an event_type into a natural-language fungus query."""
    parts = event_type.split(".")
    domain = parts[0]
    action = ".".join(parts[1:]) if len(parts) > 1 else ""
    keyword_map = {
        "bubble": "bubble space canvas idea",
        "idea": "idea note bubble content",
        "code": "code generation file edit",
        "desktop": "desktop window automation click",
        "research": "web research scrape summarize",
        "roarboot": "knowledge graph query email",
        "schedule": "scheduled task reminder cron",
        "n8n": "n8n workflow automation",
        "agentfarm": "agent team multi-agent autogen",
        "video": "video generation vision lipsync",
        "flowzen": "wellness mood diary checkin",
        "mirofish": "forecast prediction graph",
        "minibook": "minibook collaboration",
    }
    domain_kw = keyword_map.get(domain, domain)
    return f"{action} {domain_kw} voice command user"


def _fungus_python() -> str:
    """Return python interpreter that fungus was indexed with (has faiss/sbert)."""
    import os as _os
    candidates = [
        r"C:\Users\User\.pyenv\pyenv-win\versions\3.12.0\python.exe",
        sys.executable,
    ]
    for c in candidates:
        if _os.path.exists(c):
            return c
    return sys.executable


def fungus_search(query: str, top_k: int = 8) -> list[dict]:
    """Call fungus-search via the MCPMRetriever library directly.

    Returns list of {file, score, content} dicts.
    """
    fungus_dir = ROOT / "vibemind-os" / "la-fungus-search"
    if not fungus_dir.exists():
        return []
    script = f"""
import sys, os, json, re
sys.path.insert(0, r'{fungus_dir / "src"}')
os.environ.setdefault('FUNGUS_CODEBASE', r'{ROOT / "vibemind-os"}')
try:
    from embeddinggemma.mcmp_rag import MCPMRetriever
    r = MCPMRetriever(embedding_model_name='all-MiniLM-L6-v2', num_agents=50, max_iterations=10, device_mode='auto', embed_batch_size=256)
    r.load_persistent_index()
    results = r.search_direct({query!r}, top_k={top_k})
    out = []
    for item in results.get('results', []):
        content = item.get('content', '')
        m = re.search(r'# file: (.+?) \| lines:', content)
        if m:
            f = m.group(1).replace('\\\\','/')
            body = '\\n'.join(content.split('\\n')[1:]).strip()[:600]
        else:
            f = 'unknown'
            body = content.strip()[:600]
        out.append({{'file': f, 'score': float(item.get('relevance_score', 0)), 'content': body}})
    print(json.dumps(out))
except Exception as e:
    import traceback
    print(json.dumps({{'error': str(e), 'tb': traceback.format_exc()[:500]}}))
"""
    try:
        p = subprocess.run(
            [_fungus_python(), "-c", script],
            capture_output=True, text=True, timeout=120,
            cwd=str(fungus_dir),
        )
        if p.returncode != 0:
            print(f"[fungus] rc={p.returncode} stderr={p.stderr[:400]}", file=sys.stderr)
            return []
        # Fungus prints INFO logs to stderr; stdout may have logs mixed with JSON
        stdout = p.stdout.strip()
        # Find the last JSON-looking line
        json_line = ""
        for line in reversed(stdout.splitlines()):
            s = line.strip()
            if s.startswith("[") or s.startswith("{"):
                json_line = s
                break
        if not json_line:
            print(f"[fungus] no JSON in output; stdout={stdout[:300]}", file=sys.stderr)
            return []
        data = json.loads(json_line)
        if isinstance(data, dict) and "error" in data:
            print(f"[fungus] error: {data.get('error')}", file=sys.stderr)
            return []
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[fungus] exception: {e}", file=sys.stderr)
        return []


def fungus_search_via_mcp_cli(query: str, top_k: int = 8) -> list[dict]:
    """Fallback: use claude CLI with fungus MCP as the searcher (slower).

    When la-fungus-search imports fail, we ask Claude to run the search via
    its MCP tool and return structured results.
    """
    prompt = (
        f"Call fungus_search with query={query!r} top_k={top_k} and return "
        f"the results as JSON array: [{{'file':..., 'score':..., 'content':...}}]. "
        f"Return ONLY JSON, no markdown."
    )
    try:
        p = subprocess.run(
            ["claude", "-p", "--model", "haiku", "--output-format", "json", prompt],
            capture_output=True, text=True, timeout=60,
        )
        if p.returncode != 0:
            return []
        payload = json.loads(p.stdout.strip() or "{}")
        result_text = payload.get("result", "")
        # Haiku may wrap JSON in ```json blocks — strip
        t = result_text.strip()
        if t.startswith("```"):
            t = t.split("```")[1].lstrip("json").strip()
        return json.loads(t) if t else []
    except Exception:
        return []


def _claude_cmd() -> str:
    """Locate the claude CLI (handles .cmd on Windows)."""
    import shutil
    for candidate in ("claude.cmd", "claude"):
        found = shutil.which(candidate)
        if found:
            return found
    return "claude"


def call_haiku(event_type: str, code_context: str, count: int = 40) -> list[str]:
    """Ask Haiku to produce `count` user phrases for an event."""
    prompt = HAIKU_PROMPT_TEMPLATE.format(
        event_type=event_type,
        code_context=code_context[:6000],
        count=count,
    )
    env = {k: v for k, v in __import__("os").environ.items() if k != "CLAUDECODE"}
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    try:
        p = subprocess.run(
            [_claude_cmd(), "-p", "--model", "haiku", prompt],
            capture_output=True, text=True, timeout=180,
            shell=False, env=env,
        )
        if p.returncode != 0:
            print(f"[haiku] rc={p.returncode} stderr={p.stderr[:300]}", file=sys.stderr)
            return []
        import re as _re
        raw = [l.strip() for l in p.stdout.splitlines() if l.strip()]
        cleaned: list[str] = []
        for l in raw:
            # Skip markdown headings, bullet meta-text, empty wrappers
            if l.startswith("#") or l.startswith(">") or l.startswith("```"):
                continue
            if l.startswith("**") and l.endswith("**"):
                continue
            low = l.lower()
            if any(low.startswith(p) for p in (
                "here ", "below ", "sure", "certainly", "these ", "you could ",
                "the following", "note:", "output:", "- direct ", "- formal ",
                "- with ", "- different",
            )):
                continue
            # Strip "1. ", "- ", "* "
            l = _re.sub(r"^\s*[-*\u2022]\s+", "", l)
            l = _re.sub(r"^\s*\d+[\.\)]\s+", "", l)
            # Strip surrounding quotes
            l = l.strip(' "\'`')
            # Skip blanks after cleanup
            if not l or len(l) > 120:
                continue
            # Must contain at least 2 words to be a usable phrase
            if len(l.split()) < 2:
                continue
            cleaned.append(l)
        return cleaned[:count]
    except Exception:
        return []


def augment_event(
    event_type: str, existing: dict | None, count: int = 40
) -> dict:
    """Produce augmented variant entry for one event."""
    query = fungus_query_for_event(event_type)
    chunks = fungus_search(query) or fungus_search_via_mcp_cli(query)
    code_context = "\n\n".join(
        f"# {c.get('file','')}\n{c.get('content','')[:500]}" for c in chunks[:6]
    ) or f"(no fungus results for {event_type})"

    new_variants = call_haiku(event_type, code_context, count=count)

    # Merge with existing YAML entry, dedup preserving order
    existing_variants = (existing or {}).get("variants", []) if existing else []
    seen = set()
    merged: list[str] = []
    for v in list(existing_variants) + new_variants:
        key = v.strip().lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(v.strip())

    return {
        "variants": merged,
        "placeholders": (existing or {}).get("placeholders", {
            "name": ["Marketing", "Test", "Projects", "Forschung", "Ideen"]
        }),
    }


def load_variants() -> dict[str, Any]:
    if not VARIANTS_PATH.exists():
        return {}
    with open(VARIANTS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_variants(data: dict[str, Any]) -> None:
    VARIANTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(VARIANTS_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=120)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="",
                    help="comma-separated event_types; empty = all in YAML + EVENT_SPACE_MAP")
    ap.add_argument("--count", type=int, default=40,
                    help="variants to generate per event (default 40)")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N events (0 = no limit)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    variants = load_variants()

    if args.events:
        targets = [e.strip() for e in args.events.split(",") if e.strip()]
    else:
        from tools.brain_simulator import EVENT_SPACE_MAP as esm
        targets = sorted(set(list(variants.keys()) + list(esm.keys())))

    if args.limit:
        targets = targets[: args.limit]

    print(f"Augmenting {len(targets)} events (count={args.count})")

    for i, ev in enumerate(targets, 1):
        existing = variants.get(ev)
        print(f"[{i}/{len(targets)}] {ev} ... ", end="", flush=True)
        entry = augment_event(ev, existing, count=args.count)
        n_old = len((existing or {}).get("variants") or [])
        n_new = len(entry["variants"])
        print(f"{n_old} -> {n_new} variants")
        variants[ev] = entry
        if not args.dry_run:
            save_variants(variants)

    if args.dry_run:
        print("(dry-run, nothing written)")
    else:
        print(f"\nWrote {VARIANTS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
