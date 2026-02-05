#!/usr/bin/env python3
"""
Test script for Intra-Bubble Exploration Tools - Research Paper Generation

Tests the complete workflow:
1. Parse bubble content for paper sections
2. Generate requirements from sections
3. Optimize paper coherence
4. Generate complete research paper

Usage: python test_exploration_tools.py
"""

import asyncio
import json
import logging
from typing import Dict, Any

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv('../.env')
except ImportError:
    pass

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_exploration_tools():
    """Test that exploration tools are properly defined."""

    from swarm.tools.exploration_tools import get_exploration_tools

    tools = get_exploration_tools()

    print(f"Found {len(tools)} exploration tools:")
    print()

    for i, tool in enumerate(tools, 1):
        print(f"{i}. {tool['name']}")
        print(f"   Description: {tool['description']}")
        print(f"   Parameters: {len(tool.get('parameters', {}))} defined")
        print()

    # Test tool availability
    expected_tools = [
        "start_exploration",
        "parse_bubble_content_for_paper",
        "generate_requirements_from_sections",
        "optimize_paper_coherence",
        "generate_complete_research_paper",
        "stop_exploration",
        "get_exploration_status",
        "accept_connection",
        "reject_connection",
        "explore_deeper",
        "visualize_exploration",
        "respond_to_exploration_question",
        "set_exploration_direction",
    ]

    found_tools = [t['name'] for t in tools]
    missing = [t for t in expected_tools if t not in found_tools]

    if missing:
        print(f"WARNING: Missing tools: {missing}")
    else:
        print("All expected exploration tools are available")

    return len(missing) == 0

