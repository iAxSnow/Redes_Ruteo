# Documentación de Ruteo y Modelo de Probabilidad

## Descripción General

Este documento describe la funcionalidad de ruteo y el modelo de probabilidad implementado para el proyecto de ruteo resiliente. Esto implementa los puntos 4 y 5 de la rúbrica.

## Componentes

### 1. Modelo de Probabilidad (`scripts/probability_model.py`)

Un script independiente que calcula probabilidades de falla para elementos de red basándose en la proximidad a amenazas.

#### Características
- **Gestión Automática de Columnas**: Crea columnas `fail_prob` en `rr.ways` y `rr.ways_vertices_pgr` si no existen
- **Funcionalidad de Reinicio**: Limpia todas las probabilidades de falla antes de recalcular
- **Cálculo Basado en Amenazas**: Asigna probabilidades basadas en la proximidad a amenazas
- **Reporte de Estadísticas**: Imprime resumen detallado de elementos de red afectados

#### Configuración
```python
INFLUENCE_RADIUS_M = 50      # Radio de influencia de amenaza en metros
FAILURE_PROBABILITY = 0.5     # Probabilidad asignada a elementos afectados
```

#### Uso
```bash
cd Redes_Ruteo
python scripts/probability_model.py
```

#### Algoritmo
1. Conectar a la base de datos usando variables de entorno (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`)
2. Verificar/crear columnas `fail_prob` en tablas de red
3. Reiniciar todas las probabilidades a 0.0
4. Para cada amenaza en `rr.amenazas_waze`:
   - Encontrar todos los ways dentro de 50m usando `ST_DWithin`
   - Encontrar todos los vértices dentro de 50m usando `ST_DWithin`
   - Asignar probabilidad 0.5 (mantiene la más alta si múltiples amenazas afectan el mismo elemento)
5. Imprimir estadísticas de elementos afectados

#### Ejemplo de Salida
```
============================================================
MODELO DE PROBABILIDAD - Evaluación de Fallas
============================================================

✓ Conectado a la base de datos
✓ La columna fail_prob ya existe en rr.ways
✓ La columna fail_prob ya existe en rr.ways_vertices_pgr
✓ Reiniciados 15234 ways y 8912 vértices
Procesando 142 amenazas de Waze...
✓ Actualizados 387 ways con probabilidad de falla 0.5
✓ Actualizados 215 vértices con probabilidad de falla 0.5

============================================================
ESTADÍSTICAS DE PROBABILIDAD DE FALLA
============================================================

Ways:
  Total: 15234
  Afectados (fail_prob > 0): 387
  Probabilidad promedio: 0.0127
  Probabilidad máxima: 0.5000

Vértices:
  Total: 8912
  Afectados (fail_prob > 0): 215
  Probabilidad promedio: 0.0121
  Probabilidad máxima: 0.5000
============================================================
```

### 2. API de Cálculo de Rutas

Nuevo endpoint de API REST para calcular rutas óptimas usando el algoritmo de Dijkstra de pgRouting.

#### Endpoint
```
POST /api/calculate_route
```

#### Formato de Solicitud
```json
{
  "start": {
    "lat": -33.45,
    "lng": -70.65
  },
  "end": {
    "lat": -33.46,
    "lng": -70.66
  }
}
```

#### Formato de Respuesta
```json
{
  "route_geojson": {
    "type": "Feature",
    "properties": {
      "total_length_m": 1250.5,
      "segments": 15
    },
    "geometry": {
      "type": "LineString",
      "coordinates": [
        [-70.65, -33.45],
        [-70.651, -33.451],
        ...
      ]
    }
  },
  "compute_time_ms": 45.23
}
```

#### Algoritmo
1. Recibir coordenadas de inicio/fin de la solicitud
2. Encontrar el nodo más cercano en `rr.ways_vertices_pgr` al punto de inicio usando índice espacial (operador `<->`)
3. Encontrar el nodo más cercano al punto final
4. Ejecutar consulta de pgRouting:
   ```sql
   SELECT * FROM pgr_dijkstra(
     'SELECT id, source, target, length_m as cost FROM rr.ways',
     nodo_origen,
     nodo_destino,
     directed := false
   )
   ```
5. Construir LineString GeoJSON desde segmentos de ruta
6. Medir y devolver tiempo de cálculo

#### Manejo de Errores
- 400: Formato de solicitud inválido (coordenadas faltantes)
- 404: Ruta no encontrada o nodos no encontrados
- 500: Error de base de datos

### 3. Interfaz Web - Controles de Ruteo

#### Nuevos Elementos de UI

**Sección de Panel de Control:**
```
Ruteo
├── Texto de instrucción (dinámico)
├── Botón "Calcular Ruta Óptima" (deshabilitado hasta que ambos puntos estén seleccionados)
├── Botón "Limpiar Ruta"
└── Panel de información de ruta (oculto hasta que se calcule la ruta)
```

#### Flujo de Usuario

1. **Seleccionar Punto de Inicio**
   - Hacer clic en cualquier lugar del mapa
   - Aparece marcador verde
   - Instrucción se actualiza: "Haz clic en el mapa para seleccionar el punto final"

2. **Seleccionar Punto Final**
   - Hacer clic nuevamente en el mapa
   - Aparece marcador rojo
   - El botón "Calcular Ruta Óptima" se habilita
   - Instrucción se actualiza: "Haz clic en 'Calcular Ruta Óptima'"

3. **Calcular Ruta**
   - Hacer clic en el botón "Calcular Ruta Óptima"
   - Solicitud de API enviada a `/api/calculate_route`
   - Ruta mostrada como polilínea roja en el mapa
   - Mapa se ajusta automáticamente para mostrar la ruta
   - Panel de información de ruta muestra:
     * Distancia en kilómetros
     * Tiempo de cálculo en milisegundos
     * Número de segmentos

4. **Limpiar Ruta**
   - Hacer clic en el botón "Limpiar Ruta"
   - Elimina todos los marcadores y la ruta
   - Reinicia al estado inicial
   - Botón "Calcular Ruta Óptima" deshabilitado

#### Diseño Visual

**Marcadores:**
- Inicio: Marcador verde
- Fin: Marcador rojo
- Ubicación del usuario: Marcador azul (desde geolocalización)

**Ruta:**
- Color: Rojo (#e74c3c)
- Peso: 5px
- Opacidad: 0.7

**Botones:**
- Primario (azul): "Calcular Ruta Óptima"
- Secundario (gris): "Limpiar Ruta"
- Estado deshabilitado: Atenuado, cursor no permitido

## Integración con Base de Datos

### Tablas Requeridas

1. **rr.ways** - Arcos de red
   ```sql
   - id (bigint, PK)
   - source (bigint)
   - target (bigint)
   - geom (geometry LineString)
   - length_m (numeric)
   - fail_prob (float8) -- Añadido por el modelo de probabilidad
   ```

2. **rr.ways_vertices_pgr** - Nodos de red
   ```sql
   - id (bigint, PK)
   - geom (geometry Point)
   - fail_prob (float8) -- Añadido por el modelo de probabilidad
   ```

3. **rr.amenazas_waze** - Datos de amenazas
   ```sql
   - ext_id (text, PK)
   - kind (text)
   - subtype (text)
   - severity (integer)
   - geom (geometry)
   ```

### Configuración de Base de Datos

La tabla `rr.ways_vertices_pgr` debe crearse usando pgRouting:

```sql
-- Crear topología
SELECT pgr_createTopology('rr.ways', 0.0001, 'geom', 'id');

-- Añadir columna de geometría
ALTER TABLE rr.ways_vertices_pgr ADD COLUMN geom geometry(Point, 4326);
UPDATE rr.ways_vertices_pgr SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326);

