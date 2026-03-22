# N8N Backup & Restore

Complete backup solution for N8N workflows, databases, and Docker configurations.

## Features

- **Database Backups**
  - PostgreSQL `n8n_apps` database (application data)
  - N8N internal database (workflow execution data, credentials)
  - Both binary (.dump) and SQL (.sql.gz) formats

- **Workflow Backups**
  - All workflows exported via N8N API
  - Individual JSON files per workflow
  - Complete workflow list in single file

- **Credentials Backup**
  - Encrypted credentials via N8N API

- **Docker Configuration**
  - docker-compose.yml
  - Docker environment variables
  - Container configuration
  - Volume and network information

- **N8N Data Directory**
  - Complete `.n8n` directory backup
  - Settings, cache, and runtime data

## Prerequisites

- Python 3.7+ (for Python version)
- Bash (for shell script version)
- SSH access to remote server
- N8N API key configured
- Required Python packages: `requests`, `python-dotenv`

## Installation

1. Clone or copy the backup scripts to your local machine

2. Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

3. Install Python dependencies:
```bash
pip install requests python-dotenv
```

4. Make scripts executable (Linux/Mac):
```bash
chmod +x backup.sh restore.sh
```

## Configuration

Edit `.env` file with your credentials:

```env
# SSH Configuration
SSH_HOST=your-server.com
SSH_USER=your-user
SSH_PORT=22
SSH_KEY_PATH=~/.ssh/id_ed25519

# PostgreSQL Database
PGHOST=localhost
PGPORT=5432
PGUSER=n8n_user
PGPASSWORD=your-password
PGDATABASE=n8n_apps

# N8N Configuration
N8N_HOST=https://your-n8n-instance.com
N8N_API_KEY=your-api-key
N8N_API_BASE=https://your-n8n-instance.com/api

# Docker Configuration
DOCKER_N8N_CONTAINER=n8n_docker
DOCKER_REQUIRES_SUDO=true
N8N_DOCKER_DIR=/opt/n8n_docker

# Backup Configuration
BACKUP_PATH=./backups
BACKUP_RETENTION_DAYS=30
```

## Usage

### Running Backups

**Method 1: Remote Backup & Download (Recommended for Windows)**

Creates backups on the remote host, then downloads them locally:

```bash
# Python version (recommended)
python backup_remote.py

# Bash version (alternative)
./backup_remote.sh
```

This method:
- Creates backups directly on the remote host
- Downloads completed backups to local machine
- Optionally cleans up remote files after download
- Works better on Windows (no local Docker/PostgreSQL needed)

**Method 2: Direct Backup (Requires local tools)**

Streams backup data directly from remote to local:

```bash
# Python version
python backup.py

# Bash version
./backup.sh
```

This method requires:
- `pg_dump` and `pg_restore` installed locally
- `jq` for JSON processing
- Better for Linux/Mac environments

The backup will create a timestamped directory in `backups/`:
```
backups/
  ├── 20260107_143000/
  │   ├── database/
  │   │   ├── n8n_apps_20260107_143000.dump
  │   │   ├── n8n_apps_20260107_143000.sql.gz
  │   │   ├── n8n_internal_20260107_143000.dump
  │   │   └── n8n_internal_20260107_143000.sql.gz
  │   ├── workflows/
  │   │   ├── all_workflows.json
  │   │   ├── <workflow_id>_<workflow_name>.json
  │   │   └── ...
  │   ├── docker/
  │   │   ├── docker-compose.yml
  │   │   ├── docker.env
  │   │   ├── container_inspect.json
  │   │   ├── volumes.txt
  │   │   └── network_inspect.json
  │   ├── n8n_data/
  │   │   ├── credentials.json
  │   │   └── n8n_data_20260107_143000.tar.gz
  │   └── MANIFEST.txt
  └── latest -> 20260107_143000/
```

### Restoring Backups

**Important:** Restore will overwrite existing data!

```bash
./restore.sh backups/20260107_143000
```

Or restore the latest backup:
```bash
./restore.sh backups/latest
```

The restore process will:
1. Stop the N8N container
2. Restore databases
3. Restore Docker configuration
4. Restore N8N data directory
5. Restart the container

### Automated Backups

**Linux/Mac (cron):**
```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /path/to/backup && /usr/bin/python3 backup.py >> backup.log 2>&1
```

**Windows (Task Scheduler):**
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., daily at 2 AM)
4. Action: Start a program
5. Program: `python`
6. Arguments: `backup.py`
7. Start in: `D:\Projects\workspace\hp\n8n\backup`

## Backup Management

### List Available Backups
```bash
ls -lh backups/
```

### Check Backup Size
```bash
du -sh backups/20260107_143000
```

### Manual Cleanup
```bash
# Remove specific backup
rm -rf backups/20260107_143000

# Remove backups older than 30 days
find backups/ -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;
```

### Automatic Cleanup

Set `BACKUP_RETENTION_DAYS` in `.env` to automatically remove old backups:
```env
BACKUP_RETENTION_DAYS=30
```

## Backup Verification

After backup, verify:

1. **Check backup size:**
```bash
du -sh backups/latest
```

2. **Verify database dumps:**
```bash
file backups/latest/database/*.dump
```

3. **Count workflows:**
```bash
ls -1 backups/latest/workflows/*.json | wc -l
```

4. **Check manifest:**
```bash
cat backups/latest/MANIFEST.txt
```

## Troubleshooting

### SSH Connection Issues
```bash
# Test SSH connection
ssh -i ~/.ssh/id_ed25519 -p 22 user@host "echo OK"

# Test with verbose output
ssh -v -i ~/.ssh/id_ed25519 -p 22 user@host
```

### Database Connection Issues
```bash
# Test database connection via SSH
ssh user@host "PGPASSWORD='password' psql -h localhost -U user -d database -c 'SELECT 1'"
```

### API Connection Issues
```bash
# Test N8N API
curl -X GET "https://your-n8n.com/api/v1/workflows" \
  -H "X-N8N-API-KEY: your-api-key"
```

### Docker Permission Issues
If you get permission errors, ensure `DOCKER_REQUIRES_SUDO=true` in `.env`

### Large Backup Files
For large databases, consider:
- Increasing network timeout
- Using compression
- Backing up during off-peak hours

## Security Notes

1. **Never commit `.env` to git** - it contains sensitive credentials
2. **Protect backup files** - they contain credentials and sensitive data
3. **Use SSH key authentication** - more secure than passwords
4. **Encrypt backups** if storing on external storage
5. **Regular security audits** of access logs

## File Descriptions

- `backup_remote.py` - Remote backup & download script (Python, **recommended for Windows**)
- `backup_remote.sh` - Remote backup & download script (Bash, alternative)
- `backup.py` - Direct streaming backup script (Python, requires local tools)
- `backup.sh` - Direct streaming backup script (Bash, requires local tools)
- `restore.sh` - Restore script
- `.env` - Configuration file (create from template)
- `.gitignore` - Prevents committing sensitive files
- `requirements.txt` - Python dependencies
- `README.md` - This file

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review the MANIFEST.txt in your backup
3. Check SSH/Docker/Database logs on remote server

## License

This backup solution is provided as-is for personal use.
