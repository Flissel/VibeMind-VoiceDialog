# Client Tools Setup Guide

This guide explains how to configure **Client Tools** for your ElevenLabs conversational agents. Client tools allow agents to execute Python functions during conversations.

## What are Client Tools?

**Client Tools** are Python functions that ElevenLabs agents can call during voice conversations. Unlike transfer tools (which move between agents), client tools execute actual tasks like:

- Writing files
- Fetching web content
- Running desktop automation
- Generating code
- Processing data

## Tool Types in This Project

### 1. Transfer Tools (System Tools)
- **Purpose**: Move conversation between agents
- **Configuration**: `*_tool.json` files (e.g., `project_manager_tool.json`)
- **Location**: Dashboard → Tools → Transfer to agent
- **Already configured** in the previous setup step

### 2. Client Tools (Execution Tools)
- **Purpose**: Execute Python functions during conversation
- **Configuration**: `*_client_tool.json` files
- **Location**: Dashboard → Tools → Client Tools
- **This is what we're setting up now**

## Available Client Tools

### Desktop Worker Client Tool
**File:** [desktop_worker_client_tool.json](desktop_worker_client_tool.json)
**Function:** `write_hello_desktop()` in [python/tools/hello_world_tools.py](../../python/tools/hello_world_tools.py)
**Purpose:** Test tool that writes "Hello world from Desktop Worker" to a file
**Use case:** Verify Desktop Worker agent can execute tasks

### Project Writer Client Tool
**File:** [project_writer_client_tool.json](project_writer_client_tool.json)
**Function:** `write_hello_writer()` in [python/tools/hello_world_tools.py](../../python/tools/hello_world_tools.py)
**Purpose:** Test tool that writes "Hello world from Project Writer" to a file
**Use case:** Verify Project Writer agent can execute tasks

### URL Knowledge Tool
**File:** [url_knowledge_tool.json](url_knowledge_tool.json)
**Function:** To be implemented in [python/tools/url_knowledge_tools.py](../../python/tools/url_knowledge_tools.py)
**Purpose:** Fetch and process knowledge from web URLs
**Use case:** Allow agents to learn from documentation, articles, or any web content

## Step-by-Step Setup

### Step 1: Configure Desktop Worker Client Tools

1. Go to https://elevenlabs.io/app/conversational-ai
2. Click on **Desktop Worker (Adam)** agent
3. Navigate to: **Tools** → **Client Tools** → **Add Client Tool**
4. Open [desktop_worker_client_tool.json](desktop_worker_client_tool.json)
5. Copy the entire JSON content
6. Paste into the ElevenLabs tool configuration field
7. Click **Save**

**Expected JSON:**
```json
{
  "type": "client",
  "name": "write_hello_desktop",
  "description": "Test tool that writes 'Hello world from Desktop Worker' to a timestamped file...",
  "expects_response": true,
  "response_timeout_secs": 5,
  "parameters": [],
  ...
}
```

### Step 2: Configure Project Writer Client Tools

1. Still in https://elevenlabs.io/app/conversational-ai
2. Click on **Project Writer (Antoni)** agent
3. Navigate to: **Tools** → **Client Tools** → **Add Client Tool**
4. Open [project_writer_client_tool.json](project_writer_client_tool.json)
5. Copy the entire JSON content
6. Paste into the ElevenLabs tool configuration field
7. Click **Save**

### Step 3: (Optional) Add URL Knowledge Tool

This tool can be added to **any agent** that needs web knowledge retrieval:

1. Choose an agent (e.g., Desktop Worker or Project Manager)
2. Navigate to: **Tools** → **Client Tools** → **Add Client Tool**
3. Open [url_knowledge_tool.json](url_knowledge_tool.json)
4. Copy the entire JSON content
5. Paste into the ElevenLabs tool configuration field
6. Click **Save**

**Note:** The Python implementation for this tool needs to be created. See "Implementation Checklist" below.

## Client Tool Implementation

### Existing Implementation: Hello World Tools

**File:** [python/tools/hello_world_tools.py](../../python/tools/hello_world_tools.py)

The hello world tools are already implemented:

