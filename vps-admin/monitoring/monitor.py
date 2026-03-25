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
import sqlite3
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
    """Returns (issues list, status dict {svc: 'active'|state})."""
    issues = []
    statuses = {}
    for svc in services:
        r = subprocess.run(['systemctl', 'is-active', svc],
                           capture_output=True, text=True)
        state = r.stdout.strip()
        statuses[svc] = state
        if state != 'active':
            issues.append(f"⚠️ Service <b>{svc}</b> → {state}")
    return issues, statuses


def check_docker_containers(required):
    """Returns (issues list, running dict {name: status_str})."""
    issues = []
    running = {}
    try:
        r = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}\t{{.Status}}'],
            capture_output=True, text=True
        )
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
    return issues, running


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
    """Returns (issues list, status dict {name: ok|error})."""
    issues = []
    statuses = {}
    for name, url in endpoints.items():
        try:
            req = urllib.request.Request(
                url, method='GET',
                headers={'User-Agent': 'SintarisMonitor/1.0'}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status >= 500:
                    issues.append(f"🔴 <b>{name}</b> HTTP {resp.status}")
                    statuses[name] = f"HTTP {resp.status}"
                else:
                    statuses[name] = 'ok'
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                issues.append(f"🔴 <b>{name}</b> HTTP {e.code}")
                statuses[name] = f"HTTP {e.code}"
            else:
                # 401/403/302 means service is up but requires auth — OK
                statuses[name] = 'ok'
        except Exception as e:
            issues.append(f"🔴 <b>{name}</b> unreachable: {type(e).__name__}")
            statuses[name] = f"unreachable"
    return issues, statuses


def check_nextcloud_health(url='https://cloud.dev2null.de/status.php', timeout=10):
    """Check Nextcloud: maintenance mode and version."""
    issues = []
    info = {}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SintarisMonitor/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            info['version'] = data.get('version', '?')
            info['maintenance'] = data.get('maintenance', False)
            if data.get('maintenance'):
                issues.append("⚠️ <b>Nextcloud</b> is in MAINTENANCE mode!")
            if not data.get('installed', True):
                issues.append("🔴 <b>Nextcloud</b> not installed!")
    except Exception as e:
        issues.append(f"🔴 <b>Nextcloud</b> health check failed: {type(e).__name__}")
    return issues, info


def check_n8n_health(url='https://automata.dev2null.de/healthz', timeout=10):
    """Check N8N health endpoint."""
    issues = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SintarisMonitor/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            if data.get('status') != 'ok':
                issues.append(f"⚠️ <b>N8N</b> health status: {data.get('status','unknown')}")
    except urllib.error.HTTPError as e:
        if e.code >= 500:
            issues.append(f"🔴 <b>N8N</b> health HTTP {e.code}")
        # 401 etc — service is up
    except Exception as e:
        issues.append(f"🔴 <b>N8N</b> health check failed: {type(e).__name__}")
    return issues


def check_mail_queue():
    """Check Postfix mail queue size. Returns (issues, queue_info str)."""
    issues = []
    queue_info = 'unknown'
    try:
        r = subprocess.run(['postqueue', '-p'], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().splitlines()
        last = lines[-1] if lines else ''
        if 'Mail queue is empty' in last:
            queue_info = 'empty'
        elif 'Requests:' in last or 'request' in last.lower():
            queue_info = last.strip()
            # if large queue, alert
            try:
                count = int(''.join(filter(str.isdigit, last.split('Requests')[0])))
                if count > 50:
                    issues.append(f"⚠️ <b>Mail queue</b>: {count} messages queued!")
            except Exception:
                pass
        else:
            queue_info = last or 'ok'
    except FileNotFoundError:
        queue_info = 'n/a'
    except Exception as e:
        queue_info = f'err: {e}'
    return issues, queue_info


def check_postgres_running():
    """Check if PostgreSQL accepts local connections."""
    issues = []
    try:
        r = subprocess.run(
            ['sudo', '-u', 'postgres', 'psql', '-c', 'SELECT 1', '-t', '-q'],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode != 0:
            issues.append("🔴 <b>PostgreSQL</b> not accepting connections!")
    except Exception as e:
        issues.append(f"⚠️ PostgreSQL check error: {e}")
    return issues


def check_xui_inbounds(db_path='/etc/x-ui/x-ui.db'):
    """Check x-ui Xray inbound tunnels via local SQLite DB.
    Returns (issues, inbounds list, traffic summary str).
    Runs only on dev2null.website where /etc/x-ui/x-ui.db exists."""
    issues = []
    inbounds = []
    traffic_summary = ''
    if not Path(db_path).exists():
        return issues, inbounds, traffic_summary
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            'SELECT id, remark, protocol, port, enable, up, down FROM inbounds ORDER BY id'
        ).fetchall()
        total_up = total_down = 0
        for row in rows:
            iid, remark, proto, port, enabled, up_b, down_b = row
            up_mb   = (up_b or 0) / 1024 / 1024
            down_mb = (down_b or 0) / 1024 / 1024
            total_up   += up_mb
            total_down += down_mb
            inbounds.append({
                'id': iid, 'remark': remark, 'proto': proto,
                'port': port, 'enabled': bool(enabled),
                'up_mb': up_mb, 'down_mb': down_mb,
            })
            if enabled and (up_b or 0) + (down_b or 0) == 0:
                pass  # new/unused inbound, not an issue
        # Check client traffic for expiry issues
        try:
            clients = conn.execute(
                'SELECT email, enable, expiry_time, up, down FROM client_traffics'
            ).fetchall()
            now_ms = int(datetime.datetime.now().timestamp() * 1000)
            for email, enable, expiry, up_b, down_b in clients:
                if expiry and expiry > 0 and expiry < now_ms:
                    issues.append(f"⚠️ <b>x-ui client</b> <code>{email}</code> expired!")
        except Exception:
            pass
        traffic_summary = f"↑{total_up:.0f}MB ↓{total_down:.0f}MB"
        conn.close()
    except Exception as e:
        issues.append(f"⚠️ x-ui DB check error: {e}")
    return issues, inbounds, traffic_summary


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
        # short display labels for daily report
        'services_labels': {
            'nginx': 'nginx', 'postfix': 'postfix', 'dovecot': 'dovecot',
            'mysql': 'mysql', 'postgresql@17-main': 'postgres',
            'docker': 'docker', 'fail2ban': 'fail2ban',
            'coturn': 'coturn', 'opendkim': 'opendkim',
            'php8.3-fpm': 'php-fpm', 'spamd': 'spamd',
        },
        'containers': [
            'nextcloud-docker-app-1', 'n8n-docker-n8n-1', 'n8n-runners',
            'expert-tgrm-bot', 'nextcloud-docker-db-1', 'espocrm',
            'metabase', 'bot_assistance', 'pgadmin-pgadmin-1',
        ],
        'containers_labels': {
            'nextcloud-docker-app-1': 'Nextcloud',
            'n8n-docker-n8n-1': 'N8N',
            'n8n-runners': 'N8N-runners',
            'expert-tgrm-bot': 'expert-bot',
            'nextcloud-docker-db-1': 'NC-DB',
            'espocrm': 'EspoCRM',
            'metabase': 'Metabase',
            'bot_assistance': 'assist-bot',
            'pgadmin-pgadmin-1': 'PGAdmin',
        },
        'endpoints': {
            'Nextcloud':    'https://cloud.dev2null.de/status.php',
            'N8N':          'https://automata.dev2null.de/',
            'CRM (Espo)':   'https://crm.dev2null.de/',
            'Webmail':      'https://webmail.dev2null.de/',
            'Mail (HTTPS)': 'https://mail.dev2null.de/',
        },
        'extra_checks': ['nextcloud', 'n8n', 'mail_queue', 'postgres'],
    },
    'dev2null.website': {
        'services': ['nginx', 'docker', 'x-ui', 'haproxy', 'webinar.bot'],
        'services_labels': {
            'nginx': 'nginx', 'docker': 'docker', 'x-ui': 'x-ui',
            'haproxy': 'haproxy', 'webinar.bot': 'webinar-bot',
        },
        'containers': ['amnezia-wg-easy'],
        'containers_labels': {'amnezia-wg-easy': 'amnezia-wg'},
        'endpoints': {
            'dev2null.website': 'https://dev2null.website/',
        },
        'extra_checks': ['xui'],
    },
}


