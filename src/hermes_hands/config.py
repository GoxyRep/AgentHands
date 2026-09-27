"""Configuration for hermes-hands.

Loads from environment variables and/or a .env file.
Secrets are never logged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigError


@dataclass(frozen=True)
class HandsConfig:
    """Immutable configuration for the Hermes Hands client."""

    base_url: str
    username: str
    password: str
    ca_file: str | None = None
    verify_tls: bool = True
    timeout_s: float = 30.0
    snapshot_dir: Path = field(default_factory=lambda: Path("/tmp/hermes-hands"))

    def __post_init__(self) -> None:
        if not self.base_url:
            raise ConfigError("PIKVM_BASE_URL is required")
        if not self.base_url.startswith("https://"):
            raise ConfigError("PIKVM_BASE_URL must use HTTPS")
        if not self.username:
            raise ConfigError("PIKVM_USERNAME is required")
        if not self.password:
            raise ConfigError("PIKVM_PASSWORD is required")
        if self.ca_file:
            p = Path(self.ca_file)
            if not p.is_file():
                raise ConfigError(f"PIKVM_CA_FILE does not exist: {self.ca_file}")

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "HandsConfig":
        """Build config from environment variables (or a provided dict).

        Optionally loads a .env file from the current directory.
        """
        source = env if env is not None else os.environ

        base_url = source.get("PIKVM_BASE_URL", "").strip()
        username = source.get("PIKVM_USERNAME", "").strip()
        password = source.get("PIKVM_PASSWORD", "").strip()
        ca_file = source.get("PIKVM_CA_FILE", "").strip() or None

        # Allow insecure TLS only via explicit env flag
        verify_tls = source.get("HERMES_HANDS_INSECURE_TLS", "0").strip() not in (
            "1",
            "true",
            "yes",
        )

        return cls(
            base_url=base_url,
            username=username,
            password=password,
            ca_file=ca_file,
            verify_tls=verify_tls,
        )

    @property
    def api_base(self) -> str:
        """Return base_url without trailing slash."""
        return self.base_url.rstrip("/")
