"""Guard test: the client API surface must not grow (spec §4.3).

Any new public method or endpoint on PikvmClient must be a conscious,
reviewed decision — update ALLOWED_PUBLIC / ALLOWED_ENDPOINTS here together
with the policy, docs, and SECURITY.md, not silently.
"""

import inspect
import re
from pathlib import Path

import hermes_hands.pikvm_client as pikvm_client_module
from hermes_hands.pikvm_client import PikvmClient

# The complete approved public surface (spec §4.3).
ALLOWED_PUBLIC = {
    "check_auth",
    "get_hid_state",
    "snapshot",
    "move_mouse",
    "move_mouse_relative",
    "type_text",
    "click_mouse",
    "scroll",
}

# Lifecycle methods that are public but are not API actions.
INFRASTRUCTURE_PUBLIC = {"close"}


class TestApiSurfaceGuard:
    def test_no_api_sprawl(self):
        methods = {
            name
            for name, member in inspect.getmembers(PikvmClient, inspect.isfunction)
            if not name.startswith("_")
        }
        assert methods == ALLOWED_PUBLIC | INFRASTRUCTURE_PUBLIC, (
            f"Public API changed: unexpected={methods - ALLOWED_PUBLIC - INFRASTRUCTURE_PUBLIC}, "
            f"missing={(ALLOWED_PUBLIC | INFRASTRUCTURE_PUBLIC) - methods}"
        )

    def test_no_raw_http_methods_exposed(self):
        """The client must not expose arbitrary HTTP verbs on itself."""
        for forbidden in ("get", "post", "put", "delete", "patch", "head", "request", "stream", "websocket"):
            assert not hasattr(PikvmClient, forbidden), (
                f"PikvmClient exposes raw HTTP method '{forbidden}' — API is no longer narrow"
            )

    def test_only_approved_endpoints(self):
        """Every /api/ URL in the client source must be in the approved list."""
        allowed_endpoints = {
            "/api/auth/check",
            "/api/hid",
            "/api/streamer/snapshot",
            "/api/hid/events/send_mouse_move",
            "/api/hid/events/send_mouse_relative",
            "/api/hid/events/send_mouse_button",
            "/api/hid/events/send_mouse_wheel",
            "/api/hid/print",
        }
        src = Path(pikvm_client_module.__file__).read_text(encoding="utf-8")
        found = set(re.findall(r'"(/api/[^"]+)"', src))
        assert found <= allowed_endpoints, (
            f"Unapproved endpoints found in client: {found - allowed_endpoints}"
        )

    def test_no_atx_msd_or_config_endpoints_in_client(self):
        """ATX, MSD, and config endpoints must never appear in the client source."""
        src = Path(pikvm_client_module.__file__).read_text(encoding="utf-8")
        for banned in ("/api/atx", "/api/msd", "/api/config", "/api/switch", "/api/gpio"):
            assert banned not in src, f"Banned endpoint family '{banned}' found in client"

    def test_context_manager_closes_client(self):
        """__enter__/__exit__ lifecycle must work and close the transport."""
        from hermes_hands.config import HandsConfig

        cfg = HandsConfig(
            base_url="https://pikvm-guard-test.local",
            username="u",
            password="p",
            verify_tls=False,
        )
        with PikvmClient(cfg) as hands:
            assert hands._client is not None or hands._http is not None
        # After __exit__ the internal client must be released.
        assert hands._client is None
