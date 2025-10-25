# Agent Tool Configuration

## "Transfer to agent" Tool Setup

For each agent in the ElevenLabs dashboard, you need to:
1. Enable the "Transfer to agent" tool
2. Configure which agents they can transfer to
3. Set up a rule for when to use the tool

## Agent 1: Conversational Memory

**Agent ID:** `agent_4801k8dffmgge8mt8e713sem2ze0`

### Tool Configuration

```json
{
  "type": "system",
  "name": "transfer_to_agent",
  "description": "",
  "params": {
    "system_tool_type": "transfer_to_agent",
    "transfers": [
      {
        "agent_id": "agent_2801k8dffpt2ev6rwktpyr75ze64",
        "agent_name": "Project Manager"
      }
    ],
    "voicemail_message": ""
  },
  "disable_interruptions": false
}
```

### Rule Configuration

**When to transfer:**
- User asks about projects, tasks, or work organization
- User wants to start working on something
- User needs task delegation

**Example triggers:**
- "help me with my project"
- "I need to organize my work"
- "start a new task"

---

## Agent 2: Project Manager

**Agent ID:** `agent_2801k8dffpt2ev6rwktpyr75ze64`

### Tool Configuration

```json
{
  "type": "system",
  "name": "transfer_to_agent",
  "description": "",
  "params": {
    "system_tool_type": "transfer_to_agent",
    "transfers": [
      {
        "agent_id": "agent_5901k8dffqwmfdzvaypbh6secpg5",
        "agent_name": "Desktop Worker"
      },
      {
        "agent_id": "agent_1401k8dffs7kfmbrvs9sswac8x12",
        "agent_name": "Project Writer"
      },
      {
        "agent_id": "agent_4801k8dffmgge8mt8e713sem2ze0",
        "agent_name": "Conversational Memory"
      }
    ],
    "voicemail_message": ""
  },
  "disable_interruptions": false
}
```

### Rule Configuration

**When to transfer to Desktop Worker:**
- User needs to open applications
- User wants to control windows or desktop
- User needs file/folder operations

**When to transfer to Project Writer:**
- User wants code written
- User needs documentation created
- User wants files edited

**When to transfer to Conversational Memory:**
- Task is complete, returning to casual conversation
- User wants to chat or remember something
- No specific work needed right now

---

## Agent 3: Desktop Worker

**Agent ID:** `agent_5901k8dffqwmfdzvaypbh6secpg5`

### Tool Configuration

```json
{
  "type": "system",
  "name": "transfer_to_agent",
  "description": "",
  "params": {
    "system_tool_type": "transfer_to_agent",
    "transfers": [
      {
        "agent_id": "agent_2801k8dffpt2ev6rwktpyr75ze64",
        "agent_name": "Project Manager"
      }
    ],
    "voicemail_message": ""
  },
  "disable_interruptions": false
}
```

### Rule Configuration

**When to transfer:**
- Desktop task is complete
- User asks about project context
- Need to delegate another type of task

**Example triggers:**
- "what's next?"
- "what else do I need to do?"
- Task completion acknowledgment

---

## Agent 4: Project Writer

**Agent ID:** `agent_1401k8dffs7kfmbrvs9sswac8x12`

### Tool Configuration

```json
{
  "type": "system",
  "name": "transfer_to_agent",
  "description": "",
  "params": {
    "system_tool_type": "transfer_to_agent",
    "transfers": [
      {
        "agent_id": "agent_2801k8dffpt2ev6rwktpyr75ze64",
        "agent_name": "Project Manager"
      }
    ],
    "voicemail_message": ""
  },
  "disable_interruptions": false
}
```

### Rule Configuration

**When to transfer:**
- Writing task is complete
- User asks about project status
- Need to delegate another type of task

**Example triggers:**
- "is that everything?"
- "what should I work on next?"
- Code/documentation is delivered

---

## Step-by-Step Setup in Dashboard

### For Each Agent:

1. **Go to agent settings**
   - Visit: https://elevenlabs.io/app/conversational-ai
   - Click on the agent

