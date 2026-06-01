"""Comprehensive audit script — checks all Python files for syntax and import errors."""
import ast
import os
import sys
import traceback

PROJECT_ROOT = r"c:\Users\MC\Downloads\5simTelegramBot-main\5simTelegramBot-main"
sys.path.insert(0, PROJECT_ROOT)

errors = []
warnings = []
ok_count = 0

def check_syntax(filepath):
    """Check Python syntax with ast.parse."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"

def check_imports(filepath):
    """Check if file can import its own dependencies (by walking ast)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports
    except:
        return []

# Walk all .py files
print("=" * 80)
print("PHASE 1 — FULL SOURCE CODE AUDIT")
print(f"Project Root: {PROJECT_ROOT}")
print("=" * 80)

for root, dirs, files in os.walk(PROJECT_ROOT):
    # Skip cache dirs
    dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
    for f in files:
        if not f.endswith('.py'):
            continue
        filepath = os.path.join(root, f)
        relpath = os.path.relpath(filepath, PROJECT_ROOT)
        
        # Check syntax
        ok, err = check_syntax(filepath)
        if not ok:
            errors.append((relpath, err))
            continue
        
        # Check imports
        imports = check_imports(filepath)
        ok_count += 1

print(f"\n✅ {ok_count} files pass syntax check")
if errors:
    print(f"\n❌ {len(errors)} SYNTAX ERRORS found:")
    for f, e in errors:
        print(f"   [{f}]: {e}")
else:
    print("✅ All files pass syntax check")

# Now check critical import resolution
print("\n" + "=" * 80)
print("IMPORT RESOLUTION CHECKS")
print("=" * 80)

import_checks = [
    ("config", "from config import BOT_CONFIG, PAYMENT_CONFIG, HEROSMS_CONFIG"),
    ("data.dto", "from data.dto import PaymentGateway, PaymentResultDTO, OrderStatus"),
    ("db.connection", "from db.connection import ConnectionManager"),
    ("db.schema", "from db.schema import ALL_TABLES, DEFAULT_SETTINGS, INDEXES"),
    ("db.context", "from db.context import db_context, DatabaseContext"),
    ("db.repositories.base", "from db.repositories.base import BaseRepository"),
    ("db.repositories.user_repository", "from db.repositories.user_repository import UserRepository"),
    ("db.repositories.transaction_repository", "from db.repositories.transaction_repository import TransactionRepository"),
    ("db.repositories.order_repository", "from db.repositories.order_repository import OrderRepository"),
    ("db.repositories.settings_repository", "from db.repositories.settings_repository import SettingsRepository"),
    ("db.repositories.card_payment_repository", "from db.repositories.card_payment_repository import CardPaymentRepository"),
    ("db.migrations", "from db.migrations import MigrationManager"),
    ("services.wallet_service", "from services.wallet_service import WalletService"),
    ("services.payment_service", "from services.payment_service import PaymentService, ZarinPalGateway, CardToCardGateway"),
    ("services.sms_service", "from services.sms_service import SMSService, HeroSMSProvider"),
    ("services.provider_registry", "from services.provider_registry import provider_registry"),
    ("services.event_bus", "from services.event_bus import event_bus"),
    ("services.cache_service", "from services.cache_service import CacheService"),
    ("services.settings_service", "from services.settings_service import SettingsService"),
    ("compat.legacy_facade", "from compat.legacy_facade import get_balance, sms_buy_number, sms_check_status"),
    ("i18n", "from i18n import get_text"),
    ("bot.middleware", "from bot.middleware import default_pipeline, auth_middleware"),
    ("bot.router", "from bot.router import router"),
    ("bot.error_handler", "from bot.error_handler import error_boundary"),
    ("web.health", "from web.health import health_bp"),
]

import_errors = []
import_ok = 0
for mod_name, import_stmt in import_checks:
    try:
        exec(import_stmt)
        import_ok += 1
        print(f"   ✅ {mod_name}")
    except Exception as e:
        import_errors.append((mod_name, str(e)))
        print(f"   ❌ {mod_name}: {e}")

print(f"\n✅ {import_ok}/{len(import_checks)} import checks passed")
if import_errors:
    print(f"❌ {len(import_errors)} import failures")

# Check tasks package
print("\n" + "=" * 80)
print("TASKS/CELERY CHECKS")
print("=" * 80)
try:
    import importlib as _il
    celery_app = _il.import_module('tasks').app
    print(f"   ✅ tasks.Celery app imported: {celery_app}")
    print(f"   ✅ Beat schedule: {len(celery_app.conf.beat_schedule)} tasks configured")
    for name, config in celery_app.conf.beat_schedule.items():
        print(f"      - {name}: {config}")
except Exception as e:
    print(f"   ❌ Celery import failed: {e}")

# Check for duplicate handlers
print("\n" + "=" * 80)
print("DUPLICATE HANDLER CHECK")
print("=" * 80)
from bot.router import router
cb_patterns = [p for p, _ in router._callback_handlers]
cmd_patterns = [c for c, _ in router._message_handlers]

# Find duplicates
from collections import Counter
cb_counts = Counter(cb_patterns)
cmd_counts = Counter(cmd_patterns)
dup_cb = {k: v for k, v in cb_counts.items() if v > 1}
dup_cmd = {k: v for k, v in cmd_counts.items() if v > 1}
if dup_cb:
    print(f"   ❌ DUPLICATE callback handlers: {dup_cb}")
else:
    print(f"   ✅ No duplicate callback handlers ({len(cb_patterns)} total)")
