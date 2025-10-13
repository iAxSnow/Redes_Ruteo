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
