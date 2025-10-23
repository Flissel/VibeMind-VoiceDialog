"""
Voice Orchestrator Agent - Entry point for voice dialog system
Implements handoffs pattern to delegate to specialized agents
"""

from typing import List, Dict, Any, Optional
import os
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("[VoiceOrchestrator] OpenAI library not available")


class VoiceOrchestratorAgent:
    """
    Main orchestrator agent that receives voice/text input
    and delegates to specialized agents using handoffs pattern
    """

    def __init__(self, model_client: Optional[Any] = None, name: str = "VoiceOrchestrator"):
        """
        Initialize the Voice Orchestrator Agent

        Args:
            model_client: OpenAI model client for LLM (can be API key string or client object)
            name: Agent name
        """
        self.name = name
        self.specialized_agents: Dict[str, Any] = {}
        self.status_callback = None  # Callback for status updates (Phase 1)

        # Initialize OpenAI client
        self.openai_client = None
        if OPENAI_AVAILABLE:
            if isinstance(model_client, str):
                # model_client is an API key
                self.openai_client = OpenAI(api_key=model_client)
            elif model_client is None:
                # Try to get from environment
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self.openai_client = OpenAI(api_key=api_key)
            else:
                # model_client is already a client object
                self.openai_client = model_client

        # System prompt for the orchestrator
        self.system_message = """You are a voice-controlled AI assistant orchestrator.

Your role is to:
1. Understand user requests
2. ALWAYS delegate tasks to appropriate specialized agents:
   - Desktop Agent: For ANYTHING related to desktop (checking apps/icons, finding programs, Docker, Chrome, etc.), screen capture, OCR, window management
   - Research Agent: For web search, information gathering
   - Code Agent: For code generation, analysis, and debugging

IMPORTANT: When user asks about desktop content or applications (like "is Docker on my desktop", "what's on my desktop", "find Chrome"), you MUST call delegate_to_desktop, NOT answer directly.

For simple greetings or chitchat, you can respond directly. For everything else, delegate to the specialized agent.

Always be helpful, concise, and clear in your communication."""

    def register_specialized_agent(self, agent_type: str, agent: Any):
        """
        Register a specialized agent for handoffs

        Args:
            agent_type: Type of agent (desktop, research, code, etc.)
            agent: The agent instance
        """
        self.specialized_agents[agent_type] = agent
        print(f"[{self.name}] Registered {agent_type} agent")

    def set_status_callback(self, callback):
        """
        Set callback for status updates (Phase 1)

        Args:
            callback: Function(status: str, message: str, agent: str) to call on status change
        """
        self.status_callback = callback

    def _update_status(self, status: str, message: str, agent: str = "general"):
        """
        Update status and notify callback (Phase 1)

        Args:
            status: Status string (idle, listening, thinking, speaking)
            message: Status message
            agent: Active agent name (general, desktop, research, code)
        """
        if self.status_callback:
            self.status_callback(status, message, agent)

    def get_delegate_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of delegate tools for handoffs

        Returns:
            List of tool definitions for delegating to agents
        """
        tools = []

        # Desktop agent delegate
        if "desktop" in self.specialized_agents:
            tools.append({
                "type": "function",
                "function": {
                    "name": "delegate_to_desktop",
                    "description": "Delegate task to Desktop Agent for: desktop icons/applications scanning, checking what's on desktop, finding apps/files, screen capture, OCR, window management, or visual analysis. Use for ANY question about desktop content or applications.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "The task to delegate to the desktop agent"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context from the conversation"
                            }
                        },
                        "required": ["task"]
                    }
                }
            })

        # Research agent delegate
        if "research" in self.specialized_agents:
            tools.append({
                "type": "function",
                "function": {
                    "name": "delegate_to_research",
                    "description": "Delegate task to Research Agent for web search, documentation lookup, or information gathering",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "The research task or question"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context from the conversation"
                            }
                        },
                        "required": ["task"]
                    }
                }
            })

        # Code agent delegate
        if "code" in self.specialized_agents:
            tools.append({
                "type": "function",
                "function": {
                    "name": "delegate_to_code",
                    "description": "Delegate task to Code Agent for code generation, analysis, debugging, or technical questions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "The coding task or question"
                            },
                            "language": {
                                "type": "string",
                                "description": "Programming language (if relevant)"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context from the conversation"
                            }
                        },
                        "required": ["task"]
                    }
                }
            })

        return tools

    async def process_message(self, message: str, context: Optional[List[Dict]] = None) -> str:
        """
        Process incoming message and route to appropriate agent

        Args:
            message: User's message
            context: Conversation context

        Returns:
            Response string
        """
        # Use OpenAI if available, otherwise fallback to keyword matching
        if self.openai_client:
            return await self._process_with_llm(message, context)
        else:
            return await self._process_with_keywords(message)

    async def _process_with_llm(self, message: str, context: Optional[List[Dict]] = None) -> str:
        """Process message using OpenAI LLM with tool calling"""
        try:
            # Build conversation history
            messages = [{"role": "system", "content": self.system_message}]

            # Add context if available
            if context:
                for msg in context[-5:]:  # Last 5 messages for context
                    messages.append(msg)

            # Add current message
            messages.append({"role": "user", "content": message})

            # Get available tools
            tools = self.get_delegate_tools()

            # Call OpenAI with tools
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Using faster model for responsiveness
                messages=messages,
                tools=tools if tools else None,  # Pass tools for delegation
                temperature=0.7,
                max_tokens=500
            )

            assistant_message = response.choices[0].message

            # Check if tool calls were made
            if assistant_message.tool_calls:
                print(f"[{self.name}] Tool calls detected: {len(assistant_message.tool_calls)}")

                # Process each tool call
                for tool_call in assistant_message.tool_calls:
                    import json
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    print(f"[{self.name}] Calling {function_name} with args: {function_args}")

                    # Delegate to appropriate agent
                    if function_name == "delegate_to_desktop":
                        # Phase 1: Notify UI that desktop agent is active
                        self._update_status("thinking", "Scanning desktop...", "desktop")
                        agent = self.specialized_agents.get("desktop")
                        if agent:
                            result = await agent.process_task(
                                function_args.get("task"),
                                function_args.get("context")
                            )
                            return result

                    elif function_name == "delegate_to_research":
                        # Phase 1: Notify UI that research agent is active
                        self._update_status("thinking", "Researching...", "research")
                        agent = self.specialized_agents.get("research")
                        if agent:
                            result = await agent.process_task(
                                function_args.get("task"),
                                function_args.get("context")
                            )
                            return result

                    elif function_name == "delegate_to_code":
                        # Phase 1: Notify UI that code agent is active
                        self._update_status("thinking", "Analyzing code...", "code")

                        agent = self.specialized_agents.get("code")
                        if agent:
                            result = await agent.process_task(
                                function_args.get("task"),
                                function_args.get("context")
                            )
                            return result

            # No tool calls - return direct response
            return assistant_message.content or "I'm here to help!"

        except Exception as e:
            print(f"[{self.name}] Error calling OpenAI: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to keyword matching
            return await self._process_with_keywords(message)

    async def _process_with_keywords(self, message: str) -> str:
        """Fallback keyword-based processing"""
        response_parts = [f"[{self.name}] Received: {message}"]

        # Simple routing logic for demo
        message_lower = message.lower()

        if any(word in message_lower for word in ["screenshot", "screen", "window", "ocr", "capture"]):
            if "desktop" in self.specialized_agents:
                response_parts.append("🖥️ Delegating to Desktop Agent...")
            else:
                response_parts.append("Desktop Agent not available")

        elif any(word in message_lower for word in ["search", "find", "research", "look up", "information"]):
            if "research" in self.specialized_agents:
                response_parts.append("🔍 Delegating to Research Agent...")
            else:
                response_parts.append("Research Agent not available")

        elif any(word in message_lower for word in ["code", "program", "function", "debug", "script"]):
            if "code" in self.specialized_agents:
                response_parts.append("💻 Delegating to Code Agent...")
            else:
                response_parts.append("Code Agent not available")

        else:
            response_parts.append("I can help with that! Available agents:")
            response_parts.append("- Desktop (screenshots, OCR)")
            response_parts.append("- Research (web search)")
            response_parts.append("- Code (programming)")

        return "\n".join(response_parts)

    def get_system_message(self) -> str:
        """Get the system message for this agent"""
        return self.system_message
