"""
MoireTracker v2 Agent-Team Integration für VibeMind

Dieses Paket enthält das vollständige MoireTracker v2 Agent-Team:
- OrchestratorV2: Event-driven Task-Koordination
- InteractionAgent: Desktop-Automation via PyAutoGUI
- ReasoningAgent: Task-Planung mit Vision
- VisionAgent: Element-Lokalisierung mit GPT-4o/Claude
- DataAnalystAgent: UI-Daten Strukturierung
- MonitorAgent: Bildschirm-Änderungserkennung

Verwendung:
    from moire import MoireBridge
    
    bridge = MoireBridge()
    await bridge.start()
    result = await bridge.execute_task("Öffne Word")
"""

from .bridge.moire_bridge import MoireBridge, get_moire_bridge

__version__ = "2.0.0"
__all__ = ["MoireBridge", "get_moire_bridge"]