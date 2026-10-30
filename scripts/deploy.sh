#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

command -v docker >/dev/null
docker compose version >/dev/null
[[ -f .env ]] || { echo "Execute ./scripts/init-env.sh primeiro." >&2; exit 1; }
chmod 600 .env
docker compose config --quiet
docker compose build --pull api worker
docker compose up -d --wait --wait-timeout 180 db redis
# Nenhum worker deve executar tarefas enquanto o schema é atualizado.
docker compose stop worker api
docker compose up -d --wait --wait-timeout 180 api
docker compose up -d --wait --wait-timeout 180 worker web
for attempt in {1..12}; do
  if docker compose exec -T worker celery -A app.tasks.celery_app inspect ping --timeout 5; then
    break
  fi
  if [[ "$attempt" -eq 12 ]]; then
    echo "Worker não respondeu; consulte docker compose logs worker." >&2
    exit 1
  fi
  sleep 5
done
docker compose ps
echo "Serviços iniciados. Valide o domínio HTTPS e crie o administrador conforme docs/deploy-hostinger.md."
