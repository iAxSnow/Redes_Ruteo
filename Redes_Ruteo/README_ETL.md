# Proyecto Fase 2 — ETL Infraestructura, Metadata y Amenazas (RM, Chile)

Este repositorio contiene el pipeline **ETL** para construir una red geolocalizada OSM y enriquecerla con **metadata** (hidrantes, anchos, sentidos) y **amenazas** (reductores, incidentes/cierres, clima). La visualización se realiza con Leaflet.

## 1) Infraestructura (OSM)
- **Extract**: `infraestructura/osm_roads_overpass.py` (Overpass → `ways.geojson` y `nodes.geojson`)
- **Transform & Load**: `loaders/load_ways_nodes.py` (calcula `length_m`, estimación `width_m` si falta, carga `rr.nodes`/`rr.ways`)

Documentación: `docs/infra_ways.md`, `docs/infra_nodes.md`.

## 2) Metadata (3 fuentes)
1. **Hidrantes SISS**:  
   - ETL: `metadata/hydrants_siss_parse.py` → `hydrants_siss_inspections.json`, `hydrants_siss_summary.json`  
   - Loaders: `loaders/load_hydrants_siss.py`, `loaders/load_hydrants_summary.py`
2. **Ancho de vías OSM**:  
   - ETL: `metadata/road_widths_osm.py` → `road_widths.geojson`  
   - Loader: `loaders/load_widths.py` (actualiza `rr.ways.width_m`)
3. **Sentido de vías OSM**:  
   - ETL: `metadata/road_oneway_osm_chunks.py` → `road_oneway.geojson`  
   - Loader: `loaders/load_oneway.py` (actualiza `rr.ways.oneway`)

Documentación: `docs/metadata_hydrants_siss_inspections.md`, `docs/metadata_hydrants_siss_summary.md`, `docs/metadata_road_widths.md`, `docs/metadata_road_oneway.md`.

## 3) Amenazas (3 fuentes)
- **Reductores (OSM)**: `amenazas/traffic_calming_as_threats.py` → `traffic_calming_threats.geojson` → carga en `rr.threats_incidents`.
- **Incidentes/Cierres (TomTom o Waze)**:  
  - TomTom: `amenazas/tomtom_incidents.py` → `tomtom_incidents.geojson` → `loaders/load_threats_tomtom.py`.  
  - Waze (experimental): `amenazas/waze_incidents.py` → `waze_incidents.geojson` → `loaders/load_threats_waze.py`.
- **Clima (OpenWeather)**: `amenazas/weather_openweather.py` → `weather_threats.geojson` → `loaders/load_threats_weather.py`.

Documentación: `docs/threat_traffic_calming.md`, `docs/threat_tomtom_incidents.md`, `docs/threat_weather_openweather.md`, `docs/threat_waze_incidents.md`.

## 4) BD y Ruteo
- Esquema: `schema.sql` (incluye `rr.nodes`, `rr.ways`, tablas de metadata y amenazas).  
- Vista de costo base (peor caso): `ways_cost_length` (longitud).  
- Export de ruta ejemplo con `pgr_dijkstra`: `scripts/export_route_example.py` → `site/data/route.geojson`.

## 5) Visualización
- Sitio estático Leaflet: `site/index.html` (muestra red/route + capas de metadata/amenazas).  
- Servir con: `cd site && python -m http.server 8000`.

## 6) Ejecución sugerida (orden)
1. Levantar DB (`docker-compose.yml`) y correr `schema.sql` (DBeaver).  
2. Infraestructura: `osm_roads_overpass.py` → `load_ways_nodes.py`.  
3. Metadata:  
   - `hydrants_siss_parse.py` → `load_hydrants_siss.py` y `load_hydrants_summary.py`  
   - `road_widths_osm.py` → `load_widths.py`  
   - `road_oneway_osm_chunks.py` → `load_oneway.py`  
4. Amenazas (uno o varios):  
   - `traffic_calming_as_threats.py`  
   - `tomtom_incidents.py` → `load_threats_tomtom.py` **/o** `waze_incidents.py` → `load_threats_waze.py`  
   - `weather_openweather.py` → `load_threats_weather.py`  
5. Ruta ejemplo: `scripts/export_route_example.py`  
6. Visualizar: `site/index.html`

## 7) Variables de entorno (ejemplos)
```
PGHOST=localhost
PGPORT=5432
PGDATABASE=rr
PGUSER=postgres
PGPASSWORD=postgres

BBOX_S=-34.3
BBOX_W=-71.8
BBOX_N=-32.6
BBOX_E=-70.2

OPENWEATHER_KEY=***         # no subir al repo
WEATHER_GRID=0.02
RAIN_MM_H=3.0
WIND_MS=12.0
```

> En Fase 3 se integrarán las **penalizaciones de costo** en función de metadata/amenazas para obtener rutas resilientes.
