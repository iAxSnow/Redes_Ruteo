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
