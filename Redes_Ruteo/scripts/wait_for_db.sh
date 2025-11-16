#!/usr/bin/env bash
# scripts/wait_for_db.sh CONTAINER TIMEOUT_SECONDS
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Uso: $0 <container_name> <timeout_seconds>" >&2
  exit 1
fi

C="$1"
T="$2"
echo "[wait_for_db] Esperando a que Postgres en contenedor '$C' esté listo (timeout ${T}s)…"
SECS=0
until docker exec "$C" pg_isready -U "${PGUSER:-postgres}" -h localhost >/dev/null 2>&1; do
  sleep 2
  SECS=$((SECS+2))
  if (( SECS >= T )); then
    echo "[ERROR] Timeout esperando a la BD (${T}s)" >&2
    exit 1
  fi
done
echo "[wait_for_db] OK"
