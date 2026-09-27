"""Hermes Hands v1 — open-source release. User-facing documentation."""

import argparse
import os
import sys
from pathlib import Path

from hermes_hands.audit import AuditLogger
from hermes_hands.config import HandsConfig, ConfigError
from hermes_hands.pikvm_client import PikvmClient
from hermes_hands.policy import PolicyGate
from hermes_hands import __version__

REPO = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, # comments, no quoting magic."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safety-first demo: snapshot only, zero input actions."
    )
    parser.add_argument("--output", default="snapshot.jpg", help="Output JPEG path")
    parser.add_argument(
        "--audit", default="logs/audit.jsonl", help="Audit log path (JSONL)"
    )
    parser.add_argument(
        "--count", type=int, default=1, help="Number of snapshots to take (default 1)"
    )
    args = parser.parse_args()

    load_dotenv(REPO / ".env")

    print(f"hermes-hands v{__version__} — observe-only demo")
    print("Policy: observe-only — clicks, typing, and all input are DISABLED.\n")

    # Hard guarantee: the policy gate allows nothing dangerous,
    # and this script never calls any input method.
    policy = PolicyGate(allow_mouse_click=False)

    try:
        cfg = HandsConfig.from_env()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print(f"Set PIKVM_BASE_URL / PIKVM_USERNAME / PIKVM_PASSWORD (see {REPO / '.env.example'}).", file=sys.stderr)
        return 2

    audit = AuditLogger(REPO / args.audit)

    with PikvmClient(cfg, policy=policy, audit=audit) as hands:
        auth = hands.check_auth()
        print(f"[1/4] Auth: {'OK' if auth.authenticated else 'NOT AUTHENTICATED'}")
        if not auth.authenticated:
            print("Cannot verify auth — aborting.", file=sys.stderr)
            return 1

        hid = hands.get_hid_state()
        print(
            f"[2/4] HID: keyboard={'online' if hid.keyboard_online else 'OFFLINE'}, "
            f"mouse={'online' if hid.mouse_online else 'OFFLINE'}"
        )
        if not hid.online:
            print("WARNING: HID not fully online — OTG cable may not be configured (UDC_STATE).")
            print("         This demo only observes, so continuing anyway.")

        for i in range(args.count):
            jpeg = hands.snapshot()
            out = Path(args.output if i == 0 else args.output.replace(".", f"_{i+1}.", 1))
            out.write_bytes(jpeg)
            print(f"[3/4] Snapshot {i + 1}/{args.count}: {len(jpeg)} bytes -> {out}")

    print("[4/4] Audit written to", audit.path)
    print("\nNo input was sent. Observe-only demo complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
