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
# A normal controlled publication always starts paused, even if .env says true.
# An explicitly authorized pilot must pass both settings below.
if [[ "${ORCHESTRA_ALLOW_OUTBOUND_DEPLOY:-no}" != "yes" ]]; then
  export OUTBOUND_ENABLED=false
fi
command -v docker >/dev/null
docker compose version >/dev/null
[[ -f .env ]] || { echo "Execute ./scripts/init-env.sh primeiro." >&2; exit 1; }
chmod 600 .env
docker compose config --quiet
release_commit=$(git rev-parse HEAD)
docker compose build --pull --build-arg "VCS_REF=$release_commit" api
docker compose up -d --wait --wait-timeout 180 db redis
# Nenhum worker deve executar tarefas enquanto o schema é atualizado.
docker compose stop scheduler worker api
docker compose up -d --wait --wait-timeout 180 api
docker compose up -d --wait --wait-timeout 180 worker scheduler web
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

reference_image=$(docker inspect --format '{{.Image}}' "$(docker compose ps -q api)")
for service in api worker scheduler; do
  container_id=$(docker compose ps -q "$service")
  actual_image=$(docker inspect --format '{{.Image}}' "$container_id")
  actual_revision=$(docker inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$container_id")
  if [[ "$actual_image" != "$reference_image" || "$actual_revision" != "$release_commit" ]]; then
    echo "Imagem/revisão divergente no serviço $service; publicação requer revisão." >&2
    exit 1
  fi
done
echo "Serviços iniciados na mesma imagem/revisão. Confira HTTPS, scheduler e pausa global antes do piloto."
