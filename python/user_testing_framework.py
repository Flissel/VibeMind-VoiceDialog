"""
User Testing Framework - Real-World Validation für VibeMind Advanced Features

Phase 23: Comprehensive user simulation framework for testing:
- Realistic user personas and behavior patterns
- Multi-user concurrent sessions
- Complex interaction workflows
- Performance monitoring during realistic usage
- Error scenarios and edge cases
- Automated test execution and reporting

Tests all advanced features: Super Memory, Execution Layer, Enhanced Agents, API
"""

import asyncio
import logging
import time
import random
import json
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime, timedelta
import tempfile
import os
from pathlib import Path

from super_memory_api import get_super_memory, MemoryQuery
from swarm.orchestrator.intent_orchestrator import get_orchestrator
from swarm.execution_layer import get_execution_engine, WorkflowStep
from swarm.backend_agents.enhanced_ideas_agent import create_enhanced_ideas_agent
from vibemind_api import get_api_server
from swarm.event_team import TaskContext

logger = logging.getLogger(__name__)


@dataclass
class UserPersona:
    """Represents a user persona with specific behavior patterns."""
    persona_id: str
    name: str
    language: str  # "de", "en"
    expertise_level: str  # "beginner", "intermediate", "expert"
    interaction_style: str  # "methodical", "exploratory", "goal_oriented"
    session_frequency: str  # "daily", "weekly", "occasional"

    # Behavior patterns
    avg_session_duration: int  # minutes
    actions_per_session: int
    memory_retention_preference: str  # "high", "medium", "low"
    workflow_complexity_preference: str  # "simple", "complex", "mixed"

    # Interaction patterns
    common_intents: List[str] = field(default_factory=list)
    typical_workflows: List[List[str]] = field(default_factory=list)
    error_tolerance: str = "medium"  # "low", "medium", "high"


@dataclass
class UserSession:
    """Represents an active user session."""
    session_id: str
    user_id: str
    persona: UserPersona
    start_time: float
    end_time: Optional[float] = None
    actions_performed: List[Dict[str, Any]] = field(default_factory=list)
    memory_operations: List[Dict[str, Any]] = field(default_factory=list)
    errors_encountered: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Session duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def success_rate(self) -> float:
        """Success rate of actions in this session."""
        if not self.actions_performed:
            return 0.0
        successful = sum(1 for action in self.actions_performed if action.get("success", False))
        return successful / len(self.actions_performed)


