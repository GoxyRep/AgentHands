# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-09-27

First public, open-source release. The core client (0.1.0) is unchanged and battle-tested against a live PiKVM V4 Mini; this release wraps it in the documentation, examples, and release scaffolding required for anyone to build the rig from scratch.

### Added
- **BUILD.md** — complete hardware guide: shopping list with price guides, wiring diagram, bring-up steps A1–A11 (Ethernet → serial console → power → DHCP → API check → password rotation → API user → secret storage → HDMI/OTG → first snapshot → live MVP acceptance), verification checklist, and a troubleshooting section (OTG/`UDC_STATE`, auth 401, black screen, USB-Ethernet chipsets, NTP/2FA ordering).
- **README.md** — rewritten for release: what it is (out-of-band agent hands via PiKVM), wiring overview, software-vs-hardware comparison table by failure domain, 3-command quick start, minimal code example, safety summary, v2/v3 roadmap.
- **SECURITY.md** — threat model (agent off the rails / prompt injection, network attacker, credential leakage), default-deny rationale per denied capability (ATX, MSD, send_key, send_shortcut), human-approval-as-object design, self-piloting risk warning, operational rules (factory passwords, 2FA-after-NTP, DIP/RTC rules, Keychain secrets), audit log description, disclosure policy.
- **CONTRIBUTING.md** — ground rules (narrow API, default-deny is the product, mocked tests only, docs-in-PR), dev setup, and the process for proposing allowlist changes.
- **docs/policy.md** — user-facing explanation of the default-deny policy.
- **docs/wirediagram.svg** — wiring diagram referenced from README/BUILD.
- **examples/mvp_check.py** — A11 acceptance script: auth → HID → snapshot → mouse move → type `HERMES_HANDS_MVP_OK`, with audit-trail verification.
- **examples/observe_only.py** — zero-input safety demo: auth, HID state, snapshots only; structurally incapable of input.
- **Guard test** (`tests/test_api_surface_guard.py`): the client's public API must stay exactly the spec'd 8 action methods; raw HTTP verbs must not be exposed; only approved `/api/` endpoints may appear in the client source; ATX/MSD/config endpoint families are banned. 5 new tests (72 total).
- **LICENSE** (MIT), **CHANGELOG.md** (this file).

### Changed
- Version bumped to **1.0.0** (`pyproject.toml`, `hermes_hands.__version__`).
- README rewritten from dev-notes style to a release-quality document.

### Verified
- Test suite: **72 passed**, coverage **91%** (`pytest -v --cov=hermes_hands`), all HTTP mocked — zero real network calls, zero hardware access.

## [0.1.0] — 2026-09-16

### Added
- **PiKVM API client** (`pikvm_client.py`): narrow, typed methods for `check_auth`, `get_hid_state`, `snapshot`, `move_mouse`, `move_mouse_relative`, `type_text`, `click_mouse`, `scroll`. No arbitrary URL or raw WebSocket access.
- **Policy gate** (`policy.py`): default-deny allowlist. Read-only and basic input actions allowed; ATX, mass storage, HID config changes, arbitrary shortcuts, and send-key denied by default. Mouse clicks require explicit approval. Text input is length-limited and filtered for dangerous patterns (ESC, `sudo`, fork bombs).
- **Audit logger** (`audit.py`): append-only JSONL with timestamp, request ID, action, result, duration, and artifact hash. Automatic redaction of `password`, `authorization`, `auth_token`, `cookie`, `totp`, `secret`, `token`. File permissions set to `0600`.
- **Configuration** (`config.py`): frozen dataclass loaded from environment variables. Enforces HTTPS, requires username/password, supports CA pinning, optional insecure-TLS flag for bootstrap only.
- **Error hierarchy** (`errors.py`): `HermesHandsError` base, with `ConfigError`, `PolicyDeniedError`, `AuthError`, `ApiError`, `SnapshotError`.
- **Tests**: full coverage for config validation, policy decisions, audit redaction, and all client methods with mocked HTTP (no real network calls).
- **Project scaffolding**: `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`.
