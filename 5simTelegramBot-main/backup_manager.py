"""
backup_manager.py — PostgreSQL Backup Manager
─────────────────────────────────────────────────
JSON-based backup for critical data.
Thread-safe via ConnectionManager pool.
"""

import json
import threading
import time
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class BackupManager:
    def __init__(self, backup_interval: int = 300):
        self.backup_interval = backup_interval
        self.backup_dir = os.getenv('BACKUP_DIR', 'data/backups')
        self.backup_file = os.getenv('BACKUP_FILE', 'data/users_backup.json')
        self.running = False
        self.thread = None
        self._lock = threading.Lock()
        os.makedirs(self.backup_dir, exist_ok=True)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._backup_loop, daemon=True)
        self.thread.start()
        logger.info(f"Backup manager started (interval: {self.backup_interval}s)")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def _backup_loop(self):
        while self.running:
            try:
                self.create_backup()
            except Exception as e:
                logger.error(f"Backup error: {e}")
            time.sleep(self.backup_interval)

    def create_backup(self) -> bool:
        with self._lock:
            try:
                from db.connection import ConnectionManager
                cm = ConnectionManager.get_instance()
                conn = cm.get_connection('default')
                cursor = conn.cursor()

                cursor.execute('SELECT user_id, balance FROM users')
                data = {}
                for row in cursor.fetchall():
                    data[str(row[0])] = row[1]

                cm.put_connection(conn)

                temp_file = self.backup_file + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                os.replace(temp_file, self.backup_file)
                logger.info(f"Backup created: {self.backup_file} ({len(data)} users)")
                return True
            except Exception as e:
                logger.error(f"Backup failed: {e}")
                return False

    def restore_backup(self) -> bool:
        try:
            if not os.path.exists(self.backup_file):
                return False
            from db.repositories.user_repository import UserRepository
            repo = UserRepository()
            with open(self.backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for uid, bal in data.items():
                repo.create_if_not_exists(int(uid))
                repo.add_balance(int(uid), int(bal))
            logger.info(f"Restored {len(data)} users")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
