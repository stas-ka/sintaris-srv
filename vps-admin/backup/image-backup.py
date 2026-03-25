#!/usr/bin/env python3
"""
image-backup.py — Provider image/snapshot guide for Sintaris VPS servers.

Both providers (Netcup, IONOS) require snapshots to be taken MANUALLY
via their web control panels. This script:
  - Shows step-by-step instructions for each provider
  - Sends Telegram reminders to take manual snapshots
  - Records snapshot history in a local log file
  - Reports when the last snapshot was taken

Usage:
  python3 image-backup.py guide   [--server netcup|ionos|all]  # show instructions
  python3 image-backup.py remind  [--server netcup|ionos|all]  # send Telegram reminder
  python3 image-backup.py log     --server netcup|ionos --snapshot NAME  # record manual snapshot
  python3 image-backup.py status                                # show last recorded snapshots

Provider control panels:
  Netcup (dev2null.de):   https://www.servercontrolpanel.de
  IONOS  (dev2null.website): https://my.ionos.com

Config: ../../../.env  (TG_BOT_TOKEN, TG_CHAT_ID)
History: image-backup-log.json  (local, gitignored)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
ENV_FILE   = SCRIPT_DIR / "../../../.env"
LOG_FILE   = SCRIPT_DIR / "image-backup-log.json"

NETCUP_SCP_URL = "https://www.servercontrolpanel.de"
IONOS_CP_URL   = "https://my.ionos.com"
TG_API         = "https://api.telegram.org/bot{token}/sendMessage"


def load_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env(ENV_FILE)


def cfg(key: str, default: str = "") -> str:
    return ENV.get(key, os.environ.get(key, default))


def log_msg(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def tg_notify(msg: str) -> None:
    token = cfg("TG_BOT_TOKEN")
    chat  = cfg("TG_CHAT_ID")
    if not token or not chat:
        print("  (Telegram not configured — skipping notification)")
        return
    if requests is None:
        print("  (pip3 install requests to enable Telegram)")
        return
    try:
        r = requests.post(
            TG_API.format(token=token),
            data={"chat_id": chat, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.ok:
            print("  Telegram notification sent ✓")
    except Exception as e:
        print(f"  Telegram error: {e}")


# ---------------------------------------------------------------------------
# Snapshot history log
# ---------------------------------------------------------------------------

def load_log() -> dict:
    if LOG_FILE.exists():
        return json.loads(LOG_FILE.read_text())
    return {"snapshots": []}


def save_log(data: dict) -> None:
    LOG_FILE.write_text(json.dumps(data, indent=2))


def record_snapshot(server: str, name: str, note: str = "") -> None:
    data = load_log()
    entry = {
        "server":    server,
        "snapshot":  name,
        "recorded":  datetime.now(timezone.utc).isoformat(),
        "note":      note,
    }
    data["snapshots"].append(entry)
    save_log(data)
    log_msg(f"✅ Recorded snapshot '{name}' for {server}")


def last_snapshot(server: str) -> dict | None:
    data = load_log()
    snaps = [s for s in data["snapshots"] if s["server"] == server]
    return snaps[-1] if snaps else None


# ---------------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------------

NETCUP_GUIDE = """
╔══════════════════════════════════════════════════════════════════╗
║  NETCUP Snapshot — dev2null.de                                  ║
║  Panel: https://www.servercontrolpanel.de                       ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  CREATE a snapshot:                                             ║
║  1. Log in at https://www.servercontrolpanel.de                 ║
║  2. Select your vServer (dev2null.de)                           ║
║  3. Go to: Snapshots (left sidebar)                             ║
║  4. Click "Create Snapshot"                                     ║
║  5. Enter a descriptive name, e.g. copilot-2026-03-25          ║
║  6. Confirm — snapshot creation takes a few minutes             ║
║                                                                  ║
║  RESTORE a snapshot:                                            ║
║  1. Go to Snapshots in SCP                                      ║
║  2. Click "Restore" next to the desired snapshot                ║
║  3. Confirm — server will be stopped and restored               ║
║     ⚠️  ALL data since snapshot creation will be LOST           ║
║                                                                  ║
║  Notes:                                                          ║
║  - Netcup snapshots are Copy-on-Write (fast, space-efficient)   ║
║  - Number of snapshots limited by your plan                     ║
║  - No public REST API for snapshots — web panel only            ║
║                                                                  ║
║  After creating: run 'python3 image-backup.py log               ║
║    --server netcup --snapshot <name>' to record it here         ║
╚══════════════════════════════════════════════════════════════════╝
"""

IONOS_GUIDE = """
╔══════════════════════════════════════════════════════════════════╗
║  IONOS Snapshot — dev2null.website                              ║
║  Panel: https://my.ionos.com                                    ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  CREATE a snapshot:                                             ║
║  1. Log in at https://my.ionos.com                              ║
║  2. Go to: Server & Cloud → select dev2null.website             ║
║  3. Click the "Snapshots" tab                                   ║
║  4. Click "Create Snapshot"                                     ║
║  5. Enter a name, e.g. copilot-2026-03-25                      ║
║  6. Confirm — takes a few minutes                               ║
║                                                                  ║
║  RESTORE a snapshot:                                            ║
║  1. Go to Snapshots tab                                         ║
║  2. Click "Restore" next to the snapshot                        ║
║     ⚠️  ALL data since snapshot creation will be LOST           ║
║                                                                  ║
║  Notes:                                                          ║
║  - Legacy IONOS VPS — no public REST API for snapshots          ║
║  - Snapshot limit depends on your VPS plan                      ║
║  - For scripted snapshots, consider migrating to IONOS Cloud    ║
║                                                                  ║
║  After creating: run 'python3 image-backup.py log               ║
║    --server ionos --snapshot <name>' to record it here          ║
╚══════════════════════════════════════════════════════════════════╝
"""


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_guide(args) -> None:
    servers = _resolve_servers(args.server)
    if "netcup" in servers:
        print(NETCUP_GUIDE)
    if "ionos" in servers:
        print(IONOS_GUIDE)


def cmd_remind(args) -> None:
    servers = _resolve_servers(args.server)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    parts = []
    if "netcup" in servers:
        last = last_snapshot("netcup")
        age = _age_str(last)
        parts.append(
            f"🖥 <b>dev2null.de</b> (Netcup)\n"
            f"  Last snapshot: {age}\n"
            f"  Panel: {NETCUP_SCP_URL}"
        )
    if "ionos" in servers:
        last = last_snapshot("ionos")
        age = _age_str(last)
        parts.append(
            f"🖥 <b>dev2null.website</b> (IONOS)\n"
            f"  Last snapshot: {age}\n"
            f"  Panel: {IONOS_CP_URL}"
        )

    msg = (
        f"📸 <b>Image Backup Reminder</b> — {date}\n\n"
        + "\n\n".join(parts)
        + "\n\n⚠️ Snapshots are MANUAL — log in to each panel to create them."
    )
    print(msg)
    tg_notify(msg)


def cmd_log(args) -> None:
    if not args.snapshot:
        print("ERROR: --snapshot NAME is required", file=sys.stderr)
        sys.exit(1)
    server = args.server
    if server not in ("netcup", "ionos"):
        print("ERROR: --server must be 'netcup' or 'ionos'", file=sys.stderr)
        sys.exit(1)

    record_snapshot(server, args.snapshot, args.note or "")
    tg_notify(
        f"📸 <b>Image snapshot recorded</b>\n"
        f"Server: {server} ({'dev2null.de' if server == 'netcup' else 'dev2null.website'})\n"
        f"Snapshot: {args.snapshot}\n"
        f"{'Note: ' + args.note if args.note else ''}"
    )


def cmd_status(args) -> None:
    print("=== Image Backup Status ===\n")
    data = load_log()

    for server, label, panel in [
        ("netcup", "dev2null.de",      NETCUP_SCP_URL),
        ("ionos",  "dev2null.website", IONOS_CP_URL),
    ]:
        snaps = [s for s in data["snapshots"] if s["server"] == server]
        print(f"{'─'*55}")
        print(f"  {label} ({server.upper()})")
        print(f"  Panel: {panel}")
        if snaps:
            last = snaps[-1]
            print(f"  Last recorded: {last['snapshot']}  ({last['recorded'][:16]}Z)")
            if last.get("note"):
                print(f"  Note: {last['note']}")
            if len(snaps) > 1:
                print(f"  Total recorded: {len(snaps)} snapshots")
        else:
            print(f"  Last recorded: ⚠️  none — take a snapshot and run 'log' command")
        print()

    if not data["snapshots"]:
        print("No snapshots recorded yet.")
        print("After creating snapshots via the web panels, run:")
        print("  python3 image-backup.py log --server netcup --snapshot <name>")
        print("  python3 image-backup.py log --server ionos  --snapshot <name>")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_servers(server_arg: str) -> list:
    if server_arg == "all":
        return ["netcup", "ionos"]
    if server_arg in ("netcup", "ionos"):
        return [server_arg]
    print(f"ERROR: Unknown --server '{server_arg}'. Use: netcup, ionos, all", file=sys.stderr)
    sys.exit(1)


def _age_str(last: dict | None) -> str:
    if not last:
        return "⚠️  never recorded"
    ts   = datetime.fromisoformat(last["recorded"])
    now  = datetime.now(timezone.utc)
    days = (now - ts).days
    name = last["snapshot"]
    if days == 0:
        return f"✅ today — {name}"
    if days == 1:
        return f"✅ yesterday — {name}"
    return f"⚠️  {days} days ago — {name}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Image/snapshot backup guide and tracker for Sintaris VPS servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("command", choices=["guide", "remind", "log", "status"],
                        help="Action to perform")
    parser.add_argument("--server", default="all",
                        choices=["netcup", "ionos", "all"],
                        help="Target server (default: all)")
    parser.add_argument("--snapshot", metavar="NAME",
                        help="Snapshot name to record (required for log)")
    parser.add_argument("--note", metavar="TEXT",
                        help="Optional note to attach to the log entry")
    args = parser.parse_args()

    dispatch = {
        "guide":  cmd_guide,
        "remind": cmd_remind,
        "log":    cmd_log,
        "status": cmd_status,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
