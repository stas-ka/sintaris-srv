#!/usr/bin/env python3
"""
N8N Complete Backup Script (Python Version)
============================================
This script backs up:
- PostgreSQL databases (n8n_apps and n8n itself)
- N8N workflows (individual JSON files)
- N8N settings and credentials
- Docker configurations
"""

import os
import sys
import json
import subprocess
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class N8NBackup:
    def __init__(self):
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_path = Path(os.getenv('BACKUP_PATH', './backups'))
        self.backup_dir = self.backup_path / self.timestamp
        
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
        
        # Create backup directories
        self.create_backup_structure()
    
    def create_backup_structure(self):
        """Create backup directory structure"""
        (self.backup_dir / 'database').mkdir(parents=True, exist_ok=True)
        (self.backup_dir / 'workflows').mkdir(parents=True, exist_ok=True)
        (self.backup_dir / 'docker').mkdir(parents=True, exist_ok=True)
        (self.backup_dir / 'n8n_data').mkdir(parents=True, exist_ok=True)
    
    def run_ssh_command(self, command, capture_output=True):
        """Execute command on remote host via SSH"""
        ssh_cmd = [
            'ssh',
            '-i', self.ssh_key_path,
            '-p', self.ssh_port,
            f'{self.ssh_user}@{self.ssh_host}',
            command
        ]
        
        if capture_output:
            result = subprocess.run(ssh_cmd, capture_output=True, text=False)
            if result.returncode != 0:
                print(f"Warning: Command failed: {command}")
                print(f"Error: {result.stderr.decode('utf-8', errors='ignore')}")
            return result.stdout
        else:
            subprocess.run(ssh_cmd)
            return None
    
    def backup_databases(self):
        """Backup PostgreSQL databases"""
        print("\n[1/5] Backing up PostgreSQL databases...")
        
        # Backup n8n_apps database (binary format)
        print("  - Backing up n8n_apps database (binary format)...")
        dump_cmd = f"PGPASSWORD='{self.pg_password}' pg_dump -h {self.pg_host} -p {self.pg_port} -U {self.pg_user} -d {self.pg_database} -F c"
        dump_data = self.run_ssh_command(dump_cmd)
        with open(self.backup_dir / 'database' / f'n8n_apps_{self.timestamp}.dump', 'wb') as f:
            f.write(dump_data)
        
        # Backup n8n_apps database (SQL format)
        print("  - Backing up n8n_apps database (SQL format)...")
        sql_cmd = f"PGPASSWORD='{self.pg_password}' pg_dump -h {self.pg_host} -p {self.pg_port} -U {self.pg_user} -d {self.pg_database}"
        sql_data = self.run_ssh_command(sql_cmd)
        
        import gzip
        with gzip.open(self.backup_dir / 'database' / f'n8n_apps_{self.timestamp}.sql.gz', 'wb') as f:
            f.write(sql_data)
        
        # Backup n8n internal database
        print("  - Backing up n8n internal database...")
        sudo = "sudo " if self.docker_requires_sudo else ""
        internal_dump_cmd = f"{sudo}docker exec {self.docker_container} sh -c 'PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost -U $POSTGRES_USER -d $POSTGRES_DB -F c'"
        internal_data = self.run_ssh_command(internal_dump_cmd)
        with open(self.backup_dir / 'database' / f'n8n_internal_{self.timestamp}.dump', 'wb') as f:
            f.write(internal_data)
        
        # Backup n8n internal database (SQL format)
        internal_sql_cmd = f"{sudo}docker exec {self.docker_container} sh -c 'PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost -U $POSTGRES_USER -d $POSTGRES_DB'"
        internal_sql_data = self.run_ssh_command(internal_sql_cmd)
        with gzip.open(self.backup_dir / 'database' / f'n8n_internal_{self.timestamp}.sql.gz', 'wb') as f:
            f.write(internal_sql_data)
        
        print("  ✓ Database backups completed")
    
    def backup_workflows(self):
        """Backup N8N workflows via API"""
        print("\n[2/5] Backing up N8N workflows...")
        
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
            with open(self.backup_dir / 'workflows' / 'all_workflows.json', 'w', encoding='utf-8') as f:
                json.dump(workflows_data, f, indent=2, ensure_ascii=False)
            
            # Save each workflow individually
            if 'data' in workflows_data:
                for workflow in workflows_data['data']:
                    workflow_id = workflow.get('id', 'unknown')
                    workflow_name = workflow.get('name', 'unnamed').replace(' ', '_')
                    # Clean filename
                    workflow_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in workflow_name)
                    
                    print(f"  - Saving workflow: {workflow_name} ({workflow_id})")
                    with open(self.backup_dir / 'workflows' / f'{workflow_id}_{workflow_name}.json', 'w', encoding='utf-8') as f:
                        json.dump(workflow, f, indent=2, ensure_ascii=False)
            
            print("  ✓ Workflow backups completed")
        except Exception as e:
            print(f"  ✗ Error backing up workflows: {e}")
    
    def backup_credentials(self):
        """Backup N8N credentials (encrypted)"""
        print("\n[3/5] Backing up N8N credentials...")
        
        headers = {
            'X-N8N-API-KEY': self.n8n_api_key,
            'Accept': 'application/json'
        }
        
        try:
            response = requests.get(f'{self.n8n_api_base}/v1/credentials', headers=headers)
            response.raise_for_status()
            credentials_data = response.json()
            
            with open(self.backup_dir / 'n8n_data' / 'credentials.json', 'w', encoding='utf-8') as f:
                json.dump(credentials_data, f, indent=2, ensure_ascii=False)
            
            print("  ✓ Credentials backup completed")
        except Exception as e:
            print(f"  ✗ Error backing up credentials: {e}")
    
    def backup_docker_config(self):
        """Backup Docker configurations"""
        print("\n[4/5] Backing up Docker configurations...")
        
        # Backup docker-compose.yml
        print("  - Backing up docker-compose.yml...")
        compose_data = self.run_ssh_command(f"cat {self.n8n_docker_dir}/docker-compose.yml")
        with open(self.backup_dir / 'docker' / 'docker-compose.yml', 'wb') as f:
            f.write(compose_data)
        
        # Backup .env file
        print("  - Backing up Docker .env file...")
        env_data = self.run_ssh_command(f"cat {self.n8n_docker_dir}/.env 2>/dev/null || echo '# No .env file found'")
        with open(self.backup_dir / 'docker' / 'docker.env', 'wb') as f:
            f.write(env_data)
        
        # Backup container inspection
        print("  - Backing up container inspection...")
        sudo = "sudo " if self.docker_requires_sudo else ""
        inspect_data = self.run_ssh_command(f"{sudo}docker inspect {self.docker_container}")
        with open(self.backup_dir / 'docker' / 'container_inspect.json', 'wb') as f:
            f.write(inspect_data)
        
        # Backup volume information
        print("  - Backing up volume information...")
        volumes_data = self.run_ssh_command(f"{sudo}docker volume ls --format '{{{{.Name}}}}' | grep n8n || true")
        with open(self.backup_dir / 'docker' / 'volumes.txt', 'wb') as f:
            f.write(volumes_data)
        
        # Backup network information
        print("  - Backing up network information...")
        network_cmd = f"{sudo}docker network inspect $({sudo}docker inspect {self.docker_container} | jq -r '.[0].NetworkSettings.Networks | keys[]') 2>/dev/null || echo '[]'"
        network_data = self.run_ssh_command(network_cmd)
        with open(self.backup_dir / 'docker' / 'network_inspect.json', 'wb') as f:
            f.write(network_data)
        
        print("  ✓ Docker configuration backups completed")
    
    def backup_n8n_data(self):
        """Backup N8N data directory"""
        print("\n[5/5] Backing up N8N data directory...")
        
        sudo = "sudo " if self.docker_requires_sudo else ""
        tar_cmd = f"{sudo}docker exec {self.docker_container} tar czf - /home/node/.n8n 2>/dev/null || echo 'Data dir backup skipped'"
        tar_data = self.run_ssh_command(tar_cmd)
        
        with open(self.backup_dir / 'n8n_data' / f'n8n_data_{self.timestamp}.tar.gz', 'wb') as f:
            f.write(tar_data)
        
        print("  ✓ N8N data directory backup completed")
    
    def create_manifest(self):
        """Create backup manifest"""
        print("\nCreating backup manifest...")
        
        manifest = f"""N8N Backup Manifest
==================
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Timestamp: {self.timestamp}
Host: {self.ssh_host}
User: {self.ssh_user}
Container: {self.docker_container}

Backup Contents:
- database/n8n_apps_{self.timestamp}.dump        : n8n_apps database (binary format)
- database/n8n_apps_{self.timestamp}.sql.gz      : n8n_apps database (SQL format)
- database/n8n_internal_{self.timestamp}.dump    : n8n internal database (binary format)
- database/n8n_internal_{self.timestamp}.sql.gz  : n8n internal database (SQL format)
- workflows/all_workflows.json                   : All workflows in single file
- workflows/*_*.json                             : Individual workflow files
- n8n_data/credentials.json                      : N8N credentials (encrypted)
- n8n_data/n8n_data_{self.timestamp}.tar.gz     : Complete N8N data directory
- docker/docker-compose.yml                      : Docker Compose configuration
- docker/docker.env                              : Docker environment variables
- docker/container_inspect.json                  : Container configuration
- docker/volumes.txt                             : Docker volumes list
- docker/network_inspect.json                    : Network configuration

Backup Location: {self.backup_dir}
"""
        
        with open(self.backup_dir / 'MANIFEST.txt', 'w') as f:
            f.write(manifest)
        
        print(manifest)
    
    def cleanup_old_backups(self):
        """Remove old backups based on retention policy"""
        print("\nCleaning up old backups...")
        
        if self.retention_days > 0:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            for backup in self.backup_path.iterdir():
                if backup.is_dir() and backup.name != self.timestamp:
                    try:
                        backup_date = datetime.strptime(backup.name, '%Y%m%d_%H%M%S')
                        if backup_date < cutoff_date:
                            import shutil
                            shutil.rmtree(backup)
                            print(f"  - Removed old backup: {backup.name}")
                    except ValueError:
                        pass  # Skip directories that don't match the timestamp format
            
            print(f"  ✓ Removed backups older than {self.retention_days} days")
        else:
            print("  - No retention policy configured (keeping all backups)")
    
    def create_latest_symlink(self):
        """Create a 'latest' symlink to the current backup"""
        latest_link = self.backup_path / 'latest'
        if latest_link.exists():
            latest_link.unlink()
        
        # On Windows, create a junction instead of symlink
        if sys.platform == 'win32':
            import subprocess
            subprocess.run(['mklink', '/J', str(latest_link), str(self.backup_dir)], shell=True)
        else:
            latest_link.symlink_to(self.timestamp)
        
        print(f"\nLatest backup: {latest_link} -> {self.timestamp}")
    
    def run(self):
        """Run the complete backup process"""
        print("=" * 42)
        print(f"N8N Backup Started: {self.timestamp}")
        print("=" * 42)
        
        try:
            self.backup_databases()
            self.backup_workflows()
            self.backup_credentials()
            self.backup_docker_config()
            self.backup_n8n_data()
            self.create_manifest()
            self.cleanup_old_backups()
            self.create_latest_symlink()
            
            # Calculate backup size
            total_size = sum(f.stat().st_size for f in self.backup_dir.rglob('*') if f.is_file())
            size_mb = total_size / (1024 * 1024)
            
            print("\n" + "=" * 42)
            print("Backup completed successfully!")
            print("=" * 42)
            print(f"Backup location: {self.backup_dir}")
            print(f"Backup size: {size_mb:.2f} MB")
            print()
            
        except Exception as e:
            print(f"\n✗ Backup failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    backup = N8NBackup()
    backup.run()
