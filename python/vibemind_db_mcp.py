"""VibeMind DB MCP Server — Supabase-backed database access via MCP.

Connects to local Supabase (PostgreSQL + PostgREST) for all CRUD operations.
Reusable by OpenClaw, Claude Code, or any MCP client.

Tables: ideas, projects, persistent_tasks, scheduled_tasks, conversations,
flowzen_activity, canvas_nodes, video_projects.

Usage (stdio):
    python vibemind_db_mcp.py

Environment:
    SUPABASE_URL     (default: http://localhost:54321)
    SUPABASE_ANON_KEY (default: local dev key)
"""
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any

SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://localhost:54321")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
)


def _api(method: str, path: str, body: Any = None, params: str = "") -> dict:
    """Call the Supabase REST API (PostgREST)."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    data = json.dumps(body, default=str, ensure_ascii=False).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {"ok": True}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:300]
        return {"error": f"HTTP {e.code}: {err}"}
    except Exception as e:
        return {"error": str(e)}


# ── MCP Tools ───────────────────────────────────────────────────────

TOOLS = [
    # === Ideas / Bubbles ===
    {"name": "db_ideas_list", "description": "List ideas/bubbles. filter: text search, status: raw/scored/promoted/archived, limit, order.",
     "inputSchema": {"type": "object", "properties": {
         "filter": {"type": "string"}, "status": {"type": "string"},
         "limit": {"type": "integer", "default": 20}, "order": {"type": "string", "default": "created_at.desc"}}}},
    {"name": "db_ideas_get", "description": "Get idea by ID or title.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "title": {"type": "string"}}}},
    {"name": "db_ideas_create", "description": "Create a new idea/bubble.",
     "inputSchema": {"type": "object", "properties": {
         "title": {"type": "string"}, "description": {"type": "string", "default": ""},
         "source": {"type": "string", "default": "mcp"}, "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["title"]}},
    {"name": "db_ideas_update", "description": "Update idea by ID.",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"},
         "status": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["id"]}},
    {"name": "db_ideas_delete", "description": "Delete idea by ID.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},

    # === Projects ===
    {"name": "db_projects_list", "description": "List projects.",
     "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}}},
    {"name": "db_projects_get", "description": "Get project by ID or name.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}}}},

    # === Tasks ===
    {"name": "db_tasks_list", "description": "List persistent tasks. Optional status filter.",
     "inputSchema": {"type": "object", "properties": {
         "status": {"type": "string"}, "limit": {"type": "integer", "default": 20}}}},

    # === Schedule ===
    {"name": "db_schedule_list", "description": "List scheduled tasks.",
     "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}}},

    # === Conversations ===
    {"name": "db_conversations_list", "description": "List recent conversation sessions.",
     "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}}},
    {"name": "db_conversations_messages", "description": "Get messages for a session.",
     "inputSchema": {"type": "object", "properties": {
         "session_id": {"type": "string"}, "limit": {"type": "integer", "default": 50}},
         "required": ["session_id"]}},

    # === Flowzen ===
    {"name": "db_flowzen_activity", "description": "List Flowzen activity entries.",
     "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}}},

    # === Canvas ===
    {"name": "db_canvas_nodes", "description": "List canvas nodes.",
     "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 50}}}},

    # === Raw query (read-only via PostgREST RPC) ===
    {"name": "db_query", "description": "Query any table with PostgREST filters. Example: table=ideas, select=id,title, filters=status=eq.raw",
     "inputSchema": {"type": "object", "properties": {
         "table": {"type": "string"}, "select": {"type": "string", "default": "*"},
         "filters": {"type": "string", "description": "PostgREST filter, e.g. status=eq.raw&score=gt.50"},
         "order": {"type": "string", "default": ""}, "limit": {"type": "integer", "default": 20}},
         "required": ["table"]}},

    # === Schema ===
    {"name": "db_schema", "description": "Show all tables in the VibeMind Supabase database.",
     "inputSchema": {"type": "object", "properties": {}}},
]


def handle_tool(name: str, args: dict) -> str:
    try:
        # === Ideas ===
        if name == "db_ideas_list":
            params = f"select=*&order={args.get('order', 'created_at.desc')}&limit={args.get('limit', 20)}"
            if args.get("filter"):
                params += f"&or=(title.ilike.%25{args['filter']}%25,description.ilike.%25{args['filter']}%25)"
            if args.get("status"):
                params += f"&status=eq.{args['status']}"
            data = _api("GET", "ideas", params=params)
            return json.dumps({"count": len(data) if isinstance(data, list) else 0, "ideas": data}, default=str, ensure_ascii=False)

        elif name == "db_ideas_get":
            if args.get("id"):
                data = _api("GET", "ideas", params=f"id=eq.{args['id']}")
            elif args.get("title"):
                data = _api("GET", "ideas", params=f"title=ilike.%25{args['title']}%25")
            else:
                return "Provide id or title"
            return json.dumps(data[0] if isinstance(data, list) and data else data, default=str, ensure_ascii=False)

        elif name == "db_ideas_create":
            body = {"title": args["title"], "description": args.get("description", ""),
                    "source": args.get("source", "mcp"), "tags": args.get("tags", [])}
            data = _api("POST", "ideas", body=[body])
            return json.dumps({"created": data}, default=str, ensure_ascii=False)

        elif name == "db_ideas_update":
            update = {k: v for k, v in args.items() if k != "id" and v is not None}
            data = _api("PATCH", "ideas", body=update, params=f"id=eq.{args['id']}")
            return json.dumps({"updated": data}, default=str, ensure_ascii=False)

        elif name == "db_ideas_delete":
            data = _api("DELETE", "ideas", params=f"id=eq.{args['id']}")
            return json.dumps({"deleted": args["id"]}, default=str, ensure_ascii=False)

        # === Projects ===
        elif name == "db_projects_list":
            data = _api("GET", "projects", params=f"select=*&limit={args.get('limit', 20)}&order=created_at.desc")
            return json.dumps({"count": len(data) if isinstance(data, list) else 0, "projects": data}, default=str, ensure_ascii=False)

        elif name == "db_projects_get":
            if args.get("id"):
                data = _api("GET", "projects", params=f"id=eq.{args['id']}")
            elif args.get("name"):
                data = _api("GET", "projects", params=f"name=ilike.%25{args['name']}%25")
            else:
                return "Provide id or name"
            return json.dumps(data[0] if isinstance(data, list) and data else data, default=str, ensure_ascii=False)

        # === Tasks ===
        elif name == "db_tasks_list":
            params = f"select=*&limit={args.get('limit', 20)}&order=created_at.desc"
            if args.get("status"):
                params += f"&status=eq.{args['status']}"
            data = _api("GET", "persistent_tasks", params=params)
            return json.dumps({"count": len(data) if isinstance(data, list) else 0, "tasks": data}, default=str, ensure_ascii=False)

        # === Schedule ===
        elif name == "db_schedule_list":
            data = _api("GET", "scheduled_tasks", params=f"select=*&limit={args.get('limit', 20)}")
            return json.dumps({"count": len(data) if isinstance(data, list) else 0, "scheduled": data}, default=str, ensure_ascii=False)

        # === Conversations ===
        elif name == "db_conversations_list":
            data = _api("GET", "conversation_sessions", params=f"select=*&limit={args.get('limit', 10)}&order=created_at.desc")
            return json.dumps({"count": len(data) if isinstance(data, list) else 0, "sessions": data}, default=str, ensure_ascii=False)

        elif name == "db_conversations_messages":
            data = _api("GET", "conversation_history",
                        params=f"session_id=eq.{args['session_id']}&select=*&limit={args.get('limit', 50)}&order=timestamp.asc")
            return json.dumps({"count": len(data) if isinstance(data, list) else 0, "messages": data}, default=str, ensure_ascii=False)

        # === Flowzen ===
        elif name == "db_flowzen_activity":
            data = _api("GET", "flowzen_activity", params=f"select=*&limit={args.get('limit', 20)}&order=timestamp.desc")
            return json.dumps({"count": len(data) if isinstance(data, list) else 0, "activity": data}, default=str, ensure_ascii=False)

        # === Canvas ===
        elif name == "db_canvas_nodes":
            data = _api("GET", "canvas_nodes", params=f"select=*&limit={args.get('limit', 50)}")
            return json.dumps({"count": len(data) if isinstance(data, list) else 0, "nodes": data}, default=str, ensure_ascii=False)

        # === Raw query ===
        elif name == "db_query":
            params = f"select={args.get('select', '*')}&limit={args.get('limit', 20)}"
            if args.get("filters"):
                params += f"&{args['filters']}"
            if args.get("order"):
                params += f"&order={args['order']}"
            data = _api("GET", args["table"], params=params)
            return json.dumps({"count": len(data) if isinstance(data, list) else 0, "rows": data}, default=str, ensure_ascii=False)

        # === Schema ===
        elif name == "db_schema":
            tables = ["ideas", "projects", "persistent_tasks", "scheduled_tasks",
                       "conversation_sessions", "conversation_history", "flowzen_activity",
                       "flowzen_checkins", "flowzen_diary", "canvas_nodes", "canvas_edges",
                       "video_projects", "videos", "user_preferences"]
            schema = {}
            for t in tables:
                data = _api("GET", t, params="select=*&limit=0")
                count_data = _api("GET", t, params="select=count")
                count = count_data[0].get("count", "?") if isinstance(count_data, list) and count_data else "?"
                schema[t] = {"row_count": count}
            return json.dumps(schema, default=str, ensure_ascii=False)

        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error: {e}"


# ── MCP stdio server ───────────────────────────────────────────────

def main():
    def send(obj):
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        sys.stdout.buffer.write(line.encode("utf-8"))
        sys.stdout.buffer.flush()

    while True:
        try:
            raw = sys.stdin.buffer.readline()
            if not raw:
                break
            req = json.loads(raw.decode("utf-8").strip())
        except Exception:
            break

        method = req.get("method", "")
        req_id = req.get("id")
        params = req.get("params", {})

        if method == "initialize":
            send({"jsonrpc": "2.0", "id": req_id, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "vibemind-db-supabase", "version": "2.0.0"}
            }})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            result_text = handle_tool(params.get("name", ""), params.get("arguments", {}))
            send({"jsonrpc": "2.0", "id": req_id, "result": {
                "content": [{"type": "text", "text": result_text}]
            }})
        elif method == "notifications/initialized":
            pass
        else:
            if req_id is not None:
                send({"jsonrpc": "2.0", "id": req_id, "error": {
                    "code": -32601, "message": f"Method not found: {method}"
                }})


if __name__ == "__main__":
    main()
