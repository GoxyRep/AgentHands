"""Tests for hermes_hands.config."""

import os
import pytest

from hermes_hands.config import HandsConfig
from hermes_hands.errors import ConfigError


class TestHandsConfig:
    def test_valid_config(self):
        cfg = HandsConfig(
            base_url="https://192.168.1.100",
            username="hermes-agent",
            password="secret",
        )
        assert cfg.api_base == "https://192.168.1.100"
        assert cfg.verify_tls is True

    def test_trailing_slash_stripped(self):
        cfg = HandsConfig(
            base_url="https://192.168.1.100/",
            username="u",
            password="p",
        )
        assert cfg.api_base == "https://192.168.1.100"

    def test_missing_base_url(self):
        with pytest.raises(ConfigError, match="PIKVM_BASE_URL"):
            HandsConfig(base_url="", username="u", password="p")

    def test_non_https(self):
        with pytest.raises(ConfigError, match="HTTPS"):
            HandsConfig(base_url="http://192.168.1.100", username="u", password="p")

    def test_missing_username(self):
        with pytest.raises(ConfigError, match="PIKVM_USERNAME"):
            HandsConfig(base_url="https://x", username="", password="p")

    def test_missing_password(self):
        with pytest.raises(ConfigError, match="PIKVM_PASSWORD"):
            HandsConfig(base_url="https://x", username="u", password="")

    def test_from_env(self):
        env = {
            "PIKVM_BASE_URL": "https://10.0.0.5",
            "PIKVM_USERNAME": "admin",
            "PIKVM_PASSWORD": "pass123",
        }
        cfg = HandsConfig.from_env(env)
        assert cfg.base_url == "https://10.0.0.5"
        assert cfg.username == "admin"
        assert cfg.password == "pass123"

    def test_from_env_insecure_tls(self):
        env = {
            "PIKVM_BASE_URL": "https://10.0.0.5",
            "PIKVM_USERNAME": "admin",
            "PIKVM_PASSWORD": "pass",
            "HERMES_HANDS_INSECURE_TLS": "1",
        }
        cfg = HandsConfig.from_env(env)
        assert cfg.verify_tls is False

    def test_from_env_missing_all(self):
        with pytest.raises(ConfigError):
            HandsConfig.from_env({})

    def test_ca_file_not_found(self):
        with pytest.raises(ConfigError, match="CA_FILE"):
            HandsConfig(
                base_url="https://x",
                username="u",
                password="p",
                ca_file="/nonexistent/ca.pem",
            )


class TestKeychainPassword:
    """PIKVM_PASSWORD=keychain:<service> fetches from macOS Keychain."""

    def _patch_security(self, monkeypatch, output: str, returncode: int = 0):
        """Replace subprocess.run with a fake `security` binary."""
        class FakeCompleted:
            def __init__(self, stdout, returncode):
                self.stdout = stdout
                self.returncode = returncode

        def fake_run(cmd, **kwargs):
            assert cmd[0] == "security" and "find-generic-password" in cmd
            assert "-a" in cmd and "-s" in cmd and "-w" in cmd
            return FakeCompleted(output, returncode)

        monkeypatch.setattr("subprocess.run", fake_run)

    def test_keychain_password_fetched(self, monkeypatch):
        self._patch_security(monkeypatch, "k3ycha1n-pw\n")
        cfg = HandsConfig.from_env({
            "PIKVM_BASE_URL": "https://10.0.0.5",
            "PIKVM_USERNAME": "hermes",
            "PIKVM_PASSWORD": "keychain:pikvm",
        })
        assert cfg.password == "k3ycha1n-pw"

    def test_keychain_default_service(self, monkeypatch):
        """keychain: with no service name defaults to 'pikvm'."""
        self._patch_security(monkeypatch, "pw\n")
        cfg = HandsConfig.from_env({
            "PIKVM_BASE_URL": "https://10.0.0.5",
            "PIKVM_USERNAME": "hermes",
            "PIKVM_PASSWORD": "keychain:",
        })
        assert cfg.password == "pw"

    def test_keychain_uses_username_as_account(self, monkeypatch):
        seen = {}

        class FakeCompleted:
            stdout = "pw\n"
            returncode = 0

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            return FakeCompleted()

        monkeypatch.setattr("subprocess.run", fake_run)
        HandsConfig.from_env({
            "PIKVM_BASE_URL": "https://10.0.0.5",
            "PIKVM_USERNAME": "agent-x",
            "PIKVM_PASSWORD": "keychain:pikvm",
        })
        # -a should carry the configured username
        assert seen["cmd"][seen["cmd"].index("-a") + 1] == "agent-x"

    def test_keychain_failure_raises_config_error(self, monkeypatch):
        self._patch_security(monkeypatch, "", returncode=44)
        with pytest.raises(ConfigError, match="Keychain"):
            HandsConfig.from_env({
                "PIKVM_BASE_URL": "https://10.0.0.5",
                "PIKVM_USERNAME": "hermes",
                "PIKVM_PASSWORD": "keychain:pikvm",
            })

    def test_keychain_empty_output_raises_config_error(self, monkeypatch):
        """A keychain entry that exists but is empty must fail loudly."""
        self._patch_security(monkeypatch, "\n", returncode=0)
        with pytest.raises(ConfigError, match="empty password"):
            HandsConfig.from_env({
                "PIKVM_BASE_URL": "https://10.0.0.5",
                "PIKVM_USERNAME": "hermes",
                "PIKVM_PASSWORD": "keychain:pikvm",
            })

    def test_plain_password_untouched(self, monkeypatch):
        """A normal password never triggers the keychain path."""
        def fail_run(cmd, **kwargs):
            raise AssertionError("subprocess.run must not be called")

        monkeypatch.setattr("subprocess.run", fail_run)
        cfg = HandsConfig.from_env({
            "PIKVM_BASE_URL": "https://10.0.0.5",
            "PIKVM_USERNAME": "admin",
            "PIKVM_PASSWORD": "plain-secret",
        })
        assert cfg.password == "plain-secret"
