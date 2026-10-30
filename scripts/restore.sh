#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -lt 1 || $# -gt 2 ]]; then echo "Uso: $0 <backup-db.dump.enc> [backup-data.tar.gz.enc]" >&2; exit 2; fi
DB_BACKUP=$(realpath "$1")
DATA_BACKUP="${2:-}"
[[ -s "$DB_BACKUP" ]] || { echo "Backup do banco não encontrado ou vazio." >&2; exit 1; }
if [[ -n "$DATA_BACKUP" ]]; then DATA_BACKUP=$(realpath "$DATA_BACKUP"); [[ -s "$DATA_BACKUP" ]] || { echo "Backup de dados não encontrado ou vazio." >&2; exit 1; }; fi
BACKUP_ENV_FILE="${BACKUP_ENV_FILE:-$HOME/.config/orquestra-backup/env}"
if [[ -f "$BACKUP_ENV_FILE" ]]; then set -a; source "$BACKUP_ENV_FILE"; set +a; fi
: "${BACKUP_PASSPHRASE:?Defina BACKUP_PASSPHRASE em arquivo local protegido}"

# Valida a senha de backup e os formatos antes de parar a aplicação.
openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -salt -md sha256 -pass env:BACKUP_PASSPHRASE -in "$DB_BACKUP" \
  | docker compose exec -T db sh -c 'pg_restore --list -' >/dev/null
if [[ -n "$DATA_BACKUP" ]]; then
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -salt -md sha256 -pass env:BACKUP_PASSPHRASE -in "$DATA_BACKUP" | tar -tzf - >/dev/null
fi
cat <<'WARNING'
ATENÇÃO: a restauração substitui dados atuais no PostgreSQL.
Se fornecido, o arquivo app_data também substitui o volume atual.
WARNING
read -r -p "Digite RESTAURAR para continuar: " CONFIRM
[[ "$CONFIRM" == "RESTAURAR" ]] || { echo "Cancelado."; exit 1; }

docker compose stop api worker
openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -salt -md sha256 -pass env:BACKUP_PASSPHRASE -in "$DB_BACKUP" \
  | docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges --exit-on-error -'
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" --set app_user="$APP_DB_USER"' <<'SQL'
SELECT format('ALTER TABLE %I.%I OWNER TO %I', schemaname, tablename, :'app_user')
FROM pg_tables WHERE schemaname = 'public' \gexec
SELECT format('ALTER SEQUENCE %I.%I OWNER TO %I', schemaname, sequencename, :'app_user')
FROM pg_sequences WHERE schemaname = 'public' \gexec
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO :"app_user";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :"app_user";
GRANT ALL PRIVILEGES ON SCHEMA public TO :"app_user";
SQL
if [[ -n "$DATA_BACKUP" ]]; then
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 250000 -salt -md sha256 -pass env:BACKUP_PASSPHRASE -in "$DATA_BACKUP" \
    | docker compose run --rm --no-deps --entrypoint sh api -c 'python -c '\''from pathlib import Path; import shutil; root=Path("/app/data"); [shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink() for p in root.iterdir()]'\'' && tar -xzf - -C /app/data'
fi
docker compose up -d api worker
echo "Restauração concluída; verifique /health, migrações e estado dos workers."