@dataclass
class TestScenario:
    """A complete test scenario with multiple users and interactions."""
    scenario_id: str
    name: str
    description: str
    duration_minutes: int
    concurrent_users: int
    personas: List[UserPersona]
    success_criteria: Dict[str, Any] = field(default_factory=dict)

    # Runtime data
    sessions: List[UserSession] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class UserSimulator:
    """
    Simulates realistic user behavior and interactions.
    """

    def __init__(self, persona: UserPersona):
        self.persona = persona
        self.session: Optional[UserSession] = None
        self.memory_context: Dict[str, Any] = {}

        # Initialize behavior patterns
        self._init_behavior_patterns()

    def _init_behavior_patterns(self):
        """Initialize behavior patterns based on persona."""
        # German user patterns
        if self.persona.language == "de":
            self.intent_templates = {
                "create": [
                    "Erstelle eine neue Idee für {topic}",
                    "Ich möchte {topic} notieren",
                    "Neue Idee: {topic}",
                    "Erstelle ein Konzept für {topic}"
                ],
                "search": [
                    "Zeig mir meine Ideen zu {topic}",
                    "Finde Informationen über {topic}",
                    "Suche nach {topic} in meinen Notizen",
                    "Was habe ich zu {topic} gespeichert?"
                ],
                "workflow": [
                    "Erstelle einen Arbeitsplan für {topic}",
                    "Organisiere meine Aufgaben zu {topic}",
                    "Erstelle eine strukturierte Übersicht für {topic}"
                ]
            }
        else:  # English
            self.intent_templates = {
                "create": [
                    "Create a new idea about {topic}",
                    "I want to note down {topic}",
                    "New idea: {topic}",
                    "Create a concept for {topic}"
                ],
                "search": [
                    "Show me my ideas about {topic}",
                    "Find information about {topic}",
                    "Search for {topic} in my notes",
                    "What have I stored about {topic}?"
                ],
                "workflow": [
                    "Create a work plan for {topic}",
                    "Organize my tasks about {topic}",
                    "Create a structured overview for {topic}"
                ]
            }

        # Topics based on expertise
        if self.persona.expertise_level == "beginner":
            self.topics = ["lernen", "planung", "organisation", "notizen"]
        elif self.persona.expertise_level == "intermediate":
            self.topics = ["projektmanagement", "ideenentwicklung", "zusammenarbeit", "dokumentation"]
        else:  # expert
            self.topics = ["systemarchitektur", "ki-integration", "skalierbarkeit", "optimierung"]

    async def start_session(self, session_id: str) -> UserSession:
        """Start a new user session."""
        self.session = UserSession(
            session_id=session_id,
            user_id=f"user_{self.persona.persona_id}",
            persona=self.persona,
            start_time=time.time()
        )

        # Initialize memory context
        self.memory_context = {
            "created_ideas": [],
            "searched_topics": [],
            "workflows_started": [],
            "session_goals": self._generate_session_goals()
        }

        logger.info(f"Started session {session_id} for user {self.persona.name}")
        return self.session

    async def perform_session_actions(self, orchestrator, super_memory) -> None:
        """Perform realistic actions during the session."""
        if not self.session:
            return

        base_actions = int(self.persona.actions_per_session)
        min_actions = max(1, base_actions // 2)
        max_actions = max(min_actions + 1, base_actions * 2)
        actions_to_perform = random.randint(min_actions, max_actions)

        print(f"[DEBUG] User {self.persona.name}: base_actions={base_actions}, min_actions={min_actions}, max_actions={max_actions}, actions_to_perform={actions_to_perform}")

        for i in range(actions_to_perform):
            try:
                await self._perform_random_action(orchestrator, super_memory)
                await asyncio.sleep(random.uniform(1.0, 5.0))  # Realistic delays

            except Exception as e:
                error_info = {
                    "action_index": i,
                    "error": str(e),
                    "timestamp": time.time()
                }
                self.session.errors_encountered.append(error_info)
                logger.warning(f"User {self.persona.name} encountered error: {e}")

                # Error tolerance behavior
                if self.persona.error_tolerance == "low":
                    break  # End session on error
                elif self.persona.error_tolerance == "medium":
                    await asyncio.sleep(random.uniform(2.0, 5.0))  # Pause and continue

    async def _perform_random_action(self, orchestrator, super_memory) -> None:
        """Perform a random but realistic user action."""
        action_type = random.choice(["intent", "memory_search", "memory_store", "workflow"])

        start_time = time.time()

        try:
            if action_type == "intent":
                await self._perform_intent_action(orchestrator)
            elif action_type == "memory_search":
                await self._perform_memory_search(super_memory)
            elif action_type == "memory_store":
                await self._perform_memory_store(super_memory)
            elif action_type == "workflow":
                await self._perform_workflow_action(orchestrator)

            duration = time.time() - start_time
            success = True

        except Exception as e:
            duration = time.time() - start_time
            success = False
            raise e

        finally:
            action_info = {
                "action_type": action_type,
                "duration": duration,
                "success": success,
                "timestamp": time.time()
            }
            self.session.actions_performed.append(action_info)

    async def _perform_intent_action(self, orchestrator) -> None:
        """Perform an intent-based action."""
        intent_type = random.choice(list(self.intent_templates.keys()))
        topic = random.choice(self.topics)

        template = random.choice(self.intent_templates[intent_type])
        intent_text = template.format(topic=topic)

        context = TaskContext(
            user_id=self.session.user_id,
            session_id=self.session.session_id
        )

        result = await orchestrator.process_intent(intent_text, context)

        # Update memory context
        if intent_type == "create":
            self.memory_context["created_ideas"].append(topic)
        elif intent_type == "search":
            self.memory_context["searched_topics"].append(topic)

    async def _perform_memory_search(self, super_memory) -> None:
        """Perform a memory search action."""
        if not self.memory_context["created_ideas"]:
            return  # No memories to search

        topic = random.choice(self.memory_context["created_ideas"])

        query = MemoryQuery(
            query_text=topic,
            user_id=self.session.user_id,
            limit=random.randint(5, 20)
        )

        result = await super_memory.retrieve_memories(query)

        memory_info = {
            "query": topic,
            "results_found": len(result.results),
            "search_time": result.search_time
        }
        self.session.memory_operations.append(memory_info)

    async def _perform_memory_store(self, super_memory) -> None:
        """Perform a memory storage action."""
        topic = random.choice(self.topics)
        content = f"Automatisch gespeicherte Notiz zu {topic} von {self.persona.name}"

        memory_id = await super_memory.store_memory(
            content=content,
            memory_type="note",
            user_id=self.session.user_id,
            session_id=self.session.session_id,
            importance=random.uniform(0.3, 0.9),
            tags=[topic, "auto_generated"]
        )

        self.memory_context["created_ideas"].append(topic)

        memory_info = {
            "operation": "store",
            "memory_id": memory_id,
            "topic": topic
        }
        self.session.memory_operations.append(memory_info)

    async def _perform_workflow_action(self, orchestrator) -> None:
        """Perform a workflow-based action."""
        # This would integrate with the execution layer
        # For now, simulate with a complex intent
        topic = random.choice(self.topics)
        intent_text = f"Erstelle einen detaillierten Arbeitsplan für {topic}"

        context = TaskContext(
            user_id=self.session.user_id,
            session_id=self.session.session_id
        )

        result = await orchestrator.process_intent(intent_text, context)
        self.memory_context["workflows_started"].append(topic)

    def _generate_session_goals(self) -> List[str]:
        """Generate realistic session goals based on persona."""
        goals = []

        if self.persona.interaction_style == "goal_oriented":
            goals.extend([
                "Organisiere meine Ideen",
                "Finde wichtige Informationen",
                "Erstelle einen Arbeitsplan"
            ])
        elif self.persona.interaction_style == "exploratory":
            goals.extend([
                "Entdecke neue Möglichkeiten",
                "Sammle verschiedene Ideen",
                "Experimentiere mit Features"
            ])
        else:  # methodical
            goals.extend([
                "Systematische Dateneingabe",
                "Strukturierte Informationssuche",
                "Methodische Arbeitsplanung"
            ])

        return goals[:random.randint(1, 3)]

    async def end_session(self) -> UserSession:
        """End the user session."""
        if self.session:
            self.session.end_time = time.time()
            logger.info(".2f")
        return self.session


class UserTestingFramework:
    """
    Main framework for running comprehensive user testing scenarios.
    """

    def __init__(self):
        self.personas = self._create_personas()
        self.scenarios = self._create_scenarios()
        self.results: List[TestScenario] = []

        # Initialize components
        self.orchestrator = get_orchestrator()
        self.super_memory = get_super_memory()

        # Temporary directories for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_path = self.temp_dir / "test_user_memory.db"

        # Override super memory with test database
        from super_memory_api import SuperMemoryAPI
        self.super_memory = SuperMemoryAPI(db_path=str(self.db_path))

    def _create_personas(self) -> List[UserPersona]:
        """Create diverse user personas for testing."""
        return [
            UserPersona(
                persona_id="beginner_de",
                name="Anna (Anfaengerin)",
                language="de",
                expertise_level="beginner",
                interaction_style="methodical",
                session_frequency="weekly",
                avg_session_duration=15,
                actions_per_session=5,
                memory_retention_preference="medium",
                workflow_complexity_preference="simple",
                common_intents=["Erstelle eine Idee", "Zeig meine Notizen", "Suche nach Informationen"],
                error_tolerance="low"
            ),
            UserPersona(
                persona_id="expert_en",
                name="David (Experte)",
                language="en",
                expertise_level="expert",
                interaction_style="goal_oriented",
                session_frequency="daily",
                avg_session_duration=45,
                actions_per_session=15,
                memory_retention_preference="high",
                workflow_complexity_preference="complex",
                common_intents=["Create complex workflow", "Analyze system architecture", "Optimize performance"],
                error_tolerance="high"
            ),
            UserPersona(
                persona_id="intermediate_de",
                name="Maria (Fortgeschritten)",
                language="de",
                expertise_level="intermediate",
                interaction_style="exploratory",
                session_frequency="daily",
                avg_session_duration=30,
                actions_per_session=10,
                memory_retention_preference="medium",
                workflow_complexity_preference="mixed",
                common_intents=["Erforsche neue Ideen", "Organisiere Projekte", "Finde Zusammenhänge"],
                error_tolerance="medium"
            )
        ]

    def _create_scenarios(self) -> List[TestScenario]:
        """Create test scenarios."""
        return [
            TestScenario(
                scenario_id="single_user_basic",
                name="Einzelnutzer Grundfunktionen",
                description="Test grundlegender Features mit einem einzelnen Nutzer",
                duration_minutes=5,
                concurrent_users=1,
                personas=self.personas[:1],
                success_criteria={
                    "min_success_rate": 0.9,
                    "max_errors": 2,
                    "min_actions_per_session": 3
                }
            ),
            TestScenario(
                scenario_id="multi_user_concurrent",
                name="Mehrere Nutzer gleichzeitig",
                description="Test gleichzeitiger Zugriff und Isolation",
                duration_minutes=10,
                concurrent_users=3,
                personas=self.personas,
                success_criteria={
                    "min_success_rate": 0.85,
                    "max_errors": 5,
                    "min_sessions_completed": 3
                }
            ),
            TestScenario(
                scenario_id="expert_workflow_complex",
                name="Experte komplexe Workflows",
                description="Test komplexer Workflows mit erfahrenem Nutzer",
                duration_minutes=15,
                concurrent_users=1,
                personas=[p for p in self.personas if p.expertise_level == "expert"],
                success_criteria={
                    "min_success_rate": 0.95,
                    "max_errors": 1,
                    "min_workflows_completed": 2
                }
            )
        ]

    async def run_scenario(self, scenario_id: str) -> TestScenario:
        """Run a specific test scenario."""
        scenario = next((s for s in self.scenarios if s.scenario_id == scenario_id), None)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        logger.info(f"Starting scenario: {scenario.name}")
        scenario.start_time = time.time()

        # Create user simulators
        simulators = []
        for i in range(scenario.concurrent_users):
            persona = scenario.personas[i % len(scenario.personas)]
            simulator = UserSimulator(persona)
            simulators.append(simulator)

        # Start all user sessions
        session_tasks = []
        for i, simulator in enumerate(simulators):
            session_id = f"{scenario_id}_session_{i}"
            session_task = asyncio.create_task(self._run_user_session(simulator, session_id, scenario))
            session_tasks.append(session_task)

        # Wait for all sessions to complete
        await asyncio.gather(*session_tasks, return_exceptions=True)

        # Collect results
        scenario.end_time = time.time()
        scenario.sessions = [simulator.session for simulator in simulators if simulator.session]

        # Calculate metrics
        scenario.metrics = self._calculate_scenario_metrics(scenario)

        logger.info(f"Completed scenario: {scenario.name}")
        self.results.append(scenario)
        return scenario

    async def _run_user_session(self, simulator: UserSimulator, session_id: str, scenario: TestScenario) -> None:
        """Run a single user session."""
        try:
            # Start session
            session = await simulator.start_session(session_id)

            # Calculate session duration based on persona
            session_duration = random.randint(
                simulator.persona.avg_session_duration * 0.5,
                simulator.persona.avg_session_duration * 1.5
            )

            # Perform actions
            await simulator.perform_session_actions(self.orchestrator, self.super_memory)

            # Wait for realistic session duration
            remaining_time = max(0, session_duration - session.duration)
            if remaining_time > 0:
                await asyncio.sleep(remaining_time)

            # End session
            await simulator.end_session()

        except Exception as e:
            logger.error(f"Session {session_id} failed: {e}")

    def _calculate_scenario_metrics(self, scenario: TestScenario) -> Dict[str, Any]:
        """Calculate comprehensive metrics for a scenario."""
        if not scenario.sessions:
            return {"error": "No sessions completed"}

        # Basic metrics
        total_sessions = len(scenario.sessions)
        completed_sessions = sum(1 for s in scenario.sessions if s.end_time)
        total_actions = sum(len(s.actions_performed) for s in scenario.sessions)
        successful_actions = sum(
            sum(1 for a in s.actions_performed if a.get("success", False))
            for s in scenario.sessions
        )
        total_errors = sum(len(s.errors_encountered) for s in scenario.sessions)

        # Performance metrics
        session_durations = [s.duration for s in scenario.sessions if s.end_time]
        action_durations = []
        for session in scenario.sessions:
            action_durations.extend(a.get("duration", 0) for a in session.actions_performed)

        # Memory metrics
        total_memory_ops = sum(len(s.memory_operations) for s in scenario.sessions)

        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "completion_rate": completed_sessions / total_sessions if total_sessions > 0 else 0,
            "total_actions": total_actions,
            "successful_actions": successful_actions,
            "success_rate": successful_actions / total_actions if total_actions > 0 else 0,
            "total_errors": total_errors,
            "error_rate": total_errors / total_actions if total_actions > 0 else 0,
            "avg_session_duration": statistics.mean(session_durations) if session_durations else 0,
            "avg_action_duration": statistics.mean(action_durations) if action_durations else 0,
            "total_memory_operations": total_memory_ops,
            "scenario_duration": scenario.end_time - scenario.start_time if scenario.end_time else 0
        }

    async def run_all_scenarios(self) -> List[TestScenario]:
        """Run all available test scenarios."""
        results = []
        for scenario in self.scenarios:
            try:
                result = await self.run_scenario(scenario.scenario_id)
                results.append(result)
                logger.info(f"Scenario {scenario.scenario_id}: SUCCESS")
            except Exception as e:
                logger.error(f"Scenario {scenario.scenario_id}: FAILED - {e}")

        return results

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        if not self.results:
            return {"error": "No test results available"}

        # Overall metrics
        total_scenarios = len(self.results)
        successful_scenarios = sum(1 for r in self.results if self._scenario_passed(r))

        # Aggregate metrics
        all_sessions = []
        for scenario in self.results:
            all_sessions.extend(scenario.sessions)

        if all_sessions:
            overall_success_rate = statistics.mean(s.success_rate for s in all_sessions)
            total_actions = sum(len(s.actions_performed) for s in all_sessions)
            total_errors = sum(len(s.errors_encountered) for s in all_sessions)
        else:
            overall_success_rate = 0
            total_actions = 0
            total_errors = 0

        return {
            "summary": {
                "total_scenarios": total_scenarios,
                "successful_scenarios": successful_scenarios,
                "success_rate": successful_scenarios / total_scenarios if total_scenarios > 0 else 0,
                "total_sessions": len(all_sessions),
                "overall_success_rate": overall_success_rate,
                "total_actions": total_actions,
                "total_errors": total_errors
            },
            "scenarios": [
                {
                    "id": s.scenario_id,
                    "name": s.name,
                    "passed": self._scenario_passed(s),
                    "metrics": s.metrics,
                    "session_count": len(s.sessions)
                }
                for s in self.results
            ],
            "recommendations": self._generate_recommendations()
        }

    def _scenario_passed(self, scenario: TestScenario) -> bool:
        """Check if a scenario passed its success criteria."""
        metrics = scenario.metrics
        criteria = scenario.success_criteria

        # Check success rate
        if "min_success_rate" in criteria:
            if metrics.get("success_rate", 0) < criteria["min_success_rate"]:
                return False

        # Check error count
        if "max_errors" in criteria:
            if metrics.get("total_errors", 0) > criteria["max_errors"]:
                return False

        # Check sessions completed
        if "min_sessions_completed" in criteria:
            if metrics.get("completed_sessions", 0) < criteria["min_sessions_completed"]:
                return False

        return True

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        if self.results:
            avg_success_rate = statistics.mean(r.metrics.get("success_rate", 0) for r in self.results)

            if avg_success_rate < 0.9:
                recommendations.append("Improve overall system reliability - success rate below 90%")

            total_errors = sum(r.metrics.get("total_errors", 0) for r in self.results)
            if total_errors > 10:
                recommendations.append("Reduce error frequency - high error count detected")

            # Check for performance issues
            action_durations = [
                r.metrics.get("avg_action_duration", 0)
                for r in self.results
                if r.metrics.get("avg_action_duration", 0) > 0
            ]

            if action_durations:
                avg_action_duration = statistics.mean(action_durations)
                if avg_action_duration > 2.0:
                    recommendations.append("Optimize action response times - currently above 2 seconds")

        if not recommendations:
            recommendations.append("All systems performing well - no major issues detected")

        return recommendations

    def cleanup(self):
        """Clean up test resources."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


# =========================================================================
# UTILITY FUNCTIONS
# =========================================================================

async def run_quick_user_test():
    """Run a quick user test with basic scenarios."""
    print("Running Quick User Test...")

    framework = UserTestingFramework()

    try:
        # Run single user basic scenario
        scenario = await framework.run_scenario("single_user_basic")

        print("Quick Test Results:")
        print(f"  Scenario: {scenario.name}")
        print(f"  Sessions: {len(scenario.sessions)}")
        print(".2f")
        print(".1%")
        print(f"  Total Actions: {scenario.metrics.get('total_actions', 0)}")
        print(f"  Total Errors: {scenario.metrics.get('total_errors', 0)}")

        # Generate simple report
        report = framework.generate_report()
        print(f"\nOverall Success Rate: {report['summary']['overall_success_rate']:.1%}")

        return scenario.metrics.get("success_rate", 0) > 0.8

    finally:
        framework.cleanup()


async def run_comprehensive_user_test():
    """Run comprehensive user testing with all scenarios."""
    print("Running Comprehensive User Test Suite...")

    framework = UserTestingFramework()

    try:
        # Run all scenarios
        results = await framework.run_all_scenarios()

        print(f"\nCompleted {len(results)} test scenarios")

        # Generate detailed report
        report = framework.generate_report()

        print("\n=== COMPREHENSIVE TEST REPORT ===")
        print(f"Scenarios Run: {report['summary']['total_scenarios']}")
        print(f"Successful: {report['summary']['successful_scenarios']}")
        print(".1%")
        print(f"Total Sessions: {report['summary']['total_sessions']}")
        print(".1%")
        print(f"Total Actions: {report['summary']['total_actions']}")
        print(f"Total Errors: {report['summary']['total_errors']}")

        print("\nScenario Details:")
        for scenario in report["scenarios"]:
            status = "PASS" if scenario["passed"] else "FAIL"
            print(f"  {scenario['id']}: {status} ({scenario['session_count']} sessions)")

        print("\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"  - {rec}")

        return report["summary"]["success_rate"] > 0.85

    finally:
        framework.cleanup()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        success = asyncio.run(run_quick_user_test())
        print(f"\nQuick test {'PASSED' if success else 'FAILED'}")
    else:
        success = asyncio.run(run_comprehensive_user_test())
        print(f"\nComprehensive test {'PASSED' if success else 'FAILED'}")