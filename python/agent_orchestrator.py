"""
Voice Dialog Agent Orchestrator
Manages Autogen runtime and coordinates multi-agent interactions
"""

import sys
import asyncio
from typing import Optional, Callable, Dict, Any
from tools.moire_service import MoireTrackerService


class AgentOrchestrator:
    """
    Orchestrates multi-agent system with voice/visual interface integration
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """
        Initialize the agent orchestrator

        Args:
            api_key: OpenAI API key
            model: Model to use for agents
        """
        self.api_key = api_key
        self.model = model
        self.agents: Dict[str, Any] = {}
        self.response_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None

        # Agent state
        self.current_agent = None
        self.conversation_history = []

        # MoireTracker service manager
        self.moire_service = MoireTrackerService()

    async def initialize(self):
        """Initialize the agent system"""
        print("[ORCHESTRATOR] Initializing agent system...")

        # Auto-start MoireTracker if enabled in config
        if self.moire_service.config.auto_start and not self.moire_service.is_running():
            print("[ORCHESTRATOR] Auto-starting MoireTracker (silent mode)...")
            if self._start_moire_silent():
                print("[ORCHESTRATOR] [OK] MoireTracker auto-started successfully")
            else:
                print("[ORCHESTRATOR] [WARN] Auto-start failed, trying to connect to existing instance...")

        # Check if MoireTracker is running (works for both auto-start and manual)
        print("[ORCHESTRATOR] Checking for MoireTracker service...")
        if self.moire_service.is_running():
            print("[ORCHESTRATOR] [OK] MoireTracker service detected (enhanced mode)")
        else:
            print("[ORCHESTRATOR] [WARN] MoireTracker not running - start it manually for desktop features")
            print("[ORCHESTRATOR]        Or click the circle to enable auto-start")
            print("[ORCHESTRATOR]        Running in basic mode (no desktop agent)")

        # For demo mode, we don't need full Autogen runtime
        # Just register our custom agents
        model_client = self.api_key if self.api_key else None
        if self.api_key:
            print(f"[ORCHESTRATOR] Using OpenAI model: {self.model}")
            print("[ORCHESTRATOR] API key configured - agents will have AI capabilities")
        else:
            print("[ORCHESTRATOR] Running in demo mode (no API key)")

        # Register agents
        await self._register_agents(model_client)

        print("[ORCHESTRATOR] Agent system initialized!")

    async def _register_agents(self, model_client):
        """Register all agents with the runtime"""
        from agents.voice_orchestrator import VoiceOrchestratorAgent
        from agents.desktop_agent import DesktopAgent
        from agents.research_agent import ResearchAgent
        from agents.code_agent import CodeAgent

        # Create voice orchestrator
        self.voice_orchestrator = VoiceOrchestratorAgent(model_client)
        self.agents["orchestrator"] = self.voice_orchestrator

        # Create specialized agents
        self.desktop_agent = DesktopAgent()
        self.research_agent = ResearchAgent()
        self.code_agent = CodeAgent()

        # Register specialized agents with orchestrator
        self.voice_orchestrator.register_specialized_agent("desktop", self.desktop_agent)
        self.voice_orchestrator.register_specialized_agent("research", self.research_agent)
        self.voice_orchestrator.register_specialized_agent("code", self.code_agent)

        self.agents["desktop"] = self.desktop_agent
        self.agents["research"] = self.research_agent
        self.agents["code"] = self.code_agent

        print(f"[ORCHESTRATOR] Registered {len(self.agents)} agents")

    async def process_user_input(self, text: str) -> str:
        """
        Process user input through the agent system

        Args:
            text: User's text input

        Returns:
            Agent's response
        """
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": text})

        # Update status
        if self.status_callback:
            self.status_callback("thinking", "Processing your request...")

        # Route through voice orchestrator
        response = await self.voice_orchestrator.process_message(text, self.conversation_history)

        # Check if we need to delegate to a specialized agent
        text_lower = text.lower()

        if any(word in text_lower for word in ["screenshot", "screen", "window", "ocr", "capture"]):
            if self.status_callback:
                self.status_callback("working", "Desktop Agent working...")
            delegate_response = await self.desktop_agent.process_task(text)
            response += "\n\n" + delegate_response

        elif any(word in text_lower for word in ["search", "find", "research", "look up"]):
            if self.status_callback:
                self.status_callback("working", "Research Agent working...")
            delegate_response = await self.research_agent.process_task(text)
            response += "\n\n" + delegate_response

        elif any(word in text_lower for word in ["code", "program", "function", "debug"]):
            if self.status_callback:
                self.status_callback("working", "Code Agent working...")
            delegate_response = await self.code_agent.process_task(text)
            response += "\n\n" + delegate_response

        self.conversation_history.append({"role": "assistant", "content": response})

        if self.status_callback:
            self.status_callback("idle", "")

        return response

    def set_response_callback(self, callback: Callable):
        """
        Set callback for agent responses

        Args:
            callback: Function to call when agent responds
        """
        self.response_callback = callback

    def set_status_callback(self, callback: Callable):
        """
        Set callback for status updates

        Args:
            callback: Function to call with status updates (state, message)
        """
        self.status_callback = callback

    def _start_moire_silent(self) -> bool:
        """
        Start MoireTracker with output suppression to avoid Unicode encoding issues

        Returns:
            True if started successfully
        """
        try:
            import subprocess
            import time

            exe_path = self.moire_service.moire_exe
            if not exe_path.exists():
                return False

            # Start with output suppression (no Unicode issues!)
            self.moire_service.process = subprocess.Popen(
                [str(exe_path)],
                cwd=str(self.moire_service.moire_path),
                stdout=subprocess.DEVNULL,  # Suppress output
                stderr=subprocess.DEVNULL,  # Suppress output
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            # Wait for initialization (7 seconds for shared memory + desktop scan)
            time.sleep(7)

            # Check if process started successfully
            if not self.moire_service.is_running():
                return False

            # Generate and store IPC auth token (if enabled)
            if self.moire_service.auth_manager:
                print("[ORCHESTRATOR] Generating IPC authentication token...")
                self.moire_service.auth_token = self.moire_service.auth_manager.generate_and_store_token()
                if self.moire_service.auth_token:
                    print("[ORCHESTRATOR] IPC token generated and stored successfully")
                else:
                    print("[ORCHESTRATOR] [WARN] Failed to generate IPC token")

            return True
        except Exception as e:
            print(f"[ORCHESTRATOR] Auto-start error: {e}")
            return False

    async def shutdown(self):
        """Shutdown the agent system"""
        print("[ORCHESTRATOR] Shutting down agent system...")

        # Stop MoireTracker only if we auto-started it
        if self.moire_service.config.auto_start and self.moire_service.process:
            print("[ORCHESTRATOR] Stopping auto-started MoireTracker...")
            self.moire_service.stop()
        else:
            print("[ORCHESTRATOR] MoireTracker left running (manually managed)")

        print("[ORCHESTRATOR] Agent system shut down")


# Global orchestrator instance
_orchestrator: Optional[AgentOrchestrator] = None


async def get_orchestrator(api_key: Optional[str] = None) -> AgentOrchestrator:
    """
    Get or create the global orchestrator instance

    Args:
        api_key: OpenAI API key (if not provided, will check OPENAI_API_KEY environment variable)

    Returns:
        AgentOrchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        # If no API key provided, try to get from environment
        if api_key is None:
            import os
            api_key = os.getenv("OPENAI_API_KEY")

        _orchestrator = AgentOrchestrator(api_key=api_key)
        await _orchestrator.initialize()
    return _orchestrator
