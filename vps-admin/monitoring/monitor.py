#!/usr/bin/env python3
"""
Sintaris VPS Monitor
Checks system health and sends Telegram alerts.

Deploy to: /opt/sintaris-monitor/monitor.py
Config:    /opt/sintaris-monitor/.env  (BOT_TOKEN, CHAT_ID, HOSTNAME_LABEL)

Usage:
  python3 monitor.py          # health check, alert only if issues
  python3 monitor.py daily    # daily summary (always sends)
  python3 monitor.py test     # send test message and exit
"""

import os
import sys
import json
import subprocess
import urllib.request
import urllib.error
import datetime
import socket
from pathlib import Path


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_env():
    env_file = Path(__file__).parent / '.env'
    config = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                config[k.strip()] = v.strip().strip('"').strip("'")
    for key in ['BOT_TOKEN', 'CHAT_ID', 'HOSTNAME_LABEL']:
        if key in os.environ:
            config[key] = os.environ[key]
    return config


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    }).encode()
    req = urllib.request.Request(
        url, data=data, headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_systemd_services(services):
    issues = []
    for svc in services:
        r = subprocess.run(['systemctl', 'is-active', svc],
                           capture_output=True, text=True)
        state = r.stdout.strip()
        if state != 'active':
            issues.append(f"⚠️ Service <b>{svc}</b> → {state}")
    return issues


def check_docker_containers(required):
    issues = []
    try:
        r = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}\t{{.Status}}'],
            capture_output=True, text=True
        )
        running = {}
        for line in r.stdout.strip().splitlines():
            parts = line.split('\t', 1)
            if len(parts) == 2:
                running[parts[0]] = parts[1]
        for name in required:
            if name not in running:
                issues.append(f"🔴 Container <b>{name}</b> NOT running")
            elif not running[name].startswith('Up'):
                issues.append(f"⚠️ Container <b>{name}</b>: {running[name]}")
    except FileNotFoundError:
        issues.append("⚠️ docker not found — is Docker installed?")
    except Exception as e:
        issues.append(f"⚠️ Docker check error: {e}")
    return issues


def check_disk(warn=80, crit=90):
    issues = []
    r = subprocess.run(['df', '-h', '--output=target,pcent'],
                       capture_output=True, text=True)
    for line in r.stdout.strip().splitlines()[1:]:
        parts = line.split()
        if len(parts) == 2:
            try:
                pct = int(parts[1].rstrip('%'))
                if pct >= crit:
                    issues.append(f"🔴 Disk <b>{parts[0]}</b> {pct}% full!")
                elif pct >= warn:
                    issues.append(f"⚠️ Disk <b>{parts[0]}</b> {pct}% full")
            except ValueError:
                pass
    return issues


