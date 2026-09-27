"""MVP acceptance script: auth -> HID -> snapshot -> mouse -> type (spec A11).

Run against a live PiKVM after BUILD.md steps A1-A10:
    uv run python examples/mvp_check.py

Success criteria:
    1. Auth check returns 200
    2. HID state: keyboard + mouse online
    3. Snapshot: valid JPEG saved
    4. Mouse moves (verified by a second snapshot)
    5. HERMES_HANDS_MVP_OK typed (verify in a focused text editor)
    6. Every action present in the audit JSONL
"""

import sys
import time
from pathlib import Path

import os

from hermes_hands.audit import AuditLogger
from hermes_hands.config import HandsConfig, ConfigError
from hermes_hands.pikvm_client import PikvmClient
from hermes_hands.policy import PolicyGate
from hermes_hands import __version__

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = REPO / "logs"


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
    print(f"hermes-hands v{__version__} — MVP acceptance check")
    print("WARNING: this script MOVES THE MOUSE and TYPES. Open TextEdit, focus it, then run.\n")

    load_dotenv(REPO / ".env")

    # Mouse click stays disabled: MVP check only moves and types.
    policy = PolicyGate(allow_mouse_click=False)

    try:
        cfg = HandsConfig.from_env()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print(f"Set PIKVM_BASE_URL / PIKVM_USERNAME / PIKVM_PASSWORD (see {REPO / '.env.example'}).", file=sys.stderr)
        return 2

    SNAPSHOT_DIR.mkdir(exist_ok=True)
    audit = AuditLogger(SNAPSHOT_DIR / "audit.jsonl")

    ok = True
    with PikvmClient(cfg, policy=policy, audit=audit) as hands:
        # 1. Auth
        try:
            auth = hands.check_auth()
            print(f"[1/5] Auth check: {'OK' if auth.authenticated else 'FAILED'}")
            ok = ok and auth.authenticated
        except Exception as e:
            print(f"[1/5] Auth check FAILED: {e}", file=sys.stderr)
            return 1

        # 2. HID
        hid = hands.get_hid_state()
        print(
            f"[2/5] HID: keyboard={'online' if hid.keyboard_online else 'OFFLINE'}, "
            f"mouse={'online' if hid.mouse_online else 'OFFLINE'}"
        )
        if not (hid.keyboard_online and hid.mouse_online):
            print("     HID not fully online. See BUILD.md troubleshooting (UDC_STATE=configured).", file=sys.stderr)
            return 1

        # 3. Snapshot (before)
        before = hands.snapshot()
        (SNAPSHOT_DIR / "mvp_before.jpg").write_bytes(before)
        print(f"[3/5] Snapshot: {len(before)} bytes -> logs/mvp_before.jpg")

        # 4. Move mouse
        hands.move_mouse(to_x=-200, to_y=-100)
        time.sleep(0.5)
        after = hands.snapshot()
        (SNAPSHOT_DIR / "mvp_after.jpg").write_bytes(after)
        cursor_moved = before != after
        print(f"[4/5] Mouse move: {'cursor moved (snapshots differ)' if cursor_moved else 'snapshots identical — check OTG'}")
        ok = ok and cursor_moved

        # 5. Type
        hands.type_text("HERMES_HANDS_MVP_OK")
        print("[5/5] Typed 'HERMES_HANDS_MVP_OK' — verify it appeared in your focused editor.")

    # 6. Audit
    entries = audit.read()
    actions = [e["action"] for e in entries]
    expected = {"check_auth", "get_hid_state", "snapshot", "move_mouse", "type_text"}
    audited = expected.issubset(set(actions))
    print(f"\nAudit trail ({len(entries)} entries): {', '.join(actions)}")
    print(f"Expected actions all audited: {'YES' if audited else 'NO'}")

    if ok and audited:
        print("\nMVP: PASS — hands are working.")
        return 0
    print("\nMVP: FAIL — see steps above.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
