#!/usr/bin/env python3
"""
Test script for ElevenLabs integration with IntentAnalysisTeam
"""

import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from swarm.elevenlabs_input import ElevenLabsInput, extract_elevenlabs_metadata, test_elevenlabs_metadata_extraction
from swarm.analysis import get_intent_analysis_team
from swarm.analysis.user_context import get_user_context_builder

async def test_elevenlabs_integration():
    """Test the complete ElevenLabs integration pipeline."""

    print("Testing ElevenLabs Integration")
    print("=" * 50)

    # 1. Test metadata extraction
    print("\n1. Testing ElevenLabs Metadata Extraction...")
    extracted, is_valid = test_elevenlabs_metadata_extraction()
    print(f"   ✓ Extraction: {'PASS' if is_valid else 'FAIL'}")

    # 2. Test IntentAnalysisTeam with ElevenLabs data
    print("\n2. Testing IntentAnalysisTeam Integration...")

    # Create analysis team
    analysis_team = get_intent_analysis_team()
    print("   ✓ AnalysisTeam created")

    # Create user context
    context_builder = get_user_context_builder()
    context = await context_builder.build("test_user", "test_session")
    print("   ✓ UserContext created")

    # Test analysis with ElevenLabs data
    test_input = "Erstelle eine neue Idee für ein Projekt"
    print(f"   Testing input: '{test_input}'")

    hypotheses = await analysis_team.analyze(test_input, context, extracted)
    print(f"   ✓ Generated {len(hypotheses)} hypotheses")

    for i, h in enumerate(hypotheses[:3]):
        print(f"     {i+1}. {h.event_type} ({h.confidence:.0%}) - {h.source}")

    # 3. Test without ElevenLabs data (fallback)
    print("\n3. Testing Fallback (without ElevenLabs)...")
    hypotheses_fallback = await analysis_team.analyze(test_input, context)
    print(f"   ✓ Generated {len(hypotheses_fallback)} hypotheses (fallback)")

    for i, h in enumerate(hypotheses_fallback[:3]):
        print(f"     {i+1}. {h.event_type} ({h.confidence:.0%}) - {h.source}")

    # 4. Compare results
    print("\n4. Comparison:")
    if hypotheses and hypotheses_fallback:
        with_elevenlabs = hypotheses[0].confidence
        without_elevenlabs = hypotheses_fallback[0].confidence
        improvement = with_elevenlabs - without_elevenlabs
        print(".2f"
        if improvement > 0:
            print("   🎉 ElevenLabs integration improves confidence!"
    print("\n✅ ElevenLabs Integration Test Complete!")

if __name__ == "__main__":
    asyncio.run(test_elevenlabs_integration())