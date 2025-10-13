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
