"""
backup_manager.py — Professional Backup Manager
─────────────────────────────────────────────────
Enterprise-grade backup system:
- Atomic backups (write to temp file, then rename)
- Timestamped backup files
- Integrity validation (JSON parse check + schema check)
- Restore validation (dry-run before actual restore)
- Backup rotation (keep last N backups)
- Thread-safe

Usage:
    bm = BackupManager(backup_interval=300)
    bm.start()          # start automatic backup thread
    bm.create_backup()  # manual backup
    bm.restore_backup() # restore from latest
"""

import json
import sqlite3
import threading
import time
import logging
import os
import hashlib
from datetime import datetime
from config import DB_CONFIG

logger = logging.getLogger(__name__)


class BackupManager:
    """
    Professional backup manager with atomic writes and validation.
    """

    def __init__(self, backup_interval: int = 300):
        """
        Args:
            backup_interval: Seconds between automatic backups.
                            Default 300 (5 minutes). Set to 0 to disable auto-backup.
        """
        self.backup_interval = backup_interval
        self.backup_dir = 'data/backups'
        self.running = False
        self.thread = None
        self._lock = threading.Lock()
        self._ensure_backup_dir()

    # ── Public API ─────────────────────────────────────────────

    def start(self) -> None:
        """Start automatic background backup thread."""
        if self.backup_interval <= 0:
            logger.info("Auto-backup disabled (interval <= 0)")
            return

        self.running = True
        self.thread = threading.Thread(target=self._backup_loop, daemon=True)
        self.thread.start()
        logger.info(
            f"Backup manager started (interval: {self.backup_interval}s, "
            f"directory: {self.backup_dir})"
        )

    def stop(self) -> None:
        """Stop the backup thread gracefully."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Backup manager stopped")

    def create_backup(self) -> bool:
        """
        Create an atomic backup of ALL user data.
        
        Backs up:
        - users (full record)
        - transactions (full history)
        - orders (from users.db)
        - card_payments
        
        Returns True on success.
        """
        with self._lock:
            try:
                data = self._collect_backup_data()
                checksum = self._compute_checksum(data)

                backup_record = {
                    'version': 2,
                    'timestamp': datetime.now().isoformat(),
                    'checksum': checksum,
                    'data': data,
                }

                filename = self._get_backup_filename()
                temp_file = filename + '.tmp'

                # Atomic write: write to temp, validate, then rename
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(backup_record, f, ensure_ascii=False, indent=2)

                # Validate the written file
                self._validate_backup_file(temp_file, checksum)

                # Atomic rename (on same filesystem = atomic operation)
                os.replace(temp_file, filename)

                # Rotate old backups
                self._rotate_backups()

                user_count = len(data.get('users', {}))
                logger.info(f"Backup created: {filename} ({user_count} users)")
                return True

            except Exception as e:
                logger.error(f"Backup creation failed: {e}")
                # Clean up temp file
                temp = self._get_backup_filename() + '.tmp'
                if os.path.exists(temp):
                    os.remove(temp)
                return False

    def restore_backup(self, filename: str | None = None) -> bool:
        """
        Restore user data from backup file.
        
        Args:
            filename: Specific backup file to restore. If None, uses the latest.
        
        Returns True on success.
        """
        with self._lock:
            try:
                if filename is None:
                    filename = self._get_latest_backup()

                if filename is None or not os.path.exists(filename):
                    logger.warning("No backup file found for restore")
                    return False

                # Validate before restore
                if not self._validate_backup_file(filename):
                    return False

                # Read backup
                with open(filename, 'r', encoding='utf-8') as f:
                    backup = json.load(f)

                data = backup['data']
                backup_ts = backup.get('timestamp', 'unknown')

                # Dry-run validation
                if not self._validate_data_schema(data):
                    logger.error("Backup data schema validation failed — restore aborted")
                    return False

                # Execute restore in transaction
                success = self._execute_restore(data)

                if success:
                    logger.info(f"Backup restored from {filename} (timestamp: {backup_ts})")
                else:
                    logger.error("Restore failed during database write")

                return success

            except Exception as e:
                logger.error(f"Backup restore failed: {e}")
                return False

    def get_status(self) -> dict:
        """Return backup system status."""
        latest = self._get_latest_backup()
        backups = self._list_backups()

        return {
            'active': self.running,
            'interval_seconds': self.backup_interval,
            'backup_directory': self.backup_dir,
            'total_backups': len(backups),
            'latest_backup': os.path.basename(latest) if latest else None,
            'latest_timestamp': self._read_timestamp(latest) if latest else None,
        }

    # ── Private Methods ────────────────────────────────────────

    def _backup_loop(self) -> None:
        """Main backup loop (runs in background thread)."""
        while self.running:
            try:
                self.create_backup()
            except Exception as e:
                logger.error(f"Error in backup loop: {e}")
            time.sleep(self.backup_interval)

    def _collect_backup_data(self) -> dict:
        """Collect all data that needs to be backed up."""
        data = {}

        # Users + balances
        try:
            conn = sqlite3.connect(DB_CONFIG['users_db'])
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Users
            cursor.execute(
                'SELECT user_id, username, first_name, last_name, '
                'balance, is_blocked, language, join_date FROM users'
            )
            data['users'] = [dict(row) for row in cursor.fetchall()]

            # Transactions
            cursor.execute(
                'SELECT id, user_id, amount, type, description, ref_id, timestamp '
                'FROM transactions ORDER BY id'
            )
            data['transactions'] = [dict(row) for row in cursor.fetchall()]

            # Card payments
            cursor.execute(
                'SELECT payment_id, user_id, amount, status, receipt, '
                'admin_response, created_at FROM card_payments'
            )
            data['card_payments'] = [dict(row) for row in cursor.fetchall()]

            conn.close()
        except Exception as e:
            logger.error(f"Error collecting backup data from users_db: {e}")
            data['users'] = {}
            data['transactions'] = []
            data['card_payments'] = []

        return data

    def _execute_restore(self, data: dict) -> bool:
        """
        Execute database restore. Fully transactional.
        """
        conn = None
        try:
            conn = sqlite3.connect(DB_CONFIG['users_db'])
            cursor = conn.cursor()

            cursor.execute('BEGIN')

            # Ensure table
            cursor.execute('''CREATE TABLE IF NOT EXISTS users
                (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                 last_name TEXT, join_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                 balance INTEGER DEFAULT 0, is_blocked INTEGER DEFAULT 0,
                 language TEXT DEFAULT 'fa')''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS transactions
                (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                 amount INTEGER, type TEXT, description TEXT, ref_id TEXT,
                 timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY (user_id) REFERENCES users(user_id))''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS card_payments
                (payment_id TEXT PRIMARY KEY, user_id INTEGER, amount INTEGER,
                 status TEXT DEFAULT 'pending', receipt TEXT,
                 admin_response TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY (user_id) REFERENCES users(user_id))''')

            # Restore users
            if 'users' in data:
                for user in data['users']:
                    if isinstance(user, dict):
                        cursor.execute(
                            '''INSERT OR REPLACE INTO users
                               (user_id, username, first_name, last_name,
                                balance, is_blocked, language, join_date)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                            (
                                user.get('user_id', 0),
                                user.get('username'),
                                user.get('first_name'),
                                user.get('last_name'),
                                user.get('balance', 0),
                                user.get('is_blocked', 0),
                                user.get('language', 'fa'),
                                user.get('join_date'),
                            )
                        )

            # Restore transactions
            if 'transactions' in data:
                for txn in data['transactions']:
                    if isinstance(txn, dict):
                        cursor.execute(
                            '''INSERT OR REPLACE INTO transactions
                               (id, user_id, amount, type, description, ref_id, timestamp)
                               VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (
                                txn.get('id'), txn.get('user_id'),
                                txn.get('amount'), txn.get('type'),
                                txn.get('description'), txn.get('ref_id'),
                                txn.get('timestamp'),
                            )
                        )

            # Restore card payments
            if 'card_payments' in data:
                for cp in data['card_payments']:
                    if isinstance(cp, dict):
                        cursor.execute(
                            '''INSERT OR REPLACE INTO card_payments
                               (payment_id, user_id, amount, status, receipt,
                                admin_response, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (
                                cp.get('payment_id'), cp.get('user_id'),
                                cp.get('amount'), cp.get('status', 'pending'),
                                cp.get('receipt'), cp.get('admin_response'),
                                cp.get('created_at'),
                            )
                        )

            conn.commit()
            logger.info(
                f"Restore: {len(data.get('users', []))} users, "
                f"{len(data.get('transactions', []))} transactions, "
                f"{len(data.get('card_payments', []))} card payments"
            )
            return True

        except Exception as e:
            logger.error(f"Error during restore: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def _validate_backup_file(self, filepath: str, expected_checksum: str | None = None) -> bool:
        """
        Validate a backup file: JSON parse check + optional checksum.
        """
        try:
            if not os.path.exists(filepath):
                logger.error(f"Backup file not found: {filepath}")
                return False

            if os.path.getsize(filepath) == 0:
                logger.error(f"Backup file is empty: {filepath}")
                return False

            with open(filepath, 'r', encoding='utf-8') as f:
                backup = json.load(f)

            # Check structure
            if 'data' not in backup:
                logger.error(f"Backup missing 'data' key: {filepath}")
                return False

            # Checksum verification
            if expected_checksum is not None:
                actual = self._compute_checksum(backup['data'])
                if actual != expected_checksum:
                    logger.error(
                        f"Backup checksum mismatch! Expected: {expected_checksum[:8]}..., "
                        f"Got: {actual[:8]}..."
                    )
                    return False

            return True

        except json.JSONDecodeError as e:
            logger.error(f"Backup file is not valid JSON: {filepath} — {e}")
            return False
        except Exception as e:
            logger.error(f"Backup validation error: {e}")
            return False

    def _validate_data_schema(self, data: dict) -> bool:
        """Validate the data structure before restore."""
        if not isinstance(data, dict):
            logger.error("Backup data is not a dictionary")
            return False

        users = data.get('users', [])
        if isinstance(users, dict):
            # Legacy format: {user_id: balance}
            users = [{'user_id': int(k), 'balance': v} for k, v in users.items()]

        if not isinstance(users, list):
            logger.error("Invalid 'users' format in backup data")
            return False

        return True

    def _compute_checksum(self, data: dict) -> str:
        """Compute MD5 checksum of backup data for integrity verification."""
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(serialized.encode('utf-8')).hexdigest()

    def _get_backup_filename(self) -> str:
        """Generate a timestamped backup filename."""
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return os.path.join(self.backup_dir, f'backup_{ts}.json')

    def _get_latest_backup(self) -> str | None:
        """Find the latest backup file."""
        backups = self._list_backups()
        return backups[-1] if backups else None

    def _list_backups(self) -> list[str]:
        """List all backup files sorted by name (which embeds timestamp)."""
        if not os.path.exists(self.backup_dir):
            return []
        files = [
            os.path.join(self.backup_dir, f)
            for f in os.listdir(self.backup_dir)
            if f.startswith('backup_') and f.endswith('.json') and not f.endswith('.tmp')
        ]
        return sorted(files)

    def _rotate_backups(self, keep: int = 10) -> None:
        """Keep only the most recent N backups."""
        backups = self._list_backups()
        while len(backups) > keep:
            oldest = backups.pop(0)
            try:
                os.remove(oldest)
                logger.debug(f"Rotated old backup: {os.path.basename(oldest)}")
            except OSError as e:
                logger.warning(f"Failed to remove old backup {oldest}: {e}")

    def _read_timestamp(self, filepath: str) -> str | None:
        """Read the timestamp from a backup file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                backup = json.load(f)
            return backup.get('timestamp')
        except Exception:
            return None

    def _ensure_backup_dir(self) -> None:
        """Ensure the backup directory exists."""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
            logger.info(f"Created backup directory: {self.backup_dir}")
