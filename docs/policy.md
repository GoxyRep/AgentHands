# The default-deny policy — why your agent's hands are on a leash

`hermes-hands` can move a real mouse and type on a real keyboard. That is a strange and powerful thing to hand a piece of software, so the module is built around one idea: **the agent is not trusted with capability decisions — the policy is**.

This document explains the policy in user terms. For the security rationale, see [SECURITY.md](../SECURITY.md); for the exact rules, read `src/hermes_hands/policy.py` — it's short, and it's the source of truth.

## How the gate works

Every client call first passes through a `PolicyGate`. The gate is an **allowlist**: an action is permitted only if it is explicitly on the list and passes its constraints. Everything else — including actions nobody has thought of yet — is denied by default. A denied action raises `PolicyDeniedError` and is still written to the audit log with the reason.

```
agent call ──► PolicyGate (allowlist + constraints) ──► PiKVM API
                      │ denied
                      ▼
              audit log entry + PolicyDeniedError
```

## What the agent may do by default

| Action | Constraints |
|---|---|
| `check_auth`, `get_hid_state` | none — read-only, no side effects on the target |
| `snapshot` | returns a JPEG of the screen (also hashed into the audit log) |
| `move_mouse`, `move_mouse_relative` | coordinates limited to ±32767 |
| `scroll` | none (low risk: scrolls a window, can't click anything) |
| `type_text` | ≤ 128 characters; rejects ESC sequences, `sudo`, `rm -rf`, fork-bomb patterns |
| `click_mouse` | **off by default** — requires `PolicyGate(allow_mouse_click=True)`; buttons limited to left/middle/right |

Note that even the "allowed" list is deliberately cramped. The length cap on `type_text` exists so a runaway agent can't paste a whole malicious script in one go — the human watching the screen can see 128 characters being typed. The forbidden patterns are tripwires, not a sandbox: they catch the lazy cases and make the intent obvious in the audit log.

## What the agent may never do in v1 — and why

These capabilities **do not exist in the client at all**. There is no method to call, and a guard test fails the build if one appears.

- **ATX (power on/off/reset the machine)** — the fastest way for a confused agent to destroy unsaved work or corrupt a filesystem. Power actions need a human hand on the button, period.
- **MSD (virtual drives)** — mounting a drive the machine boots from is arbitrary code execution. This is the most dangerous thing a KVM can do, so the client simply doesn't speak MSD.
- **`send_key` (single keystrokes)** — key-by-key input is how you assemble dangerous system shortcuts (⌘⌥⌫, Ctrl-Alt-Del, ⌘Space…) that the text filter can never inspect as a whole. No single-key channel, no shortcut assembly.
- **`send_shortcut` (system combinations)** — same reason, one level up.
- **Any config endpoint** — the client is a fixed set of 8 methods over a fixed set of URLs. No arbitrary requests.

## Human approval is an object, not a button

For actions that are dangerous but sometimes legitimate, the policy supports an explicit approval *object*:

```python
from hermes_hands.policy import Action, PolicyGate

policy = PolicyGate(allow_dangerous={Action.ATX_POWER})
```

The point of the design: **there is no code path in this repository by which the agent can obtain or upgrade an approval itself.** A human writes the approval into their own integration code, deliberately, where it's visible in review. If you build a flow that lets an agent "ask a human" and constructs approvals automatically, you have changed the security model — read SECURITY.md first, and don't do it casually.

## Everything is written down

Allowed or denied, every attempt lands in the audit JSONL: timestamp, request ID, action, redacted parameters, result, duration. Typed text is recorded only by its length, never its content. Secret-looking fields (`password`, `token`, `totp`, …) are replaced with `***REDACTED***` before the line is written. The log file is created with `0600` permissions and is gitignored.

Why bother, if the policy already says no? Because the audit log answers the question you'll actually have at 2 AM: *"what did the agent try to do?"* A `PolicyDeniedError` in the log with reason `"Action 'atx_power' is dangerous and requires human approval"` is a diagnosis; a silent failure is a mystery.

## Tightening it further

The defaults are a floor, not a ceiling. For an observe-only setup (the safest way to start):

```python
from hermes_hands.policy import PolicyGate
from hermes_hands.pikvm_client import PikvmClient

policy = PolicyGate(allow_mouse_click=False)
with PikvmClient(cfg, policy=policy) as hands:
    jpeg = hands.snapshot()   # eyes only
```

Or just run `examples/observe_only.py`, which is structurally incapable of input — it never calls an input method.
