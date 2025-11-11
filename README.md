# Redes_Ruteo

Sistema de ruteo resiliente para la Región Metropolitana de Chile con análisis de amenazas y cálculo de rutas óptimas.

## Descripción

Este proyecto implementa un sistema completo de ruteo resiliente que:
- Extrae y procesa datos de infraestructura vial desde OpenStreetMap
- Recopila amenazas en tiempo real desde múltiples fuentes (Waze, clima, reductores de velocidad)
- Calcula probabilidades de falla para segmentos de red
- Proporciona una interfaz web interactiva para visualización y cálculo de rutas
- Implementa múltiples algoritmos de ruteo (Dijkstra, A*) con diferentes funciones de costo

## Características

✨ **Interfaz Web Interactiva**: Mapa interactivo con Leaflet para visualizar amenazas y rutas
🗺️ **Múltiples Algoritmos**: Dijkstra (distancia), Dijkstra (probabilidad), A* (probabilidad), Dijkstra filtrado
🚨 **Datos de Amenazas en Tiempo Real**: Integración con API de Waze para incidentes y tráfico
📊 **Análisis de Probabilidad**: Modelo de probabilidad de falla basado en amenazas
🔄 **Sistema Resiliente**: Datos de muestra de respaldo cuando las APIs externas fallan
🎯 **Simulación de Fallas**: Simula fallas en la red basándose en probabilidades

## Requisitos

- Python 3.8+
- PostgreSQL 12+ con extensión PostGIS
- Docker y Docker Compose (opcional, recomendado)

## Instalación Rápida

1. **Clonar el repositorio**
```bash
git clone https://github.com/iAxSnow/Redes_Ruteo.git
cd Redes_Ruteo/Redes_Ruteo
```

2. **Configurar base de datos**
```bash
# Iniciar PostgreSQL con Docker
docker-compose up -d

# Cargar esquema
psql -U postgres -h localhost -d rr -f schema.sql
```

3. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

4. **Verificar configuración del sistema de ruteo**
```bash
# Este script diagnostica problemas comunes de configuración
python scripts/diagnose_routing.py
```

El script de diagnóstico verifica:
- ✓ Conexión a la base de datos
- ✓ Extensiones PostGIS y pgRouting instaladas
- ✓ Tablas y datos cargados correctamente
- ✓ Topología de pgRouting creada
- ✓ Funcionalidad de ruteo

Si el diagnóstico indica problemas, sigue las soluciones sugeridas.

4. **Configurar variables de entorno**
Crear archivo `.env` (ver `.env.example` para referencia completa):
```env
PGHOST=localhost
PGPORT=5432
PGDATABASE=rr
PGUSER=postgres
PGPASSWORD=postgres

# Área de interés (Santiago, Chile)
BBOX_S=-33.8
BBOX_W=-70.95
BBOX_N=-33.2
BBOX_E=-70.45

# OpenWeather API (opcional, para amenazas de clima)
OPENWEATHER_KEY=your_api_key_here
```

**Nota sobre OpenWeather API**: Las nuevas claves API pueden tardar hasta 2 horas en activarse después del registro. Si recibes errores 401 (Unauthorized), espera la activación completa antes de ejecutar el script de clima.

## Uso

### 1. Cargar Infraestructura (OSM)
```bash
# Extraer datos de OSM
python infraestructura/osm_roads_overpass_parallel.py

# Cargar en base de datos
python loaders/load_ways_nodes.py
```

### 2. Cargar Amenazas (Opcional)
**Nota**: Las amenazas son opcionales. El sistema puede calcular rutas basadas solo en distancia sin necesidad de cargar amenazas. Las amenazas permiten calcular rutas considerando probabilidades de falla.

#### 🔴 IMPORTANTE: Recolección de Datos Reales

Para producción, necesitas **datos reales de Waze**. El sistema tiene una estrategia de 3 niveles:
1. **APIs de Waze** (preferido, pero a menudo fallan)
2. **WebDriver con Firefox** (confiable para datos reales) ← **RECOMENDADO**
3. **Datos de muestra** (solo para desarrollo/testing)

