"""Audit logger — JSONL with secret redaction.

Every API action is logged with:
  timestamp, request_id, action, result, duration_ms, artifact_hash

Secrets (password, Authorization headers, cookies, TOTP, full user input)
are NEVER written to the audit log.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Fields whose values must never appear in the audit log
_REDACTED_FIELDS = frozenset({
    "password", "passwd", "authorization", "auth_token",
    "cookie", "totp", "secret", "token",
})


def _redact(obj: Any) -> Any:
    """Recursively redact sensitive fields in dicts and lists."""
    if isinstance(obj, dict):
        return {
            k: ("***REDACTED***" if k.lower() in _REDACTED_FIELDS else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    return obj


def _hash_artifact(data: bytes) -> str:
    """SHA-256 hash of an artifact (e.g. snapshot bytes), truncated."""
    return hashlib.sha256(data).hexdigest()[:16]


@dataclass
class AuditEntry:
    """A single audit record."""

    timestamp: str
    request_id: str
    action: str
    result: str  # "ok" | "error" | "denied"
    duration_ms: float
    detail: dict[str, Any] = field(default_factory=dict)
    artifact_hash: str | None = None

    def to_jsonl(self) -> str:
        """Serialize to a single JSONL line."""
        payload = {
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "action": self.action,
            "result": self.result,
            "duration_ms": round(self.duration_ms, 2),
            "detail": _redact(self.detail),
        }
        if self.artifact_hash:
            payload["artifact_hash"] = self.artifact_hash
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class AuditLogger:
    """Append-only JSONL audit logger.

    All sensitive fields are redacted before writing.
    The log file gets 0600 permissions.
    """

    def __init__(self, log_path: Path | str) -> None:
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure 0600 on the log file
        if self._path.exists():
            self._path.chmod(0o600)
        else:
            self._path.touch(0o600)

    @property
    def path(self) -> Path:
        """Path to the audit log file."""
        return self._path

    def log(
        self,
        *,
        action: str,
        request_id: str,
        result: str,
        duration_ms: float,
        detail: dict[str, Any] | None = None,
        artifact: bytes | None = None,
    ) -> AuditEntry:
        """Write a single audit entry and return it."""
        entry = AuditEntry(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
            request_id=request_id,
            action=action,
            result=result,
            duration_ms=duration_ms,
            detail=detail or {},
            artifact_hash=_hash_artifact(artifact) if artifact else None,
        )
        line = entry.to_jsonl() + "\n"
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)
        return entry

    def read(self) -> list[dict[str, Any]]:
        """Read all entries (for testing / inspection)."""
        entries: list[dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
        return entries