-- Crear índice espacial
CREATE INDEX ways_vertices_gix ON rr.ways_vertices_pgr USING GIST (geom);
```

## Pruebas

### Lista de Verificación de Pruebas Manuales

#### Modelo de Probabilidad
- [ ] El script se ejecuta sin errores
- [ ] Crea columnas fail_prob si faltan
- [ ] Reinicia probabilidades a 0.0
- [ ] Calcula probabilidades basadas en amenazas
- [ ] Imprime estadísticas correctamente

#### API de Cálculo de Rutas
- [ ] Devuelve 400 para solicitudes inválidas
- [ ] Encuentra nodos más cercanos correctamente
- [ ] Calcula ruta usando pgr_dijkstra
- [ ] Devuelve GeoJSON válido
- [ ] Reporta tiempo de cálculo
- [ ] Maneja errores de base de datos elegantemente

#### Interfaz Web
- [ ] Muestra controles de ruteo
- [ ] Primer clic crea marcador verde (inicio)
- [ ] Segundo clic crea marcador rojo (fin)
- [ ] Botón de calcular habilitado después de seleccionar ambos puntos
- [ ] Ruta se muestra correctamente en el mapa
- [ ] Información de ruta muestra distancia, tiempo, segmentos
- [ ] Botón de limpiar elimina marcadores y ruta
- [ ] Instrucciones se actualizan dinámicamente

### Pruebas Automatizadas

Ejecutar el script de verificación:
```bash
cd Redes_Ruteo
python3 << 'EOF'
import os
os.environ['FLASK_DEBUG'] = '0'

