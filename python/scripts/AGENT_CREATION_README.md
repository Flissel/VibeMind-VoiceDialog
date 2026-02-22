# Agent Creation Guide

This document explains how to create the 4 ElevenLabs agents for the multi-agent voice system.

## Quick Start

Run the automated creation script:

```bash
cd python
python create_agents.py
```

The script will attempt to create all 4 agents via the ElevenLabs API and provide you with agent IDs to add to your `.env` file.

## Prerequisites

### API Key Permissions

Your ElevenLabs API key must have the **Conversational AI Write** permission enabled.

**To check/update your API key:**

1. Go to: https://elevenlabs.io/app/settings/api-keys
2. Delete your current API key (if it exists)
3. Click "Create API Key"
4. **Enable the "Conversational AI Write" permission** (this is critical!)
5. Copy the new API key
6. Update your `.env` file:
   ```bash
   ELEVENLABS_API_KEY=your_new_key_here
   ```

## Automated Creation (Recommended)

### Step 1: Run the Script

```bash
python create_agents.py
```

### Step 2: Check Output

If successful, you'll see:

```
SUCCESS! All agents created!

======================================================================
Add these lines to your .env file:
======================================================================

AGENT_CONVERSATIONAL_MEMORY=xxxxx
AGENT_PROJECT_MANAGER=xxxxx
AGENT_DESKTOP_WORKER=xxxxx
AGENT_PROJECT_WRITER=xxxxx
```

### Step 3: Update .env File

Copy the agent IDs to your `.env` file:

```bash
# Agent IDs
AGENT_CONVERSATIONAL_MEMORY=your_agent_id_1
AGENT_PROJECT_MANAGER=your_agent_id_2
AGENT_DESKTOP_WORKER=your_agent_id_3
AGENT_PROJECT_WRITER=your_agent_id_4
```

### Step 4: Verify Setup

```bash
python test_system.py
```

If all tests pass, you're ready to use the multi-agent system!

## Manual Creation (Alternative)

If the automated script fails or you prefer manual creation:

1. Go to: https://elevenlabs.io/app/conversational-ai
2. Click "Create Agent" 4 times (once for each agent)
3. For each agent, use the configurations from `MULTI_AGENT_SETUP.md`
4. Copy each agent ID and add to your `.env` file

See [MULTI_AGENT_SETUP.md](../MULTI_AGENT_SETUP.md) for detailed step-by-step instructions with screenshots.

## Agent Configurations

The script creates 4 agents with these configurations:

### 1. Conversational Memory Assistant
- **Voice:** Rachel (21m00Tcm4TlvDq8ikWAM)
- **Role:** Entry point, learns user preferences, routes to specialists
- **First Message:** "Hello! I'm your personal memory assistant..."

### 2. Project Manager
- **Voice:** Alice (Xb7hH8MSUJpSbSDYk0k2)
- **Role:** Organizes projects, delegates tasks
- **First Message:** "Hi, I'm your Project Manager..."

### 3. Desktop Worker
- **Voice:** Adam (pNInz6obpgDQGcFmaJgB)
- **Role:** Controls desktop applications and windows
- **First Message:** "Desktop Worker here. I can control your computer..."

### 4. Project Writer
- **Voice:** Antoni (ErXwobaYiN019PkySvjV)
- **Role:** Writes code and documentation
- **First Message:** "Hello! I'm your Project Writer..."

## Troubleshooting

### Error: "missing_permissions"

**Cause:** Your API key doesn't have the `convai_write` permission.

**Solution:** Regenerate your API key with the "Conversational AI Write" permission enabled (see Prerequisites above).

### Error: "401 Unauthorized"

**Cause:** Invalid or expired API key.

**Solution:**
1. Check that `ELEVENLABS_API_KEY` is set correctly in `.env`
2. Verify the API key is valid at https://elevenlabs.io/app/settings/api-keys
3. Make sure there are no extra spaces or quotes in the `.env` file

### Error: "Invalid voice_id"

**Cause:** The voice ID doesn't exist or isn't accessible with your account.

**Solution:**
1. Check your subscription tier at https://elevenlabs.io/app/subscription
2. Some voices require paid plans
3. You can choose different voices by editing `create_agents.py`

### Script Completes but No Agents Created

**Cause:** Network issues or ElevenLabs API downtime.

**Solution:**
1. Check your internet connection
2. Try again in a few minutes
3. Check ElevenLabs status: https://status.elevenlabs.io/
4. Fall back to manual creation (see MULTI_AGENT_SETUP.md)

## API Request Format

The script makes POST requests to:

```
POST https://api.elevenlabs.io/v1/convai/agents/create
```

With payload:

```json
{
  "conversation_config": {
    "agent": {
      "prompt": {
        "prompt": "System prompt text..."
      },
      "first_message": "Hello! I'm...",
      "language": "en"
    },
    "tts": {
      "voice_id": "21m00Tcm4TlvDq8ikWAM",
      "model_id": "eleven_turbo_v2_5"
    }
  },
  "name": "Agent Name",
  "tags": []
}
```

Headers:

```
xi-api-key: your_api_key
Content-Type: application/json
```

## Next Steps

After creating agents:

1. **Verify Setup:** `python test_system.py`
2. **Configure Client Tools:** Add the `handoff_to_agent` tool to each agent in the dashboard
3. **Start System:** `python multi_agent_voice_system.py` (once implemented)

## Related Documentation

- [MULTI_AGENT_SETUP.md](../MULTI_AGENT_SETUP.md) - Detailed manual setup guide
- [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md) - Technical implementation details
- [.env.template](../.env.template) - Environment configuration template

## Support

For ElevenLabs API issues:
- Documentation: https://elevenlabs.io/docs/api-reference/agents/create
- Support: https://elevenlabs.io/support

For this repository:
- Check the documentation in the root directory
- Review the troubleshooting section above
