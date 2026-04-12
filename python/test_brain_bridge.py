"""Quick integration test for BrainOpenFangBridge pipeline."""
import asyncio
import sys
from pathlib import Path

# Mirror electron_backend.py: add vibemind-os root to sys.path for 'spaces', 'brain'
_vibemind_root = str(Path(__file__).parent.parent.parent)
if _vibemind_root not in sys.path:
    sys.path.insert(0, _vibemind_root)

# Load .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

def main():
    # Test 1: ContextAssembler
    print("=== Test 1: ContextAssembler ===")
    from swarm.routing.context_assembler import ContextAssembler, WorkspaceContext
    assembler = ContextAssembler()
    ctx = assembler.assemble()
    print(f"  WorkspaceContext: space={ctx.current_space}, bubble={ctx.current_bubble}, ideas={ctx.idea_count}")
    print(f"  Brain prefix: \"{ContextAssembler.to_brain_prefix(ctx)}\"")

    mock_ctx = WorkspaceContext(
        current_space="coding",
        current_bubble="Backend Refactor",
        idea_count=7,
        idea_titles=["API Design", "Auth Flow", "DB Schema"],
        active_task_count=1,
        recent_intents=["code.generate", "idea.create"],
        user_habits="top intents: idea.create (32x), bubble.enter (28x)",
        conversation_turns=[
            {"speaker": "user", "text": "Erstelle eine Idee"},
            {"speaker": "rachel", "text": "Idee erstellt"},
        ],
    )
    print(f"  Brain prefix (mock): \"{ContextAssembler.to_brain_prefix(mock_ctx)}\"")
    print(f"  Brain context dict: {ContextAssembler.to_brain_context_dict(mock_ctx)}")
    print()
    print("  OpenFang block:")
    for line in ContextAssembler.to_openfang_block(mock_ctx).split("\n"):
        print(f"    {line}")
    print("  OK")

    # Test 2: BrainOpenFangBridge
    print()
    print("=== Test 2: BrainOpenFangBridge ===")
    from swarm.routing.brain_openfang_bridge import BrainOpenFangBridge, SPACE_AGENT_MAP
    bridge = BrainOpenFangBridge()
    print(f"  Brain URL: {bridge._brain_url}")
    print(f"  OpenFang URL: {bridge._openfang_url}")
    print(f"  Space mappings: {len(bridge._space_map)}")
    for space, agent in sorted(bridge._space_map.items()):
        print(f"    {space:15s} -> {agent}")
    print("  OK")

    # Test 3: Brain reachability
    print()
    print("=== Test 3: Brain reachability ===")
    import aiohttp

    async def check_brain():
        try:
            timeout = aiohttp.ClientTimeout(total=2.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("http://localhost:5000/api/cortex/route/stats") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"  Brain ONLINE: {data}")
                        return True
                    else:
                        print(f"  Brain returned {resp.status}")
                        return False
        except Exception as e:
            print(f"  Brain OFFLINE: {type(e).__name__}")
            return False

    brain_ok = asyncio.run(check_brain())

    # Test 4: OpenFang reachability
    print()
    print("=== Test 4: OpenFang reachability ===")

    async def check_openfang():
        try:
            timeout = aiohttp.ClientTimeout(total=2.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("http://localhost:4200/api/health") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"  OpenFang ONLINE: {data}")
                        return True
                    else:
                        print(f"  OpenFang returned {resp.status}")
                        return False
        except Exception as e:
            print(f"  OpenFang OFFLINE: {type(e).__name__}")
            return False

    openfang_ok = asyncio.run(check_openfang())

    # Test 5: Full pipeline (if both online)
    if brain_ok and openfang_ok:
        print()
        print("=== Test 5: Full pipeline ===")

        async def test_pipeline():
            result = await bridge.execute(
                intent_text="Erstelle eine Idee fuer API Design",
                context=None,
                pre_classification="idea.create",
            )
            if result:
                print(f"  event_type: {result.event_type}")
                print(f"  stream: {result.stream}")
                print(f"  response: {result.response_hint[:100]}...")
                print(f"  error: {result.error}")
                return True
            else:
                print("  Bridge returned None (fell through)")
                return False

        pipeline_ok = asyncio.run(test_pipeline())
    else:
        pipeline_ok = False

    # Summary
    print()
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"  ContextAssembler:    OK")
    print(f"  BrainOpenFangBridge: OK")
    print(f"  Brain server:        {'ONLINE' if brain_ok else 'OFFLINE'}")
    print(f"  OpenFang daemon:     {'ONLINE' if openfang_ok else 'OFFLINE'}")
    if brain_ok and openfang_ok:
        print(f"  Full pipeline:       {'OK' if pipeline_ok else 'FAILED'}")
    print()
    if not brain_ok:
        print("  Start Brain:   cd brain/the_brain && python -m web.brain_server")
    if not openfang_ok:
        print("  Start OpenFang: openfang start")
    if brain_ok and openfang_ok:
        print("  Pipeline READY")


if __name__ == "__main__":
    main()
