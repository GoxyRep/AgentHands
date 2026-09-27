"""Policy gate — default-deny action allowlist.

Only explicitly approved actions pass through.
ATX, mass storage, shutdown, config changes, arbitrary shortcuts — all denied.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import PolicyDeniedError


class Action(str, Enum):
    """All known Hermes Hands actions."""

    # Read-only (always allowed in MVP)
    CHECK_AUTH = "check_auth"
    GET_HID_STATE = "get_hid_state"
    SNAPSHOT = "snapshot"

    # Input (allowed with constraints)
    MOVE_MOUSE = "move_mouse"
    TYPE_TEXT = "type_text"
    CLICK_MOUSE = "click_mouse"
    SCROLL = "scroll"

    # Dangerous — denied by default, require explicit human approval
    ATX_POWER = "atx_power"
    ATX_RESET = "atx_reset"
    MSD_CONNECT = "msd_connect"
    MSD_DISCONNECT = "msd_disconnect"
    MSD_UPLOAD = "msd_upload"
    SET_HID_PARAMS = "set_hid_params"
    SET_CONNECTED = "set_connected"
    HID_RESET = "hid_reset"
    SEND_SHORTCUT = "send_shortcut"
    SEND_KEY = "send_key"


# Actions that are fundamentally dangerous and require human-in-the-loop
_DANGEROUS_ACTIONS = frozenset({
    Action.ATX_POWER,
    Action.ATX_RESET,
    Action.MSD_CONNECT,
    Action.MSD_DISCONNECT,
    Action.MSD_UPLOAD,
    Action.SET_HID_PARAMS,
    Action.SET_CONNECTED,
    Action.HID_RESET,
    Action.SEND_SHORTCUT,
    Action.SEND_KEY,
})

# Text patterns that are never allowed (system-level shortcuts, shell commands)
_FORBIDDEN_TEXT_PATTERNS = (
    "\x1b",  # ESC sequences
    "sudo ",
    "rm -rf",
    ":(){",  # fork bomb
)

# Max text length for type_text in MVP
MAX_TEXT_LENGTH = 128

# Max absolute mouse coordinate magnitude
MAX_MOUSE_COORD = 32767


@dataclass(frozen=True)
class PolicyDecision:
    """Result of a policy check."""

    allowed: bool
    reason: str = ""


class PolicyGate:
    """Default-deny policy gate.

    Usage:
        gate = PolicyGate()
        gate.check(Action.SNAPSHOT)  # -> allowed
        gate.check(Action.ATX_POWER)  # -> raises PolicyDeniedError
    """

    def __init__(
        self,
        *,
        allow_mouse_click: bool = False,
        allow_shortcut: bool = False,
        allow_dangerous: set[Action] | None = None,
    ) -> None:
        self._allow_mouse_click = allow_mouse_click
        self._allow_shortcut = allow_shortcut
        self._allow_dangerous = allow_dangerous or set()

    def check(
        self,
        action: Action,
        *,
        text: str | None = None,
        to_x: int | None = None,
        to_y: int | None = None,
        delta_x: int | None = None,
        delta_y: int | None = None,
        button: str | None = None,
    ) -> PolicyDecision:
        """Evaluate whether an action is allowed.

        Returns PolicyDecision. Raises PolicyDeniedError if denied.
        """
        # Read-only actions: always allowed
        if action in (Action.CHECK_AUTH, Action.GET_HID_STATE, Action.SNAPSHOT):
            return PolicyDecision(allowed=True)

        # Mouse move — validate coordinates
        if action == Action.MOVE_MOUSE:
            if to_x is not None and abs(to_x) > MAX_MOUSE_COORD:
                return PolicyDecision(
                    False, f"to_x={to_x} exceeds max {MAX_MOUSE_COORD}"
                )
            if to_y is not None and abs(to_y) > MAX_MOUSE_COORD:
                return PolicyDecision(
                    False, f"to_y={to_y} exceeds max {MAX_MOUSE_COORD}"
                )
            if delta_x is not None and abs(delta_x) > MAX_MOUSE_COORD:
                return PolicyDecision(False, f"delta_x exceeds max")
            if delta_y is not None and abs(delta_y) > MAX_MOUSE_COORD:
                return PolicyDecision(False, f"delta_y exceeds max")
            return PolicyDecision(allowed=True)

        # Mouse click — must be explicitly enabled
        if action == Action.CLICK_MOUSE:
            if not self._allow_mouse_click:
                return PolicyDecision(False, "Mouse clicks require explicit approval")
            if button and button not in ("left", "right", "middle"):
                return PolicyDecision(False, f"Unknown button: {button}")
            return PolicyDecision(allowed=True)

        # Scroll — allowed (low risk)
        if action == Action.SCROLL:
            return PolicyDecision(allowed=True)

        # Type text — validate content
        if action == Action.TYPE_TEXT:
            if text is None:
                return PolicyDecision(False, "text is required for type_text")
            if len(text) > MAX_TEXT_LENGTH:
                return PolicyDecision(
                    False, f"Text length {len(text)} exceeds max {MAX_TEXT_LENGTH}"
                )
            for pattern in _FORBIDDEN_TEXT_PATTERNS:
                if pattern in text:
                    return PolicyDecision(
                        False, f"Forbidden pattern in text: {repr(pattern)}"
                    )
            return PolicyDecision(allowed=True)

        # Dangerous actions — require explicit per-action approval
        if action in _DANGEROUS_ACTIONS:
            if action not in self._allow_dangerous:
                return PolicyDecision(
                    False,
                    f"Action '{action.value}' is dangerous and requires human approval",
                )
            return PolicyDecision(allowed=True)

        # Default: deny
        return PolicyDecision(False, f"Action '{action.value}' is not in the allowlist")

    def assert_allowed(
        self,
        action: Action,
        **kwargs: object,
    ) -> None:
        """Raise PolicyDeniedError if the action is not allowed."""
        decision = self.check(action, **kwargs)  # type: ignore[arg-type]
        if not decision.allowed:
            raise PolicyDeniedError(action.value, decision.reason)
