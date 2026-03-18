"""Tests for eyeTerm command parser regex grammar."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spaces.desktop.eyeterm.audio.command_parser import CommandParser, ParsedCommand


class TestCommandParser:
    def setup_method(self):
        self.parser = CommandParser()

    # --- Control commands ---

    def test_apply(self):
        cmd = self.parser.parse("apply")
        assert cmd.action == "apply"

    def test_apply_german(self):
        cmd = self.parser.parse("anwenden")
        assert cmd.action == "apply"

    def test_cancel(self):
        cmd = self.parser.parse("cancel")
        assert cmd.action == "cancel"

    def test_cancel_german(self):
        cmd = self.parser.parse("abbrechen")
        assert cmd.action == "cancel"

    def test_recalibrate(self):
        cmd = self.parser.parse("recalibrate")
        assert cmd.action == "recalibrate"

    def test_calibrate_german(self):
        cmd = self.parser.parse("kalibrieren")
        assert cmd.action == "recalibrate"

    def test_undo(self):
        cmd = self.parser.parse("undo")
        assert cmd.action == "undo"

    # --- Read ---

    def test_read(self):
        cmd = self.parser.parse("read")
        assert cmd.action == "read"

    def test_read_this(self):
        cmd = self.parser.parse("read this")
        assert cmd.action == "read"

    def test_lies_vor(self):
        cmd = self.parser.parse("lies vor")
        assert cmd.action == "read"

    def test_vorlesen(self):
        cmd = self.parser.parse("vorlesen")
        assert cmd.action == "read"

    # --- Click ---

    def test_click_bare(self):
        cmd = self.parser.parse("click")
        assert cmd.action == "click"
        assert cmd.target is None

    def test_click_target(self):
        cmd = self.parser.parse("click on OK button")
        assert cmd.action == "click"
        assert cmd.target == "OK button"

    def test_klick_auf(self):
        cmd = self.parser.parse("klick auf Speichern")
        assert cmd.action == "click"
        assert cmd.target == "Speichern"

    # --- Type ---

    def test_type(self):
        cmd = self.parser.parse("type hello world")
        assert cmd.action == "type"
        assert cmd.prompt == "hello world"

    def test_schreibe(self):
        cmd = self.parser.parse("schreibe Hallo Welt")
        assert cmd.action == "type"
        assert cmd.prompt == "Hallo Welt"

    # --- Select ---

    def test_select(self):
        cmd = self.parser.parse("select")
        assert cmd.action == "select"

    def test_select_target(self):
        cmd = self.parser.parse("select the second item")
        assert cmd.action == "select"
        assert cmd.target == "the second item"

    def test_markiere(self):
        cmd = self.parser.parse("markiere das")
        assert cmd.action == "select"

    # --- Edit ---

    def test_edit_with_file_and_lines(self):
        cmd = self.parser.parse("edit src/auth.py lines 120 to 160: add logging")
        assert cmd.action == "edit"
        assert cmd.file_path == "src/auth.py"
        assert cmd.line_range == (120, 160)
        assert cmd.instruction == "add logging"

    def test_edit_with_dash_range(self):
        cmd = self.parser.parse("edit main.js lines 10-20: refactor loop")
        assert cmd.action == "edit"
        assert cmd.file_path == "main.js"
        assert cmd.line_range == (10, 20)
        assert cmd.instruction == "refactor loop"

    def test_edit_without_file(self):
        cmd = self.parser.parse("edit: replace with async version")
        assert cmd.action == "edit"
        assert cmd.instruction == "replace with async version"

    # --- Run tests ---

    def test_run_tests(self):
        cmd = self.parser.parse("run tests")
        assert cmd.action == "run_tests"

    def test_run_test_singular(self):
        cmd = self.parser.parse("run test")
        assert cmd.action == "run_tests"

    # --- Ask ---

    def test_ask(self):
        cmd = self.parser.parse("ask what is this function doing")
        assert cmd.action == "ask"
        assert cmd.prompt == "what is this function doing"

    def test_frag(self):
        cmd = self.parser.parse("frag was macht diese Funktion")
        assert cmd.action == "ask"
        assert cmd.prompt == "was macht diese Funktion"

    # --- Switch pane ---

    def test_switch_pane(self):
        cmd = self.parser.parse("switch to pane 2")
        assert cmd.action == "switch"
        assert cmd.target == "2"

    def test_switch_pane_short(self):
        cmd = self.parser.parse("switch 1")
        assert cmd.action == "switch"
        assert cmd.target == "1"

    # --- Scroll ---

    def test_scroll_down(self):
        cmd = self.parser.parse("scroll down")
        assert cmd.action == "scroll"
        assert cmd.target == "down"

    def test_scroll_up_amount(self):
        cmd = self.parser.parse("scroll up 5")
        assert cmd.action == "scroll"
        assert cmd.target == "up"
        assert cmd.prompt == "5"

    # --- Freeform fallback ---

    def test_freeform(self):
        cmd = self.parser.parse("do something completely custom")
        assert cmd.action == "freeform"
        assert cmd.prompt == "do something completely custom"

    # --- Edge cases ---

    def test_empty_string(self):
        assert self.parser.parse("") is None

    def test_whitespace_only(self):
        assert self.parser.parse("   ") is None

    def test_case_insensitive(self):
        cmd = self.parser.parse("CLICK on Save")
        assert cmd.action == "click"
        assert cmd.target == "Save"