# Importar y probar todos los componentes
from scripts import probability_model
from app import app

# Verificar que todas las funciones y endpoints existan
assert hasattr(probability_model, 'calculate_failure_probabilities')
assert 'api_calculate_route' in [r.endpoint for r in app.url_map.iter_rules()]

print("✓ Todos los componentes verificados")
EOF
```

## Mejoras Futuras

1. **Ruteo Consciente del Riesgo**
   - Modificar función de costo para incluir `fail_prob`
   - Ejemplo: `cost = length_m * (1 + fail_prob * peso)`
   - Proporciona balance entre distancia y seguridad

2. **Algoritmos de Ruta Alternativos**
   - A* para cálculo más rápido
   - Múltiples opciones de ruta (más corta, más segura, más rápida)
   - Interfaz de comparación de rutas

3. **Actualizaciones Dinámicas**
   - Actualizaciones de amenazas en tiempo real
   - Recálculo automático de rutas
   - Integración de WebSocket

4. **Modelos Avanzados de Probabilidad**
   - Decaimiento de probabilidad basado en tiempo
   - Escalado de probabilidad basado en severidad
   - Integración de múltiples fuentes de amenazas

## Solución de Problemas

### Problemas del Modelo de Probabilidad

**Problema:** "La tabla ways_vertices_pgr no existe"
**Solución:** Ejecutar `pgr_createTopology` para crear la topología

**Problema:** "Columna geom no encontrada en ways_vertices_pgr"
**Solución:** Añadir columna de geometría como se muestra en Configuración de Base de Datos

### Problemas de Cálculo de Rutas

**Problema:** "No se pudo encontrar nodo de inicio/fin en la red"
**Solución:** Asegurar que los nodos estén dentro de los límites de la red y que la topología esté construida

**Problema:** "No se encontró ruta entre los puntos especificados"
**Solución:** Verificar que la red esté conectada, considerar aumentar tolerancia de búsqueda

### Problemas de Interfaz Web

**Problema:** El mapa no se carga
**Solución:** Verificar consola del navegador, asegurar que el CDN de Leaflet sea accesible

**Problema:** Error "Fallo al calcular ruta"
**Solución:** Verificar conexión a base de datos, asegurar que las tablas de red existan

## Variables de Entorno

Variables de entorno requeridas para ambos componentes:

```bash
PGHOST=localhost
PGPORT=5432
PGDATABASE=rr
PGUSER=postgres
PGPASSWORD=postgres

# Opcional para desarrollo
FLASK_DEBUG=1
```

## Consideraciones de Rendimiento

### Modelo de Probabilidad
- Tiempo de ejecución: ~1-5 segundos para 100-200 amenazas
- Depende de: Número de amenazas, tamaño de red, rendimiento de índice espacial
- Recomendación: Ejecutar periódicamente (ej. cada hora) en lugar de en tiempo real

### Cálculo de Rutas
- Tiempo de respuesta típico: 20-100ms para rutas dentro de 10km
- Depende de: Tamaño de red, longitud de ruta, carga de base de datos
- Los índices espaciales son críticos para el rendimiento

### Consejos de Optimización
1. Asegurar que existan índices espaciales: `CREATE INDEX ... USING GIST (geom)`
2. Ejecutar `ANALYZE` después de cargar datos
3. Usar agrupación de conexiones para múltiples solicitudes
4. Considerar almacenar en caché rutas solicitadas frecuentemente
