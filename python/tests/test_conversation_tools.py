"""
Test Conversation Tools with Simulated Dialog

Tests the conversation capture and canvas integration:
1. Record simulated conversation messages
2. Save conversation summary to canvas
3. Extract key points
4. Create idea from discussion

This simulates the flow when a user talks with the voice AI
about ideas and wants to save insights to their canvas.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from tools.conversation_tools import (
    record_message,
    clear_conversation,
    get_conversation_transcript,
    get_conversation_summary,
    save_conversation,
    save_summary,
    extract_key_points,
    create_idea_from_discussion,
    add_to_current_bubble,
)

# Simulated conversation about building a "team of perspectives"
SIMULATED_CONVERSATION = [
    ("user", "I've been thinking about how to organize different viewpoints in my project"),
    ("agent", "That's interesting! Are you thinking about different stakeholder perspectives or different analytical lenses?"),
    ("user", "Both actually. I want to capture thoughts from different perspectives - like a product person, an engineer, and a designer all looking at the same problem"),
    ("agent", "A multi-perspective approach! That could help you spot blind spots. Would you want these perspectives to be automated agents or templates for your own thinking?"),
    ("user", "I think automated agents would be powerful. Each one could analyze an idea from their angle and add their thoughts to my canvas"),
    ("agent", "So a team of AI agents, each with a distinct viewpoint, contributing to a shared knowledge canvas. That's quite powerful for brainstorming!"),
    ("user", "Exactly! And they could build on each other's ideas. The engineer might see implementation challenges that the product person missed"),
    ("agent", "Cross-pollination of perspectives. You could even have them debate or synthesize their views into a final recommendation."),
    ("user", "Yes! That's the supermemory concept - all these different viewpoints get captured and synthesized over time"),
    ("agent", "A living document of collective intelligence. Would you like me to save this conversation to your canvas so you can build on it later?"),
]


def test_conversation_flow():
    """Run through the full conversation flow."""
    print("=" * 60)
    print("Testing Conversation Tools")
    print("=" * 60)
    print()

    # Clear any previous conversation
    clear_conversation()
    print("1. Cleared previous conversation buffer")
    print()

    # Record the simulated conversation
    print("2. Recording simulated conversation...")
    for speaker, text in SIMULATED_CONVERSATION:
        record_message(speaker, text)
        label = "You" if speaker == "user" else "AI"
        print(f"   [{label}]: {text[:60]}...")
    print()

    # Get transcript
    print("3. Full Transcript:")
    print("-" * 40)
    transcript = get_conversation_transcript()
    print(transcript[:500] + "..." if len(transcript) > 500 else transcript)
    print()

    # Get summary
    print("4. Conversation Summary (last 6 exchanges):")
    print("-" * 40)
    summary = get_conversation_summary()
    print(summary)
    print()

    # Test extract_key_points
    print("5. Extracting Key Points...")
    result = extract_key_points({})
    print(f"   Result: {result}")
    print()

    # Test save to bubble
    print("6. Saving conversation to 'Ideas' bubble...")
    result = save_conversation({
        "bubble_name": "Ideas",
        "title": "Multi-Perspective AI Team",
        "save_full": False  # Save summary, not full transcript
    })
    print(f"   Result: {result}")
    print()

    # Test create idea
    print("7. Creating idea from discussion...")
    result = create_idea_from_discussion({
        "title": "Perspective Team - AI agents with different viewpoints",
        "description": "Build a team of AI agents that each analyze ideas from different perspectives (product, engineering, design) and contribute to a shared canvas. Enables cross-pollination of ideas and synthesis into recommendations."
    })
    print(f"   Result: {result}")
    print()

    # Test extract and save key points
    print("8. Extracting and saving key points to 'Research Hub'...")
    result = extract_key_points({
        "bubble_name": "Research Hub"
    })
    print(f"   Result: {result}")
    print()

    print("=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("- Check vibemind.db for saved nodes")
    print("- Check canvas_nodes table for conversation content")
    print("- Check ideas table for new idea")


def test_add_to_current():
    """Test adding content to current bubble."""
    print()
    print("=" * 60)
    print("Testing Add to Current Bubble")
    print("=" * 60)
    print()

    # First record a message
    record_message("user", "This is a test note about supermemory architecture")

    # Add summary to current bubble
    result = add_to_current_bubble({
        "content_type": "note",
        "text": "Supermemory stores conversation context across sessions, enabling agents to build on previous discussions and maintain coherent long-term projects."
    })
    print(f"Add note result: {result}")
    print()


def check_database():
    """Check what was saved to the database."""
    print()
    print("=" * 60)
    print("Database Contents")
    print("=" * 60)
    print()

    from data import CanvasRepository, IdeasRepository

    # Check canvas nodes
    canvas_repo = CanvasRepository()
    nodes = canvas_repo.list_nodes(limit=10)
    print(f"Canvas Nodes ({len(nodes)} found):")
    for node in nodes:
        print(f"  - [{node.node_type}] {node.title}")
        if node.content:
            preview = node.content[:100] + "..." if len(node.content) > 100 else node.content
            print(f"    Content: {preview}")
        if node.metadata:
            print(f"    Metadata: {node.metadata}")
    print()

    # Check ideas
    ideas_repo = IdeasRepository()
    ideas = ideas_repo.list(limit=5)
    print(f"Ideas ({len(ideas)} found):")
    for idea in ideas:
        print(f"  - {idea.title}")
        if idea.description:
            preview = idea.description[:100] + "..." if len(idea.description) > 100 else idea.description
            print(f"    {preview}")
        print(f"    Tags: {idea.tags}, Source: {idea.source}")
    print()


if __name__ == "__main__":
    # Run the conversation flow test
    test_conversation_flow()

    # Test adding to current bubble
    test_add_to_current()

    # Show database contents
    check_database()
