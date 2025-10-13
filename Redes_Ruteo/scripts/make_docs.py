#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCS.mkdir(parents=True, exist_ok=True)

files = {
    DOCS / "infra_ways.md": r"""
# ways.geojson — Infraestructura OSM (aristas)

**Archivo:** `infraestructura/ways.geojson`  
**Tipo:** GeoJSON `FeatureCollection` de `LineString` (EPSG:4326)

## Esquema de `properties` por Feature

| Campo            | Tipo                 | Unidades/valores                | ¿Null? | Descripción |
|------------------|----------------------|----------------------------------|--------|-------------|
| id               | int                  | —                                | no     | Identificador interno (igual a `osm_id`). |
| osm_id           | int                  | —                                | no     | ID del way en OpenStreetMap. |
| source           | int                  | —                                | no     | ID de nodo origen para pgRouting (corresponde a `nodes.id`). |
| target           | int                  | —                                | no     | ID de nodo destino para pgRouting. |
| highway          | string               | ej. `residential`, `primary`     | sí     | Clasificación OSM del tipo de vía. |
| oneway           | boolean              | `true`/`false`                   | sí     | Si la vía es unidireccional. |
| maxspeed_kmh     | int                  | km/h                             | sí     | Límite de velocidad informado en OSM. |
| lanes            | int                  | número                           | sí     | Cantidad de carriles (si existe en OSM). |
| width_raw        | string               | texto libre                      | sí     | Valor original OSM del ancho (sin normalizar). |
| maxwidth_raw     | string               | texto libre                      | sí     | Restricción de ancho original OSM. |
| surface          | string               | ej. `asphalt`, `unpaved`         | sí     | Superficie de la vía (OSM). |
| access           | string               | ej. `no`, `permissive`           | sí     | Restricciones de acceso (OSM). |
| tags             | object (JSON)        | —                                | sí     | Resto de tags OSM asociados al way. |

**Geometry:** `LineString` con coordenadas `[lon, lat]` en WGS84.

## Ejemplo mínimo
```json
{
  "type": "Feature",
  "id": 123,
  "geometry": { "type": "LineString", "coordinates": [[-70.7,-33.45],[-70.69,-33.44]] },
  "properties": {
    "id": 123, "osm_id": 123, "source": 111, "target": 222,
    "highway": "residential", "oneway": false,
    "maxspeed_kmh": 50, "lanes": 2,
    "width_raw": "7", "maxwidth_raw": null,
    "surface": "asphalt", "access": null,
    "tags": { "name": "Calle Falsa 123" }
  }
}
```

**Procedencia:** Overpass API (OSM).  
**Actualización:** cuando se ejecute `infraestructura/osm_roads_overpass.py`.  
**Uso:** base del grafo de ruteo, enriquecido luego en BD con `length_m`, `width_m`, `oneway`, etc.
""",
    DOCS / "infra_nodes.md": r"""
# nodes.geojson — Infraestructura OSM (nodos)

**Archivo:** `infraestructura/nodes.geojson`  
**Tipo:** GeoJSON `FeatureCollection` de `Point` (EPSG:4326)

## Esquema de `properties`

| Campo | Tipo | ¿Null? | Descripción |
|------|------|--------|-------------|
| id   | int  | no     | ID del nodo OSM (coincide con vértice que usan `source/target` en ways). |

**Geometry:** `Point` `[lon, lat]`.

## Ejemplo
```json
{
  "type": "Feature",
  "id": 111,
  "geometry": { "type": "Point", "coordinates": [-70.7, -33.45] },
  "properties": { "id": 111 }
}
```

**Procedencia:** Overpass API (OSM).  
**Uso:** generación de vértices para pgRouting.
""",
    DOCS / "metadata_hydrants_siss_inspections.md": r"""
# hydrants_siss_inspections.json — Inspecciones de grifos (SISS)

**Archivo:** `metadata/hydrants_siss_inspections.json`  
**Tipo:** JSON array de objetos (uno por inspección, sin geometría)

## Campos por objeto

| Campo                 | Tipo                    | ¿Null? | Descripción |
|-----------------------|-------------------------|--------|-------------|
| rut_empresa           | string                  | sí     | RUT de la sanitaria. |
| empresa               | string                  | sí     | Nombre de la sanitaria. |
| periodo               | int                     | sí     | Período reportado (AAAAMM o similar). |
| codigo_comuna         | int                     | sí     | Código comuna según SISS. |
| nombre_comuna         | string                  | sí     | Nombre comuna. |
| codigo_localidad      | int                     | sí     | Código localidad SISS. |
| nombre_localidad      | string                  | sí     | Nombre localidad. |
| codigo_grifo          | string                  | sí     | Identificador del grifo dentro del reporte. |
| direccion             | string                  | sí     | Dirección de referencia. |
| referencia            | string                  | sí     | Observaciones. |
| fecha_inspeccion      | timestamp ISO8601       | sí     | Fecha de inspección (normalizada). |
| hora_medicion         | string                  | sí     | Hora de medición. |
| presion               | number                  | sí     | Presión medida (kPa o según reporte; en BD se deja `numeric`). |
| cumple_presion        | boolean                 | sí     | Cumple umbral de presión. |
| cumple_caudal         | boolean                 | sí     | Cumple umbral de caudal. |
| opera_vastago         | boolean                 | sí     | Vástago operativo. |
| valvula_pie_operativa | boolean                 | sí     | Válvula de pie operativa. |
| fuga_agua             | boolean                 | sí     | Presencia de fuga. |
| estado_calc           | string (categoría)      | sí     | Heurística: `VIGENTE_APTO` / `VIGENTE_CON_OBSERV` / `NO_OPERATIVO`. |
| raw                   | object                  | sí     | Fila original normalizada (auditoría). |

## Ejemplo
```json
{
  "rut_empresa":"76.XXXXX-0",
  "empresa":"Aguas X",
  "periodo":202406,
  "codigo_comuna":13101,
  "nombre_comuna":"Santiago",
  "codigo_grifo":"G-123",
  "direccion":"Av. Siempre Viva 742",
  "fecha_inspeccion":"2024-06-15T00:00:00Z",
  "presion": 350,
  "cumple_presion": true,
  "cumple_caudal": true,
  "estado_calc":"VIGENTE_APTO",
  "raw":{ "...": "..." }
}
```

**Procedencia:** Excel SISS `PR036001_ESTADO_DE_GRIFOS_202406_202506.xlsx`, hoja “2-Inspección Grifos”.  
**ETL:** `metadata/hydrants_siss_parse.py`.  
**Uso:** calidad operativa por registro; *join* por comuna/localidad o cruce espacial en Fase 3.
""",
    DOCS / "metadata_hydrants_siss_summary.md": r"""
# hydrants_siss_summary.json — Resumen por comuna/localidad (SISS)

**Archivo:** `metadata/hydrants_siss_summary.json`  
**Tipo:** JSON array de objetos (sin geometría)

## Campos por objeto

| Campo                | Tipo   | ¿Null? | Descripción |
|----------------------|--------|--------|-------------|
| periodo              | int    | sí     | Período del reporte. |
| codigo_comuna        | int    | sí     | Código comuna. |
| nombre_comuna        | string | sí     | Nombre comuna. |
| codigo_localidad     | int    | sí     | Código localidad. |
| nombre_localidad     | string | sí     | Nombre localidad. |
| grifos_existente     | int    | sí     | Total grifos existentes. |
| grifos_no_operativos | int    | sí     | Grifos no operativos. |
| grifos_reparados     | int    | sí     | Cantidad reparados. |
| grifos_reemplazados  | int    | sí     | Cantidad reemplazados. |
| grifos_reparar       | int    | sí     | Plan de reparar. |
| grifos_reemplazar    | int    | sí     | Plan de reemplazar. |
| inversion_total      | number | sí     | Monto total (si reporta). |
| inversion_programada | number | sí     | Monto programado. |
| tasa_no_operativos   | number | sí     | `grifos_no_operativos / grifos_existente`. |
| tasa_a_reparar       | number | sí     | `grifos_reparar / grifros_existente`. |
| tasa_a_reemplazar    | number | sí     | `grifos_reemplazar / grifros_existente`. |
| raw                  | object | sí     | Fila original. |

## Ejemplo
```json
{
  "periodo":202406,
  "codigo_comuna":13101,
  "nombre_comuna":"Santiago",
  "grifos_existente":1200,
  "grifos_no_operativos":48,
  "tasa_no_operativos":0.04,
  "raw":{ "...":"..." }
}
```

**Procedencia:** Excel SISS, hoja “3-Estado Grifos”.  
**ETL:** `metadata/hydrants_siss_parse.py`.  
**Uso:** indicadores comunales; futuro *join* espacial con hidrantes OSM.
""",
    DOCS / "metadata_road_widths.md": r"""
# road_widths.geojson — Metadata de ancho de vías (OSM)

**Archivo:** `metadata/road_widths.geojson`  
**Tipo:** GeoJSON `FeatureCollection` de `LineString` (EPSG:4326)

## `properties`

| Campo        | Tipo    | ¿Null? | Descripción |
|--------------|---------|--------|-------------|
| osm_id       | int     | no     | ID del way en OSM. |
| highway      | string  | sí     | Tipo de vía OSM. |
| lanes        | int     | sí     | Carriles reportados. |
| width_raw    | string  | sí     | Valor original (`"7 m"`, `"12 ft"`, etc.). |
| maxwidth_raw | string  | sí     | Restricción de ancho original. |
| width_m      | number  | sí     | **Ancho normalizado en metros**. |
| maxwidth_m   | number  | sí     | **Restricción de ancho en metros**. |

## Ejemplo
```json
{
  "type":"Feature",
  "geometry":{"type":"LineString","coordinates":[[-70.7,-33.45],[-70.69,-33.45]]},
  "properties":{
    "osm_id":999,"highway":"secondary","lanes":2,
    "width_raw":"7","maxwidth_raw":null,
    "width_m":7.0,"maxwidth_m":null
  }
}
```

**Procedencia:** Overpass (OSM), script `metadata/road_widths_osm.py`.  
**Uso:** actualizar `rr.ways.width_m` (loader `loaders/load_widths.py`).
""",
    DOCS / "metadata_road_oneway.md": r"""
# road_oneway.geojson — Metadata de sentido de vías (OSM)

**Archivo:** `metadata/road_oneway.geojson`  
**Tipo:** GeoJSON `FeatureCollection` de `LineString` (EPSG:4326)

## `properties`

| Campo      | Tipo    | ¿Null? | Descripción |
|------------|---------|--------|-------------|
| osm_id     | int     | no     | ID del way en OSM. |
| highway    | string  | sí     | Tipo de vía OSM. |
| oneway_raw | string  | sí     | Valor OSM crudo (`"yes"`, `"no"`, `"-1"`). |
| oneway     | boolean | sí     | Interpretación booleana (`true` si `yes/-1`, `false` si `no`). |

## Ejemplo
```json
{
  "type":"Feature",
  "geometry":{"type":"LineString","coordinates":[[-70.7,-33.45],[-70.69,-33.45]]},
  "properties":{"osm_id":555,"highway":"residential","oneway_raw":"yes","oneway":true}
}
```

**Procedencia:** Overpass (OSM), script `metadata/road_oneway_osm_chunks.py`.  
**Uso:** actualizar `rr.ways.oneway` (loader `loaders/load_oneway.py`).
""",
    DOCS / "threat_traffic_calming.md": r"""
# traffic_calming_threats.geojson — Amenaza: reductores (lomos de toro)

**Archivo:** `amenazas/traffic_calming_threats.geojson`  
**Tipo:** GeoJSON `FeatureCollection` de `Point` (EPSG:4326)

## `properties`

| Campo    | Tipo    | ¿Null? | Descripción |
|----------|---------|--------|-------------|
| provider | string  | no     | `"OSM"`. |
| ext_id   | string  | no     | ID OSM del nodo (como string). |
| kind     | string  | no     | `"incident"`. |
| subtype  | string  | no     | `"TRAFFIC_CALMING"`. |
| severity | int     | no     | Severidad heurística (1). |
| props    | object  | sí     | Tags OSM originales del elemento. |

## Ejemplo
```json
{
  "type":"Feature",
  "geometry":{"type":"Point","coordinates":[-70.7,-33.45]},
  "properties":{"provider":"OSM","ext_id":"123456","kind":"incident","subtype":"TRAFFIC_CALMING","severity":1,"props":{"traffic_calming":"bump"}}
}
```

**Procedencia:** Overpass (OSM), script `amenazas/traffic_calming_as_threats.py`.  
**Uso:** penalización de coste en vías cercanas.
""",
    
    DOCS / "threat_weather_openweather.md": r"""
# weather_threats.geojson — Amenaza: clima (OpenWeather)

**Archivo:** `amenazas/weather_threats.geojson`  
**Tipo:** GeoJSON `FeatureCollection` de `Polygon` (celdas grid)

## `properties`

| Campo            | Tipo    | ¿Null? | Descripción |
|------------------|---------|--------|-------------|
| provider         | string  | no     | `"OPENWEATHER"`. |
| ext_id           | string  | no     | `<lat,lon>:<subtype>` de la celda. |
| kind             | string  | no     | `"weather"`. |
| subtype          | string  | no     | `"RAIN"`, `"WIND"` o `"RAIN+WIND"`. |
| severity         | int     | no     | 1..2 (umbral). |
| starts_at        | string  | sí     | null (no time window). |
| ends_at          | string  | sí     | null. |
| metrics          | object  | sí     | `{ "precip_mm_h": number|null, "wind_m_s": number|null }`. |

## Ejemplo
```json
{
  "type":"Feature",
  "geometry":{"type":"Polygon","coordinates":[[[-70.7,-33.46],[-70.68,-33.46],[-70.68,-33.44],[-70.7,-33.44],[-70.7,-33.46]]]},
  "properties":{"provider":"OPENWEATHER","ext_id":"-33.45,-70.69:RAIN","kind":"weather","subtype":"RAIN","severity":1,"metrics":{"precip_mm_h":4.2,"wind_m_s":6.0}}
}
```

**Procedencia:** OpenWeather One Call 3.0, script `amenazas/weather_openweather.py`.  
**Uso:** penalizar tramos dentro de celdas con lluvia/viento fuertes.
""",
    DOCS / "threat_waze_incidents.md": r"""
# waze_incidents.geojson — Amenaza: incidentes/jams (Waze web feed)

**Archivo:** `amenazas/waze_incidents.geojson`  
**Tipo:** GeoJSON `FeatureCollection` (features `Point` para alerts, `LineString` para jams)

## `properties`

| Campo       | Tipo    | ¿Null? | Descripción |
|-------------|---------|--------|-------------|
| provider    | string  | no     | `"WAZE"`. |
| ext_id      | string  | no     | `uuid/id` del evento (si falta se sintetiza). |
| kind        | string  | no     | `"incident"`. |
| subtype     | string  | no     | `"CLOSURE"`, `"INCIDENT"` o `"TRAFFIC_JAM"`. |
| severity    | int     | no     | 1..2 (heurística). |
| description | string  | sí     | Texto libre del reporte (si existe). |
| street      | string  | sí     | Calle asociada (si existe). |
| type_raw    | string  | sí     | Tipo crudo del feed. |
| metrics     | object  | sí     | Para jams: `{ "speed_kmh": number|null }`. |

## Ejemplo (alerta)
```json
{
  "type":"Feature",
  "geometry":{"type":"Point","coordinates":[-70.7,-33.45]},
  "properties":{"provider":"WAZE","ext_id":"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee","kind":"incident","subtype":"INCIDENT","severity":1,"description":"Choque leve","street":"Alameda"}
}
```

**Procedencia:** Endpoint público web de Waze (sujeto a cambios), script `amenazas/waze_incidents.py`.  
**Uso:** evitar incidentes y congestiones relevantes.
""",
    ROOT / "README_ETL.md": r"""
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
- **Incidentes/Cierres (Waze)**:  
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
"""
}

def write_file(path: Path, content: str):
    path.write_text(content.lstrip("\n"), encoding="utf-8")
    print(f"[OK] {path}")

for p, c in files.items():
    write_file(p, c)

print("\nTodo listo. Revisa la carpeta 'docs/' y el 'README_ETL.md' en la raíz.\n")
