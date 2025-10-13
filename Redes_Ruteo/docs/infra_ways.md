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
