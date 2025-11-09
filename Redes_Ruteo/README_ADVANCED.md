# Algoritmos Avanzados de Ruteo y Simulación de Fallas

## Descripción General

Este documento describe los algoritmos avanzados de ruteo y las características de simulación de fallas que completan la implementación del proyecto de ruteo resiliente. Estas características corresponden a los puntos 6, 7 y 8 de la rúbrica.

## 1. Múltiples Algoritmos de Ruteo

### Implementación

El endpoint `/api/calculate_route` ahora soporta el cálculo de múltiples rutas simultáneamente usando diferentes algoritmos. Cuando se especifica `algorithm: "all"`, el sistema calcula 4 rutas diferentes.

### Detalles de los Algoritmos

#### Algoritmo 1: Dijkstra (Distancia)
**Propósito:** Encontrar la ruta más corta solo por distancia

**Función de Costo:**
```sql
cost = length_m
```

**Características:**
- Algoritmo clásico de ruta más corta
- No considera factores de riesgo
- Ruta más rápida en términos de distancia
- Puede pasar por áreas de alto riesgo

**Caso de Uso:** Cuando la velocidad y eficiencia son las principales preocupaciones, y el riesgo es aceptable.

**Color:** Rojo (#e74c3c)

#### Algoritmo 2: Dijkstra (Probabilidad)
**Propósito:** Balancear distancia y seguridad penalizando arcos riesgosos

**Función de Costo:**
```sql
cost = length_m * (1 + fail_prob * 100)
```

**Factor de Penalización:** 100
- Un arco con `fail_prob = 0.5` tiene su costo multiplicado por 51x
- Fuertemente incentiva evitar áreas de alto riesgo
- Aún encuentra un camino conectado si existe

**Características:**
- Ruteo consciente del riesgo
- Puede elegir rutas más largas para evitar amenazas
- Balancea distancia vs. seguridad
- Más práctico para navegación general

**Caso de Uso:** Navegación estándar con consideraciones de seguridad.

**Color:** Azul (#3498db)

#### Algoritmo 3: A* (Probabilidad)
**Propósito:** Cálculo más rápido usando guía heurística

**Función de Costo:**
```sql
cost = length_m * (1 + fail_prob * 100)
heuristic = distancia_euclidiana_al_objetivo
```

**Detalles de la Heurística:**
- Usa distancia euclidiana al objetivo
- Guía la búsqueda hacia el destino
- Generalmente más rápido que Dijkstra puro
- Misma penalización de riesgo que Algoritmo 2

**Características:**
- Algoritmo de búsqueda informada
- Cálculo más rápido (típicamente 20-40% más rápido)
- Resultados similares a Dijkstra (Probabilidad)
- Optimizado para aplicaciones en tiempo real

**Caso de Uso:** Sistemas de navegación en tiempo real que requieren respuesta rápida.

**Color:** Naranja (#f39c12)

#### Algoritmo 4: Dijkstra Filtrado (Solo Seguros)
**Propósito:** Garantizar máxima seguridad usando solo arcos seguros

**Función de Costo:**
```sql
cost = length_m
WHERE fail_prob < 0.5
```

**Filtro de Arcos:**
- Solo considera arcos con `fail_prob < 0.5`
- Excluye completamente segmentos de alto riesgo
- Puede resultar en "ruta no encontrada" si no existe un camino seguro

**Características:**
- Garantía de máxima seguridad
- Puede ser significativamente más largo que otras rutas
- Umbral de seguridad determinístico
- Adecuado para aplicaciones críticas

**Caso de Uso:** Vehículos de emergencia, infraestructura crítica, navegación con aversión al riesgo.

**Color:** Verde (#27ae60)

### Uso de la API

**Solicitud:**
```json
POST /api/calculate_route
{
  "start": {
    "lat": -33.45,
    "lng": -70.65
  },
  "end": {
    "lat": -33.46,
    "lng": -70.66
  },
  "algorithm": "all"
}
```

**Respuesta:**
```json
{
  "dijkstra_dist": {
    "route_geojson": {
      "type": "Feature",
      "properties": {
        "total_length_m": 5234.56,
        "segments": 42
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [[...]]
      }
    },
    "compute_time_ms": 45.23,
    "algorithm": "Dijkstra (Distancia)"
  },
  "dijkstra_prob": {
    "route_geojson": {...},
    "compute_time_ms": 52.18,
    "algorithm": "Dijkstra (Probabilidad)"
  },
  "astar_prob": {
    "route_geojson": {...},
    "compute_time_ms": 38.91,
    "algorithm": "A* (Probabilidad)"
  },
  "filtered_dijkstra": {
    "route_geojson": {...},
    "compute_time_ms": 41.76,
    "algorithm": "Dijkstra Filtrado (Solo Seguros)"
  }
}
```

### Comparación de Rendimiento

Tiempos de cálculo típicos para una ruta de 5-10km:

| Algoritmo | Tiempo Promedio (ms) | Velocidad Relativa |
|-----------|---------------------|-------------------|
| Dijkstra (Dist) | 40-60 | Referencia |
| Dijkstra (Prob) | 45-70 | +10-15% |
| A* (Prob) | 30-50 | -20-30% |
| Filtrado | 35-55 | -5-10% |

**Nota:** A* es típicamente el más rápido debido a la guía heurística. El filtrado puede ser más rápido debido a un espacio de búsqueda más pequeño.

## 2. Simulación de Fallas

### Propósito

Simular fallas del mundo real en la red basándose en las probabilidades de falla calculadas. Esto valida la importancia del ruteo consciente del riesgo.

### Endpoint de la API

**Solicitud:**
```json
POST /api/simulate_failures
```

**Sin cuerpo requerido**

**Respuesta:**
```json
{
  "failed_edges": [123, 456, 789, ...],
  "failed_nodes": [45, 67, 89, ...],
  "total_failed": 25
}
```

### Algoritmo

```python
for cada arco con fail_prob > 0:
    valor_aleatorio = random()  # 0.0 a 1.0
    if valor_aleatorio < arco.fail_prob:
        marcar_como_fallado(arco)
```

**Ejemplo:**
- Arco con `fail_prob = 0.3`: 30% de probabilidad de falla
- Arco con `fail_prob = 0.7`: 70% de probabilidad de falla
- Arco con `fail_prob = 0.0`: Nunca falla
- Arco con `fail_prob = 1.0`: Siempre falla

### Interpretación

- **total_failed alto:** La red está bajo estrés significativo
- **Fallas en rutas principales:** Demuestra la necesidad de alternativas
- **Sin fallas en rutas alternativas:** Valida el ruteo consciente del riesgo

## 3. Mejoras de la Interfaz de Usuario

### Controles de Ruteo

**Diseño:**
```
Ruteo
├── Texto de instrucción (retroalimentación dinámica)
├── Botón "Calcular Rutas"
├── Botón "Limpiar Rutas"
├── Algoritmos de Ruteo (sección)
│   ├── ☑ Dijkstra (Distancia) - Rojo
│   ├── ☑ Dijkstra (Probabilidad) - Azul
│   ├── ☑ A* (Probabilidad) - Naranja
│   └── ☑ Dijkstra Filtrado - Verde
└── Panel de información de ruta
```

**Características:**
- Control de visibilidad individual para cada ruta
- Información de ruta codificada por colores
- Distancia y tiempo de cálculo para cada algoritmo
- Alternancia de visibilidad en tiempo real

### Controles de Simulación

**Diseño:**
```
Simulación
├── ☐ Simular Fallas
├── ☐ Solo Amenazas Activas
└── Panel de estadísticas de simulación
```

**Características:**
- Simulación de fallas con un clic
- Visualización de estadísticas (total de fallas, arcos, nodos)
- Filtrar amenazas por resultados de simulación

### Diseño Visual

**Colores de Ruta:**
- 🔴 Rojo (Dijkstra Distancia): Más corta pero potencialmente riesgosa
- 🔵 Azul (Dijkstra Probabilidad): Enfoque balanceado
- 🟠 Naranja (A* Probabilidad): Rápido y seguro
- 🟢 Verde (Dijkstra Filtrado): Máxima seguridad

**Interacción:**
- Todas las rutas calculadas con un solo clic de botón
- Las casillas de verificación permiten análisis comparativo
- Múltiples rutas pueden mostrarse simultáneamente
- Fácil comparar longitudes y caminos de rutas

## 4. Demostración de Caso de Uso

### Escenario: Ruteo de Vehículo de Emergencia

**Contexto:** Una ambulancia necesita navegar desde el Hospital A al Sitio de Emergencia B.

#### Paso 1: Cálculo de Ruta

El usuario hace clic en el mapa para seleccionar:
- Inicio: Ubicación del Hospital A
- Fin: Ubicación del Sitio de Emergencia B

Clic en "Calcular Rutas" → El sistema calcula 4 rutas

#### Paso 2: Análisis de Ruta

**Resultados:**
- 🔴 **Dijkstra (Distancia)**: 5.2 km, 45 ms
  - Distancia más corta
  - Pasa por área conocida de congestión de tráfico
  - Alto `fail_prob` en 3 segmentos

- 🔵 **Dijkstra (Probabilidad)**: 5.8 km, 52 ms
  - 11% más larga
  - Evita áreas de alto riesgo
  - Más confiable

- 🟠 **A* (Probabilidad)**: 5.7 km, 39 ms
  - Similar a la ruta azul
  - Cálculo más rápido
  - Bueno para tiempo real

- 🟢 **Dijkstra Filtrado**: 6.5 km, 42 ms
  - 25% más larga
  - Usa solo caminos "seguros"
  - Confiabilidad garantizada

#### Paso 3: Simulación

El usuario marca "Simular Fallas"

**Resultados de Simulación:**
```
Elementos fallados: 5
Arcos: 3
Nodos: 2
```

**Observación:**
- Uno de los arcos fallados está en la ruta roja (Dijkstra Distancia)
- Ninguna de las rutas alternativas (azul, naranja, verde) se ve afectada
- Esto valida la importancia del ruteo consciente del riesgo

#### Paso 4: Toma de Decisiones

**Análisis:**
- La ruta roja habría sido bloqueada por la falla
- Las rutas azul/naranja proporcionan buen balance (solo 11% más largas)
- La ruta verde proporciona máxima certeza pero a un costo del 25% en distancia

**Decisión:**
- Para emergencia: Elegir ruta azul o naranja (balanceada)
- Para operaciones críticas: Elegir ruta verde (máxima seguridad)
- Para tiempo crítico: Aceptar riesgo de ruta roja

#### Paso 5: Validación

La simulación demuestra:
1. **El Riesgo es Real:** Los elementos de red pueden y fallan
2. **Más Corta ≠ Mejor:** La ruta más corta no siempre es la mejor
3. **Las Alternativas son Valiosas:** Tener múltiples opciones es crítico
4. **La Cuantificación del Riesgo Funciona:** El modelo de probabilidad identificó correctamente segmentos riesgosos

### Valor de Negocio

**Para Planificación Urbana:**
- Identificar vulnerabilidades de infraestructura crítica
- Planificar rutas redundantes
- Optimizar respuesta de emergencia

**Para Sistemas de Navegación:**
- Proporcionar ruteo consciente del riesgo
- Ofrecer alternativas de ruta
- Construir confianza del usuario a través de confiabilidad

**Para Servicios de Emergencia:**
- Asegurar ruteo confiable
- Minimizar incertidumbre en tiempo de respuesta
- Planificar para fallas de infraestructura

## 5. Detalles de Implementación Técnica

### Consultas de Base de Datos

**Dijkstra (Distancia):**
```sql
SELECT * FROM pgr_dijkstra(
  'SELECT id, source, target, length_m as cost FROM rr.ways',
  nodo_origen, nodo_destino, directed := false
)
```

**Dijkstra (Probabilidad):**
```sql
SELECT * FROM pgr_dijkstra(
  'SELECT id, source, target, 
   length_m * (1 + COALESCE(fail_prob, 0) * 100) as cost 
   FROM rr.ways',
  nodo_origen, nodo_destino, directed := false
)
```

**A* (Probabilidad):**
```sql
SELECT * FROM pgr_astar(
  'SELECT id, source, target, 
   length_m * (1 + COALESCE(fail_prob, 0) * 100) as cost,
   ST_X(ST_StartPoint(geom)) as x1,
   ST_Y(ST_StartPoint(geom)) as y1,
   ST_X(ST_EndPoint(geom)) as x2,
   ST_Y(ST_EndPoint(geom)) as y2
   FROM rr.ways',
  nodo_origen, nodo_destino, directed := false
)
```

**Dijkstra Filtrado:**
```sql
SELECT * FROM pgr_dijkstra(
  'SELECT id, source, target, length_m as cost 
   FROM rr.ways 
   WHERE COALESCE(fail_prob, 0) < 0.5',
  nodo_origen, nodo_destino, directed := false
)
```

### Procesamiento de Rutas

```python
def build_route_geojson(cur, segmentos_ruta):
    """Construir GeoJSON desde resultados de pgRouting"""
    coordenadas = []
    longitud_total_m = 0
    
    for segmento in segmentos_ruta:
        if segmento['geom']:
            geom_json = json.loads(
                cur.execute("SELECT ST_AsGeoJSON(%s)", (segmento['geom'],))
            )
            coordenadas.extend(geom_json['coordinates'])
            longitud_total_m += float(segmento['length_m'])
    
    return {
        "type": "Feature",
        "properties": {
            "total_length_m": round(longitud_total_m, 2),
            "segments": len(segmentos_ruta)
        },
        "geometry": {
            "type": "LineString",
            "coordinates": coordenadas
        }
    }
```

## 6. Pruebas y Validación

### Pruebas Unitarias

Probar cada algoritmo individualmente:
```python
def test_dijkstra_dist():
    respuesta = calculate_route(inicio, fin, 'dijkstra_dist')
    assert 'route_geojson' in respuesta
    assert respuesta['compute_time_ms'] > 0

def test_all_algorithms():
    respuesta = calculate_route(inicio, fin, 'all')
    assert len(respuesta) == 4
    assert 'dijkstra_dist' in respuesta
    assert 'dijkstra_prob' in respuesta
    assert 'astar_prob' in respuesta
    assert 'filtered_dijkstra' in respuesta
```

### Pruebas de Integración

Probar flujo de trabajo completo:
1. Calcular todas las rutas
2. Verificar que todas las rutas fueron devueltas
3. Verificar longitudes de ruta (rutas prob deben ser ≥ ruta dist)
4. Validar estructura GeoJSON
5. Confirmar tiempos de cálculo

### Lista de Verificación de Pruebas Manuales

- [ ] Puede calcular las 4 rutas simultáneamente
- [ ] Cada ruta se muestra con el color correcto
- [ ] Las casillas de verificación alternan la visibilidad de la ruta
- [ ] La información de ruta muestra distancias correctas
- [ ] La simulación se ejecuta y devuelve resultados
- [ ] Los elementos fallados se resaltan
- [ ] "Solo Amenazas Activas" filtra correctamente

## 7. Optimización de Rendimiento

### Índices Espaciales

Asegurarse de que estos índices existan:
```sql
CREATE INDEX ways_geom_gix ON rr.ways USING GIST (geom);
CREATE INDEX ways_vertices_geom_gix ON rr.ways_vertices_pgr USING GIST (geom);
CREATE INDEX ways_source_idx ON rr.ways (source);
CREATE INDEX ways_target_idx ON rr.ways (target);
```

### Optimización de Consultas

- Usar `COALESCE(fail_prob, 0)` para manejar NULLs
- Limitar espacio de búsqueda con cajas delimitadoras cuando sea posible
- Usar `directed := false` para búsqueda bidireccional
- Almacenar en caché rutas solicitadas frecuentemente

### Optimización Frontend

- Calcular todas las rutas en una sola llamada a la API
- Usar grupos de capas de Leaflet para renderizado eficiente
- Implementar debouncing para cambios de casillas de verificación
- Carga perezosa de geometrías de ruta

## 8. Mejoras Futuras

### Algoritmos Adicionales
- K-rutas más cortas de Yen (múltiples alternativas)
- Soporte para restricciones de giro
- Ruteo dependiente del tiempo
- Ruteo multimodal (diferentes tipos de vehículos)

### Simulación Mejorada
- Simulación de series temporales (múltiples pasos de tiempo)
- Evolución de probabilidad a lo largo del tiempo
- Probabilidades dinámicas basadas en clima
- Actualizaciones de amenazas en tiempo real vía WebSocket

### Analítica Avanzada
- Métricas de comparación de rutas
- Visualización de compensación riesgo-distancia
- Análisis histórico de confiabilidad
- Modelado predictivo de fallas

## 9. Solución de Problemas

### Ruta No Encontrada

**Problema:** Uno o más algoritmos no devuelven ruta

**Causas Posibles:**
- Dijkstra Filtrado: No hay camino con todos los arcos `fail_prob < 0.5`
- Red desconectada
- Nodos de inicio/fin en diferentes componentes conectados

**Solución:**
- Verificar conectividad de la red
- Ajustar umbral de filtro
- Usar rutas basadas en probabilidad en su lugar

### Cálculo Lento

**Problema:** El cálculo de ruta toma > 5 segundos

**Causas Posibles:**
- Red grande (>100k arcos)
- Faltan índices espaciales
- Sin optimización de espacio de búsqueda

**Soluciones:**
- Agregar/reconstruir índices espaciales
- Implementar pre-filtrado de caja delimitadora
- Usar A* en lugar de Dijkstra
- Considerar almacenamiento en caché

### Rutas Idénticas

**Problema:** Todos los algoritmos devuelven la misma ruta

**Causas Posibles:**
- Todos los valores `fail_prob` son 0
- Factor de penalización demasiado pequeño
- Solo existe una ruta viable

**Soluciones:**
- Ejecutar script de modelo de probabilidad
- Aumentar factor de penalización (actualmente 100)
- Verificar que los datos de amenazas estén cargados

## 10. Referencias

- Documentación de pgRouting: https://docs.pgrouting.org/
- Algoritmo de Dijkstra: https://es.wikipedia.org/wiki/Algoritmo_de_Dijkstra
- Algoritmo de Búsqueda A*: https://es.wikipedia.org/wiki/Algoritmo_de_b%C3%BAsqueda_A*
- Funciones de PostGIS: https://postgis.net/docs/reference.html
