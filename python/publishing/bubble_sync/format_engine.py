"""LLM canvas formatter — regenerate a node's rich content_json from edited prose.

This is the engine the canvas reformat drainer (worker_canvas_reformat.py) calls
when a STRUCTURED canvas node's plain-text body was edited via the Rowboat
Knowledge tab. It takes the edited `content` + a target format type and asks an
LLM to produce a content_json object that VALIDATES against the format's JSON
schema (data/format_schemas.py).

Why schema-driven (not 12 hand-written prompt templates): every format already
has a precise JSON Schema in format_schemas.FORMAT_SCHEMAS. We hand that schema
to the LLM as the output contract and validate the response against it — one
generic path covers all 12+ formats and stays correct when a schema changes.

Provider-agnostic: uses vibemind_shared.get_client_sync(role) which returns
either an OpenAI-compatible or an Anthropic client (resolved from llm_config.yml
by role). We branch on which SDK shape we got. Sync by design — the drainer runs
it on its own thread, never inside an async loop.

NO DB writes here, NO Electron/NotificationQueue side-effects — the caller does
the GUC-fenced raw-psql write. This function only computes (content, fmt) ->
(content_json, format_schema).
"""
from __future__ import annotations

import json
import re
from typing import Any

# Role used for the format-generation LLM call. Resolved from llm_config.yml;
# falls back to the client factory's own default if the role is undefined.
FORMAT_ROLE = "format_generation"

# Cap the prose we send (mirrors the old flatten's max_chars budget) so a runaway
# node body can't blow the context / cost.
MAX_SOURCE_CHARS = 8000
MAX_OUTPUT_TOKENS = 3000


class FormatError(Exception):
    """Raised when the LLM output cannot be coerced into valid content_json."""


def _system_prompt(format_type: str, schema: dict) -> str:
    return (
        "You convert a plain-text note into a single structured JSON object.\n"
        f"The object MUST be valid against this JSON Schema for format "
        f"'{format_type}':\n\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "Rules:\n"
        f"- Output ONLY the JSON object, no prose, no markdown fences.\n"
        f"- Set \"type\" to exactly \"{format_type}\".\n"
        "- Preserve the source language (do not translate).\n"
        "- Use ONLY information present in the note; do not invent facts. If a "
        "required array would be empty, include the fields you can support and "
        "leave others as empty strings/arrays.\n"
        "- Keep enum fields within their allowed values."
    )


