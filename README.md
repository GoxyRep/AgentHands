# hermes-hands

**Hardware "eyes and hands" for an AI agent — an out-of-band KVM channel that works when nothing else does.**

`hermes-hands` is a small Python module that gives an AI agent (Hermes Agent, or any other) control of a computer through a [PiKVM](https://pikvm.org/) hardware KVM device. The agent *sees* the target machine's screen via HDMI capture and *types and moves the mouse* via USB HID — a channel that is completely independent of the target's operating system. It works on the lock screen, in BIOS/EFI, in Recovery mode, and during a kernel panic. Think IPMI for a personal computer, but the "remote hands" are an AI agent.

## How it's wired

```
                 +---------------------+
                 |   Hermes agent      |
                 |   (any machine on   |
                 |    your network)    |
                 +---------+-----------+
                           |
             HTTPS API (LAN/Wi-Fi → router → RJ45)
                           |
                 +---------v-----------+
   Mac HDMI OUT ->| HDMI IN   PiKVM    |
                 |           V4 Mini   |
   Mac USB-C   <-+ OTG (USB HID)       |
                 +---------------------+
```

- **Eyes**: Mac HDMI OUT → PiKVM HDMI IN (screen capture)
- **Hands**: PiKVM USB OTG → Mac USB-C (keyboard/mouse emulation)
- **Brain link**: agent ↔ PiKVM over HTTPS on your LAN

Full shopping list and step-by-step assembly: **[BUILD.md](BUILD.md)**.

## Why hardware, not software?

An agent could also drive a computer through the OS (Accessibility APIs, `cliclick`, AppleScript). Here is the honest comparison by failure domain:

| Situation | Software channel (Accessibility API) | Hardware channel (PiKVM) |
|---|---|---|
| Lock screen / login window | ❌ blocked | ✅ works |
| BIOS / EFI / boot picker | ❌ not reached | ✅ works |
| Recovery mode / reinstall | ❌ not reached | ✅ works |
| Kernel panic / frozen OS | ❌ dead | ✅ works |
| DRM-protected video content | ✅ sees the pixels | ❌ black box on capture* |
| Screen locked by policy / MDM | ❌ blocked | ✅ works |
| Agent runs headless / no GUI session | ❌ often blocked | ✅ works |
| Speed | ✅ fast, native | ⚠️ JPEG snapshot ~0.5–2 s per look |
| Cost | ✅ free | 💰 ~$150–200 of hardware |

\* HDMI capture of protected content (e.g. Netflix in Safari) yields a black image — this is HDCP doing its job. Not a bug, and not bypassable.

## Quick start

```bash
git clone https://github.com/<you>/hermes-hands && cd hermes-hands
uv sync --extra dev        # or: pip install -e ".[dev]"
uv run pytest -v --cov=hermes_hands   # 78 tests, zero network calls
```

No hardware needed for the test suite — all HTTP is mocked. To drive a real machine, build the rig first: **[BUILD.md](BUILD.md)**.

## Minimal example

```python
from hermes_hands.config import HandsConfig
from hermes_hands.pikvm_client import PikvmClient

cfg = HandsConfig.from_env()            # PIKVM_BASE_URL / USERNAME / PASSWORD
with PikvmClient(cfg) as hands:
    jpeg = hands.snapshot()              # "eyes": screen as JPEG bytes
    open("screen.jpg", "wb").write(jpeg)
```

Input methods: `move_mouse(to_x, to_y)`, `move_mouse_relative(dx, dy)`, `click_mouse(button)`, `scroll(dx, dy)`, `type_text(text)`. Every call passes the policy gate and lands in the audit log.

## Configuration & secrets

Config comes from environment variables / `.env` (see [.env.example](.env.example)). On macOS, the password can live **only in the Keychain** — `.env` holds a pointer:

```dotenv
PIKVM_BASE_URL=https://192.168.50.2
PIKVM_USERNAME=hermes
PIKVM_PASSWORD=keychain:pikvm      # fetched from macOS Keychain at startup
PIKVM_CA_FILE=~/.pikvm/ca.pem     # pinned CA, no insecure-TLS flag needed
```

HTTPS is enforced; TLS certificates must carry your IP in their SAN (BUILD.md A8.5). Full setup walkthrough: **[BUILD.md](BUILD.md)**.

## Safety — read this before giving it hands

- **Default-deny policy.** Only read-only actions (`check_auth`, `get_hid_state`, `snapshot`) and constrained basic input are allowed by default. Power control (ATX), virtual drives (MSD), single-key events, system shortcuts, and all config endpoints are **denied** — the client doesn't even implement them.
- **No automatic approval path.** Dangerous actions need an explicit, human-constructed approval object passed in code. v1 ships no way for an agent to obtain that by itself.
- **Everything is audited.** Every attempt (allowed or denied) is a JSONL record with a request ID, action, redacted params, and result. See [docs/policy.md](docs/policy.md).
- **Threat model, self-piloting risk, hardware rules**: **[SECURITY.md](SECURITY.md)**.

## Project status

**v1 — works for one machine.** A single agent with hands on a single target computer. Tested against kvmd 4.61 on PiKVM V4 Mini, target macOS.

Roadmap:
- **v2 — agent tandem**: a local hands-equipped agent plus a remote cloud agent collaborating in one chat.
- **v3 — self-healing triad**: three machines, one agent each, mutually controlling and restoring each other.

## License

MIT — see [LICENSE](LICENSE).
