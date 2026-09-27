"""PiKVM API client — narrow, typed methods only.

Only exposes: check_auth, get_hid_state, snapshot, move_mouse, type_text,
click_mouse, scroll. No arbitrary URL, no raw WebSocket events.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .audit import AuditLogger
from .config import HandsConfig
from .errors import ApiError, AuthError, SnapshotError
from .policy import Action, PolicyGate


@dataclass
class HidState:
    """HID device state from /api/hid."""

    online: bool
    keyboard_online: bool
    mouse_online: bool
    mouse_absolute: bool
    raw: dict[str, Any]


@dataclass
class AuthResult:
    """Result of auth check."""

    authenticated: bool
    raw: dict[str, Any]


class PikvmClient:
    """Narrow PiKVM API client.

    All methods are gated by PolicyGate and audited by AuditLogger.
    """

    def __init__(
        self,
        config: HandsConfig,
        policy: PolicyGate | None = None,
        audit: AuditLogger | None = None,
    ) -> None:
        self._config = config
        self._policy = policy or PolicyGate()
        self._audit = audit
        self._client: httpx.Client | None = None

    @property
    def _http(self) -> httpx.Client:
        """Lazy-initialized HTTP client."""
        if self._client is None:
            verify: Any = self._config.ca_file or self._config.verify_tls
            self._client = httpx.Client(
                base_url=self._config.api_base,
                auth=(self._config.username, self._config.password),
                verify=verify,
                timeout=self._config.timeout_s,
                follow_redirects=False,
            )
        return self._client

    def _req_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def _audit_log(
        self,
        action: str,
        request_id: str,
        result: str,
        duration_ms: float,
        detail: dict[str, Any] | None = None,
        artifact: bytes | None = None,
    ) -> None:
        if self._audit:
            self._audit.log(
                action=action,
                request_id=request_id,
                result=result,
                duration_ms=duration_ms,
                detail=detail,
                artifact=artifact,
            )

    def _handle_error(self, resp: httpx.Response) -> None:
        """Raise appropriate error for non-2xx responses."""
        if resp.status_code == 401:
            raise AuthError("Not authenticated", resp.status_code, resp.text)
        if resp.status_code == 403:
            raise AuthError("Authentication failed (bad credentials)", resp.status_code, resp.text)
        raise ApiError("API error", resp.status_code, resp.text)

    # -- Read-only methods (always allowed) --

    def check_auth(self) -> AuthResult:
        """Check authentication via GET /api/auth/check."""
        action = Action.CHECK_AUTH
        self._policy.assert_allowed(action)
        rid = self._req_id()
        t0 = time.monotonic()
        try:
            resp = self._http.get("/api/auth/check")
            if resp.status_code == 200:
                data = resp.json()
                self._audit_log(action.value, rid, "ok", (time.monotonic() - t0) * 1000)
                return AuthResult(authenticated=True, raw=data)
            self._handle_error(resp)
        except (ApiError, AuthError) as e:
            self._audit_log(action.value, rid, "error", (time.monotonic() - t0) * 1000,
                            {"error": str(e)})
            raise
        return AuthResult(authenticated=False, raw={})

    def get_hid_state(self) -> HidState:
        """Get HID device state via GET /api/hid."""
        action = Action.GET_HID_STATE
        self._policy.assert_allowed(action)
        rid = self._req_id()
        t0 = time.monotonic()
        try:
            resp = self._http.get("/api/hid")
            if resp.status_code != 200:
                self._handle_error(resp)
            data = resp.json()
            result = data.get("result", data)
            self._audit_log(action.value, rid, "ok", (time.monotonic() - t0) * 1000)
            return HidState(
                online=result.get("online", False),
                keyboard_online=result.get("keyboard", {}).get("online", False),
                mouse_online=result.get("mouse", {}).get("online", False),
                mouse_absolute=result.get("mouse", {}).get("absolute", False),
                raw=result,
            )
        except (ApiError, AuthError) as e:
            self._audit_log(action.value, rid, "error", (time.monotonic() - t0) * 1000,
                            {"error": str(e)})
            raise

    def snapshot(self) -> bytes:
        """Capture a JPEG snapshot via GET /api/streamer/snapshot.

        Returns raw JPEG bytes.
        """
        action = Action.SNAPSHOT
        self._policy.assert_allowed(action)
        rid = self._req_id()
        t0 = time.monotonic()
        try:
            resp = self._http.get("/api/streamer/snapshot")
            if resp.status_code != 200:
                self._handle_error(resp)
            data = resp.content
            if not data or len(data) < 100:
                raise SnapshotError(f"Snapshot too small: {len(data)} bytes")
            # Validate JPEG magic bytes
            if not data.startswith(b"\xff\xd8"):
                raise SnapshotError("Not a valid JPEG (missing magic bytes)")
            self._audit_log(action.value, rid, "ok", (time.monotonic() - t0) * 1000,
                            {"bytes": len(data)}, artifact=data)
            # Persist to snapshot_dir
            outpath = self._config.snapshot_dir / f"snapshot_{rid}.jpg"
            outpath.parent.mkdir(parents=True, exist_ok=True)
            outpath.write_bytes(data)
            return data
        except (ApiError, AuthError, SnapshotError) as e:
            self._audit_log(action.value, rid, "error", (time.monotonic() - t0) * 1000,
                            {"error": str(e)})
            raise

    # -- Input methods (gated by policy) --

    def move_mouse(self, to_x: int = 0, to_y: int = 0) -> dict[str, Any]:
        """Move mouse to absolute coordinates via POST /api/hid/events/send_mouse_move.

        0,0 is the center of the screen.
        """
        action = Action.MOVE_MOUSE
        self._policy.assert_allowed(action, to_x=to_x, to_y=to_y)
        rid = self._req_id()
        t0 = time.monotonic()
        try:
            resp = self._http.post(
                "/api/hid/events/send_mouse_move",
                params={"to_x": to_x, "to_y": to_y},
            )
            if resp.status_code != 200:
                self._handle_error(resp)
            data = resp.json()
            self._audit_log(action.value, rid, "ok", (time.monotonic() - t0) * 1000,
                            {"to_x": to_x, "to_y": to_y})
            return data
        except (ApiError, AuthError) as e:
            self._audit_log(action.value, rid, "error", (time.monotonic() - t0) * 1000,
                            {"error": str(e)})
            raise

    def move_mouse_relative(self, delta_x: int = 0, delta_y: int = 0) -> dict[str, Any]:
        """Move mouse by relative offset via POST /api/hid/events/send_mouse_relative."""
        action = Action.MOVE_MOUSE
        self._policy.assert_allowed(action, delta_x=delta_x, delta_y=delta_y)
        rid = self._req_id()
        t0 = time.monotonic()
        try:
            resp = self._http.post(
                "/api/hid/events/send_mouse_relative",
                params={"delta_x": delta_x, "delta_y": delta_y},
            )
            if resp.status_code != 200:
                self._handle_error(resp)
            data = resp.json()
            self._audit_log(action.value, rid, "ok", (time.monotonic() - t0) * 1000,
                            {"delta_x": delta_x, "delta_y": delta_y})
            return data
        except (ApiError, AuthError) as e:
            self._audit_log(action.value, rid, "error", (time.monotonic() - t0) * 1000,
                            {"error": str(e)})
            raise

    def type_text(self, text: str, keymap: str = "en-us", slow: bool = True,
                 delay: float = 0.05) -> dict[str, Any]:
        """Type text via POST /api/hid/print.

        Uses slow mode by default for reliability.
        """
        action = Action.TYPE_TEXT
        self._policy.assert_allowed(action, text=text)
        rid = self._req_id()
        t0 = time.monotonic()
        try:
            params: dict[str, Any] = {"keymap": keymap}
            if slow:
                params["slow"] = "1"
                params["delay"] = delay
            resp = self._http.post(
                "/api/hid/print",
                params=params,
                content=text.encode("utf-8"),
            )
            if resp.status_code != 200:
                self._handle_error(resp)
            data = resp.json()
            self._audit_log(action.value, rid, "ok", (time.monotonic() - t0) * 1000,
                            {"text_len": len(text), "keymap": keymap})
            return data
        except (ApiError, AuthError) as e:
            self._audit_log(action.value, rid, "error", (time.monotonic() - t0) * 1000,
                            {"error": str(e)})
            raise

    def click_mouse(self, button: str = "left") -> dict[str, Any]:
        """Click a mouse button via POST /api/hid/events/send_mouse_button."""
        action = Action.CLICK_MOUSE
        self._policy.assert_allowed(action, button=button)
        rid = self._req_id()
        t0 = time.monotonic()
        try:
            resp = self._http.post(
                "/api/hid/events/send_mouse_button",
                params={"button": button, "state": "true"},
            )
            if resp.status_code != 200:
                self._handle_error(resp)
            # Release
            self._http.post(
                "/api/hid/events/send_mouse_button",
                params={"button": button, "state": "false"},
            )
            data = resp.json()
            self._audit_log(action.value, rid, "ok", (time.monotonic() - t0) * 1000,
                            {"button": button})
            return data
        except (ApiError, AuthError) as e:
            self._audit_log(action.value, rid, "error", (time.monotonic() - t0) * 1000,
                            {"error": str(e)})
            raise

    def scroll(self, delta_x: int = 0, delta_y: int = 0) -> dict[str, Any]:
        """Scroll via POST /api/hid/events/send_mouse_wheel."""
        action = Action.SCROLL
        self._policy.assert_allowed(action, delta_x=delta_x, delta_y=delta_y)
        rid = self._req_id()
        t0 = time.monotonic()
        try:
            resp = self._http.post(
                "/api/hid/events/send_mouse_wheel",
                params={"delta_x": delta_x, "delta_y": delta_y},
            )
            if resp.status_code != 200:
                self._handle_error(resp)
            data = resp.json()
            self._audit_log(action.value, rid, "ok", (time.monotonic() - t0) * 1000,
                            {"delta_x": delta_x, "delta_y": delta_y})
            return data
        except (ApiError, AuthError) as e:
            self._audit_log(action.value, rid, "error", (time.monotonic() - t0) * 1000,
                            {"error": str(e)})
            raise

    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "PikvmClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
