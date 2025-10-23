# Voice Dialog Visual System - Complete Guide

## 🎉 What Was Built

A **fully integrated multi-agent voice assistant** with audio-reactive visual interface!

### Key Innovation
**Agent voices drive the visuals!** When agents speak via TTS, their audio frequencies directly control the starfield animation, creating a synchronized voice-visual experience.

## 🎯 System Architecture

```
User Voice Input
    ↓
Speech-to-Text (Google Speech Recognition)
    ↓
Voice Orchestrator Agent
    ↓
Specialized Agents (Desktop/Research/Code)
    ↓
Agent Response Text
    ↓
Text-to-Speech (ElevenLabs)
    ↓
TTS Audio → AudioAnalyzer → Starfield Animation! ✨
```

## 📦 Components

### 1. Agent System

**`agent_orchestrator.py`** - Main coordinator
- Manages agent lifecycle
- Routes requests to appropriate agents
- Handles conversation history
- Provides status callbacks

**`agents/voice_orchestrator.py`** - Entry point agent
- Receives all user requests
- Analyzes intent
- Delegates to specialists using handoffs pattern

**`agents/desktop_agent.py`** - Screen/Desktop operations
- Screenshot capture (pyautogui)
- OCR text recognition (planned)
- Window management

**`agents/research_agent.py`** - Information gathering
- Web search (planned integration)
- Documentation lookup
- Fact checking

**`agents/code_agent.py`** - Programming tasks
- Code generation
- Code analysis
- Debugging assistance

### 2. Voice Bridge

**`voice_bridge.py`** - Connects voice I/O with agents and visuals
- Speech-to-text (Google)
- Agent coordination
- Text-to-speech (ElevenLabs)
- **TTS audio streaming to visuals**

### 3. Visual Interface

**`voice_dialog_visual.py`** - Complete integrated system
- Transparent circular starfield
- Audio-reactive particles (500 stars)
- Moiré patterns (40 rings, 80 rays)
- Agent status colors
- Chat input with auto-expand
- Drag/resize interactions

**Original visual components:**
- `transparent_circle.py` - Base visual (standalone)
- `audio_analyzer.py` - FFT and frequency analysis

## 🎨 Agent Visual Feedback

Each agent has a unique color that affects the circle's appearance:

| Agent State | Color | When Active |
|------------|-------|-------------|
| **Idle** | Cyan | No activity |
| **Listening** | Green | Recording voice |
| **Thinking** | Purple | Processing request |
| **Speaking** | Orange | TTS active |
| **Desktop** | Blue | Desktop agent working |
| **Research** | Yellow | Research agent working |
| **Code** | Magenta | Code agent working |

## 🎹 Controls

### Keyboard
- **V** - Voice input (speak to the assistant)
- **Enter** - Send text from chat
- **Arrow Up** - Make window larger
- **Arrow Down** - Make window smaller
- **ESC** / **Q** - Exit

### Mouse
- **Left-click + drag** - Move window
- **Right-click corner + drag** - Resize window
- **Mouse wheel** - Resize (scroll up/down)

## 🚀 Running the System

### Demo Mode (No API Keys)

```bash
cd python
python voice_dialog_visual.py
```

**Demo mode features:**
- ✅ Visual interface works fully
- ✅ Agent system with handoffs works
- ✅ Simulated audio drives visuals
- ❌ No real TTS (text only)
- ❌ No voice input

### Full Mode (With API Keys)

```bash
# Set API keys
export ELEVENLABS_API_KEY="your_key"
export OPENAI_API_KEY="your_key"

# Run
python voice_dialog_visual.py
```

**Full mode features:**
- ✅ Everything in demo mode PLUS:
- ✅ Real speech-to-text
- ✅ Real TTS with agent voices
- ✅ TTS audio drives visual animation
- ✅ Full agent AI capabilities

## 🎤 Voice Interaction Flow

1. **Press V** - Start voice input
2. **Speak** - "Take a screenshot" or "Search for Python tutorials"
3. **Agent responds** - Voice Orchestrator analyzes and delegates
4. **Agent speaks** - TTS generates voice
5. **Visuals react** - Starfield animates to agent's voice frequencies!

## 🔧 Configuration

### Customize Agent Voices

The system now uses **ElevenLabs API v2** with the updated `eleven_multilingual_v2` model.

When calling speak in your code, use voice names:

```python
await voice_bridge.speak("Hello!", voice="Rachel")
# Available voices: Rachel, Domi, Bella, Antoni, Elli, Josh, Arnold, Adam, Sam
```

