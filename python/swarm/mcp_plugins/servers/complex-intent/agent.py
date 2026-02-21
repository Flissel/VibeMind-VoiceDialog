import asyncio
import json
import os
import sys
import time

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Load .env
try:
    import dotenv
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '.env')
    dotenv.load_dotenv(dotenv_path=env_path)
except Exception:
    pass

# Autogen imports
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_core.model_context import BufferedChatCompletionContext
from pydantic import BaseModel

# Shared module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
from event_server import EventServer, start_ui_server
from constants import *
from model_utils import get_model_client
from model_init import init_model_client as shared_init_model_client
from logging_utils import setup_logging
from conversation_logger import ConversationLogger, SenseCategory, ThinkingLog, ToolCall, ToolResult


class ComplexIntentConfig(BaseModel):
    session_id: str
    name: str
    model: str
    task: str


async def run_complex_intent_agent(config: ComplexIntentConfig):
    """Complex intent processing agent using Society of Mind pattern."""
    logger = setup_logging(f"complex_intent_agent_{config.session_id}")
    event_server = EventServer(session_id=config.session_id, tool_name="complex_intent")

    # Initialize ConversationLogger for ML-ready conversation logs
    try:
        conv_logger = ConversationLogger(
            session_id=config.session_id,
            tool_name="complex_intent",
            sense_category=SenseCategory.COGNITIVE
        )
    except Exception as e:
        logger.warning(f"Could not initialize ConversationLogger: {e}")
        conv_logger = None

    try:
        # Start the UI server with event broadcasting
        httpd, thread, host, port = start_ui_server(
            event_server,
            host="127.0.0.1",
            port=0,  # Dynamic port assignment
            tool_name="complex_intent"
        )
        logger.info(f"UI server started on {host}:{port}")

        # Announce session (print to stdout for session manager to capture)
        announce_data = {
            "session_id": config.session_id,
            "host": host,
            "port": port,
            "ui_url": f"http://{host}:{port}/"
        }
        print(f"SESSION_ANNOUNCE {json.dumps(announce_data)}", flush=True)
        event_server.broadcast(MCP_EVENT_SESSION_ANNOUNCE, announce_data)

        # Log session start for ML dataset
        if conv_logger:
            conv_logger.log_session_start(config.task, config.model)

        # Get model client (use shared for OpenRouter compatibility)
        model_client = shared_init_model_client("complex_intent", config.task)
        logger.info(f"Model initialized: {config.model}")

        # Create Multi-Agent Team for Complex Intent Processing
        print(f"Creating complex intent team for task: {config.task}", file=sys.stderr)
        team = await _create_complex_intent_team(model_client, event_server)

        # Send running status
        event_server.broadcast("log", f"Starting complex intent processing: {config.task}")
        event_server.broadcast("status", SESSION_STATE_RUNNING)

        # Run task through the multi-agent team
        result = await team.run(task=config.task)

        # Send completion
        result_text = str(result.messages[-1].content) if result.messages else "Complex intent processing completed"
        event_server.broadcast("log", f"Result: {result_text}")
        event_server.broadcast("status", SESSION_STATE_STOPPED)

        # Log conversation turn for ML dataset
        if conv_logger:
            conv_logger.log_conversation_turn(
                agent="ComplexIntentTeam",
                agent_response=result_text,
                final_response=result_text
            )

        # Send final result event for modal display
        event_server.broadcast("agent.completion", {
            "status": "success",
            "content": result_text,
            "tool": "complex_intent",
            "timestamp": time.time()
        })

        logger.info("Complex intent processing completed")

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        event_server.broadcast("error", str(e))
        event_server.broadcast("status", SESSION_STATE_ERROR)
        raise
    finally:
        # Keep server running briefly so events can be consumed
        await asyncio.sleep(2)
        httpd.shutdown()


