# SECURITY.md — hermes-hands

## What we protect, and from what

**Asset**: the target computer — the machine whose screen and keyboard are controlled. That's the user's machine, with their data. Everything else (the PiKVM, the network) exists only to serve or threaten that asset.

**Adversary / failure modes this design assumes:**

1. **The agent goes off the rails.** A hallucination, a prompt injection in a webpage or email the agent reads, or a plain bug — any of these can make the agent *want* to do something destructive with the hands.
2. **A human attacker on the network.** The PiKVM API is a network service; anyone who can reach it and authenticate can type on your machine.
3. **Credential leakage.** Passwords in git history, in logs, in screenshots.

The module's job is to make all three survivable.

## The core rule: default-deny

The policy gate is the heart of the project. It is an allowlist, not a blocklist:

- **Allowed by default**: `check_auth`, `get_hid_state`, `snapshot` (read-only), and constrained basic input — `move_mouse`, `move_mouse_relative` (|coord| ≤ 32767), `scroll`, `type_text` (≤ 128 chars, content-filtered), `click_mouse` (only with an explicit `allow_mouse_click=True` gate, buttons left/middle/right).
- **Denied always in v1** (no code path exists, and the guard test fails if one appears):
  - `ATX` — power on/off/reset of the target machine. A wrong power action can destroy data (unflushed writes) and is the fastest way for a confused agent to brick a work session.
  - `MSD` — virtual drives. Mounting a drive = arbitrary code execution on the target at boot. This is the single most dangerous capability of a KVM.
  - `send_key` — single keystrokes. Key-by-key input is how you assemble system shortcuts (⌘⌥⌫, Ctrl-Alt-Del) the policy can't inspect as a whole.
  - `send_shortcut` — system combinations, same reason.
  - Any `/api/config` or arbitrary endpoints — the client is a fixed set of methods over a fixed set of URLs, enforced by `tests/test_api_surface_guard.py`.

**Human approval is an object, not a flag-flip.** Dangerous actions exist as `Action` enum members; a caller who wants one must construct `PolicyGate(allow_dangerous={Action.ATX_POWER})` explicitly in their own code. There is no function in this repository an agent can call to grant itself approval. Keep it that way.

`type_text` content rules: rejected if it contains ESC sequences (`\x1b`), `sudo `, `rm -rf`, or a fork-bomb pattern. These are tripwires, not a sandbox — the defense is that the human watching the screen sees a 128-char limit typed slowly in a visible window, not that dangerous strings are impossible to phrase.

## Self-piloting risk — the honest warning

**The agent controls the same machine it runs on.** It can see its own chat window through the HDMI capture and type into it. This is a real feedback loop: an agent that types into its own input channel is, in effect, prompting itself. Consequences we consider and you should too:

- A confused agent can navigate its own UI (scroll its window, type into its input) and reinforce its own mistake.
- Mitigations in v1: `click_mouse` is off by default; typing is short and slow (visible); there is no shortcut/single-key channel at all, so the agent cannot press ⏎ on itself — the human always confirms the agent's own prompts.
- Operational rule: **test in a throwaway focused app (TextEdit) first**, one action at a time, and keep the serial console open (see BUILD.md) as the emergency channel.

If you let an agent drive a *different* machine than the one it runs on, this risk shrinks dramatically — recommended setup when you have the hardware.

## Operational security rules

1. **Never use factory passwords.** PiKVM ships with publicly documented defaults for `root` and `admin`. Anyone on your LAN knows them. Change both before doing anything else (BUILD.md step A6).
2. **2FA only after NTP is stable.** TOTP depends on correct time; PiKVM without reliable NTP will reject valid codes and can lock you out. Enable 2FA last, after you've verified time sync (BUILD.md §Troubleshooting).
3. **Don't change DIP switches under power.** Physical rule for the PiKVM board.
4. **Don't use an RPi 5 RTC battery in the PiKVM.** Incompatible hardware — it damages the board.
5. **Secrets live in env/macOS Keychain, never in git.** The module reads `PIKVM_PASSWORD` from the environment; `.env` is gitignored; the audit log redacts secrets; the test suite contains no real credentials.
6. **HTTPS is enforced in code** (`ConfigError` on `http://`). For self-signed certs, pin the CA with `PIKVM_CA_FILE`; `HERMES_HANDS_INSECURE_TLS=1` is a bootstrap escape hatch, not a lifestyle.
7. **Keep the PiKVM on a trusted LAN.** Do not port-forward the PiKVM to the internet without understanding you are exposing a keyboard on your machine. Use a VPN if you need remote access.

## Audit log

- **Where**: default `logs/audit.jsonl` (gitignored), created with `0600` permissions.
- **What**: one JSON line per action — `timestamp`, `request_id`, `action`, `result` (`ok`/`error`), `duration_ms`, redacted `detail`, and `artifact_hash` (truncated SHA-256) for snapshots. Denied actions are also recorded, with the denial reason.
- **Redaction**: values of keys `password`, `passwd`, `authorization`, `auth_token`, `cookie`, `totp`, `secret`, `token` become `***REDACTED***` recursively before writing. Typed text is never stored — only its length.

## Reporting a security issue

Please open a private security advisory on GitHub (Security tab → "Report a vulnerability") or contact the maintainer directly. Don't open public issues for vulnerabilities.

## Known limitations (v1)

- No rate limiting inside the module — a caller can hammer the API; audit records everything but doesn't throttle.
- Snapshot JPEG only; no video stream (WebSocket deliberately not implemented).
- Policy applies per-`PolicyGate` instance; v1 has no central daemon, so discipline is on the integrating code.