async def test_multiversum_bubble_parsing():
    """Test parsing the Multiversum bubble content with detailed logging."""
    print("=" * 80)
    print("TESTING INTRA-BUBBLE EXPLORATION - MULTIVERSUM BUBBLE")
    print("=" * 80)

    try:
        from swarm.tools.exploration_tools import parse_bubble_content_for_paper

        # Test 1: Parse bubble content with example Multiversum content
        print("\nSTEP 1: Parsing Bubble Content...")
        print("Using example Multiversum content...")

        # Example Multiversum content (since database is empty)
        multiversum_content = """
# Multiversum: Advanced AI Agent Orchestration Framework

## Abstract
Multiversum ist ein innovatives Framework für die Orchestrierung mehrerer KI-Agenten in einem gemeinsamen Arbeitsraum. Das System ermöglicht es Agenten, miteinander zu kommunizieren, Aufgaben zu koordinieren und gemeinsam komplexe Probleme zu lösen.

## Introduction
Die Entwicklung von KI-Systemen hat sich von einzelnen Agenten zu kooperativen Multi-Agenten-Systemen entwickelt. Multiversum adressiert die Herausforderungen bei der Koordination und Kommunikation zwischen verschiedenen Agenten.

## Methodology
Multiversum verwendet einen zentralen Event-Bus für die Kommunikation zwischen Agenten. Jeder Agent kann Nachrichten senden und empfangen, und das System stellt sicher, dass Nachrichten korrekt zugestellt werden.

## Results
Erste Tests zeigen, dass Multiversum die Koordination von bis zu 10 Agenten gleichzeitig ermöglicht. Die Latenz bei der Nachrichtenübermittlung liegt unter 50ms.

## Discussion
Das Framework bietet eine flexible Architektur für verschiedene Arten von KI-Agenten. Es kann für Forschung, Entwicklung und Produktion verwendet werden.

## Conclusion
Multiversum ist ein vielversprechender Ansatz für die Orchestrierung von KI-Agenten und bietet eine solide Basis für zukünftige Entwicklungen.
"""

        result = await parse_bubble_content_for_paper(content_text=multiversum_content)

        print(f"Result success: {result.get('success')}")

        if not result.get("success"):
            print(f"ERROR: Parsing failed: {result.get('message')}")
            return

        sections = result.get("sections", [])
        print(f"SUCCESS: Parsed {len(sections)} sections:")

        for i, section in enumerate(sections, 1):
            print(f"  {i}. {section.get('type', 'unknown')}: '{section.get('title', 'Unknown')}'")
            print(f"     Content length: {len(section.get('content', ''))} chars")
            print(f"     Confidence: {section.get('confidence', 0):.2f}")
            # Show first 100 chars of content
            content_preview = section.get('content', '')[:100].replace('\n', ' ')
            print(f"     Preview: {content_preview}...")
            print()

        # Test 2: Generate requirements from sections
        print("\n[STEP 2] Generating Requirements...")
        from swarm.tools.exploration_tools import generate_requirements_from_sections

        req_result = await generate_requirements_from_sections(sections)
        print(f"[INFO] Requirements generation success: {req_result.get('success')}")

        if req_result.get("success"):
            requirements = req_result.get("requirements", {})
            req_count = len(requirements.get("requirements", []))
            print(f"[OK] Generated requirements document with {req_count} requirements")
            print(f"   Title: {requirements.get('title', 'Unknown')}")

            # Show first 2 requirements
            reqs = requirements.get("requirements", [])[:2]
            for i, req in enumerate(reqs, 1):
                print(f"   Req {i}: {req.get('title', 'Unknown')} ({req.get('priority', 'unknown')})")
        else:
            print(f"[ERROR] Requirements generation failed: {req_result.get('message')}")

        # Test 3: Optimize paper coherence
        print("\n[STEP 3] Optimizing Paper Coherence...")
        from swarm.tools.exploration_tools import optimize_paper_coherence

        coherence_result = await optimize_paper_coherence(sections)
        print(f"[INFO] Coherence optimization success: {coherence_result.get('success')}")

        if coherence_result.get("success"):
            optimized_sections = coherence_result.get("optimized_sections", [])
            coherence_score = coherence_result.get("coherence_score", 0)
            print(f"[OK] Optimized coherence. Score: {coherence_score:.2f}")
            print(f"   Optimized {len(optimized_sections)} sections")
        else:
            print(f"[ERROR] Coherence optimization failed: {coherence_result.get('message')}")

        # Test 4: Generate complete research paper
        print("\n[STEP 4] Generating Complete Research Paper...")
        from swarm.tools.exploration_tools import generate_complete_research_paper

        paper_result = await generate_complete_research_paper(
            sections,
            paper_title="Multiversum: Advanced AI Agent Orchestration Framework",
            target_journal="general",
            citation_style="APA"
        )

        print(f"[INFO] Paper generation success: {paper_result.get('success')}")

        if paper_result.get("success"):
            paper = paper_result.get("paper", {})
            quality = paper_result.get("quality_metrics", {})
            print("[OK] Research paper generated successfully!")
            print(f"   Title: {paper.get('title', 'Unknown')}")
            print(f"   Word count: {paper_result.get('word_count', 0)}")
            print(f"   Sections: {paper_result.get('section_count', 0)}")
            print(f"   Quality Score: {quality.get('overall_score', 0):.1f}/10")
            print(f"   Scientific Rigor: {quality.get('scientific_rigor', 0)}/10")
            print(f"   Clarity: {quality.get('clarity', 0)}/10")
            print(f"   Completeness: {quality.get('completeness', 0)}/10")
        else:
            print(f"[ERROR] Paper generation failed: {paper_result.get('message')}")

        print("\n" + "=" * 80)
        print("INTRA-BUBBLE EXPLORATION TEST COMPLETED!")
        print("=" * 80)

        # Save results for inspection
        test_results = {
            "parsing": result,
            "requirements": req_result if 'req_result' in locals() else None,
            "coherence": coherence_result if 'coherence_result' in locals() else None,
            "paper": paper_result if 'paper_result' in locals() else None
        }

        with open("test_output/exploration_test_results.json", "w", encoding="utf-8") as f:
            json.dump(test_results, f, indent=2, ensure_ascii=False)

        print("[INFO] Results saved to test_output/exploration_test_results.json")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"[ERROR] Test failed with error: {e}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "full":
        # Run full test with Multiversum bubble
        print("Running full Intra-Bubble Exploration test...")
        asyncio.run(test_multiversum_bubble_parsing())
    else:
        # Run basic tools test
        print("Exploration Tools Test")
        print("=" * 25)
        success = test_exploration_tools()
        print(f"\nTest result: {'PASS' if success else 'FAIL'}")
        print("\n[TIP] Run 'python test_exploration_tools.py full' for complete workflow test")