# User-Controlled Transfers & Audio Feedback Prevention Guide

## Overview

This guide explains two major improvements to the voice dialog system:

1. **User-Controlled Transfers** - YOU control which agent you talk to
2. **Audio Feedback Prevention** - Microphone doesn't pick up speaker output

---

## 1. User-Controlled Transfers

### Philosophy Change

**OLD (Automatic - REMOVED):**
```
User: "Write hello world"
Rachel: [auto-transfers to Alice]
Alice: [auto-transfers to Antoni]
```

❌ Agents made transfer decisions for you
❌ No control over who you talked to
❌ Felt automated and rigid

**NEW (User-Controlled - CURRENT):**
```
User: "Write hello world"
Rachel: "I can't write files. Would you like me to transfer you to the project manager?"
User: "Yes, transfer me"
Rachel: [transfers to Alice]
Alice: "The project writer specializes in that. Should I transfer you to Antoni?"
User: "Yes"
Alice: [transfers to Antoni]
Antoni: [writes file] "Done. Go back to Alice?"
User: "Yes"
Antoni: [transfers to Alice]
```

✅ YOU decide when to transfer
✅ Full control over agent routing
✅ Natural conversation flow

### How It Works

**Transfer Phrases (what to say):**
- "Transfer me to [agent name]"
- "Let me talk to [agent name]"
- "Connect me with [agent name]"
- "Go back to [agent name]"
- "Yes" (after agent suggests transfer)
- "Yes, transfer me"

**Agent Names:**
- Rachel / Conversational Memory
- Alice / Project Manager
- Adam / Desktop Worker
- Antoni / Project Writer

**Examples:**

#### Direct Transfer
```
User: "Transfer me to the project manager"
Rachel: [transfers to Alice]
```

#### Suggested Transfer
```
User: "Open Chrome"
Rachel: "I can't open apps. The project manager can help. Would you like a transfer?"
User: "Yes"
Rachel: [transfers to Alice]
```

#### Shortcut Transfer
```
User: "Let me talk to Antoni"
Rachel: [transfers directly to Antoni]
```

### Agent Behaviors

#### Rachel (Conversational Memory)
- Chats and answers questions
- When you ask for tasks: Suggests PM transfer, waits for permission
- Examples:
  - ✅ "Hello" → Responds without transferring
  - ✅ "Write file" → "Would you like me to transfer you to PM?"
  - ✅ "Transfer me to Alice" → Transfers immediately

#### Alice (Project Manager)
- Coordinates tasks
- When you ask for tasks: Suggests specialist, waits for permission
- Examples:
  - ✅ "Open Chrome" → "Desktop worker can help. Transfer?"
  - ✅ "Write Python script" → "Project writer specializes in that. Transfer?"
  - ✅ "Yes" → Transfers to appropriate specialist

#### Adam (Desktop Worker)
- Executes desktop tasks
- After completing task: Asks if you want to go back
- Examples:
  - ✅ "Write hello world" → [executes] "Done. Go back?"
  - ✅ "Yes" → Transfers back to Alice
  - ✅ "Do it again" → [executes again] "Done. Go back?"

#### Antoni (Project Writer)
- Creates documents and code
- After completing task: Asks if you want to go back
- Examples:
  - ✅ "Create hello file" → [executes] "Done. Go back to Alice?"
  - ✅ "Transfer me back" → Transfers to Alice

### Updating Dashboard

**For each agent in https://elevenlabs.io/app/conversational-ai:**

1. Click on the agent
2. Go to **System Prompt** section
3. Copy the ENTIRE contents of the corresponding prompt file:
   - Rachel: `docs/agents/conversational_memory_prompt.txt`
   - Alice: `docs/agents/project_manager_prompt.txt`
   - Adam: `docs/agents/desktop_worker_prompt.txt`
   - Antoni: `docs/agents/project_writer_prompt.txt`
4. Paste and save

---

## 2. Audio Feedback Prevention

### The Problem

**Audio Feedback Loop:**
```
AI speaks → Speaker outputs audio → Microphone picks it up → AI thinks you spoke → AI responds → Loop continues
```

❌ AI responds to its own voice
❌ Conversation gets stuck in loop
❌ Can't have natural conversation

### The Solution

