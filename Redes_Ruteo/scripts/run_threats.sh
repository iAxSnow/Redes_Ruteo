#!/usr/bin/env bash
set -euo pipefail

echo "[1/6] OSM traffic calming…"
PY_BIN="python"
if ! command -v "$PY_BIN" >/dev/null 2>&1; then
  PY_BIN="python3"
fi
"$PY_BIN" amenazas/traffic_calming_as_threats_parallel.py
echo "[2/6] Load calming → DB…"
python loaders/load_threats_calming.py

echo "[3/6] Waze incidents…"
"$PY_BIN" amenazas/waze_incidents_parallel_adaptive.py || echo "[warn] Waze extractor terminó con advertencias"
echo "[4/6] Load Waze → DB…"
python loaders/load_threats_waze.py

echo "[5/6] Weather threats…"
"$PY_BIN" amenazas/weather_openweather_parallel.py
echo "[6/6] Load weather → DB…"
python loaders/load_threats_weather.py

echo "[OK] Amenazas listas."
