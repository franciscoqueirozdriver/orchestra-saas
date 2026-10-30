#!/usr/bin/env bash
set -euo pipefail
: "${APP_DB_USER:?APP_DB_USER obrigatório}"
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD obrigatório}"

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 \
  --set app_user="$APP_DB_USER" --set app_pass="$APP_DB_PASSWORD" --set app_db="$POSTGRES_DB" <<'SQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_pass';
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL PRIVILEGES ON SCHEMA public TO :"app_user";
ALTER DATABASE :"app_db" OWNER TO :"app_user";
SQL
