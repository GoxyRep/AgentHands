"""Tests for hermes_hands.audit — redaction and JSONL format."""

import json
from pathlib import Path
import tempfile

from hermes_hands.audit import AuditLogger, _redact, _hash_artifact


class TestRedaction:
    def test_redact_password(self):
        assert _redact({"password": "secret"})["password"] == "***REDACTED***"

    def test_redact_authorization(self):
        assert _redact({"Authorization": "Bearer xyz"})["Authorization"] == "***REDACTED***"

    def test_redact_nested(self):
        d = {"outer": {"password": "p", "safe": "ok"}}
        r = _redact(d)
        assert r["outer"]["password"] == "***REDACTED***"
        assert r["outer"]["safe"] == "ok"

    def test_redact_list(self):
        lst = [{"password": "a"}, {"safe": "b"}]
        r = _redact(lst)
        assert r[0]["password"] == "***REDACTED***"
        assert r[1]["safe"] == "b"

    def test_redact_auth_token(self):
        assert _redact({"auth_token": "abc"})["auth_token"] == "***REDACTED***"

    def test_redact_totp(self):
        assert _redact({"totp": "123456"})["totp"] == "***REDACTED***"

    def test_non_dict_passes_through(self):
        assert _redact("hello") == "hello"
        assert _redact(42) == 42


class TestHashArtifact:
    def test_hash_deterministic(self):
        data = b"some bytes"
        h1 = _hash_artifact(data)
        h2 = _hash_artifact(data)
        assert h1 == h2

    def test_hash_length(self):
        h = _hash_artifact(b"x")
        assert len(h) == 16

    def test_hash_different_data(self):
        assert _hash_artifact(b"a") != _hash_artifact(b"b")


class TestAuditLogger:
    def test_log_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "audit.jsonl"
            logger = AuditLogger(log_path)
            entry = logger.log(
                action="snapshot",
                request_id="abc123",
                result="ok",
                duration_ms=42.5,
                detail={"bytes": 1024},
            )
            assert log_path.exists()
            lines = log_path.read_text().strip().split("\n")
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["action"] == "snapshot"
            assert data["request_id"] == "abc123"
            assert data["result"] == "ok"
            assert data["duration_ms"] == 42.5

    def test_log_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "audit.jsonl"
            logger = AuditLogger(log_path)
            logger.log(
                action="type_text",
                request_id="r1",
                result="ok",
                duration_ms=10.0,
                detail={"password": "supersecret", "text_len": 5},
            )
            data = logger.read()[0]
            assert data["detail"]["password"] == "***REDACTED***"
            assert data["detail"]["text_len"] == 5

    def test_log_with_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "audit.jsonl"
            logger = AuditLogger(log_path)
            artifact = b"\xff\xd8\xff\xe0some jpeg data"
            logger.log(
                action="snapshot",
                request_id="r2",
                result="ok",
                duration_ms=50.0,
                artifact=artifact,
            )
            data = logger.read()[0]
            assert "artifact_hash" in data
            assert len(data["artifact_hash"]) == 16

    def test_multiple_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "audit.jsonl"
            logger = AuditLogger(log_path)
            for i in range(5):
                logger.log(
                    action="check_auth",
                    request_id=f"r{i}",
                    result="ok",
                    duration_ms=float(i),
                )
            entries = logger.read()
            assert len(entries) == 5
            assert entries[0]["request_id"] == "r0"
            assert entries[4]["request_id"] == "r4"

    def test_file_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "audit.jsonl"
            AuditLogger(log_path)
            mode = log_path.stat().st_mode & 0o777
            assert mode == 0o600
