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
