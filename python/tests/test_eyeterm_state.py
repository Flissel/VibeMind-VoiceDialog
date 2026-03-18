"""Tests for eyeTerm state machine (4 states: IDLE, FOCUSED, POLISHING, PREVIEWING)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from spaces.desktop.eyeterm.state import State, Event, StateMachine


class TestStateMachineTransitions:
    """Test every valid state+event combination."""

    def _sm(self) -> StateMachine:
        return StateMachine()

    # --- IDLE state ---

    def test_idle_gaze_dwell_transitions_to_focused(self):
        sm = self._sm()
        new_state, action = sm.transition(Event.GAZE_DWELL, payload=0)
        assert new_state == State.FOCUSED
        assert action == "focus_pane"
        assert sm.focused_pane == 0

    def test_idle_gaze_dwell_stores_pane_index(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, payload=2)
        assert sm.focused_pane == 2

    def test_idle_ignores_left_wink(self):
        sm = self._sm()
        new_state, action = sm.transition(Event.LEFT_WINK)
        assert new_state == State.IDLE
        assert action is None

    def test_idle_ignores_right_wink(self):
        sm = self._sm()
        new_state, action = sm.transition(Event.RIGHT_WINK)
        assert new_state == State.IDLE
        assert action is None

    def test_idle_ignores_speech_final(self):
        sm = self._sm()
        new_state, action = sm.transition(Event.SPEECH_FINAL, "hello")
        assert new_state == State.IDLE
        assert action is None

    # --- FOCUSED state ---

    def test_focused_gaze_lost_transitions_to_idle(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        new_state, action = sm.transition(Event.GAZE_LOST)
        assert new_state == State.IDLE
        assert action == "unfocus"
        assert sm.focused_pane is None

    def test_focused_gaze_dwell_updates_focus(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        new_state, action = sm.transition(Event.GAZE_DWELL, 1)
        assert new_state == State.FOCUSED
        assert action == "update_focus"
        assert sm.focused_pane == 1

    def test_focused_left_wink_no_transcript_sends_escape(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        # No pending_transcript → fallback escape
        new_state, action = sm.transition(Event.LEFT_WINK)
        assert new_state == State.FOCUSED
        assert action == "send_escape"

    def test_focused_left_wink_with_transcript_starts_polish(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "fix this bug"
        new_state, action = sm.transition(Event.LEFT_WINK)
        assert new_state == State.POLISHING
        assert action == "start_polish"

    def test_focused_right_wink_sends_escape(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        new_state, action = sm.transition(Event.RIGHT_WINK)
        assert new_state == State.FOCUSED
        assert action == "send_escape"

    def test_focused_speech_final_sends_text(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        new_state, action = sm.transition(Event.SPEECH_FINAL, "fix this bug")
        assert new_state == State.FOCUSED
        assert action == "send_text"

    def test_focused_speech_stores_pending_transcript(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.transition(Event.SPEECH_FINAL, "hello world")
        assert sm.pending_transcript == "hello world"

    def test_focused_stays_focused_after_wink(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.transition(Event.LEFT_WINK)
        assert sm.state == State.FOCUSED
        assert sm.focused_pane == 0

    # --- POLISHING state ---

    def test_polishing_complete_transitions_to_previewing(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "fix bug"
        sm.transition(Event.LEFT_WINK)  # → POLISHING
        assert sm.state == State.POLISHING

        new_state, action = sm.transition(Event.POLISH_COMPLETE, "Fix the bug.")
        assert new_state == State.PREVIEWING
        assert action == "show_preview"
        assert sm.polished_text == "Fix the bug."

    def test_polishing_left_wink_cancels(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "fix bug"
        sm.transition(Event.LEFT_WINK)  # → POLISHING

        new_state, action = sm.transition(Event.LEFT_WINK)
        assert new_state == State.FOCUSED
        assert action == "cancel_polish"

    def test_polishing_gaze_lost_cancels_and_unfocuses(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "fix bug"
        sm.transition(Event.LEFT_WINK)  # → POLISHING

        new_state, action = sm.transition(Event.GAZE_LOST)
        assert new_state == State.IDLE
        assert action == "cancel_polish_and_unfocus"
        assert sm.focused_pane is None

    def test_polishing_ignores_gaze_dwell(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "fix bug"
        sm.transition(Event.LEFT_WINK)  # → POLISHING

        new_state, action = sm.transition(Event.GAZE_DWELL, 1)
        assert new_state == State.POLISHING
        assert action is None

    def test_polishing_ignores_right_wink(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "fix bug"
        sm.transition(Event.LEFT_WINK)  # → POLISHING

        new_state, action = sm.transition(Event.RIGHT_WINK)
        assert new_state == State.POLISHING
        assert action is None

    # --- PREVIEWING state ---

    def test_previewing_right_wink_submits(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "fix bug"
        sm.transition(Event.LEFT_WINK)  # → POLISHING
        sm.transition(Event.POLISH_COMPLETE, "Fix the bug.")  # → PREVIEWING

        new_state, action = sm.transition(Event.RIGHT_WINK)
        assert new_state == State.FOCUSED
        assert action == "submit_polished"

    def test_previewing_left_wink_rejects(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "fix bug"
        sm.transition(Event.LEFT_WINK)  # → POLISHING
        sm.transition(Event.POLISH_COMPLETE, "Fix the bug.")  # → PREVIEWING

        new_state, action = sm.transition(Event.LEFT_WINK)
        assert new_state == State.FOCUSED
        assert action == "reject_polished"
        assert sm.polished_text is None

    def test_previewing_timeout_dismisses(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "fix bug"
        sm.transition(Event.LEFT_WINK)  # → POLISHING
        sm.transition(Event.POLISH_COMPLETE, "Fix the bug.")  # → PREVIEWING

        new_state, action = sm.transition(Event.PREVIEW_TIMEOUT)
        assert new_state == State.FOCUSED
        assert action == "dismiss_preview"
        assert sm.polished_text is None

    def test_previewing_gaze_lost_dismisses_and_unfocuses(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "fix bug"
        sm.transition(Event.LEFT_WINK)  # → POLISHING
        sm.transition(Event.POLISH_COMPLETE, "Fix the bug.")  # → PREVIEWING

        new_state, action = sm.transition(Event.GAZE_LOST)
        assert new_state == State.IDLE
        assert action == "dismiss_preview_and_unfocus"

    def test_previewing_ignores_gaze_dwell(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "fix bug"
        sm.transition(Event.LEFT_WINK)
        sm.transition(Event.POLISH_COMPLETE, "Fix.")

        new_state, action = sm.transition(Event.GAZE_DWELL, 1)
        assert new_state == State.PREVIEWING
        assert action is None

    # --- Full flows ---

    def test_full_polish_submit_flow(self):
        sm = self._sm()

        # 1. Look at pane 0
        s, a = sm.transition(Event.GAZE_DWELL, 0)
        assert s == State.FOCUSED
        assert a == "focus_pane"

        # 2. Speak
        s, a = sm.transition(Event.SPEECH_FINAL, "fix this bug")
        assert s == State.FOCUSED
        assert a == "send_text"
        assert sm.pending_transcript == "fix this bug"

        # 3. Left wink → polish
        s, a = sm.transition(Event.LEFT_WINK)
        assert s == State.POLISHING
        assert a == "start_polish"

        # 4. Polish completes
        s, a = sm.transition(Event.POLISH_COMPLETE, "Fix this bug.")
        assert s == State.PREVIEWING
        assert a == "show_preview"

        # 5. Right wink → submit
        s, a = sm.transition(Event.RIGHT_WINK)
        assert s == State.FOCUSED
        assert a == "submit_polished"

    def test_full_polish_reject_flow(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.transition(Event.SPEECH_FINAL, "hello")
        sm.transition(Event.LEFT_WINK)  # → POLISHING
        sm.transition(Event.POLISH_COMPLETE, "Hello.")  # → PREVIEWING

        # Reject
        s, a = sm.transition(Event.LEFT_WINK)
        assert s == State.FOCUSED
        assert a == "reject_polished"
        assert sm.polished_text is None

    def test_switch_panes_flow(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        assert sm.focused_pane == 0
        sm.transition(Event.GAZE_DWELL, 2)
        assert sm.focused_pane == 2
        assert sm.state == State.FOCUSED

    def test_multiple_speech_stays_focused(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 1)
        for text in ["first", "second", "third"]:
            s, a = sm.transition(Event.SPEECH_FINAL, text)
            assert s == State.FOCUSED
            assert a == "send_text"
            assert sm.focused_pane == 1

    # --- Reset ---

    def test_reset(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.pending_transcript = "hello"
        sm.polished_text = "Hello."
        sm.reset()
        assert sm.state == State.IDLE
        assert sm.focused_pane is None
        assert sm.pending_transcript is None
        assert sm.polished_text is None

    # --- History tracking ---

    def test_history_recorded(self):
        sm = self._sm()
        sm.transition(Event.GAZE_DWELL, 0)
        sm.transition(Event.LEFT_WINK)  # no transcript → escape
        assert len(sm.history) == 2
        assert sm.history[0] == (State.IDLE, Event.GAZE_DWELL, State.FOCUSED, "focus_pane")
        assert sm.history[1] == (State.FOCUSED, Event.LEFT_WINK, State.FOCUSED, "send_escape")

    # --- Four states exist ---

    def test_four_states(self):
        states = list(State)
        assert len(states) == 4
        assert State.IDLE in states
        assert State.FOCUSED in states
        assert State.POLISHING in states
        assert State.PREVIEWING in states

    def test_seven_events(self):
        events = list(Event)
        assert len(events) == 7
        assert Event.POLISH_COMPLETE in events
        assert Event.PREVIEW_TIMEOUT in events
