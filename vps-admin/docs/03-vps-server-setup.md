# 03 — VPS Server Setup

**Server:** dev2null.de (152.53.224.213)  
**OS:** Ubuntu 24.04, aarch64  
**Hostname:** mail.dev2null.de

## Access

```bash
cd ~/projects/sintaris-srv
source .env
ssh ${VPS_USER}@${VPS_HOST}
```

SSH key (`~/.ssh/id_ed25519`) is set up for passwordless login.  
`sudo` requires the password stored in `.env` as `VPS_PASS`.

## Domains

| Domain | DNS Provider | Purpose |
|--------|-------------|---------|
| dev2null.de | netcup | Primary server domain |
| sintaris.net | neoserv.si | Aliases → dev2null.de |
| sintaris.eu | neoserv.si | Aliases → dev2null.de |
| sintaru.com | neoserv.si | Separate mailboxes |

---

## nginx

Reverse proxy for all services. Configs in `/etc/nginx/sites-enabled/`.

```bash
sudo nginx -t                  # test config
sudo systemctl reload nginx    # apply changes
ls /etc/nginx/sites-enabled/   # list active sites
```

Active site configs: `crm.conf`, `crm.sintaris.net`, `mail.dev2null.de`,
`webmail.*`, `automata.dev2null.de`, `cloud.dev2null.de`, `wp.sintaris.*`, etc.

### SSL Certificates

Managed by Certbot / Let's Encrypt. Stored in `/etc/letsencrypt/`.

```bash
sudo certbot --nginx -d example.com          # issue new cert
sudo certbot renew --dry-run                 # test renewal
sudo certbot certificates                    # list all certs
```

---

## Mail Server

### Architecture

```
Postfix (MTA) + Dovecot (IMAP/POP3) + Roundcube (webmail) + PostfixAdmin (admin UI)
```

Mail is stored as Maildir in `/var/mail/vhosts/<domain>/<user>/`.

All domains and mailboxes are managed via PostfixAdmin — **do not edit `/etc/postfix/virtual` manually**.

### Domain → Mailbox Mapping

| Domain | Mailbox | Notes |
|--------|---------|-------|
| dev2null.de | info@, admin@ | Real mailboxes (Maildir) |
| sintaris.net | info@, admin@ | Aliases → dev2null.de |
| sintaris.eu | info@, admin@ | Aliases → dev2null.de |
| sintaru.com | info@, admin@ | Separate real mailboxes |

### PostfixAdmin

Web UI: **https://mail.dev2null.de/admin/**  
Superadmin: `admin@dev2null.de`

Use PostfixAdmin to:
- Add/remove mailboxes and aliases
- Add new domains
- Change passwords

### Postfix Key Settings (`/etc/postfix/main.cf`)

```
virtual_mailbox_domains = pgsql:/etc/postfix/pgsql-virtual-domains.cf
virtual_mailbox_maps    = pgsql:/etc/postfix/pgsql-virtual-mailboxes.cf
virtual_alias_maps      = pgsql:/etc/postfix/pgsql-virtual-aliases.cf
virtual_mailbox_base    = /var/mail/vhosts
virtual_uid_maps        = static:5000   # vmail user
virtual_gid_maps        = static:5000
mynetworks              = 127.0.0.0/8 ... 172.17.0.0/16 172.18.0.0/16 172.25.0.0/16
smtpd_milters           = unix:/opendkim/opendkim.sock  # chroot-relative path
```

### Webmail URLs

| URL | Domain |
|-----|--------|
| https://webmail.dev2null.de | dev2null.de |
| https://webmail.sintaris.net | sintaris.net |
| https://webmail.sintaris.eu | sintaris.eu |
| https://webmail.sintaru.com | sintaru.com |
| https://mail.dev2null.de | Roundcube (original) |

### PostfixAdmin Setup (initial, one-time)

```bash
# PostgreSQL DB was created as:
sudo -u postgres createdb postfixadmin
sudo -u postgres createuser postfixadmin
# Config: /var/www/postfixadmin/config.local.php
# DB password stored in .env as PFA_DB_PASS
```

### Dovecot

Auth: PostgreSQL via `/etc/dovecot/dovecot-sql.conf.ext`  
Mail location: `maildir:/var/mail/vhosts/%d/%n`

```bash
sudo doveadm auth test user@domain.com password   # test login
sudo doveadm user user@domain.com                 # user info
sudo systemctl restart dovecot
```

---

## PostgreSQL (host install)

```bash
sudo -u postgres psql
\l                          # list databases
\c postfixadmin             # connect to DB
```

Key databases:
- `postfixadmin` — PostfixAdmin mail management
- `n8n` — N8N workflow metadata
- `n8n_apps` — N8N application data (with pgvector)

---

## OpenDKIM

DKIM signing for outgoing mail.

```bash
sudo systemctl status opendkim
# Socket (chroot-relative): unix:/opendkim/opendkim.sock
# Full path: /var/spool/postfix/opendkim/opendkim.sock
# Config: /etc/opendkim.conf
```

Permissions fix (if socket errors appear):
```bash
sudo usermod -aG opendkim postfix
sudo systemctl restart opendkim postfix
```

---

## Service Quick Reference

```bash
sudo systemctl status nginx postfix dovecot opendkim
sudo systemctl reload nginx
sudo systemctl reload postfix
sudo systemctl restart dovecot

# Logs
sudo tail -f /var/log/mail.log
sudo journalctl -u nginx -n 50 --no-pager
```
