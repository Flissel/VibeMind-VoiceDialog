"""Tests for CommandRouter voice command routing."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spaces.desktop.eyeterm.routing.command_router import CommandRouter, RouteTarget


class TestCommandRouter:
    """Test routing logic: direct vs agent team vs local AI."""

    def _router(self):
        return CommandRouter()

    # --- Direct actions ---

    def test_click_routes_direct(self):
        r = self._router()
        result = r.route("klick auf OK")
        assert result.target == RouteTarget.DIRECT
        assert result.command.action == "click"

    def test_type_routes_direct(self):
        r = self._router()
        result = r.route("type hello world")
        assert result.target == RouteTarget.DIRECT
        assert result.command.action == "type"

    def test_scroll_routes_direct(self):
        r = self._router()
        result = r.route("scroll down")
        assert result.target == RouteTarget.DIRECT
        assert result.command.action == "scroll"

    def test_cancel_routes_direct(self):
        r = self._router()
        result = r.route("cancel")
        assert result.target == RouteTarget.DIRECT
        assert result.command.action == "cancel"

    def test_read_routes_direct(self):
        r = self._router()
        result = r.route("lies vor")
        assert result.target == RouteTarget.DIRECT
        assert result.command.action == "read"

    # --- Complex tasks → agent team ---

    def test_complex_task_explicit(self):
        r = self._router()
        result = r.route("erstelle ein umfangreiches Konzept fuer Marketing Strategie")
        assert result.target == RouteTarget.AGENT_TEAM
        assert result.command.action == "complex_task"

    def test_write_pages_routes_agent(self):
        r = self._router()
        result = r.route("schreibe 20 Seiten Business Plan")
        assert result.target == RouteTarget.AGENT_TEAM

    def test_plan_routes_agent(self):
        r = self._router()
        result = r.route("plane eine komplette Architektur fuer das Projekt")
        assert result.target == RouteTarget.AGENT_TEAM

    def test_analyse_routes_agent(self):
        r = self._router()
        result = r.route("analysiere die gesamte Codebase und finde Bugs")
        assert result.target == RouteTarget.AGENT_TEAM

    # --- Freeform with complex keywords → agent team ---

    def test_freeform_long_text_routes_agent(self):
        r = self._router()
        # >15 words → complex
        long_text = "ich brauche eine detaillierte Analyse der aktuellen Situation und einen Vorschlag wie wir das verbessern koennen bitte schau dir alles genau an"
        result = r.route(long_text)
        assert result.target == RouteTarget.AGENT_TEAM

    def test_freeform_with_keyword_routes_agent(self):
        r = self._router()
        result = r.route("erstelle mir bitte etwas")
        assert result.target == RouteTarget.AGENT_TEAM

    # --- Short freeform → local AI ---

    def test_short_freeform_routes_local_ai(self):
        r = self._router()
        result = r.route("was ist das hier")
        assert result.target == RouteTarget.LOCAL_AI
        assert result.command.action == "freeform"

    def test_simple_question_routes_local_ai(self):
        r = self._router()
        result = r.route("wie heisst diese Datei")
        assert result.target == RouteTarget.LOCAL_AI

    # --- Empty input ---

    def test_empty_returns_direct(self):
        r = self._router()
        result = r.route("")
        assert result.target == RouteTarget.DIRECT
        assert result.command is None

    # --- Callbacks fire ---

    def test_direct_callback_fires(self):
        fired = []
        r = CommandRouter(on_direct=lambda cmd, el: fired.append(("direct", cmd.action)))
        r.route("klick auf OK")
        assert len(fired) == 1
        assert fired[0] == ("direct", "click")

    def test_agent_callback_fires(self):
        fired = []
        r = CommandRouter(on_agent_team=lambda text, ctx: fired.append(("agent", text)))
        r.route("erstelle ein komplettes Konzept fuer das neue Produkt")
        assert len(fired) == 1
        assert fired[0][0] == "agent"

    def test_local_ai_callback_fires(self):
        fired = []
        r = CommandRouter(on_local_ai=lambda text, el: fired.append(("ai", text)))
        r.route("was ist das")
        assert len(fired) == 1
        assert fired[0][0] == "ai"