**Amplitude Threshold Filtering:**
```
User voice (close to mic) = HIGH amplitude → CAPTURED ✅
Speaker output (far from mic) = LOW amplitude → FILTERED ❌
```

✅ Only your voice triggers responses
✅ Speaker output ignored
✅ Natural conversation possible

### How It Works

1. **Microphone captures audio** at 16kHz
2. **Calculate RMS amplitude** (loudness measure)
3. **Compare to threshold** (default: 0.03 or 3%)
4. **Above threshold?** Pass to AI (user voice)
5. **Below threshold?** Drop silently (speaker feedback)

### Configuration

#### Option 1: Use .env File (Recommended)

Add to `.env`:
```
# Amplitude threshold (0.0 to 1.0)
# Higher = only louder sounds
# Lower = captures quieter sounds
AUDIO_THRESHOLD=0.03

# Minimum speech duration (seconds)
MIN_SPEECH_DURATION=0.3

# Enable/disable filtering
USE_THRESHOLD_FILTERING=true
```

#### Option 2: Test Different Thresholds

Run threshold test script:
```bash
cd python

# Test with default threshold (0.03)
python custom_audio_interface.py

# Test with custom threshold
python custom_audio_interface.py 0.05   # Higher threshold
python custom_audio_interface.py 0.02   # Lower threshold
```

**What to look for:**
- ✅ When you speak: "✓ SPEECH DETECTED - RMS: 0.0456"
- ✅ When speaker plays: Nothing (filtered below threshold)

**Adjusting:**
- **If speaker triggers detection:** INCREASE threshold
  - Try 0.04, 0.05, 0.06, etc.
  - Update `AUDIO_THRESHOLD` in `.env`
- **If your voice doesn't trigger:** DECREASE threshold
  - Try 0.02, 0.01, 0.005, etc.
  - Update `AUDIO_THRESHOLD` in `.env`

### Testing Audio Feedback Prevention

1. **Find your threshold:**
   ```bash
   cd python
   python custom_audio_interface.py 0.03
   ```

2. **Speak normally:**
   - Should see: "✓ SPEECH DETECTED"
   - RMS should be 0.03 or higher

3. **Let agent respond through speakers:**
   - Should see: Nothing (or occasional low RMS values)
   - Speaker output should NOT trigger detection

4. **Adjust if needed:**
   ```bash
   # If speaker triggers detection:
   python custom_audio_interface.py 0.05  # Try higher

   # If your voice doesn't trigger:
   python custom_audio_interface.py 0.02  # Try lower
   ```

5. **Update .env with working threshold:**
   ```
   AUDIO_THRESHOLD=0.04  # Example: Your tested value
   ```

### Advanced: Custom Audio Interface

**Current Status:**
- `custom_audio_interface.py` is created and ready
- May need ElevenLabs SDK integration updates
- For now, use system audio volume adjustments as backup

