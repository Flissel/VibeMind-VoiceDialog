# Multi-Agent Voice System Setup Guide

This guide will help you set up the voice-controlled desktop automation system with multiple specialized agents.

## 🎯 Overview

The system consists of 4 specialized AI agents, each with a unique voice, that work together:

1. **Rachel - Multiverse Navigator** (Entry Agent)
   - Entry point for all voice interactions
   - Manages spaces, bubbles, and ideas
   - Routes requests to appropriate specialists
   - Voice: Rachel (warm, friendly)

2. **Alice - Coordinator Hub** (Orchestrator)
   - Coordinates and delegates tasks
   - Routes to Desktop Worker or Coding Worker
   - Maintains project context
   - Voice: Alice (professional, organized)

3. **Adam - Desktop Worker** (System Automation)
   - Controls desktop applications
   - Opens windows, clicks buttons, types text
   - Executes system commands
   - Voice: Adam (efficient, direct)

4. **Antoni - Coding Worker** (Code Generation)
   - Writes code and documentation
   - Creates projects and files
   - Follows coding patterns
   - Voice: Antoni (creative, expressive)

## 📋 Prerequisites

- Python 3.8+
- ElevenLabs API account
- Supermemory API account
- OpenAI or OpenRouter API key

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
uv venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the template and fill in your API keys:

```bash
cp .env.template .env
```

