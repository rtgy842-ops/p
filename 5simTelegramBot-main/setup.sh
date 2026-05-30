#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# setup.sh — One-Command Bare-Metal Setup (No Docker)
# ═══════════════════════════════════════════════════════════════
# Installs and configures: PostgreSQL, Redis, Python deps, DB schema, systemd services
# Run once:  chmod +x setup.sh && ./setup.sh
# ═══════════════════════════════════════════════════════════════

set -e
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
log() { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }
err() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  NumGenius Enterprise SaaS — Setup Script     ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# ── 1. Load .env ─────────────────────────────────────
[ -f .env ] || err ".env file not found in $PROJECT_DIR"
export $(grep -v '^#' .env | xargs)
log "Loaded environment from .env"

# ── 2. System Packages ────────────────────────────────
info "Installing system packages..."
if [ -f /etc/debian_version ]; then
    apt-get update -qq
    apt-get install -y -qq postgresql postgresql-client redis-server python3 python3-pip python3-venv curl libpq-dev > /dev/null 2>&1
elif [ -f /etc/redhat-release ]; then
    dnf install -y postgresql-server postgresql redis python3 python3-pip curl libpq-devel > /dev/null 2>&1
fi
log "System packages installed"

# ── 3. PostgreSQL Setup ───────────────────────────────
info "Configuring PostgreSQL..."
if ! systemctl is-active --quiet postgresql 2>/dev/null; then
    systemctl start postgresql
    systemctl enable postgresql
fi

# Create user and database
su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_USER:-smsbot}'\" | grep -q 1 || psql -c \"CREATE USER ${POSTGRES_USER:-smsbot} WITH PASSWORD '${POSTGRES_PASSWORD:-MyS3cur3Pssw0r}';\"" 2>/dev/null || true
su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB:-smsbot}'\" | grep -q 1 || psql -c \"CREATE DATABASE ${POSTGRES_DB:-smsbot} OWNER ${POSTGRES_USER:-smsbot};\"" 2>/dev/null || true
su - postgres -c "psql -c 'GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB:-smsbot} TO ${POSTGRES_USER:-smsbot};'" 2>/dev/null || true

# Configure pg_hba.conf for password auth
PG_HBA=$(su - postgres -c "psql -t -c 'SHOW hba_file;'" 2>/dev/null | tr -d ' ')
if [ -n "$PG_HBA" ] && ! grep -q "smsbot" "$PG_HBA" 2>/dev/null; then
    echo "local   smsbot          smsbot                                  md5" >> "$PG_HBA"
    echo "host    smsbot          smsbot          127.0.0.1/32           md5" >> "$PG_HBA"
    systemctl reload postgresql 2>/dev/null || true
fi
log "PostgreSQL configured (user: ${POSTGRES_USER:-smsbot}, db: ${POSTGRES_DB:-smsbot})"

# ── 4. Redis Setup ────────────────────────────────────
info "Configuring Redis..."
if ! systemctl is-active --quiet redis-server 2>/dev/null && ! systemctl is-active --quiet redis 2>/dev/null; then
    systemctl start redis-server 2>/dev/null || systemctl start redis 2>/dev/null || true
    systemctl enable redis-server 2>/dev/null || systemctl enable redis 2>/dev/null || true
fi
log "Redis running"

# ── 5. Python Environment ─────────────────────────────
info "Setting up Python environment..."
python3 -m venv venv 2>/dev/null || python3 -m virtualenv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
log "Python dependencies installed"

# ── 6. Database Schema ────────────────────────────────
info "Creating database tables..."
source venv/bin/activate
python3 -c "
from database import setup_databases
from db.migrations import MigrationManager
setup_databases()
mm = MigrationManager()
mm.migrate()
print('Schema created and migrations applied.')
"
log "Database schema initialized"

# ── 7. Systemd Service Files ──────────────────────────
info "Creating systemd service files..."

# Customer Bot
cat > /etc/systemd/system/numgenius-customer.service << SYSTEMD
[Unit]
Description=NumGenius Customer Bot
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/bot.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SYSTEMD

# Admin Bot
cat > /etc/systemd/system/numgenius-admin.service << SYSTEMD
[Unit]
Description=NumGenius Admin Bot
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/admin_bot.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SYSTEMD

# Celery Worker
cat > /etc/systemd/system/numgenius-worker.service << SYSTEMD
[Unit]
Description=NumGenius Celery Worker
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/celery -A tasks worker --loglevel=info --concurrency=2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SYSTEMD

# Celery Beat
cat > /etc/systemd/system/numgenius-beat.service << SYSTEMD
[Unit]
Description=NumGenius Celery Beat Scheduler
After=network.target redis-server.service
Requires=redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/celery -A tasks beat --loglevel=info
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SYSTEMD

systemctl daemon-reload
log "Systemd services created"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  SETUP COMPLETE!                              ║"
echo "╠═══════════════════════════════════════════════╣"
echo "║  Start all services:                         ║"
echo "║    systemctl start numgenius-customer         ║"
echo "║    systemctl start numgenius-admin            ║"
echo "║    systemctl start numgenius-worker           ║"
echo "║    systemctl start numgenius-beat             ║"
echo "║                                               ║"
echo "║  Enable auto-start on boot:                  ║"
echo "║    systemctl enable numgenius-customer \\      ║"
echo "║        numgenius-admin numgenius-worker \\     ║"
echo "║        numgenius-beat                        ║"
echo "║                                               ║"
echo "║  Check status:                               ║"
echo "║    systemctl status numgenius-*               ║"
echo "║                                               ║"
echo "║  View logs:                                  ║"
echo "║    journalctl -u numgenius-customer -f        ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""