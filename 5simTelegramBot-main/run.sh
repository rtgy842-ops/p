#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# run.sh — NumGenius Enterprise SaaS Docker Launcher
# ═══════════════════════════════════════════════════════════════
# chmod +x run.sh
# ./run.sh full       # Start every service
# ./run.sh stop       # Stop everything
# ./run.sh restart    # Restart all
# ./run.sh status     # Show container status
# ./run.sh logs       # Tail all logs
# ./run.sh logs bot   # Tail specific service
# ./run.sh build      # Rebuild images
# ═══════════════════════════════════════════════════════════════

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

[ -f .env ] || { err ".env not found — copy .env.example to .env and fill values"; exit 1; }

case "${1:-full}" in

  full)
    info "Starting ALL services (customer + admin + workers)..."
    docker compose --profile full up -d --build --remove-orphans
    sleep 5
    log "All services started"
    echo ""
    echo "  🟢 Customer Bot:  https://api.abunumapp.com"
    echo "  🟢 Admin Bot:     https://admin.abunumapp.com"
    echo "  🟢 Web Panel:     https://api.abunumapp.com/admin?token=ADMIN_API_TOKEN"
    echo ""
    ;;

  customer)
    info "Starting Customer Bot only..."
    docker compose --profile customer up -d --build
    log "Customer Bot running"
    ;;

  admin)
    info "Starting Admin Bot only..."
    docker compose --profile admin up -d --build
    log "Admin Bot running"
    ;;

  worker)
    info "Starting Celery workers only..."
    docker compose --profile worker up -d --build
    log "Workers running"
    ;;

  stop)
    info "Stopping all services..."
    docker compose --profile full down
    log "All services stopped"
    ;;

  restart)
    info "Restarting..."
    docker compose --profile full down
    docker compose --profile full up -d --build
    log "Restarted"
    ;;

  build)
    info "Rebuilding all Docker images..."
    docker compose --profile full build --no-cache
    log "Build complete"
    ;;

  status)
    docker compose ps
    ;;

  logs)
    svc="${2:-}"
    if [ -n "$svc" ]; then
      docker compose logs -f --tail=100 "$svc"
    else
      docker compose logs -f --tail=100
    fi
    ;;

  migrate)
    info "Running DB migrations..."
    docker compose run --rm customer_bot python -c "
from database import setup_databases; setup_databases()
from db.migrations import MigrationManager
MigrationManager().migrate()
print('Migrations applied')
"
    log "Done"
    ;;

  health)
    info "Checking provider health..."
    docker compose run --rm worker python -c "
from services.provider_registry import provider_registry
from services.sms_service import HeroSMSProvider
provider_registry.register(HeroSMSProvider(),'HeroSMS',priority=1)
print(provider_registry.health_check_all())
"
    ;;

  *)
    echo "NumGenius Enterprise — Docker Launcher"
    echo ""
    echo "Usage: ./run.sh <command> [args]"
    echo ""
    echo "Commands:"
    echo "  full         Start everything (customer + admin + workers)"
    echo "  customer     Start Customer Bot only"
    echo "  admin        Start Admin Bot only"
    echo "  worker       Start Celery workers only"
    echo "  stop         Stop all services"
    echo "  restart      Restart everything"
    echo "  build        Rebuild all Docker images"
    echo "  status       Show container status"
    echo "  logs [svc]   Tail logs (customer_bot, admin_bot, worker, beat)"
    echo "  migrate      Run database migrations"
    echo "  health       Check provider health status"
    ;;
esac
