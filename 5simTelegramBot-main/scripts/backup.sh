#!/bin/bash
# ── scripts/backup.sh — Automated Database Backup ──────────────
# Features: timestamped, compressed, retention policy
# Usage: ./scripts/backup.sh [--restore latest]

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-data/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DB_USERS="${DB_USERS:-users.db}"
DB_ADMIN="${DB_ADMIN:-admin.db}"
DB_BOT="${DB_BOT:-bot.db}"

# ── Colors ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Create backup ─────────────────────────────────────────────
create_backup() {
    mkdir -p "$BACKUP_DIR"

    local timestamp
    timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_file="${BACKUP_DIR}/backup_${timestamp}.tar.gz"

    log "Creating backup: $backup_file"

    # Create temp directory
    local tmpdir
    tmpdir=$(mktemp -d)

    # Copy database files (SQLite safe copy via .backup)
    for db in "$DB_USERS" "$DB_ADMIN" "$DB_BOT"; do
        if [ -f "$db" ]; then
            sqlite3 "$db" ".backup '${tmpdir}/${db}'" 2>/dev/null || cp "$db" "$tmpdir/"
            log "  Backed up: $db"
        fi
    done

    # Also backup JSON backup if exists
    if [ -f data/users_backup.json ]; then
        cp data/users_backup.json "$tmpdir/"
    fi

    # Compress
    tar -czf "$backup_file" -C "$tmpdir" .
    rm -rf "$tmpdir"

    # Verify
    if [ -f "$backup_file" ] && [ -s "$backup_file" ]; then
        local size
        size=$(du -h "$backup_file" | cut -f1)
        log "Backup created: $backup_file ($size)"
    else
        err "Backup creation failed!"
        return 1
    fi
}

# ── Restore backup ────────────────────────────────────────────
restore_backup() {
    local backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        err "Backup file not found: $backup_file"
        return 1
    fi

    log "Restoring from: $backup_file"

    local tmpdir
    tmpdir=$(mktemp -d)
    tar -xzf "$backup_file" -C "$tmpdir"

    for db in "$DB_USERS" "$DB_ADMIN" "$DB_BOT"; do
        if [ -f "${tmpdir}/${db}" ]; then
            cp "${tmpdir}/${db}" "${db}.restore"
            log "  Restored: $db → ${db}.restore"
        fi
    done

    rm -rf "$tmpdir"
    warn "Restore staged. Verify ${db}.restore files, then rename to replace originals."
}

# ── Cleanup old backups ───────────────────────────────────────
cleanup_old_backups() {
    log "Cleaning backups older than ${RETENTION_DAYS} days..."
    find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
    log "Cleanup complete"
}

# ── List backups ──────────────────────────────────────────────
list_backups() {
    log "Available backups:"
    ls -lht "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null || echo "  (none)"
}

# ── Main ──────────────────────────────────────────────────────
case "${1:-backup}" in
    backup)
        create_backup
        cleanup_old_backups
        ;;
    restore)
        if [ "${2:-}" = "latest" ]; then
            latest=$(ls -t "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | head -1)
            if [ -z "$latest" ]; then
                err "No backups found"
                exit 1
            fi
            restore_backup "$latest"
        elif [ -n "${2:-}" ]; then
            restore_backup "$2"
        else
            echo "Usage: $0 restore <file|latest>"
            exit 1
        fi
        ;;
    list)
        list_backups
        ;;
    *)
        echo "Usage: $0 {backup|restore <file|latest>|list}"
        exit 1
        ;;
esac