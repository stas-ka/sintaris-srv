# 01 — GitHub CLI Setup

## Prerequisites

```bash
sudo apt install gh git
```

## Authentication

```bash
gh auth login
# Choose: GitHub.com → SSH → Generate new SSH key → authenticate via browser
```

Verify:
```bash
gh auth status
# Should show: ✓ Logged in to github.com account stas-ka
```

## SSH Key

The GitHub CLI creates and registers an SSH key automatically during `gh auth login`.
The active key is `~/.ssh/id_ed25519`.

For VPS access, copy the public key:
```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub stas@dev2null.de
```

## Git Global Config

```bash
git config --global user.name "Stas"
git config --global user.email "your@email.com"
git config --global init.defaultBranch main
```

## sintaris-srv Repository

The main admin workspace lives at `~/projects/sintaris-srv`:

```bash
mkdir -p ~/projects
cd ~/projects
gh repo clone stas-ka/sintaris-srv
```

### Structure

```
sintaris-srv/
  .env              # VPS credentials — NEVER commit (gitignored)
  .env.example      # Template for .env
  .gitignore
  README.md
  docs/             # This installation guide
  local-dev/        # Local Docker dev stack
  vps-admin/        # Copilot instructions for VPS management
  n8n/              # N8N workflow exports & notes
  wb/, web/, WEB_Downloader/   # Other subprojects
```

### .env file

Create `~/projects/sintaris-srv/.env` (not committed):
```bash
VPS_HOST=dev2null.de
VPS_USER=stas
VPS_SSH_PORT=22
VPS_PASS=<vps_sudo_password>
PFA_DB_PASS=<postfixadmin_db_password>
PFA_SETUP_PASS=<postfixadmin_setup_password>
```

## Useful gh Commands

```bash
gh repo list                  # list all repos
gh repo create <name>         # create new repo
gh pr list                    # list pull requests
gh issue list                 # list issues
```