```python
def write_hello_desktop() -> str:
    """Writes 'Hello world from Desktop Worker Agent' to a file"""
    # Creates: hello_desktop_YYYYMMDD_HHMMSS.txt
    # Returns: Success message with file path

def write_hello_writer() -> str:
    """Writes 'Hello world from Project Writer Agent' to a file"""
    # Creates: hello_writer_YYYYMMDD_HHMMSS.txt
    # Returns: Success message with file path
```

### To Implement: URL Knowledge Tool

**File to create:** `python/tools/url_knowledge_tools.py`

**Required function:**
```python
def add_url_knowledge(url: str, summary_length: str = "medium") -> str:
    """
    Fetch and process knowledge from a web URL.

    Args:
        url: The full HTTP/HTTPS URL to fetch
        summary_length: 'brief', 'medium', or 'detailed'

    Returns:
        str: Summary of the fetched content
    """
    # TODO: Implement URL fetching
    # TODO: Extract text content
    # TODO: Summarize based on summary_length
    # TODO: Store in knowledge base (optional)
    pass
```

**Suggested libraries:**
- `requests` or `httpx` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `markdownify` - Convert HTML to markdown
- `tiktoken` - Token counting for summaries

## Connecting Python Functions to ElevenLabs

### How Client Tools Work

1. **User speaks**: "Write hello world"
2. **Agent decides**: Desktop Worker recognizes this matches `write_hello_desktop` tool
3. **ElevenLabs calls**: ElevenLabs SDK invokes your Python function via client tools
4. **Function executes**: `write_hello_desktop()` runs and returns result
5. **Agent responds**: Desktop Worker speaks the result: "Hello world file created"

### Registering Functions with ElevenLabs SDK

The ElevenLabs Python SDK automatically discovers functions based on the client tool JSON configuration. Ensure:

1. **Function name matches** the `"name"` field in JSON
2. **Function is importable** from your Python environment
3. **Function parameters match** the `"parameters"` array in JSON
4. **Function returns string** (the result spoken by the agent)

### Tool Discovery by ElevenLabs

When you start a conversation with an agent:

```python
from elevenlabs.conversational_ai.conversation import Conversation

conversation = Conversation(
    agent_id="agent_4101k8dnc7v7fdk9cwkknedzkqqa",  # Desktop Worker
    requires_auth=False,
    # Client tools are automatically discovered from:
    # 1. The agent's dashboard configuration
    # 2. Your local Python environment
)
```

ElevenLabs will:
1. Read the agent's client tool configurations from the dashboard
2. Look for matching Python functions in your environment
3. Call those functions when the agent decides to use them

## Testing Your Setup

### Test 1: Desktop Worker Hello World

1. Start voice conversation with **Conversational Memory** agent (Rachel)
2. Say: **"Write hello world"**
3. Expected flow:
   - Rachel transfers to Project Manager
   - Project Manager transfers to Desktop Worker
   - Desktop Worker calls `write_hello_desktop()` client tool
   - File created: `hello_desktop_YYYYMMDD_HHMMSS.txt`
   - Desktop Worker says: "Success! Desktop Worker wrote file: ..."
   - Desktop Worker transfers back to Project Manager

4. Verify file exists in your working directory

### Test 2: Project Writer Hello World

1. Continue conversation or start new one
2. Say: **"Create a hello document"**
3. Expected flow:
   - Transfers to Project Manager
   - Project Manager transfers to Project Writer
   - Project Writer calls `write_hello_writer()` client tool
   - File created: `hello_writer_YYYYMMDD_HHMMSS.txt`
   - Project Writer says: "Success! Project Writer wrote file: ..."
   - Project Writer transfers back to Project Manager

4. Verify file exists in your working directory

### Test 3: URL Knowledge (when implemented)

1. Say: **"Learn from this URL: https://microsoft.github.io/autogen"**
2. Expected flow:
   - Agent calls `add_url_knowledge(url="https://...")` client tool
   - Tool fetches and processes URL
   - Agent says: "I've learned about AutoGen from that URL"

3. Ask follow-up: **"What did you learn?"**
4. Agent should reference the fetched content

## Troubleshooting

### Problem: Agent doesn't call the tool

**Symptoms:**
- Agent says it doesn't know how to do the task
- Agent doesn't mention the tool at all

