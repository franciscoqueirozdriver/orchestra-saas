#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# The local working copy and GitHub are the source; refuse drift before effects.
git rev-parse --is-inside-work-tree >/dev/null
checkout_status=$(git status --porcelain --untracked-files=all)
if [[ -n "$checkout_status" ]]; then
  echo "Publicação recusada: checkout com alterações pendentes." >&2
  exit 1
fi
if [[ -n "${ORCHESTRA_EXPECTED_COMMIT:-}" ]] && [[ "$(git rev-parse HEAD)" != "$ORCHESTRA_EXPECTED_COMMIT" ]]; then
  echo "HEAD difere do commit validado." >&2
  exit 1
fi
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