Voice names are automatically mapped to ElevenLabs voice IDs in `voice_bridge.py`:
- Rachel → `21m00Tcm4TlvDq8ikWAM`
- Domi → `AZnzlk1XvdvUeBnXmlld`
- Bella → `EXAVITQu4vr4xnSDxMaL`
- And 6 more premade voices...

You can also pass voice_id directly if using a custom cloned voice.

### Customize Visual Colors

Edit `voice_dialog_visual.py` - `agent_colors` dict:

```python
self.agent_colors = {
    "idle": (180, 0.7, 0.8),    # (Hue, Saturation, Value)
    "speaking": (30, 0.9, 0.9), # Orange - change hue (0-360)
}
```

### Adjust Animation Speed

In `voice_dialog_visual.py`:

```python
self.phase += audio.amplitude * 0.05  # Increase for faster animation
self.num_particles = 500  # More particles = denser starfield
```

## 📁 File Structure

```
voice_dialog/
├── python/
│   ├── voice_dialog_visual.py  ✨ MAIN - Run this!
│   ├── voice_bridge.py          Voice ↔ Agents ↔ Visuals
│   ├── agent_orchestrator.py    Agent coordinator
│   ├── agents/
│   │   ├── voice_orchestrator.py  Entry point agent
│   │   ├── desktop_agent.py       Desktop operations
│   │   ├── research_agent.py      Web search
│   │   └── code_agent.py          Programming
│   ├── audio_analyzer.py        FFT analysis
│   ├── transparent_circle.py    Original visual (standalone)
│   └── test_agents.py           Agent system test
└── VOICE_DIALOG_GUIDE.md       This file
```

## 🎯 Example Interactions

### Voice Commands

**Desktop tasks:**
- "Take a screenshot"
- "Capture my screen"
- "Show me what's on my screen"

**Research tasks:**
- "Search for Python async programming"
- "Find information about Autogen"
- "Look up React hooks documentation"

**Code tasks:**
- "Generate a function to calculate fibonacci"
- "Explain this code to me"
- "Help me debug this error"

**General:**
- "Hello! What can you do?"
- "Help me with..."

## 🔬 Audio-Visual Synchronization

The key innovation is **TTS audio → AudioAnalyzer → Visuals**:

### How It Works

1. **Agent generates text response** → `agent_orchestrator.py`
2. **Text → TTS audio stream** → `voice_bridge.py`
3. **Audio chunks analyzed** → `audio_analyzer.py`
   - FFT extracts frequency spectrum
   - Detects bass, mid, treble
   - Identifies beats
4. **Visual responds to frequencies**:
   - **Bass** → Ring pulsing
   - **Mid** → Color shifts
   - **Treble** → Ray length
   - **Beats** → Boundary pulse

Result: **Agent's voice visibly shapes the starfield!**

## 🚧 Future Enhancements

### Planned Features
- [ ] Real OCR implementation (pytesseract)
- [ ] Web search API integration
- [ ] LLM integration for actual code generation
- [ ] Voice activity detection (continuous listening)
- [ ] Multi-turn conversations with context
- [ ] Agent memory across sessions
- [ ] MCP tool integration
- [ ] Screen analysis with vision models

### Visual Enhancements
- [ ] Per-agent particle behaviors
- [ ] Agent "thinking" animation
- [ ] Tool execution visualization
- [ ] Conversation history display
- [ ] Agent name labels

## 💡 Tips

1. **For best visuals**: Use headphones or speakers for TTS audio to avoid feedback
2. **Performance**: Reduce `num_particles` (line ~152) if laggy
3. **Quiet mode**: Disable TTS audio output, keep visual updates
4. **Testing agents**: Use `test_agents.py` for quick agent testing without UI
5. **Customize**: All colors, speeds, sizes are easily adjustable

## 🐛 Troubleshooting

**"No microphone available"**
- Check microphone permissions
- Install PyAudio: `pip install pyaudio`

**"ElevenLabs error"**
- Check API key is set
- Verify internet connection
- Falls back to demo mode automatically

**Visual not updating**
- Check AudioAnalyzer is receiving chunks
- Verify audio buffer size (2048 samples)

**Agents not responding**
- Check agent_orchestrator initialization
- Verify voice_bridge is connected
- Look for error messages in console

## 📝 Credits

**Built with:**
- **Autogen** - Multi-agent framework (Microsoft)
- **ElevenLabs** - Text-to-speech
- **PyQt5** - GUI framework
- **NumPy** - Audio processing
- **SpeechRecognition** - Speech-to-text

**Design patterns:**
- Handoffs (Autogen/OpenAI Swarm)
- Sequential workflow
- Concurrent agents

---

🎉 **Enjoy your voice-controlled multi-agent visual assistant!** 🎉
