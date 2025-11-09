# Interfaz Web para el Proyecto de Ruteo

Este directorio contiene la interfaz web basada en Flask para el proyecto de ruteo.

## Estructura

```
Redes_Ruteo/
├── app.py                  # Servidor Flask con rutas principales y API
├── templates/
│   └── index.html         # Plantilla HTML principal
├── static/
│   ├── css/
│   │   └── style.css      # Estilos para mapa y panel de control
│   └── js/
│       └── main.js        # Lógica frontend para mapa y amenazas
├── requirements.txt        # Dependencias de Python incluyendo Flask
└── .env                   # Variables de entorno (no en el repo)
```

## Características

1. **Mapa Interactivo**: Mapa basado en Leaflet centrado en Santiago, Chile
2. **Geolocalización**: Botón para centrar el mapa en la ubicación del usuario
3. **Visualización de Amenazas**: Muestra amenazas de múltiples fuentes (Waze, Reductores de Velocidad, Clima)
4. **Control de Capas**: Checkbox para mostrar/ocultar marcadores de amenazas
5. **Detalles de Amenazas**: Haz clic en los marcadores para ver información detallada en ventanas emergentes
6. **Estadísticas**: Conteo en tiempo real de amenazas por fuente
7. **Cálculo de Rutas**: Calcula múltiples rutas óptimas usando diferentes algoritmos (Dijkstra, A*)
8. **Simulación de Fallas**: Simula fallas en la red basándose en probabilidades

## Instalación

1. Instalar dependencias de Python:
```bash
cd Redes_Ruteo
pip install -r requirements.txt
```

2. Configurar variables de entorno (crear archivo `.env`):
```
PGHOST=localhost
PGPORT=5432
PGDATABASE=rr
PGUSER=postgres
PGPASSWORD=postgres

# Opcional: Habilitar modo de depuración para desarrollo (NO para producción)
# FLASK_DEBUG=1
```

3. Asegurarse de que la base de datos PostgreSQL esté ejecutándose con el esquema cargado:
```bash
docker-compose up -d
```

4. Cargar datos de amenazas:
```bash
# Cargar datos de muestra o ejecutar extractores de Waze
cd Redes_Ruteo
python loaders/load_threats_waze.py
```

## Ejecutar la Aplicación

Iniciar el servidor de desarrollo Flask:
```bash
cd Redes_Ruteo
python app.py
```

La aplicación estará disponible en http://localhost:5000

## Endpoints de la API

### GET /
Devuelve la interfaz web principal.

### GET /api/threats
Devuelve todas las amenazas de la base de datos como una FeatureCollection GeoJSON.

**Formato de respuesta:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "ext_id": "...",
        "kind": "incident",
        "subtype": "CLOSURE",
        "severity": 3,
        "source": "waze",
        ...
      },
      "geometry": {
        "type": "Point",
        "coordinates": [-70.65, -33.45]
      }
    }
  ]
}
```

### POST /api/calculate_route
Calcula rutas óptimas entre dos puntos usando diferentes algoritmos.

**Parámetros de entrada:**
```json
{
  "start": {"lat": -33.45, "lng": -70.65},
  "end": {"lat": -33.43, "lng": -70.64},
  "algorithm": "all"
}
```

**Respuesta:**
```json
{
  "dijkstra_dist": {
    "route_geojson": {...},
    "compute_time_ms": 45.2,
    "algorithm": "Dijkstra (Distancia)"
  },
  "dijkstra_prob": {...},
  "astar_prob": {...},
  "filtered_dijkstra": {...}
}
```

### POST /api/simulate_failures
Simula fallas en elementos de la red basándose en sus probabilidades de falla.

**Respuesta:**
```json
{
  "failed_edges": [1, 5, 23, ...],
  "failed_nodes": [12, 45, ...],
  "total_failed": 42
}
```

## Desarrollo

La aplicación usa:
- **Flask 3.0.0**: Framework web
- **Leaflet 1.9.4**: Biblioteca de mapas interactivos
- **PostgreSQL + PostGIS**: Base de datos espacial
- **psycopg2**: Adaptador PostgreSQL para Python

## Solución de Problemas

### La aplicación no puede conectarse a la base de datos
- Verifica que PostgreSQL esté ejecutándose: `docker-compose ps`
- Verifica las credenciales en el archivo `.env`
- Asegúrate de que el esquema esté cargado: `psql -U postgres -d rr -f schema.sql`

### No se muestran amenazas
- Ejecuta el cargador de amenazas: `python loaders/load_threats_waze.py`
- Si la API de Waze falla, el sistema usará datos de muestra de `amenazas/amenazas_muestra.geojson`

### Error al calcular rutas
- Verifica que los datos de infraestructura (ways, nodes) estén cargados en la base de datos
- Asegúrate de que los puntos de inicio y fin estén dentro del área de cobertura de la red

## Mejoras Futuras

Próximas mejoras incluirán:
- Actualización de rutas en tiempo real basadas en amenazas
- Visualización de funciones de costo
- Comparación de múltiples algoritmos de ruteo
- Exportación de rutas calculadas

