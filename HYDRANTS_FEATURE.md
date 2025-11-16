# Funcionalidad de Hidrantes - Documentación

## Vista General

Se ha agregado una nueva funcionalidad para visualizar hidrantes en el mapa con código de colores según su estado.

## Interfaz de Usuario

### Panel de Control

En el panel de control lateral, se ha agregado una nueva sección "Hidrantes" que incluye:

1. **Botón de control**: "🚰 Mostrar Hidrantes" / "🚰 Ocultar Hidrantes"
   - Alterna la visibilidad de la capa de hidrantes
   - El texto cambia dinámicamente según el estado

2. **Información de hidrantes**: 
   - Total de hidrantes
   - Contadores por estado:
     - ● Funcionales (verde)
     - ● No funcionales (rojo)
     - ● Desconocido (gris)

3. **Leyenda de colores**:
   - Se muestra cuando los hidrantes están visibles
   - Explica el significado de cada color

## Código de Colores

### Verde (#2ecc71) - Funcional
Estados considerados funcionales:
- "vigente"
- "operativo"
- "bueno"

### Rojo (#e74c3c) - No Funcional
Estados considerados no funcionales:
- "no vigente"
- "malo"
- "no_operativo"
- "fuera de servicio"

### Gris (#95a5a6) - Desconocido
- Estados no clasificados
- Estado "desconocido"

## Información del Popup

Cuando se hace clic en un hidrante, se muestra un popup con:
- **ID**: Identificador único del hidrante
- **Estado**: Estado actual (con color correspondiente)
- **Proveedor**: Fuente de los datos (ej: SISS)
- **Ubicación**: Dirección o ubicación del hidrante
- **Modelo**: Modelo del hidrante
- **Diámetro**: Diámetro nominal

## Fuente de Datos

Los datos provienen de:
- **Base de datos**: Tabla `rr.metadata_hydrants`
- **Excel SISS**: `PR036001_ESTADO_DE_GRIFOS_202406_202506.xlsx`
- **Campos clave**: 
  - ESTADO_USO (0/1)
  - CODIGO_ESTADO_USO (VIGENTE/NO VIGENTE)
  - UBICACION
  - MODELO
  - DIAMETRO_NOMINAL

## API Endpoint

### GET `/api/hydrants`

Devuelve un GeoJSON FeatureCollection con todos los hidrantes:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "ext_id": "...",
        "status": "vigente",
        "functional_status": "functional",
        "provider": "SISS",
        "type": "hydrant",
        "UBICACION": "...",
        "MODELO": "...",
        "DIAMETRO_NOMINAL": "..."
      },
      "geometry": {
        "type": "Point",
        "coordinates": [lon, lat]
      }
    }
  ]
}
```

## Uso

1. Abrir la aplicación web
2. En el panel de control, buscar la sección "Hidrantes"
3. Hacer clic en "🚰 Mostrar Hidrantes"
4. Los hidrantes aparecerán en el mapa como círculos de colores
5. Hacer clic en cualquier hidrante para ver su información detallada
6. La leyenda muestra el significado de los colores
7. Para ocultar, hacer clic nuevamente en el botón (ahora dice "Ocultar Hidrantes")

## Integración con Ruteo

Los hidrantes se muestran como una capa independiente y no interfieren con:
- Capas de amenazas (Waze, clima, reductores)
- Rutas calculadas
- Marcadores de inicio/fin
- Simulación de fallas

Esto permite a los bomberos visualizar simultáneamente:
- Rutas óptimas
- Amenazas en el camino
- Ubicación de hidrantes disponibles

## Consideraciones de Rendimiento

- Los hidrantes se cargan solo cuando se solicitan (lazy loading)
- Se almacenan en caché una vez cargados
- No se recargan al mostrar/ocultar la capa
- Los markers son CircleMarkers de Leaflet (ligeros)

## Ejemplo de Visualización

```
Panel de Control:
┌─────────────────────────────┐
│ Hidrantes                   │
├─────────────────────────────┤
│ [🚰 Ocultar Hidrantes]     │
│                             │
│ Total: 1,247                │
│ ● Funcionales: 892          │
│ ● No funcionales: 298       │
│ ● Desconocido: 57           │
│                             │
│ ┌─────────────────────────┐ │
│ │ Leyenda:                │ │
│ │ ● Funcional             │ │
│ │ ● No Funcional          │ │
│ │ ● Desconocido           │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘

Mapa:
[Círculos verdes, rojos y grises distribuidos por el área]

Popup al hacer clic:
┌─────────────────────────────┐
│ Hidrante                    │
├─────────────────────────────┤
│ ID: grifo_12345             │
│ Estado: VIGENTE [verde]     │
│ Proveedor: SISS             │
│ Ubicación: Av. Principal... │
│ Modelo: ABC-100             │
│ Diámetro: 100mm             │
└─────────────────────────────┘
```

## Mejoras Futuras Sugeridas

1. Filtrar hidrantes por estado (mostrar solo funcionales)
2. Búsqueda de hidrantes por ubicación
3. Información de última inspección
4. Distancia desde punto seleccionado
5. Resaltar hidrantes más cercanos a la ruta
6. Exportar lista de hidrantes en la ruta
