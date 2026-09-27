"""Tests for hermes_hands.policy."""

import pytest

from hermes_hands.policy import Action, PolicyGate, PolicyDeniedError, MAX_TEXT_LENGTH, MAX_MOUSE_COORD


class TestPolicyGate:
    def setup_method(self):
        self.gate = PolicyGate()

    def test_readonly_actions_allowed(self):
        assert self.gate.check(Action.CHECK_AUTH).allowed
        assert self.gate.check(Action.GET_HID_STATE).allowed
        assert self.gate.check(Action.SNAPSHOT).allowed

    def test_move_mouse_allowed(self):
        assert self.gate.check(Action.MOVE_MOUSE, to_x=100, to_y=200).allowed

    def test_move_mouse_coord_too_large(self):
        d = self.gate.check(Action.MOVE_MOUSE, to_x=99999, to_y=0)
        assert not d.allowed
        assert "exceeds max" in d.reason

    def test_move_mouse_negative_too_large(self):
        d = self.gate.check(Action.MOVE_MOUSE, to_x=-99999, to_y=0)
        assert not d.allowed

    def test_type_text_allowed(self):
        assert self.gate.check(Action.TYPE_TEXT, text="HERMES_HANDS_MVP_OK").allowed

    def test_type_text_too_long(self):
        long_text = "A" * (MAX_TEXT_LENGTH + 1)
        d = self.gate.check(Action.TYPE_TEXT, text=long_text)
        assert not d.allowed
        assert "exceeds max" in d.reason

    def test_type_text_forbidden_pattern_esc(self):
        d = self.gate.check(Action.TYPE_TEXT, text="hello\x1bworld")
        assert not d.allowed
        assert "Forbidden" in d.reason

    def test_type_text_forbidden_sudo(self):
        d = self.gate.check(Action.TYPE_TEXT, text="sudo rm -rf /")
        assert not d.allowed

    def test_type_text_forbidden_fork_bomb(self):
        d = self.gate.check(Action.TYPE_TEXT, text=":(){ :|:& };:")
        assert not d.allowed

    def test_click_mouse_denied_by_default(self):
        d = self.gate.check(Action.CLICK_MOUSE, button="left")
        assert not d.allowed
        assert "approval" in d.reason

    def test_click_mouse_allowed_when_enabled(self):
        gate = PolicyGate(allow_mouse_click=True)
        assert gate.check(Action.CLICK_MOUSE, button="left").allowed

    def test_click_mouse_invalid_button(self):
        gate = PolicyGate(allow_mouse_click=True)
        d = gate.check(Action.CLICK_MOUSE, button="supernova")
        assert not d.allowed

    def test_scroll_allowed(self):
        assert self.gate.check(Action.SCROLL, delta_x=0, delta_y=100).allowed

    def test_atx_power_denied(self):
        d = self.gate.check(Action.ATX_POWER)
        assert not d.allowed
        assert "dangerous" in d.reason.lower() or "approval" in d.reason.lower()

    def test_atx_reset_denied(self):
        d = self.gate.check(Action.ATX_RESET)
        assert not d.allowed

    def test_msd_actions_denied(self):
        assert not self.gate.check(Action.MSD_CONNECT).allowed
        assert not self.gate.check(Action.MSD_UPLOAD).allowed

    def test_send_shortcut_denied(self):
        d = self.gate.check(Action.SEND_SHORTCUT)
        assert not d.allowed

    def test_send_key_denied(self):
        d = self.gate.check(Action.SEND_KEY)
        assert not d.allowed

    def test_dangerous_action_with_explicit_approval(self):
        gate = PolicyGate(allow_dangerous={Action.ATX_POWER})
        assert gate.check(Action.ATX_POWER).allowed
        # But reset still denied
        assert not gate.check(Action.ATX_RESET).allowed

    def test_assert_allowed_raises(self):
        with pytest.raises(PolicyDeniedError):
            self.gate.assert_allowed(Action.ATX_POWER)

    def test_assert_allowed_passes(self):
        self.gate.assert_allowed(Action.SNAPSHOT)  # Should not raise
