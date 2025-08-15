#!/usr/bin/env python3
"""
Production Backup System - Nightly Qdrant Snapshots + Neo4j Dumps
Implements automated backup with off-site sync capability
"""

import os
import sys
import subprocess
import datetime
import logging
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductionBackupSystem:
    """Automated backup system for Qdrant + Neo4j"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._load_default_config()
        self.backup_root = Path(self.config["backup_root"])
        self.backup_root.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Backup system initialized: {self.backup_root}")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default backup configuration"""
        return {
            "backup_root": "/app/backups",
            "retention_days": 7,
            "qdrant": {
                "host": "qdrant",
                "port": 6333,
                "collection": "project_context"
            },
            "neo4j": {
                "host": "neo4j",
                "port": 7687,
                "user": "neo4j", 
                "database": "neo4j"
            },
            "offsite": {
                "enabled": True,
                "method": "rsync",  # or "rclone"
                "destination": "backup-server:/context-store-backups/"
            }
        }
    
    async def create_qdrant_snapshot(self) -> Dict[str, Any]:
        """Create Qdrant collection snapshot"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"qdrant_snapshot_{timestamp}"
        
        try:
            # Create snapshot via Qdrant API
            import requests
            
            qdrant_url = f"http://{self.config['qdrant']['host']}:{self.config['qdrant']['port']}"
            collection = self.config['qdrant']['collection']
            
            # Trigger snapshot creation
            response = requests.post(
                f"{qdrant_url}/collections/{collection}/snapshots",
                timeout=300  # 5 minute timeout for large collections
            )
            
            if response.status_code == 200:
                snapshot_info = response.json()
                
                # Download snapshot
                snapshot_url = f"{qdrant_url}/collections/{collection}/snapshots/{snapshot_info['result']['name']}"
                download_response = requests.get(snapshot_url, stream=True, timeout=600)
                
                if download_response.status_code == 200:
                    snapshot_path = self.backup_root / f"{snapshot_name}.snapshot"
                    
                    with open(snapshot_path, "wb") as f:
                        for chunk in download_response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    # Verify snapshot
                    size_mb = snapshot_path.stat().st_size / (1024 * 1024)
                    
                    logger.info(f"✅ Qdrant snapshot created: {snapshot_path} ({size_mb:.1f} MB)")
                    
                    return {
                        "success": True,
                        "snapshot_path": str(snapshot_path),
                        "size_mb": size_mb,
                        "timestamp": timestamp,
                        "collection": collection
                    }
                else:
                    raise Exception(f"Failed to download snapshot: {download_response.status_code}")
            else:
                raise Exception(f"Failed to create snapshot: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Qdrant snapshot failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_neo4j_dump(self) -> Dict[str, Any]:
        """Create Neo4j database dump"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_name = f"neo4j_dump_{timestamp}.dump"
        dump_path = self.backup_root / dump_name
        
        try:
            # Use neo4j-admin dump command
            neo4j_config = self.config["neo4j"]
            
            # Command to run inside Neo4j container
            dump_cmd = [
                "docker", "exec", "context-store-neo4j-1",
                "neo4j-admin", "database", "dump", 
                "--database", neo4j_config["database"],
                "--to-path", "/backups",
                f"--overwrite-destination={dump_name}"
            ]
            
            # Ensure backup directory exists in container
            subprocess.run([
                "docker", "exec", "context-store-neo4j-1",
                "mkdir", "-p", "/backups"
            ], check=True)
            
            # Create dump
            result = subprocess.run(dump_cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                # Copy dump from container
                subprocess.run([
                    "docker", "cp", 
                    f"context-store-neo4j-1:/backups/{dump_name}",
                    str(dump_path)
                ], check=True)
                
                # Verify dump
                size_mb = dump_path.stat().st_size / (1024 * 1024)
                
                logger.info(f"✅ Neo4j dump created: {dump_path} ({size_mb:.1f} MB)")
                
                return {
                    "success": True,
                    "dump_path": str(dump_path),
                    "size_mb": size_mb,
                    "timestamp": timestamp,
                    "database": neo4j_config["database"]
                }
            else:
                raise Exception(f"neo4j-admin failed: {result.stderr}")
                
        except Exception as e:
            logger.error(f"❌ Neo4j dump failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def sync_offsite(self, local_path: Path) -> Dict[str, Any]:
        """Sync backup to offsite location"""
        if not self.config["offsite"]["enabled"]:
            return {"success": True, "message": "Offsite sync disabled"}
        
        try:
            method = self.config["offsite"]["method"]
            destination = self.config["offsite"]["destination"]
            
            if method == "rsync":
                cmd = [
                    "rsync", "-avz", "--progress",
                    str(local_path),
                    destination
                ]
            elif method == "rclone":
                cmd = [
                    "rclone", "copy", 
                    str(local_path),
                    destination
                ]
            else:
                raise Exception(f"Unknown sync method: {method}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            
            if result.returncode == 0:
                logger.info(f"✅ Offsite sync successful: {local_path.name}")
                return {"success": True, "method": method, "destination": destination}
            else:
                raise Exception(f"Sync failed: {result.stderr}")
                
        except Exception as e:
            logger.error(f"❌ Offsite sync failed: {e}")
            return {"success": False, "error": str(e)}
    
    def cleanup_old_backups(self) -> Dict[str, Any]:
        """Clean up old backups based on retention policy"""
        retention_days = self.config["retention_days"]
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        
        removed_files = []
        total_size_freed = 0
        
        try:
            for backup_file in self.backup_root.glob("*"):
                if backup_file.is_file():
                    # Check file age
                    file_time = datetime.datetime.fromtimestamp(backup_file.stat().st_mtime)
                    
                    if file_time < cutoff_date:
                        size_mb = backup_file.stat().st_size / (1024 * 1024)
                        backup_file.unlink()
                        removed_files.append(backup_file.name)
                        total_size_freed += size_mb
            
            if removed_files:
                logger.info(f"🗑️ Cleaned up {len(removed_files)} old backups ({total_size_freed:.1f} MB freed)")
            
            return {
                "success": True,
                "removed_files": removed_files,
                "size_freed_mb": total_size_freed
            }
            
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def run_nightly_backup(self) -> Dict[str, Any]:
        """Execute complete nightly backup routine"""
        logger.info("🌙 Starting nightly backup routine...")
        
        start_time = datetime.datetime.now()
        results = {
            "start_time": start_time.isoformat(),
            "qdrant": {},
            "neo4j": {},
            "offsite": [],
            "cleanup": {}
        }
        
        # 1. Create Qdrant snapshot
        results["qdrant"] = await self.create_qdrant_snapshot()
        
        # 2. Create Neo4j dump
        results["neo4j"] = await self.create_neo4j_dump()
        
        # 3. Sync to offsite (if enabled)
        for backup_type, backup_result in [("qdrant", results["qdrant"]), ("neo4j", results["neo4j"])]:
            if backup_result.get("success") and backup_result.get(f"{backup_type}_path" if backup_type == "neo4j" else "snapshot_path"):
                backup_path = Path(backup_result[f"{backup_type}_path" if backup_type == "neo4j" else "snapshot_path"])
                sync_result = await self.sync_offsite(backup_path)
                sync_result["backup_type"] = backup_type
                results["offsite"].append(sync_result)
        
        # 4. Clean up old backups
        results["cleanup"] = self.cleanup_old_backups()
        
        # Calculate total time
        end_time = datetime.datetime.now()
        results["end_time"] = end_time.isoformat()
        results["duration_minutes"] = (end_time - start_time).total_seconds() / 60
        
        # Overall success
        results["overall_success"] = (
            results["qdrant"].get("success", False) and 
            results["neo4j"].get("success", False)
        )
        
        if results["overall_success"]:
            logger.info(f"✅ Nightly backup completed successfully ({results['duration_minutes']:.1f} min)")
        else:
            logger.error("❌ Nightly backup had failures")
        
        return results


# CLI interface
async def main():
    """CLI entry point for backup system"""
    backup_system = ProductionBackupSystem()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "qdrant":
            result = await backup_system.create_qdrant_snapshot()
        elif command == "neo4j":
            result = await backup_system.create_neo4j_dump()
        elif command == "cleanup":
            result = backup_system.cleanup_old_backups()
        elif command == "nightly":
            result = await backup_system.run_nightly_backup()
        else:
            print("Usage: python backup_system.py [qdrant|neo4j|cleanup|nightly]")
            sys.exit(1)
    else:
        result = await backup_system.run_nightly_backup()
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())