def check_memory(warn=80, crit=90):
    issues = []
    try:
        r = subprocess.run(['free', '-m'], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if line.startswith('Mem:'):
                parts = line.split()
                total, used = int(parts[1]), int(parts[2])
                pct = (used / total) * 100
                if pct >= crit:
                    issues.append(f"🔴 RAM {pct:.0f}% ({used}MB/{total}MB)")
                elif pct >= warn:
                    issues.append(f"⚠️ RAM {pct:.0f}% ({used}MB/{total}MB)")
    except Exception as e:
        issues.append(f"⚠️ Memory check error: {e}")
    return issues


def check_http(endpoints, timeout=10):
    issues = []
    for name, url in endpoints.items():
        try:
            req = urllib.request.Request(
                url, method='GET',
                headers={'User-Agent': 'SintarisMonitor/1.0'}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status >= 500:
                    issues.append(f"🔴 <b>{name}</b> HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                issues.append(f"🔴 <b>{name}</b> HTTP {e.code}")
            # 401/403/302 means service is up but requires auth — OK
        except Exception as e:
            issues.append(f"🔴 <b>{name}</b> unreachable: {type(e).__name__}")
    return issues


def check_fail2ban(state_file='/tmp/sintaris-monitor-f2b.txt'):
    issues = []
    try:
        r = subprocess.run(['fail2ban-client', 'status'],
                           capture_output=True, text=True, timeout=5)
        if 'Jail list:' not in r.stdout:
            return issues
        jail_line = next(
            (l for l in r.stdout.splitlines() if 'Jail list:' in l), None
        )
        if not jail_line:
            return issues
        jails = [j.strip() for j in jail_line.split(':', 1)[1].split(',') if j.strip()]
        total_bans = 0
        for jail in jails:
            rj = subprocess.run(['fail2ban-client', 'status', jail],
                                capture_output=True, text=True, timeout=5)
            for line in rj.stdout.splitlines():
                if 'Total banned' in line:
                    try:
                        total_bans += int(line.split(':', 1)[1].strip())
                    except ValueError:
                        pass
        prev = 0
        try:
            prev = int(Path(state_file).read_text().strip())
        except Exception:
            pass
        Path(state_file).write_text(str(total_bans))
        new_bans = total_bans - prev
        if new_bans >= 10:
            issues.append(
                f"🛡️ Fail2ban: <b>{new_bans} new bans</b> (total {total_bans}) — possible attack!"
            )
    except FileNotFoundError:
        pass  # fail2ban not installed
    except Exception as e:
        issues.append(f"⚠️ Fail2ban check error: {e}")
    return issues


def load_avg_warning(crit=4.0):
    issues = []
    try:
        avg = os.getloadavg()
        if avg[0] >= crit:
            issues.append(f"🔴 Load average high: {avg[0]:.2f} / {avg[1]:.2f} / {avg[2]:.2f}")
        elif avg[0] >= crit * 0.7:
            issues.append(f"⚠️ Load average elevated: {avg[0]:.2f} / {avg[1]:.2f} / {avg[2]:.2f}")
    except Exception:
        pass
    return issues


def check_backup_health(warn_days=2, state_file='/opt/sintaris-backup/.last_backup'):
    """Alert if last successful backup is older than warn_days days."""
    issues = []
    try:
        p = Path(state_file)
        if not p.exists():
            issues.append("⚠️ Backup: no backup record found — has backup.sh ever run?")
            return issues
        ts_str = p.read_text().strip()
        last_backup = datetime.datetime.fromisoformat(ts_str)
        age_days = (datetime.datetime.now() - last_backup).days
        if age_days >= warn_days:
            issues.append(
                f"⚠️ Backup: last backup <b>{age_days} day(s) ago</b> ({ts_str}) — check sintaris-backup.timer"
            )
    except Exception as e:
        issues.append(f"⚠️ Backup health check error: {e}")
    return issues


# ---------------------------------------------------------------------------
# Server-specific config
# ---------------------------------------------------------------------------

PROFILES = {
    'dev2null.de': {
        'services': [
            'nginx', 'postfix', 'dovecot', 'mysql',
            'postgresql@17-main', 'docker', 'fail2ban',
            'coturn', 'opendkim', 'php8.3-fpm', 'spamd',
        ],
        'containers': [
            'nextcloud-docker-app-1', 'n8n-docker-n8n-1', 'n8n-runners',
            'expert-tgrm-bot', 'nextcloud-docker-db-1', 'espocrm',
            'metabase', 'bot_assistance', 'pgadmin-pgadmin-1',
        ],
        'endpoints': {
            'Nextcloud':    'https://cloud.dev2null.de/status.php',
            'N8N':          'https://automata.dev2null.de/',
            'CRM (Espo)':   'https://crm.dev2null.de/',
            'Webmail':      'https://webmail.dev2null.de/',
            'Mail (HTTPS)': 'https://mail.dev2null.de/',
        },
    },
    'dev2null.website': {
        'services': ['nginx', 'docker', 'x-ui', 'haproxy', 'webinar.bot'],
        'containers': ['amnezia-wg-easy'],
        'endpoints': {
            'dev2null.website': 'https://dev2null.website/',
        },
    },
}


def get_profile(label):
    for key in PROFILES:
        if key in label:
            return PROFILES[key]
    # fallback: minimal checks
    return {'services': [], 'containers': [], 'endpoints': {}}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    config = load_env()
    bot_token = config.get('BOT_TOKEN', '')
    chat_id = config.get('CHAT_ID', '')
    label = config.get('HOSTNAME_LABEL', socket.gethostname())
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'

    if not bot_token or not chat_id:
        print("ERROR: BOT_TOKEN and CHAT_ID must be set in .env", file=sys.stderr)
        sys.exit(1)

    if mode == 'test':
        ok = send_telegram(bot_token, chat_id,
                           f"✅ <b>Sintaris Monitor</b> — test OK\nHost: <b>{label}</b>")
        print("Test message sent:", ok)
        return

    profile = get_profile(label)
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    issues = []
    issues += check_systemd_services(profile['services'])
    issues += check_docker_containers(profile['containers'])
    issues += check_disk()
    issues += check_memory()
    issues += load_avg_warning()
    issues += check_fail2ban()
    issues += check_backup_health()

    if mode != 'quick':
        issues += check_http(profile['endpoints'])

    if mode == 'daily':
        status = "✅ Everything OK" if not issues else f"⚠️ {len(issues)} issue(s) found"
        msg = (
            f"📊 <b>Daily Report — {label}</b>\n"
            f"🕐 {now}\n\n"
            f"{status}"
        )
        if issues:
            msg += "\n\n" + "\n".join(issues)
        send_telegram(bot_token, chat_id, msg)

    elif issues:
        msg = (
            f"🚨 <b>Alert — {label}</b>\n"
            f"🕐 {now}\n\n"
            + "\n".join(issues)
        )
        send_telegram(bot_token, chat_id, msg)
        sys.exit(1)


if __name__ == '__main__':
    main()
