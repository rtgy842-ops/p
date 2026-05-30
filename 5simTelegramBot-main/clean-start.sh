#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# clean-start.sh — Clean everything and start bots with polling
# ═══════════════════════════════════════════════════════════════
# Run: chmod +x clean-start.sh && ./clean-start.sh
# ═══════════════════════════════════════════════════════════════

set -e
cd "$(dirname "$0")"
echo "=== NumGenius Clean Start ==="

# 1. Kill any existing bot processes
echo "[1/6] Killing old processes..."
kill $(lsof -t -i:5000) 2>/dev/null || true
kill $(lsof -t -i:5001) 2>/dev/null || true
sleep 2

# 2. Delete ALL webhooks and wait
echo "[2/6] Deleting webhooks..."
curl -s "https://api.telegram.org/bot8867840427:AAG56v1yGp4XBjL2-vlhHIhPR765NikFhDI/deleteWebhook?drop_pending_updates=true" > /dev/null
curl -s "https://api.telegram.org/bot8661921297:AAFdV3aIjx_9lTPAT86gR2OqHT4j2lsZvJU/deleteWebhook?drop_pending_updates=true" > /dev/null
sleep 3

# 3. Setup venv
echo "[3/6] Setting up Python..."
python3 -m venv venv 2>/dev/null || true
source venv/bin/activate
pip install -r requirements.txt -q 2>/dev/null

# 4. Init DB once
echo "[4/6] Initializing database..."
python3 -c "
from database import setup_databases; setup_databases()
from db.migrations import MigrationManager; MigrationManager().migrate()
print('DB ready')
"

# 5. Start Customer Bot
echo "[5/6] Starting Customer Bot..."
BOT_TOKEN="8867840427:AAG56v1yGp4XBjL2-vlhHIhPR765NikFhDI" \
FLASK_PORT=5000 \
nohup venv/bin/python bot.py > logs/customer.log 2>&1 &
CUSTOMER_PID=$!
echo "  Customer PID: $CUSTOMER_PID"

# 6. Start Admin Bot
echo "[6/6] Starting Admin Bot..."
BOT_TOKEN="8661921297:AAFdV3aIjx_9lTPAT86gR2OqHT4j2lsZvJU" \
FLASK_PORT=5001 \
nohup venv/bin/python admin_bot.py > logs/admin.log 2>&1 &
ADMIN_PID=$!
echo "  Admin PID: $ADMIN_PID"

sleep 6

echo ""
echo "=== Status ==="
curl -s http://localhost:5000/ping && echo " | Customer OK" || echo " | Customer FAILED"
curl -s http://localhost:5001/ping && echo " | Admin OK" || echo " | Admin FAILED"
echo ""
echo "Logs:"
echo "--- Customer (last 8 lines) ---"
tail -8 logs/customer.log
echo "--- Admin (last 8 lines) ---"
tail -8 logs/admin.log
echo ""
echo "Now try /start on both bots in Telegram."