async def _load_swarm_tools():
    """Load tools from the Swarm system for complex intent processing."""
    tools = []

    try:
        # Load bubble tools
        from spaces.ideas.adapted.bubble_tools import BUBBLE_TOOLS
        tools.extend(BUBBLE_TOOLS)
        print(f"Loaded {len(BUBBLE_TOOLS)} bubble tools", file=sys.stderr)
    except ImportError as e:
        print(f"Warning: Could not load bubble tools: {e}", file=sys.stderr)

    try:
        # Load idea tools
        from spaces.ideas.adapted.idea_tools import IDEA_TOOLS
        tools.extend(IDEA_TOOLS)
        print(f"Loaded {len(IDEA_TOOLS)} idea tools", file=sys.stderr)
    except ImportError as e:
        print(f"Warning: Could not load idea tools: {e}", file=sys.stderr)

    print(f"Total tools loaded: {len(tools)}", file=sys.stderr)
    return tools


async def _create_complex_intent_team(model_client, event_server):
    """Create the multi-agent team for complex intent processing."""

    # Load tools for the workflow agent
    swarm_tools = await _load_swarm_tools()

    # Intent Analysis Agent - Breaks down complex requests
    intent_analyzer = AssistantAgent(
        name="IntentAnalyzer",
        model_client=model_client,
        system_message="""You are an expert at analyzing complex user requests and breaking them down into actionable steps.

Your task is to:
1. Understand the user's complex intent (e.g., 'formatiere die Ideen zu Tabellenansicht mit Fokus auf Futures und Content')
2. Identify the main action (format, filter, sort, etc.)
3. Extract specific requirements (Futures, Content, Tabellenansicht)
4. Break down into sequential tool calls
5. Pass the analysis to the WorkflowAgent

Be thorough but concise. Focus on actionable insights.

When you have analyzed the intent, say "ANALYSIS COMPLETE" and provide your breakdown.""",
    )

    # Workflow Agent - Executes the sequence of actions
    workflow_agent = AssistantAgent(
        name="WorkflowAgent",
        model_client=model_client,
        system_message="""You are a workflow execution specialist. You receive analyzed intents from the IntentAnalyzer and execute them using available tools.

Available tools for idea/bubble management:
- list_bubbles: List all bubbles/spaces
- enter_bubble: Enter a specific bubble/space
- list_ideas: List ideas in current space
- find_idea: Search for specific ideas
- update_idea: Modify existing ideas
- create_idea: Create new ideas

Your task is to:
1. Receive the intent analysis from IntentAnalyzer
2. Execute the appropriate sequence of tool calls
3. Format results clearly and structured
4. Validate that all requirements are met

Execute tools step by step and provide clear, structured results.
When you have completed the workflow, say "WORKFLOW COMPLETED" and summarize the results.""",
        tools=swarm_tools
    )

    # QA Validator - Ensures quality and completeness
    qa_validator = AssistantAgent(
        name="QAValidator",
        model_client=model_client,
        system_message="""You are a quality assurance specialist for complex intent processing.

Your task is to:
1. Review the results from the WorkflowAgent
2. Verify that all user requirements were addressed
3. Check for completeness and accuracy
4. Ensure the original complex request was fully satisfied
5. Provide final validation

Compare the results against the original user request and confirm everything was handled properly.
When validation is complete, say "VALIDATION COMPLETED" and provide your assessment.""",
    )

    # Create the team with round-robin chat
    team = RoundRobinGroupChat(
        participants=[intent_analyzer, workflow_agent, qa_validator],
        termination_condition=TextMentionTermination("VALIDATION COMPLETED"),
        max_turns=15  # Allow more turns for complex workflows
    )

    return team


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--session-id', required=False)
    parser.add_argument('--name', default='complex-intent-session')
    parser.add_argument('--model', default='openai/gpt-4o-mini')
    parser.add_argument('--task', default='Analyze: formatiere die Ideen zu Tabellenansicht mit Fokus auf Futures und Content')
    parser.add_argument('config_json', nargs='?')
    args = parser.parse_args()

    try:
        if args.config_json:
            config_dict = json.loads(args.config_json)
        elif args.session_id:
            config_dict = {
                'session_id': args.session_id,
                'name': args.name,
                'model': args.model,
                'task': args.task
            }
        else:
            print(json.dumps({"error": "Missing session config"}), file=sys.stderr)
            sys.exit(1)

        config = ComplexIntentConfig(**config_dict)
        await run_complex_intent_agent(config)

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())