Edit `.env` and add:
- `ELEVENLABS_API_KEY` - From [ElevenLabs API Keys](https://elevenlabs.io/app/settings/api-keys)
- `SUPERMEMORY_API_KEY` - From [Supermemory](https://supermemory.ai/)
- `OPENAI_API_KEY` - From [OpenAI](https://platform.openai.com/api-keys)

### 3. Create ElevenLabs Agents

You need to create 4 agents in the ElevenLabs dashboard manually.

#### Agent 1: Rachel - Multiverse Navigator

Go to https://elevenlabs.io/app/conversational-ai and create a new agent:

- **Name:** Rachel - Multiverse Navigator
- **Voice:** Rachel (21m00Tcm4TlvDq8ikWAM)
- **First Message:**
  ```
  Hello! I'm Rachel, your multiverse navigator. I help you explore spaces, manage bubbles, and capture ideas. What would you like to work on?
  ```
- **System Prompt:**
  ```
  You are Rachel, the Multiverse Navigator. Your role is to:
  1. Help users navigate spaces and bubbles in the multiverse
  2. Capture and organize ideas within bubbles
  3. Route users to Alice (Coordinator) for complex tasks
  4. Maintain a warm, friendly, and helpful personality

  When the user needs help with:
  - Complex projects or coordination: Use transfer_to_alice tool
  - Desktop automation or coding: Route through Alice first

  Always be brief and friendly. You are the entry point for voice interactions.
  ```
- **LLM:** GPT-4o-mini
- **Client Tools:** Add the transfer tool (see below)

Copy the Agent ID and add to `.env` as `RACHEL_AGENT_ID` or `AGENT_MULTIVERSE`

#### Agent 2: Alice - Coordinator Hub

- **Name:** Alice - Coordinator Hub
- **Voice:** Alice (Xb7hH8MSUJpSbSDYk0k2)
- **First Message:**
  ```
  Hi, I'm Alice, your coordinator. I help organize tasks and delegate to the right specialists. What would you like to work on?
  ```
- **System Prompt:**
  ```
  You are Alice, the Coordinator Hub. Your role is to:
  1. Coordinate and delegate tasks to specialists
  2. Route to Adam (Desktop Worker) or Antoni (Coding Worker)
  3. Maintain project context across conversations
  4. Be organized, clear, and efficient

  When the user needs:
  - Desktop automation (open apps, control windows): Use transfer_to_adam tool
  - Code/documentation writing: Use transfer_to_antoni tool
  - Space/bubble management: Use transfer_to_rachel tool

  Always understand the task before delegating.
  ```
- **LLM:** GPT-4o-mini
- **Client Tools:** Add the transfer tools

Copy the Agent ID and add to `.env` as `ALICE_AGENT_ID`

#### Agent 3: Adam - Desktop Worker

- **Name:** Adam - Desktop Worker
- **Voice:** Adam (pNInz6obpgDQGcFmaJgB)
- **First Message:**
  ```
  Adam here. I handle desktop automation - opening apps, controlling windows, and system tasks. What do you need?
  ```
- **System Prompt:**
  ```
  You are Adam, the Desktop Worker. Your role is to:
  1. Execute desktop automation tasks (open apps, control windows, click, type)
  2. Manage files and system operations
  3. Report results clearly and efficiently

  You have access to desktop control tools. Execute tasks and confirm what you've done.
  When done, use transfer_to_alice to return to the coordinator.
  Always confirm before executing destructive operations.
  ```
- **LLM:** GPT-4o-mini
- **Client Tools:** Add transfer tool + desktop automation tools

Copy the Agent ID and add to `.env` as `ADAM_AGENT_ID`

#### Agent 4: Antoni - Coding Worker

- **Name:** Antoni - Coding Worker
- **Voice:** Antoni (ErXwobaYiN019PkySvjV)
- **First Message:**
  ```
  Hey! I'm Antoni, the coding worker. I create code, projects, and documentation. What would you like me to build?
  ```
- **System Prompt:**
  ```
  You are Antoni, the Coding Worker. Your role is to:
  1. Write and edit code files
  2. Create projects and documentation
  3. Generate code based on user requirements
  4. Follow coding patterns and best practices

  Ask clarifying questions when needed. Be creative but precise.
  When done, use transfer_to_alice to return to the coordinator.
  Always explain what you're creating.
  ```
- **LLM:** GPT-4o-mini
- **Client Tools:** Add transfer tool + coding tools

Copy the Agent ID and add to `.env` as `ANTONI_AGENT_ID`

### 4. Configure Transfer Tools in ElevenLabs Dashboard

Each agent has specific transfer tools. See `docs/agents/` for JSON configurations:

- **Rachel:** `transfer_to_alice` (to coordinator)
- **Alice:** `transfer_to_rachel`, `transfer_to_adam`, `transfer_to_antoni`
- **Adam:** `transfer_to_alice` (back to coordinator)
- **Antoni:** `transfer_to_alice` (back to coordinator)

Transfer tools are user-controlled - the agent requests a transfer and the user confirms via voice.

## 🏃 Running the System

### Test Configuration

First, verify your configuration is correct:

```bash
cd python
python agent_config.py
```

This should show all 4 agents with their IDs and configurations.

### Test Supermemory Connection

```bash
cd python
python memory/supermemory_client.py
```

This should successfully connect and store/retrieve test data.

### Run the Multi-Agent System

```bash
cd python
python multi_agent_voice_system.py
```

The system will:
1. Start with the Conversational Memory Agent
2. Wait for your voice input
3. Hand off to appropriate specialist agents as needed
4. Preserve conversation context across handoffs via Supermemory

## 🎙️ Usage Examples

### Example 1: Idea Capture

```
You: "Good morning, I have an idea for a new feature"

Rachel:
  "Good morning! I'd love to hear your idea. Tell me about it and I'll
   capture it in your current bubble."
```

### Example 2: Desktop Automation

```
You: "Open Visual Studio Code"

Rachel:
  "I'll connect you with Alice to coordinate that..."
  [Transfers to Alice]

Alice:
  "I'll have Adam open VS Code for you..."
  [Transfers to Adam]

Adam:
  "Opening Visual Studio Code now... Done!"
```

### Example 3: Code Writing

```
You: "Write a function to process user data"

Alice:
  "I'll have Antoni create that for you..."
  [Transfers to Antoni]

Antoni:
  "I'll create a user data processing function. What fields should it handle?"
```

## 🔧 Troubleshooting

### Agents not switching

Check that:
1. All 4 agent IDs are in `.env` (RACHEL_AGENT_ID, ALICE_AGENT_ID, ADAM_AGENT_ID, ANTONI_AGENT_ID)
2. Transfer tools are configured in each agent's dashboard
3. See `python/tools/transfer_handler.py` for transfer logic

### Desktop automation not working

Desktop tools are in `python/tools/desktop_tools.py`. Ensure Adam has access to these tools in the ElevenLabs dashboard.

## 📁 Project Structure

```
python/
├── voice_dialog_main.py         # Main entry point
├── electron_backend.py          # Electron IPC handler
├── agent_config.py              # Agent registry
├── agents/                      # Agent configurations
│   ├── rachel/                  # Multiverse Navigator
│   ├── alice/                   # Coordinator Hub
│   ├── adam/                    # Desktop Worker
│   └── antoni/                  # Coding Worker
└── tools/
    ├── transfer_handler.py      # Agent transfer logic
    ├── bubble_tools.py          # Space/bubble management
    ├── idea_tools.py            # Idea capture
    ├── desktop_tools.py         # Desktop automation
    └── coding_tools.py          # Code generation
```

## 🔄 Next Steps

1. **Create the 4 agents** in ElevenLabs dashboard (follow steps above)
2. **Add agent IDs** to `.env` (RACHEL_AGENT_ID, ALICE_AGENT_ID, ADAM_AGENT_ID, ANTONI_AGENT_ID)
3. **Configure transfer tools** for each agent
4. **Test the system** with `python voice_dialog_main.py`
5. **Try the Electron app** with `cd electron-app && npm start`

## 📚 Additional Resources

- [ElevenLabs Conversational AI Docs](https://elevenlabs.io/docs/conversational-ai)
- [User Transfers Guide](USER_CONTROLLED_TRANSFERS_GUIDE.md) - Audio settings and transfer flow
- [Client Tools Setup](agents/CLIENT_TOOLS_SETUP.md) - Tool implementation

## 🆘 Support

If you encounter issues:
1. Check logs in `python/logs/`
2. Run `python -m agents` to verify agent registry
3. Verify all API keys in `.env`
4. Check agent configurations in ElevenLabs dashboard