**Solutions:**
1. Verify tool JSON is saved in dashboard (Tools → Client Tools)
2. Check `"name"` field matches Python function name exactly
3. Ensure tool `"description"` clearly explains when to use it
4. Check agent's system prompt mentions using client tools

### Problem: Tool call fails with error

**Symptoms:**
- Agent says "Error executing tool"
- Function raises an exception

**Solutions:**
1. Check Python function is importable: `from tools.hello_world_tools import write_hello_desktop`
2. Test function manually: `print(write_hello_desktop())`
3. Check function parameters match JSON `"parameters"` array
4. Review ElevenLabs conversation logs in dashboard

### Problem: Function runs but agent doesn't hear response

**Symptoms:**
- File is created successfully
- Agent says "No response received"

**Solutions:**
1. Ensure function returns a string (not None)
2. Check `"expects_response": true` in JSON
3. Verify `"response_timeout_secs"` is sufficient (5-30 seconds)
4. Function should complete within timeout period

### Problem: Wrong agent calls the tool

**Symptoms:**
- Desktop Worker tool called by Project Writer (or vice versa)

**Solutions:**
1. Each agent should only have its own client tools configured
2. Don't add `write_hello_desktop` to Project Writer agent
3. Don't add `write_hello_writer` to Desktop Worker agent
4. URL knowledge tool can be added to multiple agents if desired

## Next Steps: Real Tools

Once hello world tests are working, you can create real client tools:

### For Desktop Worker:
- `open_application(app_name: str)` - Open applications
- `close_application(app_name: str)` - Close applications
- `find_window(title: str)` - Find and focus windows
- `click_element(description: str)` - Click UI elements
- `type_text(text: str)` - Type into active window

### For Project Writer:
- `create_file(path: str, content: str)` - Create new file
- `edit_file(path: str, changes: str)` - Modify existing file
- `write_code(language: str, description: str)` - Generate code
- `create_documentation(type: str, content: str)` - Write docs

### For Knowledge/Research:
- `add_url_knowledge(url: str)` - Fetch web content
- `search_web(query: str)` - Web search
- `query_database(query: str)` - Database queries
- `semantic_search(query: str)` - Vector search

## Advanced: AutoGen gRPC Integration

For complex tools that need:
- Heavy computation
- Long-running processes
- Distributed execution
- Advanced agent reasoning

Consider integrating **AutoGen gRPC Workers** (Phase 2 of the implementation plan).

See: [AUTOGEN_GRPC_SETUP.md](AUTOGEN_GRPC_SETUP.md) (to be created)

## File Reference

### Configuration Files (JSON)
- `desktop_worker_client_tool.json` - Desktop Worker hello world tool config
- `project_writer_client_tool.json` - Project Writer hello world tool config
- `url_knowledge_tool.json` - URL knowledge ingestion tool config

### Implementation Files (Python)
- `python/tools/hello_world_tools.py` - Hello world test functions
- `python/tools/url_knowledge_tools.py` - URL knowledge functions (to be created)
- `python/tools/desktop_tools.py` - Desktop automation functions (future)
- `python/tools/writer_tools.py` - File/code writing functions (future)

### Documentation
- This file: `CLIENT_TOOLS_SETUP.md` - Complete setup guide
- `README.md` - Agent configuration overview
- `../../MULTI_AGENT_SETUP.md` - Overall system architecture

## Summary

**What you've done:**
1. ✅ Created 4 ElevenLabs agents with distinct voices
2. ✅ Configured transfer tools for agent coordination
3. ✅ Written system prompts for each agent's behavior
4. ✅ Created client tool JSON configurations
5. ✅ Implemented hello world test functions

**What's working now:**
- Voice conversation with Conversational Memory entry point
- Agent-to-agent transfers via transfer tools
- Simple task execution via client tools (hello world)

**What's next:**
1. Test hello world tools in live conversation
2. Implement real client tools for desktop automation
3. Implement URL knowledge ingestion
4. (Optional) Integrate AutoGen gRPC for advanced capabilities

**Test command:**
```bash
cd python
python voice_dialog_main.py
# Say: "Write hello world"
# Verify file creation
```

Good luck with your multi-agent voice system! 🎉
