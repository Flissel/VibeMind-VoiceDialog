# Agent Configuration Files

This directory contains the individual configuration files for each ElevenLabs agent.

## File Structure

Each agent has two configuration files:

1. **`{agent_name}_tool.json`** - Transfer to agent tool configuration (with condition, transfer_message, delay_ms, enable_transferred_agent_first_message fields)
2. **`{agent_name}_prompt.txt`** - System prompt focusing ONLY on tool calls to other agents

## Available Agents

### 1. Conversational Memory (Rachel)
- **Agent ID:** `agent_4201k8dnc4pseff87kx5hgfkb7vy`
- **Voice:** Rachel (21m00Tcm4TlvDq8ikWAM)
- **Files:**
  - [conversational_memory_tool.json](conversational_memory_tool.json) - Tool configuration
  - [conversational_memory_prompt.txt](conversational_memory_prompt.txt) - System prompt
- **Role:** Entry point, chats with user, transfers to Project Manager for any tasks
- **Can transfer to:** Project Manager only
- **Does NOT:** Execute any tasks, write files, or control desktop

### 2. Project Manager (Alice)
- **Agent ID:** `agent_1201k8dnc6gre3sscfxygcy7jhp4`
- **Voice:** Alice (Xb7hH8MSUJpSbSDYk0k2)
- **Files:**
  - [project_manager_tool.json](project_manager_tool.json) - Tool configuration
  - [project_manager_prompt.txt](project_manager_prompt.txt) - System prompt
- **Role:** Understands tasks, delegates to specialists
- **Can transfer to:** Desktop Worker, Project Writer, Conversational Memory
- **Does NOT:** Execute tasks, only coordinates via transfers

### 3. Desktop Worker (Adam)
- **Agent ID:** `agent_4101k8dnc7v7fdk9cwkknedzkqqa`
- **Voice:** Adam (pNInz6obpgDQGcFmaJgB)
- **Files:**
  - [desktop_worker_tool.json](desktop_worker_tool.json) - Tool configuration
  - [desktop_worker_prompt.txt](desktop_worker_prompt.txt) - System prompt
- **Role:** Executes desktop automation via CLIENT TOOLS (not ElevenLabs tools)
- **Can transfer to:** Project Manager only (after completing task)
- **Uses:** Client tools for opening apps, controlling windows, file operations

### 4. Project Writer (Antoni)
- **Agent ID:** `agent_1501k8dnc90pe1r9ptna5j7vef5f`
- **Voice:** Antoni (ErXwobaYiN019PkySvjV)
- **Files:**
  - [project_writer_tool.json](project_writer_tool.json) - Tool configuration
  - [project_writer_prompt.txt](project_writer_prompt.txt) - System prompt
- **Role:** Creates code/docs via CLIENT TOOLS (not ElevenLabs tools)
- **Can transfer to:** Project Manager only (after completing task)
- **Uses:** Client tools for writing files, generating code, creating documents

## How to Use These Files

### Dashboard Setup (Manual)

For each agent:

1. **Configure Transfer Tool:**
   - Go to: https://elevenlabs.io/app/conversational-ai
   - Click on the agent
   - Navigate to: Tools → Transfer to agent → Enable
   - Copy the contents of `{agent_name}_tool.json`
   - Paste into the configuration field
   - Save

2. **Update System Prompt:**
   - In the same agent settings
   - Navigate to: Prompt/Instructions section
   - Copy the contents of `{agent_name}_prompt.txt`
   - Paste into the prompt field (replace existing)
   - Save

3. **Configure Client Tools (Desktop Worker & Project Writer only):**
   - These agents use CLIENT TOOLS configured in ElevenLabs dashboard
   - Go to: Tools → Client Tools → Add Client Tool
   - Copy JSON from `{agent_name}_client_tool.json` files:
     - `desktop_worker_client_tool.json` - For Desktop Worker agent
     - `project_writer_client_tool.json` - For Project Writer agent
     - `url_knowledge_tool.json` - For URL knowledge ingestion (any agent)
   - Paste JSON into the tool configuration
   - Save each tool
   - **Implementation**: Tools are defined in `python/tools/hello_world_tools.py`
   - See: [CLIENT_TOOLS_SETUP.md](CLIENT_TOOLS_SETUP.md) for detailed instructions

## Transfer Flow

```
User speaks
    ↓
Conversational Memory (Rachel) - Greets, chats, transfers
    ↓ [transfer_to_agent]
Project Manager (Alice) - Understands task, delegates
    ↓                          ↓                        ↓
[Desktop tasks]         [Writing tasks]         [Chat/Done]
    ↓                          ↓                        ↓
Desktop Worker          Project Writer      Conversational Memory
(Adam)                  (Antoni)            (Rachel)
Uses client tools       Uses client tools
    ↓                          ↓
[transfer back]         [transfer back]
    ↓                          ↓
Project Manager (Alice) - Coordinates next step
```

## Important Notes

### Agents DO NOT Execute Tasks Directly

- **Conversational Memory:** Only chats and transfers (no task execution)
- **Project Manager:** Only coordinates and transfers (no task execution)
- **Desktop Worker:** Uses CLIENT TOOLS (configured outside ElevenLabs) for desktop automation
- **Project Writer:** Uses CLIENT TOOLS (configured outside ElevenLabs) for file/code creation

### ElevenLabs Tools vs Client Tools

- **ElevenLabs Tools:** ONLY "transfer_to_agent" (configured in dashboard, in these JSON files)
- **Client Tools:** Separate tools for desktop/writing operations (configured via client SDK, NOT in these files)

## Tool Configuration Structure

Each `*_tool.json` file includes:

```json
{
  "type": "system",
  "name": "transfer_to_agent",
  "description": "When to use this transfer",
  "params": {
    "system_tool_type": "transfer_to_agent",
    "transfers": [
      {
        "agent_id": "target_agent_id",
        "condition": "When to transfer to this agent",
        "transfer_message": "What to say when transferring",
        "delay_ms": 0,
        "enable_transferred_agent_first_message": true
      }
    ],
    "voicemail_message": ""
  },
  "disable_interruptions": false
}
```

## File Naming Convention

- Tool configs: `{agent_name}_tool.json`
- System prompts: `{agent_name}_prompt.txt`
- Agent names use snake_case: `conversational_memory`, `project_manager`, `desktop_worker`, `project_writer`

## Validation

To verify your configurations:

1. **Check Agent IDs:**
   - Ensure IDs in `*_tool.json` files match `.env` file
   - Run: `python python/test_system.py`

2. **Check JSON Syntax:**
   - Validate JSON structure
   - Ensure all required fields present: `agent_id`, `condition`, `transfer_message`, `delay_ms`, `enable_transferred_agent_first_message`

3. **Test Transfers:**
   - Start with Conversational Memory agent
   - Say "Open Chrome" - should transfer to PM → Desktop Worker
   - Say "Write a script" - should transfer to PM → Project Writer
   - Verify voice changes (Rachel → Alice → Adam/Antoni)

## Related Documentation

- [MULTI_AGENT_SETUP.md](../../MULTI_AGENT_SETUP.md) - Client tool configuration for Desktop Worker & Project Writer
- [IMPLEMENTATION_STATUS.md](../../IMPLEMENTATION_STATUS.md) - Current system status
- [.env](.env) - Agent IDs configuration
