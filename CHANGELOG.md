# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **macOS Keychain password support**: set `PIKVM_PASSWORD=keychain:<service>` and the client fetches the secret from the macOS Keychain at startup (`security find-generic-password -a <username> -s <service> -w`). No file on disk ever contains the password itself; a literal `PIKVM_PASSWORD` still works. An empty Keychain entry fails loudly with a clear `ConfigError`. 6 new tests (78 total, coverage 91%).

### Changed
- **BUILD.md** — hardened with field-tested findings from the first full v1 rig bring-up (direct-link build, no router):
  - **§3.5 (new)**: power-off & reconnect ritual — clean `shutdown` before unplugging, cable order for reconnect (network → serial → power → HDMI → OTG), verification commands; everything persists across power cycles, nothing to reconfigure.
  - A1/A4: direct USB-C→RJ45 point-to-point link is now a documented layout (Realtek RTL8153 / ASIX AX88179 chipsets, static IPs on both ends, persistent `systemd-networkd` config on the PiKVM).
  - A8.5 (new): regenerate the PiKVM TLS certificate with a proper SAN (`DNS:pikvm, DNS:localhost, IP:<your IP>`) so CA pinning works without `HERMES_HANDS_INSECURE_TLS`; stock `CN=localhost` certs fail hostname validation. A8 now recommends the `keychain:` pointer for the password.
  - A9: **the #1 trap** — a USB-C→USB-C cable on the OTG port silently fails with macOS (PiKVM reports `UDC_STATE=configured`, the Mac never mounts the HID gadget). Use the C→A cable + A→C adapter for OTG.
  - A10: on kvmd ≥ 4.2 (janus video stack), API snapshots need automatic snapshots enabled via `override.yaml` (`idle_interval`/`live_interval`); otherwise `/api/streamer/snapshot` returns 503.
  - Troubleshooting §5.1 rewritten (C→C trap first, macOS "Allow new accessories" policy, `hidutil`/`ioreg` verification commands); §5.5 fixed (`pacman -Q kvmd`, not `dpkg`; RTC-supercapacitor noise explained — it self-charges, no battery to replace on V4 Mini); §5.7 (new) NAT recipe for `pikvm-update` on a routerless rig; §5.8 (new) SAN/cert-pinning failure mode.
- **examples** — both `observe_only.py` and `mvp_check.py` now load the repo's `.env` automatically (minimal built-in dotenv loader, no new dependency; real env vars still take precedence).
- **.env.example** — documents the `keychain:` pointer and the SAN-certificate step.

### Field-verified (live rig, 2026-09-27)
- Full A1–A11 bring-up on a routerless direct link; kvmd updated 4.61 → 4.217; NTP synchronized (persistent default route + DNS in `systemd-networkd`, IP-based NTP servers in `timesyncd.conf.d`); RTC supercapacitor self-charged (no more `low voltage` spam).

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
