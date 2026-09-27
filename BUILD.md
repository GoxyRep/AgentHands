# BUILD.md — Build your AI agent's hands in one evening

This guide takes you from a pile of boxes to a working `hermes-hands` rig: an AI agent that can see your computer's screen and type on its keyboard **through hardware**, no software on the target machine required.

You need: basic familiarity with `ssh`, `curl`, and a terminal. No PiKVM experience required. Every step says **what to do → what you should see → what to try if it fails**.

---

## 1. Shopping list

| # | Item | Price guide | What it's for |
|---|------|-------------|---------------|
| 1 | [PiKVM V4 Mini](https://pikvm.org/) | ~$140 | the KVM device itself (eyes + hands) |
| 2 | HDMI cable (length to fit your desk) | ~$8 | eyes: Mac → PiKVM |
| 3 | USB-C→USB-A cable + USB-A→USB-C adapter, or a USB-C OTG cable | ~$12 | hands: PiKVM → Mac (OTG) |
| 4 | Active USB-C→RJ45 adapter (e.g. LogiLink 10 m) **or** a regular Ethernet cable to your router | ~€26 / ~$5 | network: the HTTPS API |
| 5 | 5.1 V / 3 A USB-C power supply (if not included) | ~$10 | powering the PiKVM |
| 6 | USB-Serial adapter | ~$8 | the emergency recovery console |

Example store links: PiKVM devices are sold via the [official store](https://pikvm.org/) and resellers (Amazon, AliExpress); cables — any electronics store. Prices are orientation, not quotes.

**If your machine has a built-in Ethernet port** (Mac Studio, most desktops): skip item 4's adapter and just run an Ethernet cable from the PiKVM to your router. That's the recommended setup — USB-Ethernet adapters (ECM/NCM mode) are known to be flaky with some macOS + kvmd versions.

## 2. Wiring diagram

```
                 YOUR ROUTER
                      │ RJ45 (Ethernet)
                      │
     ┌────────────────┴────────────────┐
     │  PiKVM V4 Mini                  │
     │  front port: RJ45 ──────────────┘  (item 4)
     │                                 │
     │  HDMI IN  ◄────────────────────── Mac HDMI OUT   (item 2: the eyes)
     │  USB OTG  ───────────────────────► Mac USB-C     (item 3: the hands)
     │                                 │
     │  USB-C PWR ◄───────────────────── 5.1V/3A PSU   (item 5)
     │  µSD / serial ◄────────────────── USB-Serial → your other computer (item 6)
     └─────────────────────────────────┘
```

Label every cable the day you buy them — future-you will thank you at 2 AM.

---

## 3. Assembly & bring-up: steps A1–A11

### A1 — Ethernet
**Do**: with the PiKVM **unpowered**, plug the RJ45 cable from the PiKVM front port into your router (or the USB-C→RJ45 adapter into your Mac).
**Expect**: nothing. This is a passive step.
**If it fails**: nothing to fail yet — just double-check the cable sits in the *front* RJ45 port.

### A2 — Serial console
**Do**: connect the USB-Serial adapter to the PiKVM's serial pins/connector and to another computer. Open a terminal there and run:

```bash
screen /dev/cu.usbserial-* 115200
```

**Expect**: a blank screen waiting. This is your **emergency channel** — keep this `screen` session open the whole evening. If the PiKVM ever loses the network, this is how you talk to it.
**If it fails**: `ls /dev/cu.usbserial*` — if nothing appears, the adapter needs a driver (FTDI/CP2102 chips: macOS has them built in; some cheap CH340 chips need the driver).

### A3 — Power
**Do**: plug in the 5.1 V / 3 A USB-C power supply.
**Expect**: boot log starts scrolling in the serial console. Wait for it to settle (about a minute).
**If it fails**: no log in serial → check the adapter's TX/RX aren't swapped; red LED off → check the PSU actually delivers 3 A.

### A4 — DHCP: find the IP
**Do**: in the serial console, log in as `root` (default password — see the PiKVM docs; you'll change it in A6) and run:

```bash
ip -br address
```

**Expect**: an IPv4 address like `192.168.1.42` on `eth0`. **Write it down.** All following steps use `<IP>` for it.
**If it fails**: no address → the router didn't hand one out; check the RJ45 link LEDs at both ends, try another port/cable.

### A5 — API alive?
**Do**: from your main computer:

```bash
curl -ksS https://<IP>/api/auth/check
```

**Expect**: **HTTP 401**. That's *correct* — it means the API is alive and demanding authentication. This is the first "the thing works" moment.
**If it fails**: connection refused → the PiKVM web service isn't up yet, give it another minute in serial; timeout → wrong IP or a firewall between you and the PiKVM.

### A6 — Change the factory passwords
**Do**: in the serial console, change the passwords of **both** `root` and the web `admin` user. Factory passwords are publicly documented — anyone on your LAN knows them.

```bash
passwd root          # serial console
kvmd-htpasswd set admin   # web admin password
```

**Expect**: both commands succeed, and logging in with the new passwords works.
**If it fails**: `kvmd-htpasswd set admin` unknown → your kvmd version may use the older flow; run `kvmd-htpasswd --help` to see the exact subcommand.
**Why before everything else**: until this step, your PiKVM accepts known-to-the-world credentials over the network. Don't skip it, don't postpone it.

### A7 — Create the API user `hermes`
**Do**: in the serial console:

```bash
kvmd-htpasswd add hermes
```

Enter a strong password (this is what the agent will use; it's distinct from `admin` on purpose — you can revoke the agent without locking yourself out).
**Expect**: `kvmd-htpasswd list` shows both `admin` and `hermes`.
**If it fails**: unknown command → check `kvmd-htpasswd --help`; on very old kvmd the tool may be `kvmd-htpasswd` with different args.

### A8 — Store the secret, fill `.env`
**Do**: store the `hermes` password in macOS Keychain (preferred):

```bash
security add-generic-password -a hermes -s pikvm -w '<the password>'
# later, to read it into your shell:
security find-generic-password -a hermes -s pikvm -w
```

or export it in your `~/.bashrc` / `~/.zshrc`. Then create `.env` in the `hermes-hands` repo (never commit it — it's gitignored):

```dotenv
PIKVM_BASE_URL=https://<IP>
PIKVM_USERNAME=hermes
PIKVM_PASSWORD=<the password>
PIKVM_CA_FILE=
```

**Expect**: `security find-generic-password -a hermes -s pikvm -w` prints the password; the `.env` file exists locally.
**If it fails**: "The specified item could not be found" → re-run `add-generic-password` and check the service/account spelling.

### A9 — HDMI + OTG (the eyes and the hands)
**Do**: with everything still powered as-is:
1. HDMI cable: Mac HDMI OUT → PiKVM **HDMI IN** (item 2).
2. OTG: PiKVM OTG port → USB-A cable → USB-A→USB-C adapter → Mac (item 3).

Verify in the serial console (or the web interface) that the OTG device connected:

```bash
kvmd-otgconf    # shows OTG state; look for UDC_STATE
```

**Expect**: `UDC_STATE=configured` — the Mac has accepted the PiKVM as a USB keyboard/mouse. In the web interface's HID menu, keyboard and mouse show as **online**.
**If it fails**: see Troubleshooting §5.1 — this is the single most common stumble point (cable/port/adapter).

### A10 — First snapshot (sanity)
**Do**: open `https://<IP>` in your browser, log in as `admin`, look at the live stream.
**Expect**: the picture matches your Mac's actual screen. Colors may look slightly off — fine. Black screen → Troubleshooting §5.3.
**If it fails**: (see troubleshooting table below).

### A11 — Live test: the acceptance run
**Do**: on the Mac, open **TextEdit** (or any harmless text app), create an empty document, click into it. Then, from the `hermes-hands` repo:

```bash
uv run python examples/mvp_check.py
```

**Expect**, in order:
1. `[1/5] Auth check: OK`
2. `[2/5] HID: keyboard=online, mouse=online`
3. `[3/5] Snapshot: ... bytes -> logs/mvp_before.jpg` — open it, it's your screen
4. `[4/5] Mouse move: cursor moved` — you saw the cursor jump
5. `HERMES_HANDS_MVP_OK` appears **in TextEdit**
6. `MVP: PASS` and the audit summary: every action is in `logs/audit.jsonl`

**If it fails**: any step — check `logs/audit.jsonl` (it tells you exactly which call failed and why), then the Troubleshooting section. Also try the zero-input sanity check first:

```bash
uv run python examples/observe_only.py    # snapshots only, no input at all
```

---

## 4. Verification checklist

You're done when all of these are true:

- [ ] `curl -ksS https://<IP>/api/auth/check` → 401 without credentials
- [ ] `kvmd-htpasswd list` shows `admin` + `hermes`, factory passwords changed
- [ ] Web interface shows a live picture matching the real screen (A10)
- [ ] `examples/observe_only.py` saves a snapshot, sends **zero** input
- [ ] `examples/mvp_check.py` prints `MVP: PASS`
- [ ] `logs/audit.jsonl` contains records for every action, no plaintext passwords anywhere in it
- [ ] From the repo: `uv run pytest -v --cov=hermes_hands` — all green (this works without any hardware)

## 5. Troubleshooting

### 5.1 `UDC_STATE` never shows `configured`
The Mac isn't accepting the PiKVM as a USB device. In order:
1. Re-seat both ends of the OTG path; try a different USB port on the Mac.
2. Swap the USB-A→USB-C adapter — most OTG failures are the adapter.
3. Try a different USB-A cable (it must be a *data* cable, not charge-only).
4. In serial: `kvmd-otgconf -c` to list/change the gadget config; some setups need the OTG state toggled (`kvmd-otgconf --set-state=...` per your kvmd version).

### 5.2 401 on auth-check even after changing the password
1. Your `curl` may be reusing a stale session cookie — the `X-KVMD-User`/`X-KVMD-Passwd` headers (or HTTP Basic auth, which the client uses) don't use cookies at all; make sure you're sending them.
2. Confirm the user exists: `kvmd-htpasswd list` in serial.
3. Confirm you changed the *web* admin password, not only the `root` shell password — they're different stores.

### 5.3 Black screen on snapshot / stream
1. HDMI cable not fully seated, or the Mac's HDMI output is off — check System Settings → Displays.
2. Wrong source: the PiKVM has one HDMI IN; make sure the Mac's *built-in* display isn't the only active one (mirror or extend the desktop).
3. Resolution the capture chip can't parse (rare) — set the Mac to a standard resolution (e.g. 1920×1080) and retry.
4. HDCP-protected content shows black **by design** — see README's comparison table.

### 5.4 macOS doesn't see the USB-C→RJ45 network adapter
1. Check the chipset: **ASIX (AX88179) and Realtek (RTL8153)** work out of the box on modern macOS. Odd chipsets need third-party drivers — avoid.
2. Prefer the plain Ethernet-to-router route entirely (item 4's alternative) — it's more reliable and the recommended setup anyway.

### 5.5 "Don't enable 2FA until NTP is stable" — and other iron rules
- **2FA/TOTP needs correct time.** If the PiKVM's clock drifts (no reliable NTP), every TOTP code is rejected and you can lock yourself out. Check `date` in the serial console first; only then enable 2FA in the web interface.
- Don't change DIP switches while the board is powered.
- Don't use a Raspberry Pi 5 RTC battery in the PiKVM — incompatible, it damages the board.
- kvmd versions: if your device ships an old kvmd (check in serial: `dpkg -l | grep kvmd`), run `pikvm-update` once the network is up — but not mid-session; do it before A9 and re-verify afterward.

### 5.6 Snapshots work, input doesn't (or vice versa)
- Eyes and hands are **independent channels**: HDMI (eyes) and OTG (hands). A failure in one doesn't imply the other. Re-verify A9 (`UDC_STATE`) for hands, A10 for eyes.

---

Questions the guide didn't answer? Open an issue — this document is meant to be the last thing between a stranger and working hands.
