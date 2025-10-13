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
