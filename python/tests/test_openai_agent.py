"""
Simple test for OpenAI agent integration
Tests voice orchestrator with real AI responses
"""

import asyncio
import os


async def test_openai_agent():
    """Test the agent system with OpenAI"""
    print("=" * 60)
    print("VOICE DIALOG OPENAI INTEGRATION TEST")
    print("=" * 60)
    print()

    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY not found in environment")
        return

    print(f"[OK] API key found: {api_key[:20]}...")
    print()

    # Test simple orchestrator without full agent system
    from agents.voice_orchestrator import VoiceOrchestratorAgent

    print("Creating Voice Orchestrator with OpenAI client...")
    orchestrator = VoiceOrchestratorAgent(model_client=api_key)
    print(f"[OK] OpenAI client: {orchestrator.openai_client is not None}")
    print()

    # Test messages
    test_inputs = [
        "Hello! What can you help me with?",
        "Tell me a short joke about programming",
        "What is 2 + 2?",
    ]

    print("Running test cases...")
    print()

    for i, test_input in enumerate(test_inputs, 1):
        print(f"Test {i}: {test_input}")
        print('-' * 60)

        try:
            # Process input
            response = await orchestrator.process_message(test_input)
            print(f"Response: {response}")
            print()

        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            print()

        # Wait a bit between tests
        await asyncio.sleep(0.5)

    print("=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_openai_agent())
    except KeyboardInterrupt:
        print("\n[EXIT] Test interrupted")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
