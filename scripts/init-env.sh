#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ -e .env ]; then
  echo ".env já existe; não será sobrescrito." >&2
  exit 1
fi
if [ "$(id -u)" -eq 0 ]; then
  echo "Execute com usuário não-root; use sudo apenas para configuração do servidor." >&2
  exit 1
fi
printf "URL pública HTTPS deste sistema (ex.: https://app.seudominio.com): "
IFS= read -r PUBLIC_BASE_URL
case "$PUBLIC_BASE_URL" in
  https://*) ;;
  *) echo "A URL pública precisa começar com https://" >&2; exit 1 ;;
esac
PUBLIC_DOMAIN=${PUBLIC_BASE_URL#https://}
PUBLIC_DOMAIN=${PUBLIC_DOMAIN%/}
if ! PUBLIC_DOMAIN=$(python3 - "$PUBLIC_DOMAIN" <<'PY'
import ipaddress
import re
import sys
host = sys.argv[1].rstrip(".").lower()
labels = host.split(".")
valid = (len(host) <= 253 and len(labels) >= 2 and all(
    1 <= len(label) <= 63 and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
    for label in labels
))
try:
    ipaddress.ip_address(host)
    valid = False
except ValueError:
    pass
if not valid:
    print("Informe um domínio DNS público válido, sem porta, caminho, query, fragmento ou IP.", file=sys.stderr)
    raise SystemExit(1)
print(host)
PY
); then
  exit 1
fi
PUBLIC_BASE_URL="https://${PUBLIC_DOMAIN}"
POSTGRES_PASSWORD=$(openssl rand -hex 32)
APP_DB_PASSWORD=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 48)
CREDENTIALS_ENCRYPTION_KEY=$(python3 -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())')
cat > .env <<EOF
POSTGRES_DB=orquestra
POSTGRES_USER=orquestra_admin
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
APP_DB_USER=orquestra_app
APP_DB_PASSWORD=${APP_DB_PASSWORD}
JWT_SECRET=${JWT_SECRET}
CREDENTIALS_ENCRYPTION_KEY=${CREDENTIALS_ENCRYPTION_KEY}
PUBLIC_BASE_URL=${PUBLIC_BASE_URL}
PUBLIC_DOMAIN=${PUBLIC_DOMAIN}
ZAPI_API_BASE_URL=https://api.z-api.io
ACCESS_TOKEN_MINUTES=30
ENVIRONMENT=production
UPLOAD_MAX_MB=20
EMBEDDING_DIMENSIONS=1536
MESSAGE_GROUP_WINDOW_SECONDS=3
MEDIA_DIR=/app/data/media
EOF
chmod 600 .env
echo ".env criado com senhas aleatórias e permissão 600. As chaves Z-API/LLM serão inseridas pelo painel."