**Backup Methods if Threshold Doesn't Work:**
1. **Reduce speaker volume** (so mic doesn't pick it up)
2. **Position microphone closer** to you (increases your RMS)
3. **Position speakers farther** from microphone (decreases speaker RMS)
4. **Use headphones** (eliminates speaker feedback entirely)

---

## 3. Complete Testing Workflow

### Step 1: Update Dashboard Prompts

For each agent at https://elevenlabs.io/app/conversational-ai:

1. Rachel (Conversational Memory)
   - Copy `docs/agents/conversational_memory_prompt.txt`
   - Paste into System Prompt
   - Save

2. Alice (Project Manager)
   - Copy `docs/agents/project_manager_prompt.txt`
   - Paste into System Prompt
   - Save

3. Adam (Desktop Worker)
   - Copy `docs/agents/desktop_worker_prompt.txt`
   - Paste into System Prompt
   - Save

4. Antoni (Project Writer)
   - Copy `docs/agents/project_writer_prompt.txt`
   - Paste into System Prompt
   - Save

### Step 2: Test Audio Threshold

```bash
cd python
python custom_audio_interface.py 0.03
```

- Speak normally
- Listen to speakers play
- Adjust threshold if needed
- Update `.env` with working value

### Step 3: Test User-Controlled Transfers

```bash
cd python
python voice_dialog_main.py
```

**Test Conversation 1: Greeting (No Transfer)**
```
User: "Hello"
Rachel: "Hi! What can I help with?"
```
✅ Should NOT transfer

**Test Conversation 2: Explicit Transfer**
```
User: "Transfer me to the project manager"
Rachel: [transfers]
Alice: [responds]
```
✅ Should transfer immediately

**Test Conversation 3: Suggested Transfer**
```
User: "Write hello world"
Rachel: "I can't write files. Would you like me to transfer you to the project manager?"
User: "Yes"
Rachel: [transfers]
Alice: "The project writer specializes in that. Should I transfer you to Antoni?"
User: "Yes"
Alice: [transfers]
Antoni: [executes tool] "Done. Go back to Alice?"
User: "Yes"
Antoni: [transfers back]
```
✅ Should require explicit permission at each step

**Test Conversation 4: Shortcut Transfer**
```
User: "Let me talk to Antoni"
Rachel: [transfers directly]
Antoni: "What would you like me to create?"
User: "Write hello world"
Antoni: [executes] "Done. Go back?"
```
✅ Should transfer directly when explicitly requested

### Step 4: Verify No Feedback Loop

1. **Let agent speak through speakers**
2. **Observe microphone threshold**
3. **Agent should NOT respond to its own voice**
4. **Wait for your next input**

✅ No feedback loop
✅ Agent waits for your voice
✅ Natural conversation flow

---

## 4. Troubleshooting

### Problem: Agent Keeps Responding to Itself

**Cause:** Audio threshold too low, speaker output triggers microphone

**Solutions:**
1. **Increase threshold:** Try 0.04, 0.05, 0.06 in `.env`
2. **Reduce speaker volume**
3. **Move microphone closer to you**
4. **Move speakers farther from microphone**
5. **Use headphones** (best solution)

### Problem: Agent Doesn't Hear My Voice

**Cause:** Audio threshold too high, your voice doesn't trigger

**Solutions:**
1. **Decrease threshold:** Try 0.02, 0.01 in `.env`
2. **Speak louder**
3. **Move closer to microphone**
4. **Check microphone is selected in system settings**

### Problem: Agent Still Transfers Automatically

**Cause:** Dashboard prompts not updated

**Solutions:**
1. **Verify:** Each agent has the NEW prompt from `docs/agents/*.txt`
2. **Check:** System prompt in ElevenLabs dashboard matches file exactly
3. **Refresh:** Dashboard and restart conversation

### Problem: Agent Doesn't Transfer When Asked

**Cause:** Transfer tool not configured or prompt issue

**Solutions:**
1. **Check:** Transfer tool is enabled in ElevenLabs dashboard
2. **Verify:** Agent ID in transfer tool matches target agent
3. **Try explicit phrase:** "Transfer me to [name]" instead of "Yes"

---

## 5. Quick Reference

### Transfer Phrases
- "Transfer me to [agent]"
- "Let me talk to [agent]"
- "Connect me with [agent]"
- "Go back"
- "Return to [agent]"
- "Yes" (after transfer suggestion)

### Agent Names
- Rachel, Conversational Memory (entry point)
- Alice, Project Manager (coordinator)
- Adam, Desktop Worker (desktop automation)
- Antoni, Project Writer (code/docs)

### Audio Threshold Values
- `0.03` - Default (3% amplitude)
- `0.04-0.06` - Use if speaker triggers mic
- `0.01-0.02` - Use if voice doesn't trigger

### Files to Update
- `.env` - Audio threshold configuration
- ElevenLabs Dashboard - System prompts for all 4 agents

### Testing Commands
```bash
# Test audio threshold
python custom_audio_interface.py 0.03

# Run voice dialog
python voice_dialog_main.py
```

---

## Summary

**User-Controlled Transfers:**
- ✅ YOU decide when to transfer
- ✅ Explicit permission required
- ✅ Natural conversation flow

**Audio Feedback Prevention:**
- ✅ Threshold filtering blocks speaker output
- ✅ Only your voice triggers responses
- ✅ Configurable via `.env`

**Next Steps:**
1. Update all 4 agent prompts in ElevenLabs dashboard
2. Test audio threshold and adjust `.env`
3. Test user-controlled transfer flow
4. Enjoy natural voice conversations!