def get_profile(label):
    for key in PROFILES:
        if key in label:
            return PROFILES[key]
    return {'services': [], 'services_labels': {}, 'containers': [],
            'containers_labels': {}, 'endpoints': {}, 'extra_checks': []}


# ---------------------------------------------------------------------------
# Daily report builder — structured per-service table
# ---------------------------------------------------------------------------

def _svc_line(label, ok, detail=''):
    icon = '✅' if ok else '🔴'
    suffix = f' <i>({detail})</i>' if detail else ''
    return f"{icon} {label}{suffix}"


def build_daily_report(label, now, svc_statuses, svc_labels,
                       container_statuses, container_labels,
                       endpoint_statuses, issues,
                       extra_info=None):
    """Build a structured daily report message (HTML, ≤4000 chars)."""
    lines = [f"📊 <b>Daily Report — {label}</b>", f"🕐 {now}", ""]

    # ── Services ──
    if svc_statuses:
        ok_svcs = [svc_labels.get(s, s) for s, st in svc_statuses.items() if st == 'active']
        bad_svcs = [(svc_labels.get(s, s), st) for s, st in svc_statuses.items() if st != 'active']
        svc_row = '  '.join(f'✅ {s}' for s in ok_svcs)
        if bad_svcs:
            svc_row += '  ' + '  '.join(f'🔴 {s}({st})' for s, st in bad_svcs)
        lines.append(f"<b>Services:</b>\n{svc_row}")
        lines.append("")

    # ── Containers ──
    if container_labels:
        c_parts = []
        for name, label_short in container_labels.items():
            st = container_statuses.get(name, 'NOT running')
            ok = st.startswith('Up')
            c_parts.append(f"{'✅' if ok else '🔴'} {label_short}")
        lines.append(f"<b>Containers:</b>\n{'  '.join(c_parts)}")
        lines.append("")

    # ── Endpoints ──
    if endpoint_statuses:
        ep_parts = [
            f"{'✅' if st == 'ok' else '🔴'} {name}"
            for name, st in endpoint_statuses.items()
        ]
        lines.append(f"<b>Endpoints:</b>\n{'  '.join(ep_parts)}")
        lines.append("")

    # ── Extra info (mail queue, postgres, x-ui inbounds) ──
    if extra_info:
        lines.append("<b>Details:</b>")
        for item in extra_info:
            lines.append(f"  {item}")
        lines.append("")

    # ── Issues summary ──
    if issues:
        lines.append(f"<b>⚠️ Issues ({len(issues)}):</b>")
        for iss in issues:
            lines.append(f"  {iss}")
    else:
        lines.append("✅ <b>Everything OK</b>")

    return "\n".join(lines)


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
    extra_checks = profile.get('extra_checks', [])
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    # --- Run all checks ---
    svc_issues, svc_statuses = check_systemd_services(profile['services'])
    ctr_issues, ctr_running  = check_docker_containers(profile['containers'])
    disk_issues  = check_disk()
    mem_issues   = check_memory()
    load_issues  = load_avg_warning()
    f2b_issues   = check_fail2ban()
    bkp_issues   = check_backup_health()

    http_issues, ep_statuses = [], {}
    if mode != 'quick':
        http_issues, ep_statuses = check_http(profile['endpoints'])

    # --- Extra per-service checks ---
    extra_issues = []
    extra_info   = []

    if 'nextcloud' in extra_checks:
        nc_issues, nc_info = check_nextcloud_health()
        extra_issues += nc_issues
        if nc_info.get('maintenance'):
            extra_info.append(f"🔧 Nextcloud: <b>MAINTENANCE</b> v{nc_info.get('version','?')}")
        elif nc_info.get('version'):
            extra_info.append(f"☁️ Nextcloud v{nc_info['version']}")

    if 'n8n' in extra_checks:
        extra_issues += check_n8n_health()

    if 'mail_queue' in extra_checks:
        mq_issues, mq_info = check_mail_queue()
        extra_issues += mq_issues
        extra_info.append(f"📬 Mail queue: {mq_info}")

    if 'postgres' in extra_checks:
        extra_issues += check_postgres_running()

    if 'xui' in extra_checks:
        xui_issues, inbounds, traffic = check_xui_inbounds()
        extra_issues += xui_issues
        if inbounds:
            active = [ib for ib in inbounds if ib['enabled']]
            disabled = [ib for ib in inbounds if not ib['enabled']]
            ib_lines = []
            for ib in active:
                ib_lines.append(
                    f"  ✅ {ib['remark']} ({ib['proto']}:{ib['port']}) "
                    f"↑{ib['up_mb']:.0f}MB ↓{ib['down_mb']:.0f}MB"
                )
            for ib in disabled:
                ib_lines.append(f"  ⬜ {ib['remark']} ({ib['port']}) — disabled")
            extra_info.append(
                f"🔒 <b>Xray Inbounds</b> ({len(active)} active / {len(disabled)} disabled):"
            )
            extra_info += ib_lines
            if traffic:
                extra_info.append(f"  📊 Total traffic: {traffic}")

    # Disk info for extra_info
    r = subprocess.run(['df', '-h', '--output=target,pcent,avail'], capture_output=True, text=True)
    for line in r.stdout.strip().splitlines()[1:]:
        parts = line.split()
        if len(parts) == 3 and parts[0] == '/':
            extra_info.append(f"💾 Disk {parts[0]}: {parts[1]} used, {parts[2]} free")

    # Memory info
    r = subprocess.run(['free', '-m'], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith('Mem:'):
            p = line.split()
            total, used = int(p[1]), int(p[2])
            pct = used * 100 // total
            extra_info.append(f"🧠 RAM: {used}MB / {total}MB ({pct}%)")

    all_issues = (svc_issues + ctr_issues + disk_issues + mem_issues +
                  load_issues + f2b_issues + bkp_issues + http_issues + extra_issues)

    # --- Send messages ---
    if mode == 'daily':
        msg = build_daily_report(
            label=label,
            now=now,
            svc_statuses=svc_statuses,
            svc_labels=profile.get('services_labels', {}),
            container_statuses=ctr_running,
            container_labels=profile.get('containers_labels', {}),
            endpoint_statuses=ep_statuses,
            issues=all_issues,
            extra_info=extra_info,
        )
        send_telegram(bot_token, chat_id, msg)

    elif all_issues:
        msg = (
            f"🚨 <b>Alert — {label}</b>\n"
            f"🕐 {now}\n\n"
            + "\n".join(all_issues)
        )
        send_telegram(bot_token, chat_id, msg)
        sys.exit(1)


if __name__ == '__main__':
    main()
