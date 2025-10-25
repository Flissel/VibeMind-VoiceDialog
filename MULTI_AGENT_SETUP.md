# Multi-Agent Voice System Setup Guide

This guide will help you set up the voice-controlled desktop automation system with multiple specialized agents.

## 🎯 Overview

The system consists of 4 specialized AI agents, each with a unique voice, that work together to automate your desktop:

1. **Conversational Memory Agent** (Rachel - Professional female)
   - Entry point for all interactions
   - Learns your preferences and habits
   - Routes requests to appropriate specialists

2. **Project Manager Agent** (Alice - Calm British female)
   - Manages your projects and tasks
   - Delegates to Desktop Worker or Project Writer
   - Maintains project knowledge

3. **Desktop Worker Agent** (Adam - Confident male)
   - Controls desktop applications
   - Opens windows, clicks buttons, types text
   - Executes system commands

4. **Project Writer Agent** (Antoni - Creative male)
   - Writes code and documentation
   - Creates README files and project notes
   - Follows your coding style

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

#### Agent 1: Conversational Memory Assistant

Go to https://elevenlabs.io/app/conversational-ai and create a new agent:

- **Name:** Conversational Memory Assistant
- **Voice:** Rachel (21m00Tcm4TlvDq8ikWAM) or search for "professional female"
- **First Message:**
  ```
  Hello! I'm your personal memory assistant. I remember your preferences, habits, and projects. How can I help you today?
  ```
- **System Prompt:**
  ```
  You are a Conversational Memory Assistant. Your role is to:
  1. Learn about the user's preferences, habits, and common tasks
  2. Remember past conversations and build a user profile
  3. Route users to appropriate specialist agents based on their needs
  4. Maintain a warm, friendly, and attentive personality

  When the user needs help with:
  - Project management or tracking: Use the handoff_to_agent tool with target "ProjectManager"
  - Specific tasks: Route through Project Manager first

  Always be brief, friendly, and acknowledge what you remember about the user.
  Use the handoff_to_agent tool when you need to delegate to a specialist.
  ```
- **LLM:** GPT-4o-mini
- **Client Tools:** Add the handoff tool (see below)

Copy the Agent ID and add to `.env` as `AGENT_CONVERSATIONAL_MEMORY`

#### Agent 2: Project Manager

- **Name:** Project Manager
- **Voice:** Alice (Xb7hH8MSUJpSbSDYk0k2) or search for "calm British female"
- **First Message:**
  ```
  Hi, I'm your Project Manager. I organize your projects and delegate tasks to the right specialists. What project would you like to work on?
  ```
- **System Prompt:**
  ```
  You are a Project Manager. Your role is to:
  1. Track and organize user projects
  2. Understand project goals, deadlines, and progress
  3. Delegate tasks to Desktop Worker or Project Writer specialists
  4. Maintain project knowledge and context

  When the user needs:
  - Desktop automation (open apps, control windows): Use handoff_to_agent with target "DesktopWorker"
  - Code/documentation writing: Use handoff_to_agent with target "ProjectWriter"
  - Just wants to chat or remember things: Use handoff_to_agent with target "ConversationalMemory"

  Always be organized, clear, and brief. Understand the task before delegating.
  ```
- **LLM:** GPT-4o-mini
- **Client Tools:** Add the handoff tool

Copy the Agent ID and add to `.env` as `AGENT_PROJECT_MANAGER`

#### Agent 3: Desktop Worker

- **Name:** Desktop Worker
- **Voice:** Adam (pNInz6obpgDQGcFmaJgB) or search for "confident male"
- **First Message:**
  ```
  Desktop Worker here. I can control your computer - open applications, click buttons, manage windows. What would you like me to do?
  ```
- **System Prompt:**
  ```
  You are a Desktop Worker specialized in computer automation. Your role is to:
  1. Execute desktop automation tasks (open apps, control windows, click, type)
  2. Manage files and system operations
  3. Report results clearly to the user

  You have access to desktop control tools. Execute tasks efficiently and confirm what you've done.
  If you need project context, use handoff_to_agent with target "ProjectManager".
  Always confirm actions before executing potentially destructive operations.
  ```
- **LLM:** GPT-4o-mini
- **Client Tools:** Add the handoff tool + desktop automation tools

Copy the Agent ID and add to `.env` as `AGENT_DESKTOP_WORKER`

#### Agent 4: Project Writer

- **Name:** Project Writer
- **Voice:** Antoni (ErXwobaYiN019PkySvjV) or search for "creative male"
- **First Message:**
  ```
  Hello! I'm your Project Writer. I create code, documentation, and content for your projects. What would you like me to write?
  ```
