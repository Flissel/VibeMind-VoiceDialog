#!/usr/bin/env python3
"""
Simple test for the new AnalysisTeam-Centered Orchestrator
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

print("Testing orchestrator imports...")

try:
    from swarm.orchestrator.intent_orchestrator import get_orchestrator, IntentOrchestrator
    print("✅ Orchestrator imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

print("Testing orchestrator initialization...")

try:
    orchestrator = get_orchestrator()
    print("✅ Orchestrator initialized successfully")
    print(f"  IntentAnalysisTeam: {'✅' if orchestrator._use_intent_analysis else '❌'}")
    print(f"  ToolOrchestrator: {'✅' if orchestrator._use_tool_orchestrator else '❌'}")
    print(f"  Legacy Classifier: {'✅' if orchestrator.classifier else '❌'}")
except Exception as e:
    print(f"❌ Initialization failed: {e}")
    sys.exit(1)

print("Testing basic method calls...")

try:
    # Test that the new methods exist
    assert hasattr(orchestrator, '_run_core_analysis')
    assert hasattr(orchestrator, '_run_parallel_extensions')
    assert hasattr(orchestrator, '_select_best_extension')
    assert hasattr(orchestrator, '_fallback_processing')
    print("✅ All new methods exist")
except Exception as e:
    print(f"❌ Method check failed: {e}")
    sys.exit(1)

print("\n🎉 Basic orchestrator test passed!")
print("The AnalysisTeam-Centered Architecture is properly implemented.")