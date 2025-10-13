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