def _user_prompt(title: str, content: str) -> str:
    src = (content or "")[:MAX_SOURCE_CHARS]
    head = f"Title: {title}\n\n" if title else ""
    return f"{head}Note content to structure:\n\n{src}"


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response (tolerates ```json
    fences or leading prose)."""
    if not text:
        raise FormatError("empty LLM response")
    t = text.strip()
    # strip a leading ```json / ``` fence if present
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.DOTALL)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    # fall back: first {...} balanced-ish span
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(t[start:end + 1])
        except json.JSONDecodeError as e:
            raise FormatError(f"could not parse JSON from response: {e}")
    raise FormatError("no JSON object in response")


def _call_llm(system: str, user: str, role: str) -> str:
    """One sync LLM call via the shared client factory. Branches on whether the
    factory returned an Anthropic or an OpenAI-compatible client."""
    import os
    import sys
    from pathlib import Path
    # vibemind_shared lives under shared/src — ensure importable.
    # parents[4] is the vibemind-os root (…/vibemind-os/voice/python/publishing/
    # bubble_sync/format_engine.py → parents[4] = vibemind-os).
    vibemind_os = Path(__file__).resolve().parents[4]
    shared_src = vibemind_os / "shared" / "src"
    if shared_src.is_dir() and str(shared_src) not in sys.path:
        sys.path.insert(0, str(shared_src))
    # vibemind_shared._find_config() does NOT use a directory arg — it looks at
    # $VIBEMIND_CONFIG_DIR, CWD, then next to llm_client.py. The real config lives
    # at brain/the_brain/llm_config.yml (with the format_generation role we added).
    # Point the resolver at it unless the caller already set VIBEMIND_CONFIG_DIR.
    if not os.environ.get("VIBEMIND_CONFIG_DIR"):
        brain_cfg = vibemind_os / "brain" / "the_brain"
        if (brain_cfg / "llm_config.yml").is_file():
            os.environ["VIBEMIND_CONFIG_DIR"] = str(brain_cfg)
    from vibemind_shared.llm_client import get_client_sync, get_model, get_temperature

    client = get_client_sync(role)
    model = get_model(role)
    temp = get_temperature(role)

    # Anthropic client (messages API) vs OpenAI-compatible (chat.completions)
    if client.__class__.__module__.startswith("anthropic"):
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=temp,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # concat text blocks
        return "".join(getattr(b, "text", "") for b in resp.content)
    # OpenAI-compatible
    resp = client.chat.completions.create(
        model=model,
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=temp,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


def _validate(obj: dict, format_type: str, schema: dict) -> tuple[bool, str]:
    """Minimal structural validation against the format schema. Prefers the
    jsonschema lib if available; else falls back to a required-key check. We are
    lenient (the LLM is trusted-ish) but reject obvious shape failures so we
    never persist garbage as content_json."""
    if not isinstance(obj, dict):
        return False, "not a JSON object"
    # type tag must match (we set it in the prompt; enforce it)
    if obj.get("type") not in (format_type, schema.get("properties", {})
                               .get("type", {}).get("const", format_type)):
        # tolerate aliases by coercing the tag
        obj["type"] = format_type
    try:
        import jsonschema  # type: ignore
        jsonschema.validate(obj, schema)
        return True, ""
    except ImportError:
        # fallback: required top-level keys present
        for k in schema.get("required", []):
            if k not in obj:
                return False, f"missing required key: {k}"
        return True, ""
    except Exception as e:  # jsonschema.ValidationError
        return False, str(e)[:300]


def generate_format_content(
    content: str,
    format_type: str,
    title: str = "",
    *,
    role: str = FORMAT_ROLE,
) -> tuple[dict, dict]:
    """Regenerate rich content_json from edited prose.

    Returns (content_json, format_schema). Raises FormatError if the LLM output
    cannot be validated even after the note-format fallback. The caller persists
    the result GUC-fenced via raw psql.

    On an unsupported/invalid format_type, falls back to 'note' (the always-valid
    minimal wrapper) rather than raising — a canvas node should never be left
    unformattable.
    """
    from data.format_schemas import (
        FORMAT_SCHEMAS, get_format_schema, validate_format_type, DEFAULT_FORMAT,
    )

    if not validate_format_type(format_type):
        format_type = DEFAULT_FORMAT
    schema = get_format_schema(format_type)

    # note is the trivial wrapper — no LLM needed, always valid.
    if format_type in ("note", DEFAULT_FORMAT) and format_type == "note":
        cj = {"type": "note", "title": title or "", "text": content or ""}
        return cj, {"type": "note"}

    system = _system_prompt(format_type, schema)
    user = _user_prompt(title, content)
    raw = _call_llm(system, user, role)
    obj = _extract_json(raw)

    ok, err = _validate(obj, format_type, schema)
    if not ok:
        # one repair attempt: tell the model what failed
        repair = (
            f"Your previous output failed schema validation: {err}\n"
            "Return a corrected JSON object that validates. Output ONLY JSON."
        )
        raw2 = _call_llm(system, user + "\n\n" + repair, role)
        obj = _extract_json(raw2)
        ok, err = _validate(obj, format_type, schema)

    if not ok:
        # final fallback: a valid 'note' so we never persist invalid structure
        note_cj = {"type": "note", "title": title or "", "text": content or ""}
        return note_cj, {"type": "note"}

    obj.setdefault("type", format_type)
    if title and not obj.get("title"):
        obj["title"] = title
    return obj, {"type": format_type}
