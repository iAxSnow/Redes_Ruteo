#!/usr/bin/env bash
set -euo pipefail

# ===============================
# main.sh — Bootstrap completo
# - Crea/activa venv
# - Instala requirements
# - Levanta Postgres (pgRouting) con Docker
# - Crea BD y aplica schema.sql
# - Ejecuta ETL (paralelo si existe el script)
# - (Opcional) Inicia el sitio
# ===============================

# --- Config ---
: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGDATABASE:=rr}"
: "${PGUSER:=postgres}"
: "${PGPASSWORD:=postgres}"
: "${DB_CONTAINER:=rr_db}"
: "${SITE_PORT:=5000}"
: "${START_SITE:=false}"   # true para arrancar sitio al final

# Cargar .env si existe
if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

echo "[main] Entorno:"
echo "  PGHOST=$PGHOST PGPORT=$PGPORT PGDATABASE=$PGDATABASE PGUSER=$PGUSER"
echo "  DB_CONTAINER=$DB_CONTAINER"

# --- 1) Python venv + requirements ---
if [[ ! -d ".venv" ]]; then
  echo "[main] Creando entorno .venv"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
if [[ -f "requirements.txt" ]]; then
  echo "[main] Instalando requirements.txt"
  pip install -r requirements.txt
else
  echo "[warn] No se encontró requirements.txt — continuando…"
fi

# --- 2) Docker + Postgres (pgRouting) ---
if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] Docker no está instalado. Instálalo antes de continuar." >&2
  exit 1
fi

# docker-compose.yml debe existir en la raíz
if [[ ! -f "docker-compose.yml" ]]; then
  echo "[ERROR] No se encontró docker-compose.yml en la raíz." >&2
  exit 2
fi

echo "[main] Levantando base con docker compose…"
docker compose up -d

# --- 3) Esperar a que la BD esté lista ---
bash scripts/wait_for_db.sh "$DB_CONTAINER" 60

# --- 4) Crear BD (si no existe) y aplicar schema.sql ---
echo "[main] Creando BD (si falta)…"
docker exec -e PGPASSWORD="$PGPASSWORD" "$DB_CONTAINER" \
  psql -U "$PGUSER" -h localhost -tc "SELECT 1 FROM pg_database WHERE datname='${PGDATABASE}'" | grep -q 1 \
  || docker exec -e PGPASSWORD="$PGPASSWORD" "$DB_CONTAINER" \
       psql -U "$PGUSER" -h localhost -c "CREATE DATABASE ${PGDATABASE};"

if [[ ! -f "schema.sql" ]]; then
  echo "[ERROR] No se encontró schema.sql en la raíz del repo." >&2
  exit 3
fi

echo "[main] Aplicando schema.sql…"
# Usamos psql dentro del contenedor para evitar requerir psql en el host
docker exec -i -e PGPASSWORD="$PGPASSWORD" "$DB_CONTAINER" \
  psql -U "$PGUSER" -h localhost -d "$PGDATABASE" < schema.sql

# --- 5) Ejecutar ETL ---
if [[ -x "scripts/run_all_etl_parallel.sh" ]]; then
  echo "[main] Ejecutando scripts/run_all_etl_parallel.sh"
  bash scripts/run_all_etl_parallel.sh
elif [[ -x "scripts/run_all_etl.sh" ]]; then
  echo "[main] Ejecutando scripts/run_all_etl.sh"
  bash scripts/run_all_etl.sh
else
  echo "[warn] No hay runner ETL (scripts/run_all_etl_parallel.sh ni scripts/run_all_etl.sh)."
  echo "       Ejecuta manualmente tus scripts de infraestructura/metadata/amenazas."
fi

# --- 6) (Opcional) Levantar sitio ---
if [[ "${START_SITE}" == "true" ]]; then
  if [[ -f "site/app.py" ]]; then
    echo "[main] Iniciando Flask en puerto ${SITE_PORT}…"
    FLASK_APP=site/app.py flask run --host=0.0.0.0 --port="${SITE_PORT}"
  elif [[ -f "site/index.html" ]]; then
    echo "[main] Sirviendo sitio estático en puerto ${SITE_PORT}…"
    ( cd site && python -m http.server "${SITE_PORT}" )
  else
    echo "[warn] No se encontró site/app.py ni site/index.html; omitiendo sitio."
  fi
else
  echo "[main] START_SITE=false — omitiendo levantar sitio."
fi

echo "[main] Todo listo."
