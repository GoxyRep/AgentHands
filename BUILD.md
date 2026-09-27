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

**No router? Direct cable works fine.** A USB-C→RJ45 adapter (Realtek RTL8153 or ASIX AX88179 chipset — both native on macOS) makes a perfectly good point-to-point link: adapter into the Mac, RJ45 cable straight into the PiKVM. You lose DHCP (there's no server on a point-to-point link), so you'll assign static IPs in A4 — see the *Direct link* box there. This is a fully supported layout; it's how the v1 rig was built and tested.

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

> **Direct link (no router): assign static IPs.** With no DHCP server, the PiKVM boots with no usable address (`IP: 127.0.0.2` in the boot banner is the giveaway). Pick a /24 for the two of you — say Mac `192.168.50.1`, PiKVM `192.168.50.2`:
>
> On the **Mac** (find the adapter's service name via `networksetup -listallhardwareports`, e.g. `USB 10/100/1000 LAN`):
> ```bash
> sudo networksetup -setmanual "USB 10/100/1000 LAN" 192.168.50.1 255.255.255.0
> ```
>
> On the **PiKVM** (serial console) — set it live, then make it persistent:
> ```bash
> ip addr add 192.168.50.2/24 dev eth0        # live, right now
> rw                                          # filesystem write mode
> printf "[Match]\nName=eth0\n\n[Network]\nDHCP=no\nAddress=192.168.50.2/24\nDNSSEC=no\n" > /etc/systemd/network/eth0.network
> systemctl restart systemd-networkd
> ro                                          # back to read-only
> ```
>
> Expect `eth0` to show `192.168.50.2/24` and the link to go `UP` on both ends (`ifconfig` on the Mac). Then continue with `<IP>` = `192.168.50.2` everywhere below.

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

> **A8.5 — Pin the CA with a proper certificate (do this before first run).** The stock PiKVM certificate is issued for `CN=localhost` and **does not contain your IP in its SAN** — TLS verification will fail with `certificate is not valid for '192.168.50.2'` even after you pin it. Fix it once, on the PiKVM (serial console):
>
> ```bash
> rw
> cd /etc/kvmd/nginx/ssl
> openssl req -x509 -newkey rsa:2048 -keyout /tmp/k.key -out /tmp/k.crt -days 3000 -nodes \
>   -subj "/C=US/O=PiKVM/CN=pikvm" \
>   -addext "subjectAltName=DNS:pikvm,DNS:localhost,IP:192.168.50.2"
> mv server.crt server.crt.old && cp /tmp/k.crt server.crt && cp /tmp/k.key server.key
> systemctl restart kvmd-nginx
> ro
> ```
>
> Then fetch the new cert onto the Mac and point `.env` at it:
> ```bash
> mkdir -p ~/.pikvm
> echo | openssl s_client -connect 192.168.50.2:443 2>/dev/null | sed -n '/BEGIN CERT/,/END CERT/p' > ~/.pikvm/ca.pem
> ```
>
> Set `PIKVM_CA_FILE=~/.pikvm/ca.pem` in `.env`. Now the client verifies TLS end-to-end with **no** `HERMES_HANDS_INSECURE_TLS` escape hatch. Re-do the fetch step whenever you regenerate the certificate.

### A9 — HDMI + OTG (the eyes and the hands)
**Do**: with everything still powered as-is:
1. HDMI cable: Mac HDMI OUT → PiKVM **HDMI IN** (item 2).
2. OTG: PiKVM OTG port → USB-A cable → USB-A→USB-C adapter → Mac (item 3).

⚠️ **Do not use a USB-C→USB-C cable on the OTG port.** This is the #1 trap, confirmed in the official FAQ and in the field: many C→C cables (especially e-marker ones) fail to carry the HID gadget to macOS — the PiKVM side looks fine (`UDC_STATE=configured`, `dwc2: new device`), but the Mac never sees "PiKVM Composite Device" and no keyboard/mouse appears. Use the C→A cable + A→C adapter for OTG; the C→C cable is fine for the serial console port.

Also on the Mac: if System Settings → Privacy & Security → "Allow new accessories to connect" is set to "Ask", approve the new USB accessory when prompted.

Verify in the serial console (or the web interface) that the OTG device connected:

```bash
kvmd-otgconf    # shows OTG state; look for UDC_STATE
```

**Expect**: `UDC_STATE=configured` — and, on the Mac, `ioreg -p IOUSB -w 0 | grep PiKVM` shows "PiKVM Composite Device", `hidutil list` shows its keyboard and mouse services. In the web interface's HID menu, keyboard and mouse show as **online**.
**If it fails**: see Troubleshooting §5.1 — this is the single most common stumble point (cable/port/adapter).

### A10 — First snapshot (sanity)
**Do**: open `https://<IP>` in your browser, log in as `admin`, look at the live stream.
**Expect**: the picture matches your Mac's actual screen. Colors may look slightly off — fine. Black screen → Troubleshooting §5.3.
**If it fails**: (see troubleshooting table below).

> **kvmd ≥ 4.2 / V4 Mini: enable automatic snapshots for API access.** On the modern janus-based video stack, `GET /api/streamer/snapshot` returns **503** until either a browser has an active stream open, or automatic snapshots are enabled. The API-only route (what `hermes-hands` uses) needs the latter — set it once on the PiKVM:
>
> ```bash
> rw
> printf "kvmd:\n  snapshot:\n    idle_interval: 10\n    live_interval: 1\n" >> /etc/kvmd/override.yaml
> systemctl restart kvmd
> ro
> ```
>
> (Merge into the existing `kvmd:` key if your `override.yaml` already has one — duplicate top-level keys are a YAML error.) Then, after a few seconds:
> ```bash
> curl -k -u hermes:<password> "https://<IP>/api/streamer/snapshot?load=1" -o frame.jpg
> ```
> should return a real JPEG (`file frame.jpg` → `JPEG image data ... 1920x1080`).
>
> On older ustreamer-based kvmd (≤ 4.x with `/run/kvmd/ustreamer.sock`), snapshots work out of the box and this step is unnecessary. If your unit ships an old kvmd, upgrade it first: `pikvm-update` (needs internet — see Troubleshooting §5.7 for a temporary NAT recipe).

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

### 5.1 `UDC_STATE` never shows `configured` — or the Mac never sees the device
`UDC_STATE=configured` but the Mac shows nothing in `ioreg -p IOUSB`? The most likely culprit, in order:
1. **USB-C→USB-C cable on OTG (the classic).** Swap to the C→A cable + A→C adapter. Confirmed both by the official FAQ and in the field: the PiKVM side reports success while macOS never mounts the HID interfaces. This is the first thing to try, not the last.
2. **macOS "Allow new accessories to connect"** (System Settings → Privacy & Security) set to "Ask" — the device waits for approval silently. Switch to "Always" or approve the prompt.
3. Re-seat both ends of the OTG path; try a different USB port on the Mac.
4. Swap the USB-A→USB-C adapter — most OTG failures are the adapter.
5. Try a different USB-A cable (it must be a *data* cable, not charge-only).
6. In serial: `kvmd-otgconf -l` to check the gadget list; some setups need the OTG state toggled.

On the Mac, verify with: `ioreg -p IOUSB -w 0 | grep PiKVM` (want: "PiKVM Composite Device") and `hidutil list | grep -i pikvm` (want: keyboard/mouse HID services).

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
- An `rtc-pcf8563 ... low voltage detected` line scrolling in the serial console every ~30 s is the (separate, known) RTC battery issue — noisy, but not blocking anything.
- kvmd versions: check yours in serial with `pacman -Q kvmd` (not `dpkg` — it's Arch-based). If it ships an old kvmd (4.6x era has a broken snapshot path on janus-based images), run `pikvm-update` once the network is up — see §5.7 for the no-router NAT recipe. Do it **before** A9–A11 and re-verify the OTG link afterward (the reboot re-enumerates USB).

### 5.6 Snapshots work, input doesn't (or vice versa)
- Eyes and hands are **independent channels**: HDMI (eyes) and OTG (hands). A failure in one doesn't imply the other. Re-verify A9 (`UDC_STATE`) for hands, A10 for eyes.

### 5.7 `pikvm-update` on a direct-link rig (no internet on the PiKVM)
The PiKVM needs internet for the update, but on a point-to-point cable there's no uplink. Share the Mac's connection temporarily:

```bash
# On the Mac (Wi-Fi is en0 — adjust if yours differs):
sudo sysctl -w net.inet.ip.forwarding=1
echo "nat on en0 from 192.168.50.0/24 to any -> (en0)" | sudo tee /etc/pf-nat.conf
sudo pfctl -f /etc/pf-nat.conf; sudo pfctl -e

# On the PiKVM (serial console):
ip route add default via 192.168.50.1
echo "nameserver 1.1.1.1" > /etc/resolv.conf
ping -c 2 1.1.1.1    # expect replies — NAT is live
pikvm-update         # ~10–20 min; the device reboots itself when done
```

Note: `/etc/resolv.conf` is ephemeral on the read-only root — re-set it after each reboot of the PiKVM if you still need DNS. When done, roll the Mac back: `sudo pfctl -d; sudo sysctl -w net.inet.ip.forwarding=0`.

A `.pacnew` warning and `could not get file information for var/log/...` lines during the update are normal. On a direct link, also note the update does **not** touch your static `eth0.network` — the IP survives.

### 5.8 `certificate is not valid for '192.168.50.2'` with CA pinning
The stock PiKVM cert has `CN=localhost` and no SAN for your IP. Don't disable verification — regenerate the cert with a proper SAN (see step A8.5). One-time fix, survives reboots (but not `pikvm-update` if it replaces nginx certs — re-check after major updates).

---

Questions the guide didn't answer? Open an issue — this document is meant to be the last thing between a stranger and working hands.
