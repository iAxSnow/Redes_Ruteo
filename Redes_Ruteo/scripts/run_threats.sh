#!/usr/bin/env bash
set -euo pipefail

echo "[1/6] OSM traffic calming…"
python amenazas/traffic_calming_as_threats.py
echo "[2/6] Load calming → DB…"
python loaders/load_threats_calming.py

echo "[3/6] Waze incidents…"
python amenazas/waze_incidents.py || echo "[warn] Waze extractor terminó con advertencias"
if [[ -f "amenazas/waze_incidents.geojson" ]]; then
  echo "[ETL] Waze features: $(jq '.features|length' amenazas/waze_incidents.geojson 2>/dev/null || echo '?')"
fi
echo "[4/6] Load Waze → DB…"
python loaders/load_threats_waze.py

echo "[5/6] Weather threats…"
python amenazas/weather_openweather.py
echo "[6/6] Load weather → DB…"
python loaders/load_threats_weather.py

echo "[OK] Amenazas listas."
