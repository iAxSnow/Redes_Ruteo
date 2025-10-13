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
