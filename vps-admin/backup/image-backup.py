#!/usr/bin/env python3
"""
image-backup.py — Provider-level image/snapshot backup for Sintaris VPS servers.

Manages full-disk snapshots via hosting provider APIs:
  - dev2null.de  → Netcup SCP API (Copy-on-Write snapshots)
  - dev2null.website → IONOS legacy VPS — manual via control panel (no public REST API)
                       OR IONOS Cloud API if server was migrated to IONOS Cloud

Usage:
  python3 image-backup.py create   [--server netcup|ionos|all]
  python3 image-backup.py list     [--server netcup|ionos|all]
  python3 image-backup.py restore  --server netcup --snapshot <name>
  python3 image-backup.py delete   --server netcup --snapshot <name>
  python3 image-backup.py status

Config: ../../../.env  (NETCUP_* and IONOS_* vars — see .env.example)

Requires: pip3 install requests
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: pip3 install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / "../../../.env"

NETCUP_API_URL = "https://www.servercontrolpanel.de/SCP/User"
IONOS_API_URL  = "https://api.ionos.com/cloudapi/v6"

TG_API = "https://api.telegram.org/bot{token}/sendMessage"


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


def tg_notify(msg: str) -> None:
    token = cfg("TG_BOT_TOKEN")
    chat  = cfg("TG_CHAT_ID")
    if not token or not chat:
        return
    try:
        requests.post(
            TG_API.format(token=token),
            data={"chat_id": chat, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Netcup SCP API
# ---------------------------------------------------------------------------

class NetcupSCP:
    """
    Netcup Server Control Panel JSON-RPC API.

    Credentials required in .env:
      NETCUP_CUSTOMER_ID  — customer number (Kundennummer)
      NETCUP_API_KEY      — API key (from SCP → API → Manage API keys)
      NETCUP_API_PASS     — API password
      NETCUP_SERVER_NAME  — vServer name (shown in SCP, e.g. v1234567)

    How to get credentials:
      1. Log in to https://www.customercontrolpanel.de
      2. Go to Master Data → API → Manage API keys
      3. Create a new API key — copy Key and Password
      4. Your customer number is shown in the top-right
      5. Your server name is shown in SCP (https://www.servercontrolpanel.de)
    """

    def __init__(self):
        self.customer_id  = cfg("NETCUP_CUSTOMER_ID")
        self.api_key      = cfg("NETCUP_API_KEY")
        self.api_pass     = cfg("NETCUP_API_PASS")
        self.server_name  = cfg("NETCUP_SERVER_NAME")
        self._session_id  = None

    def _check_credentials(self) -> None:
        missing = [k for k in ("NETCUP_CUSTOMER_ID", "NETCUP_API_KEY", "NETCUP_API_PASS", "NETCUP_SERVER_NAME")
                   if not cfg(k)]
        if missing:
            die(f"Missing Netcup credentials in .env: {', '.join(missing)}\n"
                f"See backup/.env.example for details.")

    def _call(self, action: str, param: dict) -> dict:
        payload = {
            "action": action,
            "param": {
                "customernumber": self.customer_id,
                "apikey": self.api_key,
                **param,
            },
        }
        resp = requests.post(
            NETCUP_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") not in ("success", "warning"):
            raise RuntimeError(
                f"Netcup API error [{data.get('statuscode')}]: "
                f"{data.get('shortmessage')} — {data.get('longmessage')}"
            )
        return data.get("responsedata", {})

    def login(self) -> str:
        self._check_credentials()
        data = self._call("login", {"apipassword": self.api_pass})
        self._session_id = data["apisessionid"]
        return self._session_id

    def logout(self) -> None:
        if self._session_id:
            try:
                self._call("logout", {"apisessionid": self._session_id})
            except Exception:
                pass
            self._session_id = None

    def _session(self) -> dict:
        if not self._session_id:
            self.login()
        return {"apisessionid": self._session_id, "vservername": self.server_name}

    def list_snapshots(self) -> list:
        """Return list of snapshot dicts: {name, description, createdate, size}"""
        data = self._call("listVServerSnapshots", self._session())
        return data if isinstance(data, list) else []

    def create_snapshot(self, description: str = "") -> dict:
        """Create a snapshot. Returns snapshot info dict."""
        label = description or f"copilot-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        data = self._call("createVServerSnapshot", {
            **self._session(),
            "snapshotname": label,
        })
        return data

    def restore_snapshot(self, snapshot_name: str) -> None:
        """Roll back the vServer to a snapshot. Server will be stopped and rebooted."""
        self._call("rollbackVServer", {
            **self._session(),
            "snapshotname": snapshot_name,
        })

    def delete_snapshot(self, snapshot_name: str) -> None:
        """Delete a snapshot."""
        self._call("deleteVServerSnapshot", {
            **self._session(),
            "snapshotname": snapshot_name,
        })


# ---------------------------------------------------------------------------
# IONOS Cloud API (for IONOS Cloud servers only)
# ---------------------------------------------------------------------------

class IonosCloud:
    """
    IONOS Cloud REST API for snapshot management.

    NOTE: This only works for IONOS Cloud (DCD) servers, NOT legacy IONOS VPS.
    dev2null.website is a legacy IONOS VPS — see manual instructions below.

    Credentials required in .env (for IONOS Cloud):
      IONOS_API_TOKEN   — API token from IONOS Cloud DCD → Management → API keys
                          OR use IONOS_USERNAME + IONOS_PASSWORD for Basic Auth
      IONOS_SERVER_ID   — Server UUID (shown in IONOS Cloud DCD panel)
      IONOS_DATACENTER_ID — Datacenter UUID

    Manual procedure for legacy IONOS VPS (dev2null.website):
      1. Log in at https://my.ionos.com
      2. Go to Server & Cloud → your VPS
      3. Click "Snapshots" tab
      4. Click "Create Snapshot" — enter a name and confirm
      5. To restore: click "Restore" next to a snapshot
      See also: vps-admin/docs/07-vps-dev2null.website.md
    """

    IONOS_LEGACY_INSTRUCTIONS = """
⚠️  IONOS LEGACY VPS — No REST API available for snapshots.

Manual procedure at https://my.ionos.com:
  1. Server & Cloud → select dev2null.website VPS
  2. Snapshots → Create Snapshot
  3. To restore: Snapshots → Restore

Note: IONOS legacy VPS snapshots are limited (check your plan).
To enable scripted snapshots, consider migrating to IONOS Cloud (DCD).
"""

    def __init__(self):
        self.token          = cfg("IONOS_API_TOKEN")
        self.username       = cfg("IONOS_USERNAME")
        self.password       = cfg("IONOS_PASSWORD")
        self.server_id      = cfg("IONOS_SERVER_ID")
        self.datacenter_id  = cfg("IONOS_DATACENTER_ID")

    def _has_cloud_credentials(self) -> bool:
        return bool((self.token or (self.username and self.password)) and
                    self.server_id and self.datacenter_id)

    def _headers(self) -> dict:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        import base64
        creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {creds}"}

    def _get(self, path: str) -> dict:
        resp = requests.get(f"{IONOS_API_URL}{path}", headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        resp = requests.post(
            f"{IONOS_API_URL}{path}",
            headers={**self._headers(), "Content-Type": "application/json"},
            json=body, timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_snapshots(self) -> list:
        if not self._has_cloud_credentials():
            print(self.IONOS_LEGACY_INSTRUCTIONS)
            return []
        data = self._get("/snapshots")
        return data.get("items", [])

    def create_snapshot(self, description: str = "") -> dict:
        if not self._has_cloud_credentials():
            print(self.IONOS_LEGACY_INSTRUCTIONS)
            return {}
        label = description or f"copilot-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        volumes = self._get(
            f"/datacenters/{self.datacenter_id}/servers/{self.server_id}/volumes"
        ).get("items", [])
        if not volumes:
            die("No volumes found for IONOS server — check IONOS_DATACENTER_ID and IONOS_SERVER_ID")
        results = []
        for vol in volumes:
            vol_id = vol["id"]
            log(f"Creating IONOS snapshot for volume {vol_id}...")
            snap = self._post(
                f"/datacenters/{self.datacenter_id}/volumes/{vol_id}/create-snapshot",
                {"properties": {"name": label, "description": label}},
            )
            results.append(snap)
        return results


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create(args) -> None:
    servers = _resolve_servers(args.server)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    description = args.description or f"copilot-{timestamp}"

    if "netcup" in servers:
        log(f"Creating Netcup snapshot for {cfg('NETCUP_SERVER_NAME') or 'server'}...")
        tg_notify(f"📸 <b>Image backup started</b> — dev2null.de\n"
                  f"Provider: Netcup SCP\n"
                  f"Label: {description}")
        scp = NetcupSCP()
        try:
            scp.login()
            result = scp.create_snapshot(description)
            log(f"✅ Netcup snapshot created: {result}")
            tg_notify(f"✅ <b>Image backup complete</b> — dev2null.de\n"
                      f"Snapshot: {description}\n{json.dumps(result, indent=2)}")
        except Exception as e:
            tg_notify(f"❌ <b>Image backup FAILED</b> — dev2null.de\n{e}")
            die(str(e))
        finally:
            scp.logout()

    if "ionos" in servers:
        log("IONOS (dev2null.website) snapshot:")
        ionos = IonosCloud()
        if ionos._has_cloud_credentials():
            log(f"Creating IONOS Cloud snapshot...")
            tg_notify(f"📸 <b>Image backup started</b> — dev2null.website\n"
                      f"Provider: IONOS Cloud\nLabel: {description}")
            try:
                result = ionos.create_snapshot(description)
                log(f"✅ IONOS snapshot created")
                tg_notify(f"✅ <b>Image backup complete</b> — dev2null.website")
            except Exception as e:
                tg_notify(f"❌ <b>Image backup FAILED</b> — dev2null.website\n{e}")
                die(str(e))
        else:
            print(IonosCloud.IONOS_LEGACY_INSTRUCTIONS)
            tg_notify("⚠️ <b>IONOS snapshot</b> — dev2null.website\n"
                      "Legacy VPS: manual action required at https://my.ionos.com")


def cmd_list(args) -> None:
    servers = _resolve_servers(args.server)

    if "netcup" in servers:
        log(f"Listing Netcup snapshots for {cfg('NETCUP_SERVER_NAME') or 'server'}...")
        scp = NetcupSCP()
        try:
            scp.login()
            snaps = scp.list_snapshots()
            if snaps:
                print(f"\n{'='*50}")
                print(f"Netcup snapshots — {cfg('NETCUP_SERVER_NAME')} (dev2null.de)")
                print(f"{'='*50}")
                for s in snaps:
                    print(f"  Name:    {s.get('snapshotname', s.get('name', '?'))}")
                    print(f"  Created: {s.get('createdate', '?')}")
                    print(f"  Size:    {s.get('size', '?')} GB")
                    print()
            else:
                print("No Netcup snapshots found.")
        except Exception as e:
            die(str(e))
        finally:
            scp.logout()

    if "ionos" in servers:
        ionos = IonosCloud()
        if ionos._has_cloud_credentials():
            log("Listing IONOS Cloud snapshots...")
            snaps = ionos.list_snapshots()
            if snaps:
                print(f"\n{'='*50}")
                print("IONOS Cloud snapshots (dev2null.website)")
                print(f"{'='*50}")
                for s in snaps:
                    props = s.get("properties", {})
                    print(f"  ID:      {s.get('id', '?')}")
                    print(f"  Name:    {props.get('name', '?')}")
                    print(f"  Created: {props.get('createdDate', '?')}")
                    print()
            else:
                print("No IONOS Cloud snapshots found.")
        else:
            print(IonosCloud.IONOS_LEGACY_INSTRUCTIONS)


def cmd_restore(args) -> None:
    if not args.snapshot:
        die("--snapshot NAME is required for restore")

    if args.server == "netcup":
        print(f"\n⚠️  WARNING: Restoring Netcup snapshot '{args.snapshot}' on {cfg('NETCUP_SERVER_NAME')}")
        print("    The server will be STOPPED and rebooted. ALL data since snapshot will be LOST.")
        confirm = input("    Type 'YES' to confirm: ").strip()
        if confirm != "YES":
            print("Aborted.")
            sys.exit(0)

        log(f"Restoring Netcup snapshot '{args.snapshot}'...")
        tg_notify(f"⚠️ <b>Restoring image snapshot</b> — dev2null.de\n"
                  f"Snapshot: {args.snapshot}\n⚠️ Server will reboot!")
        scp = NetcupSCP()
        try:
            scp.login()
            scp.restore_snapshot(args.snapshot)
            log("✅ Rollback initiated — server is rebooting")
            tg_notify(f"🔄 <b>Snapshot restore initiated</b> — dev2null.de\n"
                      f"Snapshot: {args.snapshot}\nServer is rebooting...")
        except Exception as e:
            tg_notify(f"❌ <b>Snapshot restore FAILED</b> — dev2null.de\n{e}")
            die(str(e))
        finally:
            scp.logout()

    elif args.server == "ionos":
        ionos = IonosCloud()
        if ionos._has_cloud_credentials():
            print(f"\n⚠️  WARNING: Restoring IONOS snapshot '{args.snapshot}'")
            print("    This will OVERWRITE current server state. ALL changes will be LOST.")
            confirm = input("    Type 'YES' to confirm: ").strip()
            if confirm != "YES":
                print("Aborted.")
                sys.exit(0)
            log(f"Restoring IONOS snapshot '{args.snapshot}'...")
            # IONOS Cloud restore: POST /datacenters/{dcId}/volumes/{volId}/restore-snapshot
            ionos._post(
                f"/datacenters/{ionos.datacenter_id}/volumes/{args.snapshot}/restore-snapshot",
                {}
            )
            log("✅ IONOS snapshot restore initiated")
        else:
            print(IonosCloud.IONOS_LEGACY_INSTRUCTIONS)
    else:
        die("--server must be 'netcup' or 'ionos' for restore")


def cmd_delete(args) -> None:
    if not args.snapshot:
        die("--snapshot NAME is required for delete")
    if args.server != "netcup":
        die("delete is only supported for --server netcup (IONOS: manage via my.ionos.com)")

    print(f"⚠️  WARNING: Deleting Netcup snapshot '{args.snapshot}' permanently.")
    confirm = input("    Type 'YES' to confirm: ").strip()
    if confirm != "YES":
        print("Aborted.")
        sys.exit(0)

    scp = NetcupSCP()
    try:
        scp.login()
        scp.delete_snapshot(args.snapshot)
        log(f"✅ Snapshot '{args.snapshot}' deleted")
        tg_notify(f"🗑 <b>Snapshot deleted</b> — dev2null.de\nSnapshot: {args.snapshot}")
    except Exception as e:
        die(str(e))
    finally:
        scp.logout()


def cmd_status(args) -> None:
    print("=== Image Backup Status ===\n")

    # Netcup
    netcup_ok = all(cfg(k) for k in ("NETCUP_CUSTOMER_ID", "NETCUP_API_KEY",
                                      "NETCUP_API_PASS", "NETCUP_SERVER_NAME"))
    print(f"Netcup (dev2null.de):")
    print(f"  Credentials configured: {'✅ yes' if netcup_ok else '❌ no — add NETCUP_* to .env'}")
    if netcup_ok:
        print(f"  Server: {cfg('NETCUP_SERVER_NAME')}")
        print(f"  Run 'python3 image-backup.py list --server netcup' to see snapshots")

    print()

    # IONOS
    ionos_cloud = all(cfg(k) for k in ("IONOS_SERVER_ID", "IONOS_DATACENTER_ID")) and \
                  (cfg("IONOS_API_TOKEN") or (cfg("IONOS_USERNAME") and cfg("IONOS_PASSWORD")))
    print(f"IONOS (dev2null.website):")
    if ionos_cloud:
        print(f"  Credentials configured: ✅ IONOS Cloud API")
        print(f"  Server: {cfg('IONOS_SERVER_ID')}")
    else:
        print(f"  Credentials configured: ⚠️  Legacy VPS — no API")
        print(f"  → Manual snapshots at: https://my.ionos.com")
        print(f"  → Add IONOS_API_TOKEN + IONOS_SERVER_ID + IONOS_DATACENTER_ID")
        print(f"     to .env to enable scripted snapshots (requires IONOS Cloud)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_servers(server_arg: str) -> list:
    if server_arg == "all":
        return ["netcup", "ionos"]
    if server_arg in ("netcup", "ionos"):
        return [server_arg]
    die(f"Unknown --server '{server_arg}'. Use: netcup, ionos, all")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Provider-level image/snapshot backup for Sintaris VPS servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("command", choices=["create", "list", "restore", "delete", "status"],
                        help="Action to perform")
    parser.add_argument("--server", default="all",
                        choices=["netcup", "ionos", "all"],
                        help="Target server (default: all)")
    parser.add_argument("--snapshot", metavar="NAME",
                        help="Snapshot name (required for restore/delete)")
    parser.add_argument("--description", metavar="TEXT",
                        help="Label for new snapshot (default: copilot-YYYY-MM-DD)")
    args = parser.parse_args()

    dispatch = {
        "create":  cmd_create,
        "list":    cmd_list,
        "restore": cmd_restore,
        "delete":  cmd_delete,
        "status":  cmd_status,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
