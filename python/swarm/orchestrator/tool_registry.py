"""
Tool Registry - Extracted tool loading logic for synchronous fallback mode.

Loads all tool executors (event_type -> callable) used by IntentOrchestrator
when running in synchronous fallback mode (no Redis) or for multi-step execution.

Each _load_*() method uses lazy imports with try/except to gracefully degrade
when optional dependencies are missing.
"""

import asyncio
import concurrent.futures
import logging
import os
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine synchronously. Used by tools that wrap async functions."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class ToolRegistry:
    """Registry of tool executors for synchronous fallback mode."""

    def __init__(self):
        self._executors: Dict[str, Callable] = {}
        self._param_mappings: Dict[str, Dict[str, str]] = {}
        self._logger = logging.getLogger(__name__)

    def load_all(self, realtime_evaluator=None) -> Dict[str, Callable]:
        """
        Load all tool executors. Returns the executor dict.

        Args:
            realtime_evaluator: Optional RealtimeEvaluator instance for evaluation tools.
        """
        self._load_bubble_tools()
        self._load_idea_tools()
        self._load_coding_tools()
        self._load_desktop_tools()
        self._load_evaluation_tools(realtime_evaluator)
        self._load_summary_tools()
        self._load_format_tools()
        self._load_task_memory_tools()
        self._load_task_status_tools()
        self._load_system_status_tools()
        self._load_exploration_tools()
        self._load_requirements_tools()
        self._load_roarboot_tools()
        self._load_research_tools()
        self._load_minibook_tools()
        self._load_schedule_tools()
        self._load_n8n_tools()
        self._load_agentfarm_tools()
        self._load_messaging_tools()
        self._load_conversation_tools()
        self._load_status_stubs()
        self._load_param_mappings()
        self._logger.info(f"Loaded {len(self._executors)} tools for sync fallback")
        return self._executors

    def get_param_mappings(self) -> Dict[str, Dict[str, str]]:
        """Return consolidated PARAM_MAPPINGs from all backend agents."""
        return self._param_mappings

    def _load_param_mappings(self):
        """Collect PARAM_MAPPINGs from all backend agent classes."""
        agent_modules = [
            ("spaces.ideas.agents.bubbles_agent", "BubblesAgent"),
            ("spaces.ideas.agents.ideas_agent", "IdeasAgent"),
            ("spaces.coding.agents.coding_agent", "CodingAgent"),
            ("spaces.desktop.agents.desktop_agent", "DesktopAgent"),
            ("spaces.rowboat.agents.roarboot_agent", "RoarbootBackendAgent"),
            ("spaces.research.agents.zeroclaw_research_agent", "ZeroClawResearchAgent"),
            ("spaces.minibook.agents.minibook_agent", "MinibookBackendAgent"),
            ("spaces.schedule.agents.schedule_agent", "ScheduleBackendAgent"),
            ("spaces.n8n.agents.n8n_agent", "N8nBackendAgent"),
            ("spaces.autogen.agents.agentfarm_agent", "AgentFarmAgent"),
            ("spaces.video.agents.video_agent", "VideoAgent"),
            ("spaces.mirofish.agents.mirofish_agent", "MirofishAgent"),
        ]
        for module_path, class_name in agent_modules:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                agent_cls = getattr(mod, class_name, None)
                if agent_cls and hasattr(agent_cls, "PARAM_MAPPING"):
                    for event_type, mapping in agent_cls.PARAM_MAPPING.items():
                        # Skip _inject entries (handled separately)
                        clean_mapping = {k: v for k, v in mapping.items() if k != "_inject"}
                        if clean_mapping:
                            self._param_mappings[event_type] = clean_mapping
            except Exception as e:
                self._logger.debug(f"Could not load PARAM_MAPPING from {module_path}: {e}")
        self._logger.info(f"Loaded param mappings for {len(self._param_mappings)} event types")

    # =========================================================================
    # Bubble Tools
    # =========================================================================

    def _load_bubble_tools(self):
        """Load bubble management tools (create, enter, exit, etc.)."""
        try:
            from tools.bubble_tools import (
                list_bubbles, create_bubble, enter_bubble,
                exit_bubble, delete_bubble, delete_all_bubbles_except,
                get_bubble_stats, score_bubble, promote_bubble,
                update_bubble, find_bubble, evaluate_bubble_evolution
            )
            self._executors.update({
                "bubble.list": list_bubbles,
                "bubble.create": create_bubble,
                "bubble.enter": enter_bubble,
                "bubble.exit": exit_bubble,
                "bubble.back": exit_bubble,  # Alias for bubble.exit
                "bubble.delete": delete_bubble,
                "bubble.delete_all_except": delete_all_bubbles_except,
                "bubble.stats": get_bubble_stats,
                "bubble.score": score_bubble,
                "bubble.promote": promote_bubble,
                "bubble.update": update_bubble,
                "bubble.find": find_bubble,
                "bubble.evaluate": evaluate_bubble_evolution,
            })
            self._logger.info("Loaded bubble tools for sync fallback (12 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load bubble tools: {e}")

    # =========================================================================
    # Idea Tools
    # =========================================================================

    def _load_idea_tools(self):
        """Load idea management tools (create, list, connect, format, etc.)."""
        try:
            from tools.idea_tools import (
                create_idea, list_ideas, find_idea, delete_idea,
                update_idea, connect_ideas, add_image, get_current_space,
                expand_ideas, move_idea, auto_link_ideas, analyze_and_suggest_links,
                count_ideas, classify_idea, link_idea_to_root, connect_ideas_multi,
                disconnect_ideas, explain_idea
            )
            from tools.structured_formatting_tools import format_idea_as_table
            from tools.summary_tools import summarize_idea, generate_white_paper
            self._executors.update({
                "idea.create": create_idea,
                "idea.list": list_ideas,
                "idea.find": find_idea,
                "idea.delete": delete_idea,
                "idea.update": update_idea,
                "idea.connect": connect_ideas,
                "idea.disconnect": disconnect_ideas,
                "idea.connect_multi": connect_ideas_multi,
                "idea.add_image": add_image,
                "idea.expand": expand_ideas,
                "idea.move": move_idea,
                "idea.auto_link": auto_link_ideas,
                "idea.analyze_links": analyze_and_suggest_links,
                "idea.count": count_ideas,
                "idea.classify": classify_idea,
                "idea.link_to_root": link_idea_to_root,
                "idea.format_table": format_idea_as_table,
                "idea.summarize": summarize_idea,
                "idea.whitepaper": generate_white_paper,
                "idea.white_paper": generate_white_paper,  # Alias
                "idea.explain": explain_idea,
                "bubble.current": get_current_space,
                "idea.current_space": get_current_space,  # Alias for intent rule
            })
            self._logger.info("Loaded idea tools for sync fallback (20 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load idea tools: {e}")

    # =========================================================================
    # Coding Tools
    # =========================================================================

    def _load_coding_tools(self):
        """Load code generation tools."""
        try:
            from spaces.coding.tools.coding_tools import (
                generate_code, get_generation_status, start_preview,
                stop_preview, list_generated_projects, cancel_generation,
                exit_project
            )
            self._executors.update({
                "code.generate": generate_code,
                "code.status": get_generation_status,
                "code.preview.start": start_preview,
                "code.preview.stop": stop_preview,
                "code.list": list_generated_projects,
                "code.cancel": cancel_generation,
                "code.exit": exit_project,
            })
            self._logger.info("Loaded coding tools for sync fallback (7 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load coding tools: {e}")

    # =========================================================================
    # Desktop Tools (async wrappers)
    # =========================================================================

    def _load_desktop_tools(self):
        """Load desktop automation tools with sync wrappers for async functions."""
        try:
            from spaces.desktop.tools.desktop_tools import (
                execute_desktop_task, click_element, type_text,
                press_key, take_screenshot, scroll_screen
            )

            def _format_desktop_result(result):
                """Format desktop tool result for voice output."""
                if isinstance(result, dict):
                    if result.get("success"):
                        return result.get("message", "Done.")
                    else:
                        return f"Error: {result.get('error', result.get('message', 'Unknown error'))}"
                return str(result)

            # Sync wrapper functions for desktop tools
            def desktop_task_sync(params):
                goal = params.get("goal", "") or params.get("description", "")
                if not goal:
                    return "What should I do on the desktop?"
                result = _run_async(execute_desktop_task(goal))
                return _format_desktop_result(result)

            def click_element_sync(params):
                desc = params.get("element_description", "") or params.get("description", "")
                if not desc:
                    return "Which element should I click?"
                result = _run_async(click_element(desc))
                return _format_desktop_result(result)

            def type_text_sync(params):
                text = params.get("text", "")
                if not text:
                    return "What should I type?"
                result = _run_async(type_text(text))
                return _format_desktop_result(result)

            def press_key_sync(params):
                key = params.get("key", "")
                if not key:
                    return "Which key should I press?"
                result = _run_async(press_key(key))
                return _format_desktop_result(result)

            def take_screenshot_sync(params):
                result = _run_async(take_screenshot())
                return _format_desktop_result(result)

            def scroll_screen_sync(params):
                direction = params.get("direction", "down")
                amount = params.get("amount", 3)
                result = _run_async(scroll_screen(direction, amount))
                return _format_desktop_result(result)

            self._executors.update({
                "desktop.task": desktop_task_sync,
                "desktop.open_app": desktop_task_sync,  # Alias - open_app uses task
                "system.open_app": desktop_task_sync,   # Classifier sometimes emits system.open_app
                "desktop.click": click_element_sync,
                "desktop.type": type_text_sync,
                "desktop.press_key": press_key_sync,
                "desktop.screenshot": take_screenshot_sync,
                "desktop.scroll": scroll_screen_sync,
            })
            self._logger.info("Loaded desktop tools for sync fallback (7 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load desktop tools: {e}")

    # =========================================================================
    # Evaluation Tools (Phase 17)
    # =========================================================================

    def _load_evaluation_tools(self, realtime_evaluator=None):
        """Load evaluation feedback tools for Phase 17."""
        def eval_correct(params):
            if realtime_evaluator:
                return realtime_evaluator.on_feedback("correct")
            return "Danke fuer das Feedback!"

        def eval_incorrect(params):
            if realtime_evaluator:
                return realtime_evaluator.on_feedback("incorrect")
            return "Danke fuer die Korrektur! Was meintest du stattdessen?"

        def eval_clarify(params):
            if realtime_evaluator:
                correction = params.get("correction", "") or params.get("intended_action", "")
                return realtime_evaluator.on_clarification(correction)
            return "Verstanden, danke!"

        def eval_stats(params):
            if realtime_evaluator:
                return realtime_evaluator.format_stats_for_voice()
            return "Statistiken sind momentan nicht verfuegbar."

        self._executors.update({
            "evaluation.correct": eval_correct,
            "evaluation.incorrect": eval_incorrect,
            "evaluation.clarify": eval_clarify,
            "evaluation.stats": eval_stats,
        })
        self._logger.info("Loaded evaluation tools for sync fallback (4 tools)")

    # =========================================================================
    # Summary Tools
    # =========================================================================

    def _load_summary_tools(self):
        """Load summary and white paper generation tools."""
        try:
            from tools.summary_tools import (
                summarize_idea, generate_white_paper,
                list_summaries, get_summary
            )
            self._executors.update({
                "idea.summarize": summarize_idea,
                "idea.whitepaper": generate_white_paper,
                "summary.list": list_summaries,
                "summary.get": get_summary,
            })
            self._logger.info("Loaded summary tools for sync fallback (4 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load summary tools: {e}")

    # =========================================================================
    # Format Tools
    # =========================================================================

    def _load_format_tools(self):
        """Load structured formatting tools."""
        try:
            from tools.format_dispatcher import FORMAT_EXECUTORS
            self._executors.update(FORMAT_EXECUTORS)
            self._logger.info(f"Loaded format tools for sync fallback ({len(FORMAT_EXECUTORS)} tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load format tools: {e}")

    # =========================================================================
    # Task Memory Tools
    # =========================================================================

    def _load_task_memory_tools(self):
        """Load Supermemory-based task memory tools."""
        try:
            from tools.task_memory_tools import (
                get_tasks_today, get_recent_tasks,
                search_task_history, get_task_stats
            )
            self._executors.update({
                "task.list_today": get_tasks_today,
                "task.recent": get_recent_tasks,
                "task.search": search_task_history,
                "task.stats": get_task_stats,
            })
            self._logger.info("Loaded task memory tools for sync fallback (4 tools)")
        except ImportError as e:
            self._logger.debug(f"Could not load task memory tools: {e}")

    # =========================================================================
    # Task Status Tools
    # =========================================================================

    def _load_task_status_tools(self):
        """Load real-time Redis task status monitoring tools."""
        try:
            from tools.task_status_tools import (
                list_active_tasks, get_queue_status,
                get_recent_completions
            )
            self._executors.update({
                "system.active_tasks": list_active_tasks,
                "system.queue_status": get_queue_status,
                "system.recent_completions": get_recent_completions,
            })
            self._logger.info("Loaded task status tools for sync fallback (3 tools)")
        except ImportError as e:
            self._logger.debug(f"Could not load task status tools: {e}")

    # =========================================================================
    # System Status Tools
    # =========================================================================

    def _load_system_status_tools(self):
        """Load system status monitoring tools."""
        try:
            from tools.system_status_tools import SYSTEM_STATUS_TOOLS
            self._executors.update(SYSTEM_STATUS_TOOLS)
            self._logger.info(f"Loaded system status tools ({len(SYSTEM_STATUS_TOOLS)} tools)")
        except ImportError as e:
            self._logger.debug(f"Could not load system status tools: {e}")

    # =========================================================================
    # Exploration Tools (AI-Scientist Tree Search)
    # =========================================================================

    def _load_exploration_tools(self):
        """Load AI-Scientist exploration tools with sync wrappers."""
        try:
            from spaces.ideas.tools.exploration_tools import (
                start_exploration,
                stop_exploration,
                get_exploration_status,
                accept_connection,
                reject_connection,
                explore_deeper,
                visualize_exploration,
                respond_to_exploration_question,
                set_exploration_direction,
            )

            def _format_exploration_result(result):
                """Format exploration result for voice output."""
                if isinstance(result, dict):
                    if result.get("success"):
                        return result.get("message", "Exploration started.")
                    else:
                        return result.get("message", "Exploration failed.")
                return str(result)

            def explore_start_sync(params):
                result = _run_async(start_exploration(
                    bubble_id=params.get("bubble_id"),
                    depth=params.get("depth", 4),
                    context=params.get("context"),
                    mode=params.get("mode", "auto"),
                ))
                return _format_exploration_result(result)

            def explore_stop_sync(params):
                result = _run_async(stop_exploration())
                return _format_exploration_result(result)

            def explore_status_sync(params):
                result = _run_async(get_exploration_status())
                return _format_exploration_result(result)

            def explore_accept_sync(params):
                result = _run_async(accept_connection(
                    connection_id=params.get("connection_id")
                ))
                return _format_exploration_result(result)

            def explore_reject_sync(params):
                result = _run_async(reject_connection(
                    connection_id=params.get("connection_id")
                ))
                return _format_exploration_result(result)

            def explore_deeper_sync(params):
                result = _run_async(explore_deeper())
                return _format_exploration_result(result)

            def explore_visualize_sync(params):
                result = _run_async(visualize_exploration())
                return _format_exploration_result(result)

            def explore_respond_sync(params):
                result = _run_async(respond_to_exploration_question(
                    question_id=params.get("question_id"),
                    response_type=params.get("response_type"),
                    selected_option=params.get("selected_option"),
                    custom_text=params.get("custom_text"),
                ))
                return _format_exploration_result(result)

            def explore_direction_sync(params):
                result = _run_async(set_exploration_direction(
                    direction=params.get("direction"),
                    bubble_id=params.get("bubble_id"),
                ))
                return _format_exploration_result(result)

            self._executors.update({
                "idea.explore.start": explore_start_sync,
                "idea.explore.stop": explore_stop_sync,
                "idea.explore.status": explore_status_sync,
                "idea.explore.accept": explore_accept_sync,
                "idea.explore.reject": explore_reject_sync,
                "idea.explore.depth": explore_deeper_sync,
                "idea.explore.visualize": explore_visualize_sync,
                "idea.explore.respond": explore_respond_sync,
                "idea.explore.direction": explore_direction_sync,
                "idea.explore.continue": explore_start_sync,  # Alias
            })
            self._logger.info("Loaded exploration tools for sync fallback (10 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load exploration tools: {e}")

    # =========================================================================
    # Bubble Requirements Tools (Shuttle Pipeline)
    # =========================================================================

    def _load_requirements_tools(self):
        """Load bubble requirements tools with sync wrappers."""
        try:
            from tools.bubble_requirements_tool import (
                process_bubble_requirements,
                get_bubble_requirements,
                list_bubbles_with_requirements
            )

            def _format_requirements_result(result):
                """Format requirements result for voice output."""
                if isinstance(result, dict):
                    if result.get("error"):
                        return f"Error: {result.get('error', 'Unknown error')}"
                    elif "bubbles" in result:
                        bubbles = result.get("bubbles", [])
                        if not bubbles:
                            return "You don't have any Spaces with Requirements yet."
                        count = len(bubbles)
                        names = [b.get("bubble_title", b.get("title", "Untitled")) for b in bubbles[:5]]
                        if count <= 5:
                            return f"You have {count} Spaces with Requirements: {', '.join(names)}."
                        return f"You have {count} Spaces with Requirements. The first ones are: {', '.join(names)}."
                    elif "requirements" in result:
                        requirements = result.get("requirements", [])
                        if not requirements:
                            return "No Requirements found."
                        count = len(requirements)
                        return f"I generated {count} Requirements."
                    elif "metadata" in result:
                        metadata = result.get("metadata", {})
                        bubble_title = metadata.get("bubble_title", "Untitled")
                        node_count = metadata.get("node_count", 0)
                        total_words = metadata.get("total_words", 0)
                        return f"For Space '{bubble_title}': {node_count} nodes with {total_words} words."
                    else:
                        return str(result)
                return str(result)

            def shuttle_list_sync(params):
                """Liste alle Bubbles mit ihren Requirements."""
                result = _run_async(list_bubbles_with_requirements())
                return _format_requirements_result(result)

            def shuttle_get_sync(params):
                """Hole die Requirements fuer eine spezifische Bubble."""
                bubble_id = params.get("bubble_id")
                if not bubble_id:
                    return "Which Space should I analyze? Please provide a Space ID."
                result = _run_async(get_bubble_requirements(bubble_id))
                return _format_requirements_result(result)

            def shuttle_process_sync(params):
                """Verarbeite die Inhalte einer Bubble und generiere Requirements."""
                bubble_id = params.get("bubble_id")
                if not bubble_id:
                    return "Which Space should I analyze? Please provide a Space ID."
                result = _run_async(process_bubble_requirements(bubble_id))
                return _format_requirements_result(result)

            self._executors.update({
                "shuttle.list": shuttle_list_sync,
                "shuttle.get": shuttle_get_sync,
                "shuttle.process": shuttle_process_sync,
            })
            self._logger.info("Loaded bubble requirements tools for sync fallback (3 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load bubble requirements tools: {e}")

    # =========================================================================
    # Roarboot Tools (Rowboat Knowledge Graph)
    # =========================================================================

    def _load_roarboot_tools(self):
        """Load Rowboat knowledge graph tools."""
        try:
            from spaces.rowboat.tools.roarboot_tools import (
                search_knowledge, query_knowledge, draft_email,
                generate_meeting_brief, generate_deck, process_voice_note,
                get_status as roarboot_get_status, open_webview, reset_conversation,
                chat as roarboot_chat, rag_search, upload_document,
                explore_graph, list_tools as roarboot_list_tools,
            )
            from spaces.rowboat.tools.docker_tools import (
                start_docker, stop_docker, restart_docker, docker_status,
            )

            def _fmt_roarboot(result):
                if isinstance(result, dict):
                    return result.get("response_hint", result.get("message", "Done."))
                return str(result)

            self._executors.update({
                "roarboot.search": lambda p: _fmt_roarboot(search_knowledge(p.get("query", ""))),
                "roarboot.query": lambda p: _fmt_roarboot(query_knowledge(p.get("subject", ""), p.get("question"))),
                "roarboot.email_draft": lambda p: _fmt_roarboot(draft_email(p.get("recipient", ""), p.get("topic", ""), p.get("context", ""))),
                "roarboot.meeting_brief": lambda p: _fmt_roarboot(generate_meeting_brief(p.get("meeting", ""), p.get("participants", ""))),
                "roarboot.deck": lambda p: _fmt_roarboot(generate_deck(p.get("topic", ""), p.get("context", ""))),
                "roarboot.voice_note": lambda p: _fmt_roarboot(process_voice_note(p.get("text", ""))),
                "roarboot.status": lambda p: _fmt_roarboot(roarboot_get_status()),
                "roarboot.open": lambda p: _fmt_roarboot(open_webview(p.get("context", "default"))),
                "roarboot.reset": lambda p: _fmt_roarboot(reset_conversation(p.get("context"))),
                "roarboot.docker.start": lambda p: _fmt_roarboot(start_docker()),
                "roarboot.docker.stop": lambda p: _fmt_roarboot(stop_docker()),
                "roarboot.docker.restart": lambda p: _fmt_roarboot(restart_docker()),
                "roarboot.docker.status": lambda p: _fmt_roarboot(docker_status()),
                # High-value tools
                "roarboot.chat": lambda p: _fmt_roarboot(roarboot_chat(p.get("message", ""), p.get("context", "general"))),
                "roarboot.rag.search": lambda p: _fmt_roarboot(rag_search(p.get("query", ""))),
                "roarboot.upload": lambda p: _fmt_roarboot(upload_document(p.get("file_path"), p.get("text"), p.get("title"))),
                # Medium-value tools
                "roarboot.graph.explore": lambda p: _fmt_roarboot(explore_graph(p.get("subject", ""))),
                "roarboot.tools.list": lambda p: _fmt_roarboot(roarboot_list_tools()),
            })
            self._logger.info("Loaded roarboot tools for sync fallback (18 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load roarboot tools: {e}")

    # =========================================================================
    # AgentFarm Tools (AutoGen 0.4 Team Orchestration)
    # =========================================================================

    def _load_agentfarm_tools(self):
        """Load AgentFarm/AutoGen team orchestration tools."""
        try:
            from spaces.autogen.tools.agentfarm_tools import (
                create_team, run_team, get_farm_status, list_teams,
                stop_run, get_run_results, list_templates, start_collaboration,
                run_pipeline, get_pipeline_status, start_forge, get_forge_status,
                pipeline_answer,
            )

            def _fmt_af(result):
                if isinstance(result, dict):
                    return result.get("response_hint", result.get("message", "Done."))
                return str(result)

            # run_team is async — wrap it
            def _run_team_sync(p):
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            result = pool.submit(
                                asyncio.run, run_team(p.get("team_id", ""), p.get("task", ""))
                            ).result(timeout=30)
                        return _fmt_af(result)
                except Exception:
                    pass
                return _fmt_af(asyncio.run(run_team(p.get("team_id", ""), p.get("task", ""))))

            self._executors.update({
                "agentfarm.create_team": lambda p: _fmt_af(create_team(
                    template_id=p.get("template_id"), team_name=p.get("team_name"),
                    agents=p.get("agents"), team_type=p.get("team_type"),
                )),
                "agentfarm.run": _run_team_sync,
                "agentfarm.status": lambda p: _fmt_af(get_farm_status()),
                "agentfarm.list_teams": lambda p: _fmt_af(list_teams()),
                "agentfarm.stop": lambda p: _fmt_af(stop_run(p.get("run_id", ""))),
                "agentfarm.results": lambda p: _fmt_af(get_run_results(p.get("run_id", ""))),
                "agentfarm.list_templates": lambda p: _fmt_af(list_templates()),
                "agentfarm.collaborate": lambda p: _fmt_af(start_collaboration(
                    task=p.get("task", ""), goal=p.get("goal", ""),
                )),
                "agentfarm.pipeline.start": lambda p: run_pipeline(**p),
                "agentfarm.pipeline.status": lambda p: get_pipeline_status(**p),
                "agentfarm.pipeline.answer": lambda p: pipeline_answer(**p),
                "agentfarm.forge.start": lambda p: start_forge(**p),
                "agentfarm.forge.status": lambda p: get_forge_status(**p),
            })
            self._logger.info("Loaded agentfarm tools for sync fallback (12 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load agentfarm tools: {e}")

    # =========================================================================
    # Research Tools (ZeroClaw Web Research)
    # =========================================================================

    def _load_research_tools(self):
        """Load ZeroClaw web research tools. Requires USE_ZEROCLAW=true."""
        if os.getenv("USE_ZEROCLAW", "false").lower() != "true":
            return

        try:
            from spaces.research.tools.research_tools import (
                web_research, scrape_url, summarize_url,
                research_to_idea, research_to_rowboat,
            )

            def _fmt_research(result):
                if isinstance(result, dict):
                    return result.get("response_hint", result.get("message", "Recherche abgeschlossen."))
                return str(result)

            self._executors.update({
                "research.web": lambda p: _fmt_research(web_research(p.get("query", ""))),
                "research.scrape": lambda p: _fmt_research(scrape_url(p.get("url", ""))),
                "research.summarize": lambda p: _fmt_research(summarize_url(p.get("url", ""))),
                "research.to_idea": lambda p: _fmt_research(research_to_idea(p.get("query", ""), p.get("title"))),
                "research.to_rowboat": lambda p: _fmt_research(research_to_rowboat(p.get("query", ""))),
            })
            self._logger.info("Loaded research tools for sync fallback (5 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load research tools: {e}")

    # =========================================================================
    # Minibook Tools (Inter-Space Collaboration)
    # =========================================================================

    def _load_minibook_tools(self):
        """Load Minibook collaboration tools. Requires MINIBOOK_ENABLED=true."""
        if os.getenv("MINIBOOK_ENABLED", "false").lower() != "true":
            return

        try:
            from spaces.minibook.tools.minibook_tools import (
                get_minibook_status,
                start_discussion,
                get_discussion_results,
                list_projects,
            )
            from spaces.minibook.tools.collaboration_tools import (
                start_collaboration,
                poll_responses,
            )

            def _fmt_minibook(result):
                if isinstance(result, dict):
                    return result.get("response_hint", result.get("message", "Minibook-Aktion abgeschlossen."))
                return str(result)

            self._executors.update({
                "minibook.status": lambda p: _fmt_minibook(get_minibook_status()),
                "minibook.discuss": lambda p: _fmt_minibook(start_discussion(p.get("message", ""), p.get("topic", ""))),
                "minibook.results": lambda p: _fmt_minibook(get_discussion_results(p.get("discussion_id", ""))),
                "minibook.list_projects": lambda p: _fmt_minibook(list_projects()),
                "minibook.collaborate": lambda p: _fmt_minibook(start_collaboration(p.get("task", ""), p.get("goal", ""))),
                "minibook.poll": lambda p: _fmt_minibook(poll_responses()),
            })
            self._logger.info("Loaded minibook tools for sync fallback (6 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load minibook tools: {e}")

    # =========================================================================
    # Schedule Tools
    # =========================================================================

    def _load_schedule_tools(self):
        """Load APScheduler-based scheduling tools. Requires MINIBOOK_ENABLED=true."""
        if os.getenv("MINIBOOK_ENABLED", "false").lower() != "true":
            return

        try:
            from spaces.schedule.tools.schedule_tools import (
                create_scheduled_task,
                list_scheduled_tasks,
                cancel_scheduled_task,
                modify_scheduled_task,
                get_schedule_status,
                snooze_scheduled_task,
            )

            def _fmt_schedule(result):
                if isinstance(result, dict):
                    if result.get("success"):
                        return result.get("response_hint", result.get("message", "Done."))
                    else:
                        return result.get("response_hint", f"Error: {result.get('message', 'Unknown error')}")
                return str(result)

            self._executors.update({
                "schedule.create": lambda p: _fmt_schedule(create_scheduled_task(
                    user_text=p.get("user_text", p.get("text", "")),
                    title=p.get("title", ""),
                )),
                "schedule.list": lambda p: _fmt_schedule(list_scheduled_tasks(
                    status=p.get("status", ""),
                )),
                "schedule.cancel": lambda p: _fmt_schedule(cancel_scheduled_task(
                    task_id=p.get("task_id", p.get("id", "")),
                    title=p.get("title", p.get("name", "")),
                )),
                "schedule.modify": lambda p: _fmt_schedule(modify_scheduled_task(
                    task_id=p.get("task_id", p.get("id", "")),
                    title=p.get("title", p.get("name", "")),
                    new_time=p.get("new_time", p.get("zeit", "")),
                    new_action=p.get("new_action", ""),
                )),
                "schedule.status": lambda p: _fmt_schedule(get_schedule_status()),
                "schedule.snooze": lambda p: _fmt_schedule(snooze_scheduled_task(
                    task_id=p.get("task_id", p.get("id", "")),
                    title=p.get("title", p.get("name", "")),
                    minutes=int(p.get("minutes", 5)),
                    user_text=p.get("user_text", p.get("text", "")),
                )),
            })
            self._logger.info("Loaded schedule tools for sync fallback (6 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load schedule tools: {e}")

    # =========================================================================
    # N8n Workflow Tools
    # =========================================================================

    def _load_n8n_tools(self):
        """Load n8n workflow builder tools. Requires N8N_ENABLED=true."""
        if os.getenv("N8N_ENABLED", "false").lower() != "true":
            return

        try:
            from spaces.n8n.tools.n8n_workflow_tools import (
                generate_workflow, list_workflows, get_n8n_status,
                activate_workflow, deactivate_workflow, delete_workflow,
                execute_workflow, describe_workflow,
            )
            self._executors.update({
                "n8n.generate": lambda p: generate_workflow(**p),
                "n8n.list": lambda p: list_workflows(**p),
                "n8n.status": lambda p: get_n8n_status(**p),
                "n8n.activate": lambda p: activate_workflow(**p),
                "n8n.deactivate": lambda p: deactivate_workflow(**p),
                "n8n.delete": lambda p: delete_workflow(**p),
                "n8n.execute": lambda p: execute_workflow(**p),
                "n8n.describe": lambda p: describe_workflow(**p),
            })
            self._logger.info("Loaded n8n workflow tools for sync fallback (8 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load n8n tools: {e}")

    # =========================================================================
    # Messaging Tools (WhatsApp/Telegram via Clawdbot)
    # =========================================================================

    def _load_messaging_tools(self):
        """Load messaging pipeline tools. Requires MINIBOOK_ENABLED=true."""
        if os.getenv("MINIBOOK_ENABLED", "false").lower() != "true":
            return

        try:
            from spaces.desktop.messaging.messaging_pipeline import get_messaging_pipeline
            pipeline = get_messaging_pipeline()
            self._executors.update({
                "messaging.send": lambda p: pipeline.send_message_sync(p),
                "messaging.read": lambda p: pipeline.read_messages_sync(p),
            })
            self._logger.info("Loaded messaging pipeline tools for sync fallback (2 tools)")
        except ImportError as e:
            self._logger.warning(f"Could not load messaging pipeline tools: {e}")

    def _load_conversation_tools(self):
        """Template responses for conversation events that don't need tool execution."""
        self._executors.update({
            "conversation.greeting": lambda p: {"message": "Hallo! Wie kann ich dir helfen?"},
            "conversation.farewell": lambda p: {"message": "Tschuess! Bis zum naechsten Mal."},
            "conversation.help": lambda p: {"message": (
                "Ich kann dir helfen mit: Bubbles verwalten, Ideen erstellen, "
                "Screenshots machen, Termine planen, Workflows starten, "
                "Code-Projekte verwalten, und vieles mehr. "
                "Sag einfach was du brauchst!"
            )},
            "conversation.unknown": lambda p: {"message": "Ich habe dich nicht ganz verstanden. Kannst du das anders formulieren?"},
            "conversation.listening": lambda p: {"message": "Ich hoere zu..."},
            "evaluation.correct": lambda p: {"message": "Super, freut mich dass es passt!"},
            "evaluation.incorrect": lambda p: {"message": "OK, ich versuche es anders."},
        })
        self._logger.info("Loaded conversation tools for sync fallback (7 tools)")

    def _load_status_stubs(self):
        """Status-check stubs for spaces that don't have dedicated sync tools yet."""
        # MiroFish status
        try:
            import aiohttp
            def _mirofish_status(p):
                import urllib.request
                try:
                    url = os.environ.get("MIROFISH_URL", "http://localhost:5101")
                    resp = urllib.request.urlopen(f"{url}/health", timeout=3)
                    return {"message": f"MiroFish ist erreichbar ({url})."}
                except Exception:
                    return {"message": f"MiroFish nicht erreichbar. Docker-Container gestartet?"}
            self._executors["mirofish.status"] = _mirofish_status
        except Exception:
            pass

        # Video status
        self._executors.setdefault("video.status", lambda p: {
            "message": "Video Studio: Kein aktiver Video-Job. Sag 'video team run' um ein Video zu erstellen."
        })

        # Rose/Flowzen status
        self._executors.setdefault("rose.status", lambda p: {
            "message": "Blue Rose (Flowzen): Aktivitaets-Tracker ist bereit. Sag 'rose recommend' fuer Empfehlungen."
        })

        self._logger.info("Loaded status stubs (mirofish, video, rose)")
