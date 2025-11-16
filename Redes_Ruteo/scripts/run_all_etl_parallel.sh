#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

log(){ printf "\n\033[1;34m[ETL-PAR]\033[0m %s\n" "$*"; }
warn(){ printf "\n\033[1;33m[WARN]\033[0m %s\n" "$*"; }
runpy(){ local f="$1"; shift || true; if [[ -f "$f" ]]; then log "python $f $*"; python "$f" "$@"; else warn "No existe $f"; fi; }

# Load env & venv
if [[ -f ".env" ]]; then set -a; source .env; set +a; fi
if [[ -f ".venv/bin/activate" ]]; then source .venv/bin/activate; fi

# Infraestructura
log "Infraestructura paralela"
runpy infraestructura/osm_roads_overpass_parallel.py
runpy loaders/load_ways_nodes.py

# Metadata
log "Metadata — widths paralelo"
runpy metadata/road_widths_osm_parallel.py
runpy loaders/load_widths.py

log "Metadata — oneway paralelo"
runpy metadata/road_oneway_osm_parallel.py
runpy loaders/load_oneway.py

log "Metadata — hidrantes SISS"
runpy metadata/hydrants_siss_parse.py
runpy loaders/load_hydrants_siss.py
runpy loaders/load_hydrants_summary.py

# Amenazas
log "Amenazas — calming paralelo"
runpy amenazas/traffic_calming_as_threats_parallel.py
runpy loaders/load_threats_calming.py

log "Amenazas — Waze paralelo"
runpy amenazas/waze_incidents_parallel_adaptive.py || warn "Waze extractor warning"
runpy loaders/load_threats_waze.py

log "Amenazas — Weather paralelo"
runpy amenazas/weather_openweather_parallel.py || warn "Weather extractor warning (API key may not be activated yet)"
runpy loaders/load_threats_weather.py

# Exportar capas y abrir sitio
log "Export → site/data"
bash scripts/export_all_to_site.sh || true

log "Levantar sitio en :5000"
if command -v fuser >/dev/null 2>&1; then fuser -k 5000/tcp >/dev/null 2>&1 || true; fi
nohup python app.py >/dev/null 2>&1 &
echo $! > .flask_server_pid
sleep 2
URL="http://localhost:5000"
log "Sitio en: $URL"
if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true; fi

log "ETL paralelo COMPLETO ✅"