- **System Prompt:**
  ```
  You are a Project Writer specialized in creating content. Your role is to:
  1. Write and edit code files
  2. Create documentation and README files
  3. Generate project reports and notes
  4. Follow user's coding style and preferences

  When writing code, ask clarifying questions first. Be creative but precise.
  If you need project context, use handoff_to_agent with target "ProjectManager".
  Always explain what you're creating and why.
  ```
- **LLM:** GPT-4o-mini
- **Client Tools:** Add the handoff tool + writing tools

Copy the Agent ID and add to `.env` as `AGENT_PROJECT_WRITER`

### 4. Configure Client Tools in ElevenLabs Dashboard

For EACH agent, add the following client tool:

**Tool Name:** `handoff_to_agent`

**Description:**
```
Transfer the conversation to another specialist agent. Use this when the user's request requires expertise from a different agent.
```

**Parameters Schema:**
```json
{
  "type": "object",
  "properties": {
    "target_agent": {
      "type": "string",
      "description": "The specialist agent to hand off to",
      "enum": ["ConversationalMemory", "ProjectManager", "DesktopWorker", "ProjectWriter"]
    },
    "reason": {
      "type": "string",
      "description": "Brief explanation of why you're handing off (what the user needs help with)"
    },
    "context": {
      "type": "string",
      "description": "Important context the next agent should know (user's request, preferences, etc.)"
    }
  },
  "required": ["target_agent", "reason", "context"]
}
```

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

### Example 1: Project Management

```
You: "Good morning, I want to work on my Python project"

Conversational Memory Agent:
  "Good morning! I see you usually work on VibeMind. Let me connect you
   with the Project Manager..."
  [Handoffs to Project Manager]

Project Manager:
  "Hi! I have your VibeMind project loaded. What would you like to work on today?"
```

### Example 2: Desktop Automation

```
You: "Open Visual Studio Code and my project files"

Project Manager:
  "I'll have the Desktop Worker open that for you..."
  [Handoffs to Desktop Worker]

Desktop Worker:
  "Opening Visual Studio Code... Loading VibeMind project files...
   You're all set!"
```

### Example 3: Code Writing

```
You: "Write a function to process user preferences"

Project Manager:
  "I'll have our Project Writer create that for you..."
  [Handoffs to Project Writer]

Project Writer:
  "I'll create a user preference processing function. Based on your VibeMind
   project, I'll use the same coding style you prefer..."
```

## 🔧 Troubleshooting

### Agents not switching

Check that:
1. All 4 agent IDs are in `.env`
2. The `handoff_to_agent` tool is configured in EACH agent's dashboard
3. Supermemory API key is valid

### Memory not preserved

Check:
- Supermemory API key is valid
- Test the client: `python memory/supermemory_client.py`
- Check logs for Supermemory errors

### Desktop automation not working

The desktop automation client (`python/desktop/desktop_client.py`) is currently a stub.
Connect it to your actual desktop automation API.

## 📁 Project Structure

```
python/
├── agent_config.py              # Agent registry and configuration
├── conversation_manager.py      # Handles agent handoffs
├── setup_agents.py             # Helper script for agent setup
├── multi_agent_voice_system.py # Main entry point (to be created)
├── memory/
│   └── supermemory_client.py   # Supermemory integration
├── desktop/
│   └── desktop_client.py       # Desktop automation (stub)
└── tools/
    ├── handoff_tool.py         # Agent handoff client tool
    └── client_tools_manager.py # Legacy single-agent tools
```

## 🔄 Next Steps

1. **Create the 4 agents** in ElevenLabs dashboard (follow steps above)
2. **Add agent IDs** to `.env`
3. **Configure the handoff tool** in each agent
4. **Test the system** with `python multi_agent_voice_system.py`
5. **Connect desktop automation** to your actual automation API
6. **Customize agent behaviors** by editing system prompts

## 📚 Additional Resources

- [ElevenLabs Conversational AI Docs](https://elevenlabs.io/docs/conversational-ai)
- [Supermemory Documentation](https://supermemory.ai/docs)
- [AutoGen Documentation](https://microsoft.github.io/autogen/)

## 🆘 Support

If you encounter issues:
1. Check the logs in `voice_dialog.log`
2. Test each component individually (agent_config.py, supermemory_client.py)
3. Verify all API keys are valid
4. Ensure agents are created correctly in ElevenLabs dashboard

---

**Note:** The system is designed to work cross-platform (Windows/Linux/Mac), but desktop automation features may require platform-specific implementations.
