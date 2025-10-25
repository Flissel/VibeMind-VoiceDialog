# Simplified Agent Setup Guide

Good news! ElevenLabs has a **built-in "Transfer to agent" tool** in the dashboard, so we don't need to create custom client tools.

## Step 1: Create Agents with API Script

Since you've updated your API key with the proper permissions, run:

```bash
cd python
python create_agents.py
```

This will create all 4 agents automatically and give you agent IDs to add to your `.env` file.

## Step 2: Update .env File

Add the agent IDs from the script output:

```bash
AGENT_CONVERSATIONAL_MEMORY=your_agent_id_1
AGENT_PROJECT_MANAGER=your_agent_id_2
AGENT_DESKTOP_WORKER=your_agent_id_3
AGENT_PROJECT_WRITER=your_agent_id_4
```

## Step 3: Enable "Transfer to agent" Tool

For **each of the 4 agents** in the ElevenLabs dashboard:

1. Go to: https://elevenlabs.io/app/conversational-ai
2. Click on the agent (e.g., "Conversational Memory Assistant")
3. Scroll to the **"Tools"** section
4. Find **"Transfer to agent"** in the built-in tools list
5. **Toggle it ON** (enable it)
6. Save the agent configuration

![Transfer to agent tool](screenshot-transfer-tool.png)

That's it! The built-in tool is already configured properly by ElevenLabs.

## Step 4: Configure Which Agents Can Be Transferred To

For each agent, you need to specify which other agents it can transfer to:

### Conversational Memory Assistant
- **Can transfer to:** Project Manager
- **Reason:** Routes user requests to the appropriate specialist

### Project Manager
- **Can transfer to:** Desktop Worker, Project Writer, Conversational Memory
- **Reason:** Delegates tasks to workers or returns to memory agent

### Desktop Worker
- **Can transfer to:** Project Manager
- **Reason:** Returns to PM when task is complete or needs project context

### Project Writer
- **Can transfer to:** Project Manager
- **Reason:** Returns to PM when task is complete or needs project context

## Step 5: Test the System

Run the verification script:

```bash
cd python
python test_system.py
```

If all tests pass, you're ready!

## How Agent Handoffs Work

The built-in "Transfer to agent" tool automatically:

1. **Ends the current conversation**
2. **Transfers to the target agent** (different voice!)
3. **Passes context** from the conversation

### Example Conversation Flow:

```
User: "Hey, can you help me organize my coding projects?"

Conversational Memory (Rachel):
  "Of course! Let me connect you with our Project Manager
   who specializes in organizing projects."

  [Uses "Transfer to agent" tool → target: Project Manager]

Project Manager (Alice):
  "Hi! I'm your Project Manager. I can help you organize
   your coding projects. What would you like to work on?"

User: "I need to open Visual Studio Code and start working on my Python project"

Project Manager (Alice):
  "I'll connect you with our Desktop Worker who can
   open applications for you."

  [Uses "Transfer to agent" tool → target: Desktop Worker]

Desktop Worker (Adam):
  "Desktop Worker here. I'll open Visual Studio Code for you now."

  [Opens VS Code using desktop automation]

  "VS Code is now open. What else do you need?"
```

Notice how the **voice changes** with each agent transfer!

## What Makes This Work?

### Built-in Transfer Tool
- ElevenLabs provides the transfer mechanism
- No custom client tools needed
- Handles conversation ending and starting automatically

### Our Supermemory Integration (Optional Enhancement)
The Python code we created can **enhance** the built-in tool by:
- Storing conversation history across transfers
- Remembering user preferences long-term
- Providing project context to agents

But the basic handoff **works out of the box** with just the built-in tool!

## Next Steps

1. ✅ Run `python create_agents.py` to create agents
2. ✅ Add agent IDs to `.env`
3. ✅ Enable "Transfer to agent" tool for each agent in dashboard
4. ✅ Run `python test_system.py` to verify
5. 🚀 Start using the multi-agent voice system!

## Advanced: Adding Supermemory Context (Optional)

If you want agents to remember conversations across sessions:

1. The conversation_manager.py code we created handles this
2. It stores context in Supermemory when transfers happen
3. New agent retrieves context from Supermemory
4. This gives agents "memory" of previous conversations

But this is **optional** - the basic transfer works without it!

## Troubleshooting

### "Transfer to agent" tool not visible
- Check your ElevenLabs subscription tier
- This feature may require a paid plan
- Contact ElevenLabs support if missing

### Transfer doesn't work
- Make sure the tool is **enabled (toggled ON)** for each agent
- Verify target agent ID is correct
- Check agent configuration is saved

### Voice doesn't change on transfer
- Each agent should have a different voice_id configured
- Verify voice IDs in agent settings match our configuration:
  - Conversational Memory: Rachel (21m00Tcm4TlvDq8ikWAM)
  - Project Manager: Alice (Xb7hH8MSUJpSbSDYk0k2)
  - Desktop Worker: Adam (pNInz6obpgDQGcFmaJgB)
  - Project Writer: Antoni (ErXwobaYiN019PkySvjV)

## Summary

The setup is much simpler than expected because ElevenLabs provides:
- ✅ Built-in "Transfer to agent" tool
- ✅ Automatic conversation handoff mechanism
- ✅ Voice switching between agents

We just need to:
1. Create the 4 agents (automated with `create_agents.py`)
2. Enable the built-in transfer tool for each agent
3. Configure which agents can transfer to which

That's it! The multi-agent voice system is ready to use.
