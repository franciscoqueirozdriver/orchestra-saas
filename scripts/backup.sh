#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_ENV_FILE="${BACKUP_ENV_FILE:-$HOME/.config/orquestra-backup/env}"
if [[ -f "$BACKUP_ENV_FILE" ]]; then set -a; source "$BACKUP_ENV_FILE"; set +a; fi
: "${BACKUP_PASSPHRASE:?Defina BACKUP_PASSPHRASE em arquivo local protegido}"
BACKUP_DIR="${BACKUP_DIR:-$PWD/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
umask 077
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DB_TMP="$BACKUP_DIR/.orquestra-db-${STAMP}.dump.enc.tmp"
DATA_TMP="$BACKUP_DIR/.orquestra-data-${STAMP}.tar.gz.enc.tmp"
trap 'rm -f "$DB_TMP" "$DATA_TMP"' EXIT

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges' \
  | openssl enc -aes-256-cbc -pbkdf2 -iter 250000 -salt -md sha256 -pass env:BACKUP_PASSPHRASE -out "$DB_TMP"
test -s "$DB_TMP"
docker compose exec -T api tar -C /app/data -czf - . \
  | openssl enc -aes-256-cbc -pbkdf2 -iter 250000 -salt -md sha256 -pass env:BACKUP_PASSPHRASE -out "$DATA_TMP"
test -s "$DATA_TMP"
mv "$DB_TMP" "$BACKUP_DIR/orquestra-db-${STAMP}.dump.enc"
mv "$DATA_TMP" "$BACKUP_DIR/orquestra-data-${STAMP}.tar.gz.enc"
sha256sum "$BACKUP_DIR/orquestra-db-${STAMP}.dump.enc" "$BACKUP_DIR/orquestra-data-${STAMP}.tar.gz.enc" > "$BACKUP_DIR/orquestra-${STAMP}.sha256"
chmod 600 "$BACKUP_DIR/orquestra-db-${STAMP}.dump.enc" \
  "$BACKUP_DIR/orquestra-data-${STAMP}.tar.gz.enc" "$BACKUP_DIR/orquestra-${STAMP}.sha256"
find "$BACKUP_DIR" -type f -mtime "+${KEEP_DAYS}" -delete
echo "Backup criptografado criado em $BACKUP_DIR (UTC $STAMP)."
echo "Copie arquivos e checksums para armazenamento externo; guarde a passphrase fora desta VPS."
