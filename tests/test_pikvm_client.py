"""Tests for hermes_hands.pikvm_client — mocked HTTP, no real network."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import httpx
import pytest

from hermes_hands.config import HandsConfig
from hermes_hands.pikvm_client import PikvmClient, HidState, AuthResult
from hermes_hands.policy import PolicyGate, Action, PolicyDeniedError
from hermes_hands.audit import AuditLogger
from hermes_hands.errors import AuthError, ApiError, SnapshotError


# ---- Fixtures ----

def make_config(tmp_path):
    return HandsConfig(
        base_url="https://pikvm-test.local",
        username="testuser",
        password="testpass",
        verify_tls=False,
        snapshot_dir=tmp_path / "snapshots",
    )


def mock_response(status_code=200, json_body=None, content=b"", headers=None):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = json.dumps(json_body) if json_body else ""
    resp.json.return_value = json_body or {}
    resp.content = content
    resp.headers = headers or {}
    return resp


@pytest.fixture
def tmp_audit(tmp_path):
    return AuditLogger(tmp_path / "audit.jsonl")


@pytest.fixture
def client(tmp_path, tmp_audit):
    cfg = make_config(tmp_path)
    gate = PolicyGate(allow_mouse_click=True)
    c = PikvmClient(cfg, policy=gate, audit=tmp_audit)
    yield c
    c.close()


# ---- check_auth ----

class TestCheckAuth:
    def test_auth_success(self, client):
        mock_resp = mock_response(200, {"ok": True})
        with patch.object(client._http, "get", return_value=mock_resp):
            result = client.check_auth()
        assert result.authenticated is True

    def test_auth_401(self, client):
        mock_resp = mock_response(401)
        with patch.object(client._http, "get", return_value=mock_resp):
            with pytest.raises(AuthError):
                client.check_auth()

    def test_auth_403_bad_credentials(self, client):
        mock_resp = mock_response(403)
        with patch.object(client._http, "get", return_value=mock_resp):
            with pytest.raises(AuthError, match="bad credentials"):
                client.check_auth()


# ---- get_hid_state ----

class TestGetHidState:
    def test_hid_online(self, client):
        body = {
            "ok": True,
            "result": {
                "online": True,
                "keyboard": {"online": True, "leds": {}},
                "mouse": {"online": True, "absolute": True},
            },
        }
        mock_resp = mock_response(200, body)
        with patch.object(client._http, "get", return_value=mock_resp):
            state = client.get_hid_state()
        assert state.online is True
        assert state.keyboard_online is True
        assert state.mouse_online is True
        assert state.mouse_absolute is True

    def test_hid_offline(self, client):
        body = {
            "ok": True,
            "result": {
                "online": False,
                "keyboard": {"online": False},
                "mouse": {"online": False},
            },
        }
        mock_resp = mock_response(200, body)
        with patch.object(client._http, "get", return_value=mock_resp):
            state = client.get_hid_state()
        assert state.online is False
        assert state.keyboard_online is False


# ---- snapshot ----

class TestSnapshot:
    def test_valid_jpeg(self, client):
        # Minimal JPEG: magic bytes + some data
        jpeg_data = b"\xff\xd8\xff\xe0" + b"\x00" * 200 + b"\xff\xd9"
        mock_resp = mock_response(200, content=jpeg_data)
        with patch.object(client._http, "get", return_value=mock_resp):
            data = client.snapshot()
        assert data == jpeg_data
        assert len(data) > 100

    def test_too_small(self, client):
        mock_resp = mock_response(200, content=b"\xff\xd8\x00")
        with patch.object(client._http, "get", return_value=mock_resp):
            with pytest.raises(SnapshotError, match="too small"):
                client.snapshot()

    def test_not_jpeg(self, client):
        mock_resp = mock_response(200, content=b"\x89PNG\r\n" + b"\x00" * 200)
        with patch.object(client._http, "get", return_value=mock_resp):
            with pytest.raises(SnapshotError, match="Not a valid JPEG"):
                client.snapshot()

    def test_snapshot_saved_to_disk(self, client, tmp_path):
        jpeg_data = b"\xff\xd8\xff\xe0" + b"\x00" * 300 + b"\xff\xd9"
        mock_resp = mock_response(200, content=jpeg_data)
        with patch.object(client._http, "get", return_value=mock_resp):
            client.snapshot()
        files = list((tmp_path / "snapshots").glob("snapshot_*.jpg"))
        assert len(files) == 1
        assert files[0].read_bytes() == jpeg_data


# ---- move_mouse ----

class TestMoveMouse:
    def test_move_absolute(self, client):
        mock_resp = mock_response(200, {"ok": True, "result": {}})
        with patch.object(client._http, "post", return_value=mock_resp) as mock_post:
            result = client.move_mouse(to_x=100, to_y=200)
        assert result["ok"] is True
        # Check the URL params
        call_args = mock_post.call_args
        assert call_args.kwargs["params"]["to_x"] == 100
        assert call_args.kwargs["params"]["to_y"] == 200

    def test_move_relative(self, client):
        mock_resp = mock_response(200, {"ok": True, "result": {}})
        with patch.object(client._http, "post", return_value=mock_resp) as mock_post:
            client.move_mouse_relative(delta_x=50, delta_y=-30)
        call_args = mock_post.call_args
        assert call_args.kwargs["params"]["delta_x"] == 50
        assert call_args.kwargs["params"]["delta_y"] == -30

    def test_move_coord_too_large_denied(self, client):
        with pytest.raises(PolicyDeniedError):
            client.move_mouse(to_x=99999, to_y=0)


# ---- type_text ----

class TestTypeText:
    def test_type_text_success(self, client):
        mock_resp = mock_response(200, {"ok": True, "result": {}})
        with patch.object(client._http, "post", return_value=mock_resp) as mock_post:
            client.type_text("HERMES_HANDS_MVP_OK")
        call_args = mock_post.call_args
        assert call_args.kwargs["params"]["keymap"] == "en-us"
        assert call_args.kwargs["params"]["slow"] == "1"
        assert call_args.kwargs["content"] == b"HERMES_HANDS_MVP_OK"

    def test_type_text_forbidden_pattern(self, client):
        with pytest.raises(PolicyDeniedError):
            client.type_text("sudo rm -rf /")

    def test_type_text_too_long(self, client):
        with pytest.raises(PolicyDeniedError):
            client.type_text("A" * 200)


# ---- click_mouse ----

class TestClickMouse:
    def test_click_allowed(self, client):
        mock_resp = mock_response(200, {"ok": True, "result": {}})
        with patch.object(client._http, "post", return_value=mock_resp):
            result = client.click_mouse("left")
        assert result["ok"] is True

    def test_click_denied_without_approval(self, tmp_path, tmp_audit):
        cfg = make_config(tmp_path)
        gate = PolicyGate(allow_mouse_click=False)
        c = PikvmClient(cfg, policy=gate, audit=tmp_audit)
        with pytest.raises(PolicyDeniedError):
            c.click_mouse("left")
        c.close()


# ---- scroll ----

class TestScroll:
    def test_scroll_success(self, client):
        mock_resp = mock_response(200, {"ok": True, "result": {}})
        with patch.object(client._http, "post", return_value=mock_resp) as mock_post:
            client.scroll(delta_y=200)
        call_args = mock_post.call_args
        assert call_args.kwargs["params"]["delta_y"] == 200


# ---- audit integration ----

class TestAuditIntegration:
    def test_audit_logged_on_success(self, client, tmp_audit):
        mock_resp = mock_response(200, {"ok": True, "result": {}})
        with patch.object(client._http, "get", return_value=mock_resp):
            client.check_auth()
        entries = tmp_audit.read()
        assert len(entries) == 1
        assert entries[0]["action"] == "check_auth"
        assert entries[0]["result"] == "ok"

    def test_audit_logged_on_error(self, client, tmp_audit):
        mock_resp = mock_response(500)
        with patch.object(client._http, "get", return_value=mock_resp):
            try:
                client.check_auth()
            except (ApiError, AuthError):
                pass
        entries = tmp_audit.read()
        assert len(entries) == 1
        assert entries[0]["result"] == "error"

    def test_audit_redacts_in_detail(self, client, tmp_audit):
        mock_resp = mock_response(200, {"ok": True, "result": {}})
        with patch.object(client._http, "post", return_value=mock_resp):
            client.type_text("hello")
        entries = tmp_audit.read()
        assert entries[0]["detail"].get("text_len") == 5
        # text itself is never in detail (only length)