#### Configurar WebDriver para Datos Reales

```bash
# 1. Instalar Firefox y GeckoDriver
sudo apt-get update
sudo apt-get install -y firefox firefox-geckodriver
# O si usas Firefox ESR: sudo apt-get install -y firefox-esr firefox-geckodriver

# 2. Instalar Selenium
pip install selenium

# 3. Verificar configuración (EJECUTA ESTO PRIMERO)
python scripts/diagnose_webdriver.py

# 4. Si todo está OK, recolectar datos reales de Waze
python amenazas/waze_incidents_parallel_adaptive.py

# 5. Cargar amenazas en base de datos
python loaders/load_threats_waze.py
```

**Si `diagnose_webdriver.py` reporta errores**, sigue las soluciones indicadas. Ver `WEBDRIVER_SETUP.md` para troubleshooting detallado.

#### Otros Extractores de Amenazas

```bash
# Traffic calming (reductores de velocidad)
python amenazas/traffic_calming_as_threats_parallel.py
python loaders/load_threats_calming.py

# OpenWeather (requiere OPENWEATHER_KEY en .env y clave activada)
python amenazas/weather_openweather_parallel.py
python loaders/load_threats_weather.py
```

### 3. Calcular Probabilidades de Falla (Opcional)
**Nota**: Este paso es opcional y solo necesario si cargaste amenazas en el paso anterior. Si no ejecutas este paso, todas las rutas se calcularán basándose solo en distancia.

```bash
python scripts/probability_model.py
```

### 4. Iniciar Interfaz Web
```bash
python app.py
```

Abrir navegador en http://localhost:5000

## Estructura del Proyecto

```
Redes_Ruteo/
├── amenazas/                      # ETL de amenazas
│   ├── waze_incidents_parallel_adaptive.py
│   ├── amenazas_muestra.geojson  # Datos de respaldo
│   ├── traffic_calming_as_threats_parallel.py
│   └── weather_openweather_parallel.py
├── infraestructura/               # ETL de infraestructura OSM
│   └── osm_roads_overpass_parallel.py
├── loaders/                       # Cargadores de base de datos
│   ├── load_ways_nodes.py
│   ├── load_threats_waze.py
│   └── load_metadata.py
├── scripts/                       # Scripts de análisis
│   └── probability_model.py
├── app.py                         # Servidor Flask
├── templates/                     # Plantillas HTML
│   └── index.html
├── static/                        # Recursos estáticos
│   ├── css/
│   └── js/
│       └── main.js
├── schema.sql                     # Esquema de base de datos
├── requirements.txt               # Dependencias Python
└── README*.md                     # Documentación
```

## Documentación Adicional

- [README_WEB.md](README_WEB.md) - Documentación de la interfaz web
- [README_ETL.md](README_ETL.md) - Documentación del pipeline ETL
- [README_ROUTING.md](README_ROUTING.md) - Documentación de algoritmos de ruteo
- [README_ADVANCED.md](README_ADVANCED.md) - Características avanzadas

## Solución de Problemas

### La API de Waze devuelve errores 404
El sistema ahora usa automáticamente datos de muestra cuando la API de Waze falla. Los datos de muestra están en `amenazas/amenazas_muestra.geojson`.

### No se pueden calcular rutas
- Verifica que los datos de infraestructura estén cargados: `SELECT COUNT(*) FROM rr.ways;`
- Asegúrate de que los puntos de inicio y fin estén dentro del área de cobertura
- Revisa los logs del servidor Flask para mensajes de error detallados

### La base de datos no está conectada
- Verifica que PostgreSQL esté ejecutándose: `docker-compose ps`
- Verifica las credenciales en `.env`
- Prueba la conexión: `psql -U postgres -h localhost -d rr`

## Contribuir

Las contribuciones son bienvenidas. Por favor:
1. Haz fork del repositorio
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT.

## Contacto

Proyecto desarrollado para el curso de Redes y Ruteo, Universidad de Chile.
