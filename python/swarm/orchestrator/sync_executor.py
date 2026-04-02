"""
Sync Executor - Synchronous tool execution with dependency ordering.

Extracted from IntentOrchestrator to reduce module size.
Handles single-tool sync execution and multi-step tool chains.
"""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from swarm.orchestrator.result_formatter import (
    format_result_for_voice,
    format_multi_step_result,
    store_supermemory_task_completed,
    store_supermemory_task_failed,
)

logger = logging.getLogger(__name__)

# System status monitoring
try:
    from swarm.monitoring.system_status import get_status_monitor
    _status_monitor = get_status_monitor()
except ImportError:
    _status_monitor = None

# Tool execution logging
try:
    from swarm.logging.tool_logger import get_tool_logger
    HAS_TOOL_LOGGER = True
except ImportError:
    HAS_TOOL_LOGGER = False
    get_tool_logger = None

# UI event broadcasting for tool_failed events
try:
    from tools.workspace_tools import _broadcast_to_electron
    HAS_BROADCAST = True
except ImportError:
    HAS_BROADCAST = False
    _broadcast_to_electron = None

# Import OrchestrationResult from result_formatter (avoids circular import)
from swarm.orchestrator.result_formatter import OrchestrationResult


class SyncExecutor:
    """Executes tools synchronously with dependency ordering."""

    # Intent types that create entities (from IntentBatcher)
    CREATOR_INTENTS = {"bubble.create", "idea.create", "code.generate"}

    # Intent dependencies: {dependent_intent: creator_intent}
    DEPENDENT_INTENTS = {
        "bubble.enter": "bubble.create",
        "idea.create": "bubble.create",
        "idea.update": "idea.create",
        "idea.connect": "idea.create",
        "idea.delete": "idea.create",
        "idea.expand": "idea.create",
        "idea.move": "bubble.create",
        "idea.auto_link": "idea.create",
    }

    # Events that are purely conversational (no tool execution needed)
    CONVERSATIONAL_EVENTS = {
        "conversation.greeting",
        "conversation.help",
        "conversation.unknown",
        "direct_answer",
    }

    def __init__(
        self,
        tool_executors: Dict[str, Callable],
        task_memory=None,
        reasoning_logger=None,
        broadcast_dispatcher=None,
        sm_task_memory=None,
        sm_user_profile=None,
        sm_conversation_memory=None,
        use_broadcast_mode: bool = False,
        param_mappings: Optional[Dict[str, Dict[str, str]]] = None,
    ):
        self._tool_executors = tool_executors
        self.task_memory = task_memory
        self.reasoning_logger = reasoning_logger
        self._broadcast_dispatcher = broadcast_dispatcher
        self.sm_task_memory = sm_task_memory
        self.sm_user_profile = sm_user_profile
        self.sm_conversation_memory = sm_conversation_memory
        self._use_broadcast_mode = use_broadcast_mode
        self._param_mappings = param_mappings or {}

    def _normalize_params(self, event_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize parameter names using PARAM_MAPPINGs from backend agents.

        Maps classifier output names to tool expected names.
        E.g., {"title": "X"} -> {"bubble_name": "X"} for bubble.delete
        """
        mapping = self._param_mappings.get(event_type, {})
        if not mapping:
            return params

        normalized = {}
        for key, value in params.items():
            new_key = mapping.get(key, key)
            if new_key not in normalized:
                normalized[new_key] = value
            elif key not in mapping:
                normalized[key] = value

        return normalized

    async def process_sync(
        self,
        event_type: str,
        payload: Dict[str, Any],
        response_hint: str,
        user_id: str = "default",
        session_id: str = None,
        process_via_broadcast_fn: Callable = None,
    ) -> OrchestrationResult:
        """
        Execute tool directly without Redis (synchronous fallback).

        If USE_BROADCAST_MODE is enabled, delegates to _process_via_broadcast
        for fan-out execution with parallel user profiling.

        Args:
            event_type: Classified event type (e.g., "bubble.list")
            payload: Tool parameters
            response_hint: Default response hint from classifier
            user_id: User ID for task tracking
            session_id: Session ID for task tracking
            process_via_broadcast_fn: Optional callback for broadcast mode delegation

        Returns:
            OrchestrationResult with actual tool result in response_hint
        """
        # Broadcast mode: delegate to fan-out dispatcher
        if self._use_broadcast_mode and self._broadcast_dispatcher and process_via_broadcast_fn:
            # Extract user_input and conversation_history from payload if available
            user_input = ""
            conversation_history = []
            if payload:
                user_input = payload.pop("_user_input", "")
                conversation_history = payload.pop("_conversation_history", [])

            return await process_via_broadcast_fn(
                event_type=event_type,
                payload=payload,
                response_hint=response_hint,
                user_input=user_input,
                conversation_history=conversation_history,
                session_id=session_id,
            )

        executor = self._tool_executors.get(event_type)
        task_id = None

        # Create task in TaskMemory for tracking (non-trivial events only)
        if self.task_memory and event_type not in self.CONVERSATIONAL_EVENTS:
            try:
                # Generate task title from event type and payload
                title_parts = [event_type]
                if payload:
                    # Add key info from payload
                    for key in ["title", "name", "query", "idea_name", "bubble_name"]:
                        if key in payload and payload[key]:
                            title_parts.append(str(payload[key])[:30])
                            break
                task_title = ": ".join(title_parts)

                task = self.task_memory.create_task(
                    title=task_title,
                    intent_type=event_type,
                    payload=payload or {},
                    user_id=user_id,
                    session_id=session_id
                )
                task_id = task.id
                self.task_memory.start_task(task_id)
                logger.debug(f"Created task {task_id} for {event_type}")
            except Exception as e:
                logger.warning(f"Could not create task in TaskMemory: {e}")

        # Normalize params (e.g., "title" -> "bubble_name" for bubble.delete)
        if payload:
            payload = self._normalize_params(event_type, payload)

        if executor:
            try:
                logger.info(f"SYNC fallback: Executing {event_type} directly")
                logger.debug(f"[TOOL EXEC] {event_type} with payload: {payload}")

                # Track with status monitor
                monitor_op_id = None
                if _status_monitor:
                    tool_desc = f"{event_type}"
                    if payload:
                        for key in ["title", "name", "bubble_name", "idea_name"]:
                            if key in payload and payload[key]:
                                tool_desc += f": {str(payload[key])[:30]}"
                                break
                    monitor_op_id = _status_monitor.start_operation("tool_exec", tool_desc, {"event_type": event_type})

                # Mark tool execution start (prevents "Bist du noch da?" interrupts)
                try:
                    from tools.session_tools import mark_tool_start, mark_tool_end
                    mark_tool_start()
                except ImportError:
                    mark_tool_end = None

                # Tools expect a single params dict, not keyword arguments
                start_time = time.perf_counter()
                try:
                    result = executor(payload) if payload else executor({})
                finally:
                    # Always mark tool end, even if execution fails

                    if 'mark_tool_end' in dir() and mark_tool_end:
                        mark_tool_end()

                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.debug(f"[TOOL EXEC] {event_type} completed in {latency_ms:.1f}ms")

                # Complete monitoring
                if _status_monitor and monitor_op_id:
                    _status_monitor.complete_operation(monitor_op_id, success=True)

                # Format result for voice output
                result_str = format_result_for_voice(event_type, result)

                # Log tool execution
                if HAS_TOOL_LOGGER and get_tool_logger:
                    get_tool_logger().log_execution(
                        tool_name=event_type,
                        params=payload or {},
                        result=result_str,
                        latency_ms=latency_ms,
                        success=True,
                        source_event=event_type
                    )

                # Complete task in TaskMemory
                if self.task_memory and task_id:
                    try:
                        self.task_memory.complete_task(task_id, result_str)
                        logger.debug(f"Completed task {task_id}")
                    except Exception as e:
                        logger.warning(f"Could not complete task: {e}")

                # Store to Supermemory (non-blocking)
                job_id_final = task_id or f"sync-{str(uuid.uuid4())[:8]}"
                import asyncio
                asyncio.create_task(store_supermemory_task_completed(
                    job_id=job_id_final,
                    event_type=event_type,
                    result=result_str,
                    duration_ms=int(latency_ms),
                    session_id=session_id,
                    sm_task_memory=self.sm_task_memory,
                    sm_user_profile=self.sm_user_profile,
                ))

                return OrchestrationResult(
                    job_id=job_id_final,
                    event_type=event_type,
                    stream="local",
                    response_hint=result_str,
                    is_conversational=False
                )
            except TypeError as e:
                # Handle parameter mismatch - try with empty dict
                logger.warning(f"Parameter mismatch for {event_type}: {e}, trying with empty params")
                try:
                    start_time = time.perf_counter()
                    result = executor({})
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    result_str = format_result_for_voice(event_type, result)

                    # Log tool execution (fallback with empty params)
                    if HAS_TOOL_LOGGER and get_tool_logger:
                        get_tool_logger().log_execution(
                            tool_name=event_type,
                            params={},
                            result=result_str,
                            latency_ms=latency_ms,
                            success=True,
                            source_event=event_type
                        )

                    # Complete task even with empty params
                    if self.task_memory and task_id:
                        self.task_memory.complete_task(task_id, result_str)

                    # Store to Supermemory (non-blocking)
                    job_id_fallback = task_id or f"sync-{str(uuid.uuid4())[:8]}"
                    import asyncio
                    asyncio.create_task(store_supermemory_task_completed(
                        job_id=job_id_fallback,
                        event_type=event_type,
                        result=result_str,
                        duration_ms=int(latency_ms),
                        session_id=session_id,
                        sm_task_memory=self.sm_task_memory,
                        sm_user_profile=self.sm_user_profile,
                    ))

                    return OrchestrationResult(
                        job_id=job_id_fallback,
                        event_type=event_type,
                        stream="local",
                        response_hint=result_str,
                        is_conversational=False
                    )
                except Exception as e2:
                    logger.error(f"Sync execution failed: {e2}")
                    # Emit tool_failed event to UI
                    if HAS_BROADCAST and _broadcast_to_electron:
                        _broadcast_to_electron({
                            "type": "tool_failed",
                            "event_type": event_type,
                            "payload": {},
                            "error": str(e2),
                            "timestamp": time.time()
                        })
                    # Log failed execution
                    if HAS_TOOL_LOGGER and get_tool_logger:
                        get_tool_logger().log_error(
                            tool_name=event_type,
                            params={},
                            error=str(e2),
                            latency_ms=0
                        )
                    # Mark task as failed
                    if self.task_memory and task_id:
                        self.task_memory.update_task_status(task_id, "blocked", error=str(e2))
                    # Store failure to Supermemory (non-blocking)
                    if task_id:
                        import asyncio
                        asyncio.create_task(store_supermemory_task_failed(
                            job_id=task_id,
                            event_type=event_type,
                            error=str(e2),
                            session_id=session_id,
                            sm_task_memory=self.sm_task_memory,
                        ))
            except Exception as e:
                logger.error(f"Sync execution failed for {event_type}: {e}")
                logger.debug(f"[TOOL EXEC] FAILED {event_type}: {e}")
                # Complete monitoring with error
                if _status_monitor and monitor_op_id:
                    _status_monitor.complete_operation(monitor_op_id, success=False, error=str(e))
                # Emit tool_failed event to UI
                if HAS_BROADCAST and _broadcast_to_electron:
                    _broadcast_to_electron({
                        "type": "tool_failed",
                        "event_type": event_type,
                        "payload": payload or {},
                        "error": str(e),
                        "timestamp": time.time()
                    })
                # Log failed execution
                if HAS_TOOL_LOGGER and get_tool_logger:
                    get_tool_logger().log_error(
                        tool_name=event_type,
                        params=payload or {},
                        error=str(e),
                        latency_ms=0
                    )
                # Mark task as failed
                if self.task_memory and task_id:
                    self.task_memory.update_task_status(task_id, "blocked", error=str(e))
                # Store failure to Supermemory (non-blocking)
                if task_id:
                    import asyncio
                    asyncio.create_task(store_supermemory_task_failed(
                        job_id=task_id,
                        event_type=event_type,
                        error=str(e),
                        session_id=session_id,
                        sm_task_memory=self.sm_task_memory,
                    ))

        # Fallback response if tool not available
        logger.warning(f"No sync executor for {event_type}")
        logger.debug(f"[TOOL EXEC] NO EXECUTOR for {event_type}!")
        return OrchestrationResult(
            job_id="",
            event_type=event_type,
            stream="",
            response_hint=response_hint,  # Use classifier's hint
            is_conversational=True,
            error=f"Tool {event_type} nicht im Sync-Modus verfuegbar"
        )

    async def process_multi_step(
        self,
        steps: List[Dict[str, Any]],
        response_hint: str,
        context=None,
    ) -> OrchestrationResult:
        """
        Execute multiple tools in sequence with dependency ordering.

        Uses Kahn's algorithm for topological sorting based on
        IntentBatcher's dependency logic.

        Args:
            steps: List of {event_type, payload} dicts
            response_hint: Initial response hint from classifier
            context: Optional task context

        Returns:
            OrchestrationResult with combined results
        """
        # Generate job_id upfront for reasoning tracking
        job_id = f"multi-{uuid.uuid4().hex[:8]}"

        if not steps:
            return OrchestrationResult(
                job_id=job_id,
                event_type="multi_step",
                stream="local",
                response_hint="No steps to execute.",
                is_conversational=True
            )

        # Start reasoning context for this job
        if self.reasoning_logger:
            try:
                user_input = context.user_input if context else ""
                self.reasoning_logger.start_job(job_id, None, user_input)
            except Exception as e:
                logger.debug(f"Reasoning start_job failed (non-critical): {e}")

        # Order steps by dependencies
        ordered_steps = self._order_by_dependencies(steps)
        logger.debug(f"[MULTI-STEP] Executing {len(ordered_steps)} steps in order")
        logger.info(f"Multi-step: Executing {len(ordered_steps)} steps in order")

        # Log dependency ordering reasoning
        if self.reasoning_logger:
            reasoning = self._explain_dependency_order(steps, ordered_steps)
            try:
                await self.reasoning_logger.log_dependency_reasoning(
                    job_id=job_id,
                    ordered_steps=ordered_steps,
                    reasoning=reasoning
                )
            except Exception as e:
                logger.debug(f"Reasoning log failed (non-critical): {e}")

        results = []
        all_success = True
        created_entities = {}  # Track created entity names for later steps
        total_steps = len(ordered_steps)

        for i, step in enumerate(ordered_steps):
            event_type = step.get("event_type", "")
            payload = step.get("payload", {}).copy()  # Copy to avoid modifying original

            # Normalize params (e.g., "title" -> "bubble_name" for bubble.delete)
            payload = self._normalize_params(event_type, payload)

            # Enrich payload with created entities from previous steps
            # e.g., if bubble.create created "Businessplan", bubble.enter should use it
            if event_type in self.DEPENDENT_INTENTS:
                creator_type = self.DEPENDENT_INTENTS[event_type]
                if creator_type in created_entities:
                    entity_name = created_entities[creator_type]
                    logger.info(f"Multi-step: Enriching {event_type} with {creator_type} result: {entity_name}")
                    # Set appropriate parameter based on event type
                    if event_type == "bubble.enter" and not payload.get("bubble_name"):
                        payload["bubble_name"] = entity_name
                    elif event_type == "idea.create" and not payload.get("bubble_name"):
                        payload["bubble_name"] = entity_name
                    elif event_type == "idea.delete" and not payload.get("bubble_name"):
                        payload["bubble_name"] = entity_name

            # Get executor for this event type
            executor = self._tool_executors.get(event_type)
            if not executor:
                logger.debug(f"[MULTI-STEP] [{i+1}/{len(ordered_steps)}] No executor for {event_type}, skipping")
                logger.warning(f"Multi-step [{i+1}/{len(ordered_steps)}]: No executor for {event_type}, skipping")
                results.append({
                    "event_type": event_type,
                    "success": False,
                    "error": f"Tool {event_type} nicht verfuegbar"
                })
                continue

            try:
                logger.debug(f"[MULTI-STEP] [{i+1}/{total_steps}] Executing {event_type} payload={payload}")
                logger.info(f"Multi-step [{i+1}/{total_steps}]: Executing {event_type}")

                # Log tool start reasoning
                if self.reasoning_logger:
                    try:
                        await self.reasoning_logger.log_tool_start(
                            job_id=job_id,
                            tool_name=event_type,
                            params=payload,
                            step_index=i + 1,
                            total_steps=total_steps,
                            reasoning=f"Executing {event_type} as step {i+1} of {total_steps}"
                        )
                    except Exception as e:
                        logger.debug(f"Reasoning log failed (non-critical): {e}")

                # Execute tool with timing (with tool state tracking)
                try:
                    from tools.session_tools import mark_tool_start, mark_tool_end
                    mark_tool_start()
                except ImportError:
                    mark_tool_end = None

                start_time = time.perf_counter()
                try:
                    result = executor(payload) if payload else executor({})
                finally:
                    if 'mark_tool_end' in dir() and mark_tool_end:
                        mark_tool_end()
                latency_ms = (time.perf_counter() - start_time) * 1000

                # Track created entities for dependency resolution
                if event_type in self.CREATOR_INTENTS:
                    entity_name = payload.get("title") or payload.get("name") or ""
                    if entity_name:
                        created_entities[event_type] = entity_name

                # Format result
                result_str = format_result_for_voice(event_type, result)

                # Log successful tool execution
                if HAS_TOOL_LOGGER and get_tool_logger:
                    get_tool_logger().log_execution(
                        tool_name=event_type,
                        params=payload or {},
                        result=result_str,
                        latency_ms=latency_ms,
                        success=True,
                        source_event="multi_step"
                    )

                results.append({
                    "event_type": event_type,
                    "success": True,
                    "result": result_str
                })

                # Log tool completion reasoning
                if self.reasoning_logger:
                    try:
                        await self.reasoning_logger.log_tool_complete(
                            job_id=job_id,
                            tool_name=event_type,
                            result=result_str,
                            step_index=i + 1,
                            total_steps=total_steps,
                            latency_ms=latency_ms
                        )
                    except Exception as e:
                        logger.debug(f"Reasoning log failed (non-critical): {e}")

                logger.info(f"Multi-step [{i+1}/{total_steps}]: {event_type} completed")

            except Exception as e:
                logger.error(f"Multi-step [{i+1}/{total_steps}]: {event_type} failed: {e}")
                # Log failed tool execution
                if HAS_TOOL_LOGGER and get_tool_logger:
                    get_tool_logger().log_error(
                        tool_name=event_type,
                        params=payload or {},
                        error=str(e),
                        latency_ms=0
                    )

                # Log tool error reasoning
                if self.reasoning_logger:
                    try:
                        await self.reasoning_logger.log_tool_error(
                            job_id=job_id,
                            tool_name=event_type,
                            error=str(e),
                            step_index=i + 1,
                            total_steps=total_steps
                        )
                    except Exception as re:
                        logger.debug(f"Reasoning log failed (non-critical): {re}")

                results.append({
                    "event_type": event_type,
                    "success": False,
                    "error": str(e)
                })
                all_success = False
                # Continue with remaining steps (best effort)

        # Generate summary for voice output
        summary = format_multi_step_result(results)

        # Log result reasoning and end job
        if self.reasoning_logger:
            try:
                await self.reasoning_logger.log_result_reasoning(
                    job_id=job_id,
                    summary=summary,
                    voice_response=summary
                )
                self.reasoning_logger.end_job(job_id)
            except Exception as e:
                logger.debug(f"Reasoning log failed (non-critical): {e}")

        return OrchestrationResult(
            job_id=job_id,
            event_type="multi_step",
            stream="local",
            response_hint=summary,
            is_conversational=False,
            error=None if all_success else "Some steps failed"
        )

    def _order_by_dependencies(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Order steps based on dependency rules using Kahn's algorithm.

        Args:
            steps: List of {event_type, payload} dicts

        Returns:
            Reordered list with dependencies satisfied
        """
        if len(steps) <= 1:
            return steps

        n = len(steps)

        # Build dependency graph
        creator_indices = {}  # event_type -> index
        in_degree = {i: 0 for i in range(n)}
        graph = {i: [] for i in range(n)}  # adjacency list

        for i, step in enumerate(steps):
            event_type = step.get("event_type", "")

            # Track creator intents
            if event_type in self.CREATOR_INTENTS:
                creator_indices[event_type] = i

            # Check if this step depends on a creator
            creator_type = self.DEPENDENT_INTENTS.get(event_type)
            if creator_type and creator_type in creator_indices:
                dep_index = creator_indices[creator_type]
                graph[dep_index].append(i)
                in_degree[i] += 1
                logger.debug(f"Multi-step: {event_type} (index {i}) depends on {creator_type} (index {dep_index})")

        # Kahn's algorithm for topological sort
        queue = [i for i in range(n) if in_degree[i] == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)

            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles (should not happen with our dependency rules)
        if len(order) != n:
            logger.warning("Multi-step: Circular dependency detected, using original order")
            return steps

        # Reorder steps
        ordered = [steps[i] for i in order]
        logger.debug(f"Multi-step: Reordered steps: {[s.get('event_type') for s in ordered]}")
        return ordered

    def _explain_dependency_order(
        self,
        original_steps: List[Dict[str, Any]],
        ordered_steps: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a human-readable explanation of the dependency ordering.

        Args:
            original_steps: Steps before ordering
            ordered_steps: Steps after dependency ordering

        Returns:
            Explanation string for reasoning log
        """
        if len(ordered_steps) <= 1:
            return "Single step, no ordering needed"

        original_order = [s.get("event_type", "") for s in original_steps]
        new_order = [s.get("event_type", "") for s in ordered_steps]

        if original_order == new_order:
            return f"Order unchanged: {' → '.join(new_order)}"

        # Find dependencies that caused reordering
        explanations = []
        for i, step in enumerate(ordered_steps):
            event_type = step.get("event_type", "")
            creator_type = self.DEPENDENT_INTENTS.get(event_type)
            if creator_type:
                # Find where creator is in the order
                for _, prev_step in enumerate(ordered_steps[:i]):
                    if prev_step.get("event_type") == creator_type:
                        explanations.append(f"{event_type} depends on {creator_type}")
                        break

        if explanations:
            deps = "; ".join(explanations)
            return f"Reordered based on dependencies ({deps}): {' → '.join(new_order)}"

        return f"Reordered: {' → '.join(new_order)}"
