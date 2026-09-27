# Contributing to hermes-hands

Thanks for your interest. This project has an unusual constraint — the code controls real hardware that controls real machines — so the bar for changes is set accordingly.

## Ground rules

1. **The API surface is intentionally narrow.** The client implements exactly the methods listed in the README. If you want to add a method or an endpoint, first check whether a *policy conversation* is needed (see below). The guard test `tests/test_api_surface_guard.py` will fail on any unapproved addition — this is deliberate; update it only together with a documented decision.
2. **Default-deny is the product.** Any PR that widens what the agent can do without explicit human approval will be rejected. ATX, MSD, `send_key`, and `send_shortcut` stay out of the client in v1.
3. **No real hardware in CI/tests.** All tests must pass with the PiKVM unplugged: mock every HTTP call (see `tests/test_pikvm_client.py` for the pattern), never touch the network.
4. **Docs are code.** If your change alters behavior, update README.md, BUILD.md, SECURITY.md, docs/policy.md, and CHANGELOG.md in the same PR.

## Development setup

```bash
git clone <repo> && cd hermes-hands
uv sync --extra dev
uv run pytest -v --cov=hermes_hands
```

Requirements: Python 3.11+. Coverage should not drop below 91%.

## What good PRs look like

- Small, single-purpose: one behavior or one doc page.
- Tests first for bugfixes: a failing test that reproduces the bug, then the fix.
- `CHANGELOG.md` entry under `Unreleased` following [Keep a Changelog](https://keepachangelog.com/).
- No secrets, no real IPs of your own PiKVM, no serial numbers in diffs or test fixtures. Use `https://pikvm-test.local` style fixtures.

## Adding an action to the allowlist

This is a policy decision, not just code. Your PR must include:

1. The concrete use case (what task requires it).
2. The failure mode analysis: what can go wrong if an agent does this under prompt injection.
3. The approval design: how a human grants it, and why the agent can't grant it to itself.
4. Updates to SECURITY.md and docs/policy.md.

## Reporting bugs against real hardware

Include: kvmd version (`dpkg -l | grep kvmd`), PiKVM model, target machine OS, the audit JSONL entries (they're redacted by design — but double-check before pasting), and the console output.

## License

By contributing you agree your work is released under the project's MIT license.
