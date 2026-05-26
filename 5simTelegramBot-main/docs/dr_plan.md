# 🚨 Disaster Recovery Plan

> **Document Version:** 1.0  
> **Last Updated:** 2026-05-26  
> **Owner:** DevOps Team  
> **Review Cycle:** Quarterly  

---

## 1. Recovery Objectives

| Metric | Target |
|--------|--------|
| **RTO** (Recovery Time Objective) | < 1 hour |
| **RPO** (Recovery Point Objective) | < 5 minutes |
| **Maximum acceptable data loss** | Last 5 minutes of transactions |

---

## 2. Backup Strategy

### 2.1 What is backed up
- `users.db` — Full (users, transactions, card_payments)
- `admin.db` — Full (settings, channels, operators, card_info)
- `bot.db` — Full (orders, activation_codes)
- `data/users_backup.json` — JSON snapshot

### 2.2 Schedule
| Backup Type | Frequency | Retention |
|-------------|-----------|-----------|
| Automated (BackupManager) | Every 5 minutes | Last 10 copies |
| Script (`scripts/backup.sh`) | Hourly | 7 days |
| Full DB dump | Daily | 30 days |
| Off-site copy | Daily | 90 days |

### 2.3 Validation
- Every backup is checksum-verified (MD5)
- Monthly restore test on staging environment
- Automated integrity check after each backup

---

## 3. Restore Procedures

### 3.1 Quick Restore (from latest BackupManager backup)
```bash
# 1. Stop the bot
docker-compose stop bot worker

# 2. Restore from latest backup
python -c "
from backup_manager import BackupManager
bm = BackupManager()
bm.restore_backup()
"

# 3. Run migrations
python -c "
from db.migrations import MigrationManager
MigrationManager().migrate()
"

# 4. Start the bot
docker-compose start bot worker
```

### 3.2 Full Restore (from script backup)
```bash
# 1. List available backups
./scripts/backup.sh list

# 2. Restore from specific file
./scripts/backup.sh restore data/backups/backup_20260526_120000.tar.gz

# 3. Verify restored files
sqlite3 users.db ".tables"

# 4. Replace originals
mv users.db.restore users.db
mv admin.db.restore admin.db
mv bot.db.restore bot.db

# 5. Restart services
docker-compose restart
```

### 3.3 Emergency Rollback
```bash
# If a deployment causes issues:
git log --oneline -5
git revert <bad-commit-hash>
git push origin main

# Docker redeploy
docker-compose down
docker-compose build --no-cache bot
docker-compose up -d
```

---

## 4. Incident Response

### 4.1 Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| **P1 — Critical** | Payment failure, data loss, complete outage | Immediate (15 min) |
| **P2 — High** | SMS provider down, orders failing | 30 minutes |
| **P3 — Medium** | Admin panel slow, cache issues | 2 hours |
| **P4 — Low** | Non-critical UI issues | Next business day |

### 4.2 Incident Procedure

1. **Detect** — Monitoring alert or user report
2. **Acknowledge** — Acknowledge within response time
3. **Triage** — Determine severity and affected components
4. **Mitigate** — Apply temporary fix to stop bleeding
5. **Resolve** — Implement permanent fix
6. **Post-mortem** — Document root cause and prevention

### 4.3 Emergency Contacts
- **Primary:** System Administrator
- **Secondary:** Lead Developer
- **Escalation:** Project Manager

---

## 5. Failure Scenarios & Responses

### 5.1 Database Corruption
- **Detect:** Integrity check failures, query errors
- **Response:** Immediate restore from latest validated backup
- **Prevention:** WAL mode, regular integrity checks, backup validation

### 5.2 Payment Gateway Outage
- **Detect:** Payment verification failures spike
- **Response:** Enable fallback gateway (card-to-card), notify users
- **Prevention:** Multi-gateway architecture, health checks

### 5.3 SMS Provider Outage
- **Detect:** `getNumbersStatus` failures
- **Response:** Switch to backup provider, display maintenance message
- **Prevention:** Provider health checks every 60 seconds

### 5.4 Redis Failure
- **Detect:** Connection errors, cache misses spike
- **Response:** Application degrades gracefully (no cache = direct DB)
- **Prevention:** Redis persistence (AOF), replica

### 5.5 DDoS / Traffic Spike
- **Detect:** Rate limit hits, response time increase
- **Response:** Nginx rate limiting kicks in automatically
- **Prevention:** CDN, horizontal scaling ready

---

## 6. Testing Schedule

| Test | Frequency | Owner |
|------|-----------|-------|
| Backup integrity check | Daily (automated) | System |
| Restore test | Monthly | DevOps |
| Full DR drill | Quarterly | DevOps |
| Security audit | Annually | Security |

---

## 7. Recovery Checklist

- [ ] Backup file exists and is recent (< 10 min old)
- [ ] Backup file passes integrity check
- [ ] Restore procedure tested in last 30 days
- [ ] Database migrations are up to date
- [ ] All services health check passing
- [ ] SMS provider responding
- [ ] Payment gateway responding
- [ ] Redis connected
- [ ] Nginx serving traffic
- [ ] SSL certificates valid
