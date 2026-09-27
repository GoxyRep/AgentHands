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