if dup_cmd:
    print(f"   ❌ DUPLICATE command handlers: {dup_cmd}")
else:
    print(f"   ✅ No duplicate command handlers ({len(cmd_patterns)} total)")

# Check for dead code / unused imports
print("\n" + "=" * 80)
print("DEAD CODE CHECK (common patterns)")
print("=" * 80)
dead_patterns = {}

# Check for files that import from non-existent modules
for root, dirs, files in os.walk(PROJECT_ROOT):
    dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
    for f in files:
        if not f.endswith('.py'):
            continue
        filepath = os.path.join(root, f)
        relpath = os.path.relpath(filepath, PROJECT_ROOT)
        try:
            with open(filepath, 'r', encoding='utf-8') as fh:
                source = fh.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module:
                        # Check if module exists
                        mod_path = node.module.replace('.', os.sep)
                        check_path = os.path.join(PROJECT_ROOT, mod_path + '.py')
                        check_path2 = os.path.join(PROJECT_ROOT, mod_path, '__init__.py')
                        if not os.path.exists(check_path) and not os.path.exists(check_path2):
                            dead_patterns.setdefault(relpath, []).append(node.module)
        except:
            pass

if dead_patterns:
    print(f"   ❌ POTENTIAL BROKEN IMPORTS:")
    for f, mods in dead_patterns.items():
        for m in mods:
            print(f"      [{f}] imports '{m}' (module may not exist)")
else:
    print("   ✅ No obvious broken imports")

# Check config.py validation
print("\n" + "=" * 80)
print("CONFIG VALIDATION")
print("=" * 80)
from config import validate_secrets, _missing_secrets
print(f"   Missing secrets: {sorted(_missing_secrets) if _missing_secrets else '(none)'}")
try:
    validate_secrets()
except RuntimeError as e:
    print(f"   ❌ Config validation raised: {e}")
else:
    print(f"   ✅ Config validation passed")

# Check alembic configuration
print("\n" + "=" * 80)
print("ALEMBIC VALIDATION")
print("=" * 80)
try:
    alembic_ini_path = os.path.join(PROJECT_ROOT, '..', 'alembic.ini')
    if os.path.exists(alembic_ini_path):
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(alembic_ini_path)
        print(f"   ✅ alembic.ini found")
        print(f"   ✅ script_location: {cfg.get('alembic', 'script_location', fallback='NOT SET')}")
    else:
        print(f"   ⚠️  alembic.ini not found at expected location")
except Exception as e:
    print(f"   ❌ Alembic config error: {e}")

# Check alembic versions
print("\n   Alembic versions:")
versions_dir = os.path.join(PROJECT_ROOT, 'alembic', 'versions')
if os.path.exists(versions_dir):
    for vf in sorted(os.listdir(versions_dir)):
        if vf.endswith('.py'):
            print(f"      - {vf}")
            vpath = os.path.join(versions_dir, vf)
            with open(vpath, 'r') as vfh:
                for line in vfh:
                    if 'revision' in line or 'down_revision' in line:
                        print(f"        {line.strip()}")

# Dual migration system check
print("\n" + "=" * 80)
print("DUAL MIGRATION SYSTEM CHECK")
print("=" * 80)
print("   ⚠️  Two migration systems detected:")
print("      1. db/migrations.py (MigrationManager — direct SQL)")
print("      2. alembic/ (Alembic — ORM-based)")
print("   ⚠️  Both migrators operate on the same database.")
print("   ⚠️  db/schema.py has ALL_TABLES (CREATE IF NOT EXISTS)")
print("   ⚠️  Alembic 001_initial_schema.py duplicates DDL.")
print("   ⚠️  MigrationManager creates _migrations table.")
print("   ⚠️  Alembic creates alembic_version table.")
print("   ⚠️  TWO separate version tracking tables — potential drift.")
print("   ⚠️  db.migrations.py uses MIGRATIONS list with versions 0-6")
print("   ⚠️  alembic/versions has versions 001-003")

# Check for wallet_ledger table missing from alembic
print("\n" + "=" * 80)
print("SCHEMA CONSISTENCY CHECK (ALL_TABLES vs Alembic)")
print("=" * 80)
from db.schema import ALL_TABLES
db_tables = set(ALL_TABLES.keys())
print(f"   Tables in ALL_TABLES: {len(db_tables)}")
# Check which are in 001_initial_schema
alembic_001_path = os.path.join(PROJECT_ROOT, 'alembic', 'versions', '001_initial_schema.py')
with open(alembic_001_path, 'r') as fh:
    alembic_content = fh.read()
import re
alembic_tables = set(re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)', alembic_content))
print(f"   Tables in Alembic 001: {len(alembic_tables)}")
missing_from_alembic = db_tables - alembic_tables
if missing_from_alembic:
    print(f"   ❌ Tables in ALL_TABLES but MISSING from Alembic 001:")
    for t in sorted(missing_from_alembic):
        print(f"      - {t}")
missing_from_db = alembic_tables - db_tables
if missing_from_db:
    print(f"   ⚠️  Tables in Alembic 001 but NOT in ALL_TABLES:")
    for t in sorted(missing_from_db):
        print(f"      - {t}")

print("\n" + "=" * 80)
print("AUDIT SUMMARY")
print("=" * 80)
total_issues = len(errors) + len(import_errors)
print(f"   Syntax errors: {len(errors)}")
print(f"   Import failures: {len(import_errors)}")
print(f"   Duplicate handlers: {len(dup_cb) + len(dup_cmd)}")
print(f"   Total issues found: {total_issues}")
print("=" * 80)
