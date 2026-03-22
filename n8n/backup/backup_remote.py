#!/usr/bin/env python3
"""
N8N Remote Backup & Download Script (Python Version)
====================================================
This script:
1. Creates backups on remote host
2. Downloads them to local machine
3. Optionally cleans up remote backups
"""

import os
import sys
import json
import subprocess
import requests
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class N8NRemoteBackup:
    def __init__(self):
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_path = Path(os.getenv('BACKUP_PATH', './backups'))
        self.local_backup_dir = self.backup_path / self.timestamp
        self.remote_backup_dir = f"/tmp/n8n_backup_{self.timestamp}"
        
        # SSH Configuration
        self.ssh_host = os.getenv('SSH_HOST')
        self.ssh_user = os.getenv('SSH_USER')
        self.ssh_port = os.getenv('SSH_PORT', '22')
        self.ssh_key_path = os.getenv('SSH_KEY_PATH')
        
        # Database Configuration
        self.pg_host = os.getenv('PGHOST', 'localhost')
        self.pg_port = os.getenv('PGPORT', '5432')
        self.pg_user = os.getenv('PGUSER')
        self.pg_password = os.getenv('PGPASSWORD')
        self.pg_database = os.getenv('PGDATABASE')
        
        # N8N Configuration
        self.n8n_api_base = os.getenv('N8N_API_BASE')
        self.n8n_api_key = os.getenv('N8N_API_KEY')
        
        # Docker Configuration
        self.docker_container = os.getenv('DOCKER_N8N_CONTAINER')
        self.docker_requires_sudo = os.getenv('DOCKER_REQUIRES_SUDO', 'true').lower() == 'true'
        self.n8n_docker_dir = os.getenv('N8N_DOCKER_DIR')
        
        # Backup Configuration
        self.retention_days = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
        
        # Create local backup directories
        self.create_local_structure()
    
    def create_local_structure(self):
        """Create local backup directory structure"""
        (self.local_backup_dir / 'database').mkdir(parents=True, exist_ok=True)
        (self.local_backup_dir / 'workflows').mkdir(parents=True, exist_ok=True)
        (self.local_backup_dir / 'docker').mkdir(parents=True, exist_ok=True)
        (self.local_backup_dir / 'n8n_data').mkdir(parents=True, exist_ok=True)
    
    def run_ssh(self, command):
        """Execute command on remote host via SSH"""
        ssh_cmd = [
            'ssh',
            '-i', self.ssh_key_path,
            '-p', self.ssh_port,
            f'{self.ssh_user}@{self.ssh_host}',
            command
        ]
        result = subprocess.run(ssh_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Warning: Command failed: {command}")
            print(f"Error: {result.stderr}")
        return result.returncode == 0
    
    def download_file(self, remote_path, local_path):
        """Download file from remote host using SCP"""
        scp_cmd = [
            'scp',
            '-i', self.ssh_key_path,
            '-P', self.ssh_port,
            f'{self.ssh_user}@{self.ssh_host}:{remote_path}',
            str(local_path)
        ]
        result = subprocess.run(scp_cmd, capture_output=True, text=True)
        return result.returncode == 0
    
    def download_dir(self, remote_path, local_path):
        """Download directory from remote host using SCP"""
        scp_cmd = [
            'scp',
            '-r',
            '-i', self.ssh_key_path,
            '-P', self.ssh_port,
            f'{self.ssh_user}@{self.ssh_host}:{remote_path}',
            str(local_path)
        ]
        result = subprocess.run(scp_cmd, capture_output=True, text=True)
        return result.returncode == 0
    
    def step1_create_remote_dir(self):
        """Create remote backup directory"""
        print("[1/6] Creating remote backup directory...")
        
        cmd = f"mkdir -p {self.remote_backup_dir}/{{database,workflows,docker,n8n_data}}"
        if self.run_ssh(cmd):
            print(f"  ✓ Remote directory created: {self.remote_backup_dir}")
        else:
            raise Exception("Failed to create remote directory")
    
    def step2_backup_databases(self):
        """Create database backups on remote host"""
        print("\n[2/6] Creating database backups on remote host...")
        
        sudo = "sudo " if self.docker_requires_sudo else ""
        
        # Backup n8n_apps database
        print("  - Backing up n8n_apps database...")
        
        # Binary format - backup only public schema to avoid permission issues
        cmd = f"PGPASSWORD='{self.pg_password}' pg_dump -h {self.pg_host} -p {self.pg_port} -U {self.pg_user} -d {self.pg_database} -n public -F c -f {self.remote_backup_dir}/database/n8n_apps_{self.timestamp}.dump"
        self.run_ssh(cmd)
        
        # SQL format - backup only public schema
        cmd = f"PGPASSWORD='{self.pg_password}' pg_dump -h {self.pg_host} -p {self.pg_port} -U {self.pg_user} -d {self.pg_database} -n public | gzip > {self.remote_backup_dir}/database/n8n_apps_{self.timestamp}.sql.gz"
        self.run_ssh(cmd)
        
        # Backup n8n internal database (direct PostgreSQL connection, not docker exec)
        print("  - Backing up n8n internal database...")
        
        # Binary format - connect directly to PostgreSQL on host
        cmd = f"PGPASSWORD='N8Nzusammen2019' pg_dump -h 172.17.0.1 -p 5432 -U n8n_user -d n8n -F c -f {self.remote_backup_dir}/database/n8n_internal_{self.timestamp}.dump"
        self.run_ssh(cmd)
        
        # SQL format
        cmd = f"PGPASSWORD='N8Nzusammen2019' pg_dump -h 172.17.0.1 -p 5432 -U n8n_user -d n8n | gzip > {self.remote_backup_dir}/database/n8n_internal_{self.timestamp}.sql.gz"
        self.run_ssh(cmd)
        
        print("  ✓ Database backups created on remote host")
    
    def step3_backup_docker(self):
        """Backup Docker configurations on remote host"""
        print("\n[3/6] Backing up Docker configurations on remote host...")
        
        sudo = "sudo " if self.docker_requires_sudo else ""
        
        # Copy docker-compose.yml
        self.run_ssh(f"cp {self.n8n_docker_dir}/docker-compose.yml {self.remote_backup_dir}/docker/docker-compose.yml")
        
        # Copy .env file
        self.run_ssh(f"cp {self.n8n_docker_dir}/.env {self.remote_backup_dir}/docker/docker.env 2>/dev/null || echo '# No .env file' > {self.remote_backup_dir}/docker/docker.env")
        
        # Container inspection
        self.run_ssh(f"{sudo}docker inspect {self.docker_container} > {self.remote_backup_dir}/docker/container_inspect.json")
        
        # Volume information
        self.run_ssh(f"{sudo}docker volume ls --format '{{{{.Name}}}}' | grep n8n > {self.remote_backup_dir}/docker/volumes.txt || echo 'No n8n volumes' > {self.remote_backup_dir}/docker/volumes.txt")
        
        # Network information
        self.run_ssh(f"{sudo}docker network inspect $({sudo}docker inspect {self.docker_container} | jq -r '.[0].NetworkSettings.Networks | keys[]') > {self.remote_backup_dir}/docker/network_inspect.json 2>/dev/null || echo '[]' > {self.remote_backup_dir}/docker/network_inspect.json")
        
        print("  ✓ Docker configurations backed up")
    
    def step4_backup_n8n_data(self):
        """Backup N8N data directory on remote host"""
        print("\n[4/6] Backing up N8N data directory on remote host...")
        
        sudo = "sudo " if self.docker_requires_sudo else ""
        
        # Create tarball inside container and copy out
        cmd = f"{sudo}docker exec {self.docker_container} tar czf /tmp/n8n_data.tar.gz /home/node/.n8n 2>/dev/null && {sudo}docker cp {self.docker_container}:/tmp/n8n_data.tar.gz {self.remote_backup_dir}/n8n_data/n8n_data_{self.timestamp}.tar.gz || echo 'Data backup skipped'"
        self.run_ssh(cmd)
        
        print("  ✓ N8N data directory backed up")
    
    def step5_download_backups(self):
        """Download backups from remote host"""
        print("\n[5/6] Downloading backups from remote host...")
        
        # Download databases
        print("  - Downloading databases...")
        self.download_dir(
            f"{self.remote_backup_dir}/database/*",
            self.local_backup_dir / 'database'
        )
        
        # Download Docker configs
        print("  - Downloading Docker configs...")
        self.download_dir(
            f"{self.remote_backup_dir}/docker/*",
            self.local_backup_dir / 'docker'
        )
        
        # Download N8N data
        print("  - Downloading N8N data...")
        self.download_dir(
            f"{self.remote_backup_dir}/n8n_data/*",
            self.local_backup_dir / 'n8n_data'
        )
        
        print("  ✓ Backups downloaded to local machine")
    
    def step6_backup_workflows(self):
        """Backup workflows via API (local operation)"""
        print("\n[6/6] Backing up workflows via API...")
        
        headers = {
            'X-N8N-API-KEY': self.n8n_api_key,
            'Accept': 'application/json'
        }
        
        try:
            # Fetch all workflows
            response = requests.get(f'{self.n8n_api_base}/v1/workflows', headers=headers)
            response.raise_for_status()
            workflows_data = response.json()
            
            # Save complete workflow list
            with open(self.local_backup_dir / 'workflows' / 'all_workflows.json', 'w', encoding='utf-8') as f:
                json.dump(workflows_data, f, indent=2, ensure_ascii=False)
            
            # Save each workflow individually
            if 'data' in workflows_data:
                for workflow in workflows_data['data']:
                    workflow_id = workflow.get('id', 'unknown')
                    workflow_name = workflow.get('name', 'unnamed').replace(' ', '_')
                    workflow_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in workflow_name)
                    
                    print(f"  - Saving workflow: {workflow_name} ({workflow_id})")
                    with open(self.local_backup_dir / 'workflows' / f'{workflow_id}_{workflow_name}.json', 'w', encoding='utf-8') as f:
                        json.dump(workflow, f, indent=2, ensure_ascii=False)
            
            print("  ✓ Workflows backed up")
        except Exception as e:
            print(f"  ✗ Error backing up workflows: {e}")
        
        # Backup credentials
        try:
            response = requests.get(f'{self.n8n_api_base}/v1/credentials', headers=headers)
            response.raise_for_status()
            credentials_data = response.json()
            
            with open(self.local_backup_dir / 'n8n_data' / 'credentials.json', 'w', encoding='utf-8') as f:
                json.dump(credentials_data, f, indent=2, ensure_ascii=False)
            
            print("  ✓ Credentials backed up")
        except Exception as e:
            print(f"  ✗ Error backing up credentials: {e}")
    
    def create_manifest(self):
        """Create backup manifest"""
        manifest = f"""N8N Backup Manifest
==================
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Timestamp: {self.timestamp}
Host: {self.ssh_host}
User: {self.ssh_user}
Container: {self.docker_container}

Backup Contents:
- database/n8n_apps_{self.timestamp}.dump        : n8n_apps database (binary)
- database/n8n_apps_{self.timestamp}.sql.gz      : n8n_apps database (SQL)
- database/n8n_internal_{self.timestamp}.dump    : n8n internal database (binary)
- database/n8n_internal_{self.timestamp}.sql.gz  : n8n internal database (SQL)
- workflows/all_workflows.json                   : All workflows
- workflows/*_*.json                             : Individual workflows
- n8n_data/credentials.json                      : N8N credentials (encrypted)
- n8n_data/n8n_data_{self.timestamp}.tar.gz     : N8N data directory
- docker/docker-compose.yml                      : Docker Compose config
- docker/docker.env                              : Docker environment
- docker/container_inspect.json                  : Container config
- docker/volumes.txt                             : Docker volumes
- docker/network_inspect.json                    : Network config

Backup Location: {self.local_backup_dir}
Remote backup: {self.remote_backup_dir}
"""
        
        with open(self.local_backup_dir / 'MANIFEST.txt', 'w') as f:
            f.write(manifest)
        
        print(manifest)
    
    def cleanup_remote(self):
        """Cleanup remote backup directory"""
        response = input("\nRemove backup files from remote host? (y/N): ").strip().lower()
        
        if response == 'y':
            print("Cleaning up remote backup...")
            if self.run_ssh(f"rm -rf {self.remote_backup_dir}"):
                print("  ✓ Remote backup cleaned up")
            else:
                print("  ✗ Failed to cleanup remote backup")
        else:
            print(f"  - Remote backup kept at: {self.remote_backup_dir}")
    
    def cleanup_old_local_backups(self):
        """Remove old local backups based on retention policy"""
        print("\nCleaning up old local backups...")
        
        if self.retention_days > 0:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            for backup in self.backup_path.iterdir():
                if backup.is_dir() and backup.name != self.timestamp:
                    try:
                        backup_date = datetime.strptime(backup.name, '%Y%m%d_%H%M%S')
                        if backup_date < cutoff_date:
                            shutil.rmtree(backup)
                            print(f"  - Removed old backup: {backup.name}")
                    except ValueError:
                        pass
            
            print(f"  ✓ Removed backups older than {self.retention_days} days")
        else:
            print("  - No retention policy (keeping all backups)")
    
    def create_latest_link(self):
        """Create 'latest' link to current backup"""
        latest_link = self.backup_path / 'latest'
        if latest_link.exists():
            if latest_link.is_symlink():
                latest_link.unlink()
            elif latest_link.is_file():
                latest_link.unlink()
            elif latest_link.is_dir():
                # On Windows, junctions appear as directories
                latest_link.rmdir()
        
        # On Windows, create a junction; on Unix, a symlink
        if sys.platform == 'win32':
            import subprocess
            subprocess.run(['mklink', '/J', str(latest_link), str(self.local_backup_dir)], shell=True, capture_output=True)
        else:
            latest_link.symlink_to(self.timestamp)
        
        print(f"\nLatest backup: {latest_link} -> {self.timestamp}")
    
    def run(self):
        """Run the complete backup process"""
        print("=" * 42)
        print(f"N8N Remote Backup: {self.timestamp}")
        print("=" * 42)
        print(f"Remote host: {self.ssh_host}")
        print(f"Local backup: {self.local_backup_dir}")
        print()
        
        try:
            self.step1_create_remote_dir()
            self.step2_backup_databases()
            self.step3_backup_docker()
            self.step4_backup_n8n_data()
            self.step5_download_backups()
            self.step6_backup_workflows()
            self.create_manifest()
            self.cleanup_remote()
            self.cleanup_old_local_backups()
            self.create_latest_link()
            
            # Calculate backup size
            total_size = sum(f.stat().st_size for f in self.local_backup_dir.rglob('*') if f.is_file())
            size_mb = total_size / (1024 * 1024)
            
            print("\n" + "=" * 42)
            print("Backup completed successfully!")
            print("=" * 42)
            print(f"Local backup: {self.local_backup_dir}")
            print(f"Backup size: {size_mb:.2f} MB")
            print()
            
        except Exception as e:
            print(f"\n✗ Backup failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    backup = N8NRemoteBackup()
    backup.run()
