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
