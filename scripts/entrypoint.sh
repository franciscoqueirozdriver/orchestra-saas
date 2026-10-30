#!/bin/sh
set -eu
python -m app.wait_for_db
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  alembic upgrade head
fi
exec "$@"