2. **Scroll to "Tools" section**
   - Find "Transfer to agent" in the system tools list
   - Toggle it **ON**

3. **Configure transfers array**
   - Click the gear icon or "Configure" button
   - Add the agent IDs from the JSON above for that agent
   - For example, Conversational Memory can only transfer to Project Manager
   - But Project Manager can transfer to Desktop Worker, Project Writer, OR Conversational Memory

4. **Set up a rule (optional but recommended)**
   - In the agent's prompt or rules section
   - Add guidance on when to transfer
   - Example for Conversational Memory:
     ```
     When the user asks about projects, tasks, or work organization,
     use the transfer_to_agent tool to connect them with the Project Manager.
     ```

5. **Save the agent**

---

## Transfer Flow Examples

### Example 1: Starting a Project

```
User: "I want to work on my Python project"

Conversational Memory (Rachel):
  "Great! Let me connect you with our Project Manager who can help organize that."
  [Transfers to Project Manager]

Project Manager (Alice):
  "Hi! I'm Alice, your Project Manager. Tell me about your Python project."

User: "I need to open VS Code and start coding"

Project Manager (Alice):
  "I'll connect you with our Desktop Worker to open VS Code for you."
  [Transfers to Desktop Worker]

Desktop Worker (Adam):
  "Desktop Worker here. Opening Visual Studio Code now."
  [Opens VS Code]
  "VS Code is open. Ready to code?"
```

### Example 2: Writing Documentation

```
User: "I need to write a README for my project"

Conversational Memory (Rachel):
  "Let me connect you with the Project Manager to organize that."
  [Transfers to Project Manager]

Project Manager (Alice):
  "I'll delegate this to our Project Writer who specializes in documentation."
  [Transfers to Project Writer]

Project Writer (Antoni):
  "Hello! I can help write your README. What's your project about?"

User: "It's a Python voice dialog system"

Project Writer (Antoni):
  "Perfect! I'll create a comprehensive README for your Python voice dialog system."
  [Creates README.md]
  "I've created your README. Would you like me to add anything else?"

User: "No, that's great. Thanks!"

Project Writer (Antoni):
  "You're welcome! Sending you back to the Project Manager for your next task."
  [Transfers to Project Manager]
```

---

## Validation Checklist

For each agent, verify:

- [ ] "Transfer to agent" tool is **enabled (toggled ON)**
- [ ] `transfers` array has the correct agent IDs for allowed handoffs
- [ ] Agent names match (optional but helpful for debugging)
- [ ] System prompt includes guidance on when to transfer
- [ ] Agent is saved after configuration

### Quick Test

After setup, try this conversation:

1. Start with Conversational Memory
2. Say: "I want to work on a project"
3. Should transfer to Project Manager
4. Say: "Open VS Code"
5. Should transfer to Desktop Worker

If the voice changes and you hear different agents, it's working! 🎉

---

## Troubleshooting

### Transfer doesn't happen
- Check that the tool is **enabled (toggled ON)**
- Verify the target agent ID is in the `transfers` array
- Make sure the target agent ID is correct (copy from .env)
- Review agent's system prompt for transfer guidance

### Wrong agent receives transfer
- Check the `transfers` array for the source agent
- Verify agent IDs match what's in your .env file
- Only the agents listed in `transfers` array can receive transfers

### Voice doesn't change
- Each agent must have a different voice_id configured
- Check agent settings → Voice selection
- Verify:
  - Conversational Memory: Rachel (21m00Tcm4TlvDq8ikWAM)
  - Project Manager: Alice (Xb7hH8MSUJpSbSDYk0k2)
  - Desktop Worker: Adam (pNInz6obpgDQGcFmaJgB)
  - Project Writer: Antoni (ErXwobaYiN019PkySvjV)

### Transfer happens too often
- Refine the agent's system prompt
- Add more specific conditions for when to transfer
- Example: "Only transfer if the user explicitly asks about projects"

### Transfer doesn't happen enough
- Make transfer conditions broader in system prompt
- Add examples of transfer triggers
- Test with explicit requests: "connect me with the project manager"
