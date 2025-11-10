# Resumen de Correcciones - Redes_Ruteo

## Problema Original
El issue reportaba tres problemas principales:
1. Las rutas no se calculaban sin incidentes de Waze
2. La amenaza de OpenWeather no funcionaba después de recolectar información por más de 1 hora
3. Se necesitaba asegurar que todos los comandos funcionen correctamente

## Soluciones Implementadas

### 1. Cálculo de Rutas sin Amenazas ✓

**Problema**: El sistema requería datos de amenazas para calcular rutas.

**Solución**: 
- Las consultas de ruteo en `app.py` ya usaban `COALESCE(fail_prob, 0)`, por lo que las rutas funcionan sin amenazas
- Se actualizó `scripts/probability_model.py` para manejar tablas de amenazas vacías o inexistentes
- Se agregó documentación clara en README.md indicando que las amenazas son opcionales

**Archivos modificados**:
- `scripts/probability_model.py`: Ahora verifica si las tablas existen y maneja casos sin amenazas gracefully
- `README.md`: Clarifica que las amenazas y cálculos de probabilidad son opcionales

### 2. OpenWeather API - Manejo de Activación ✓

**Problema**: El script no informaba correctamente cuando la API key no estaba activada, silenciando los errores.

**Solución**:
- Mejorado el manejo de errores en `amenazas/weather_openweather_parallel.py`
- El script ahora reporta errores específicos (401 Unauthorized, 403 Forbidden)
- Informa al usuario que las nuevas claves API pueden tardar hasta 2 horas en activarse
- No sobrescribe archivos existentes si todas las solicitudes fallan
- Muestra progreso cada 10 celdas procesadas

**Archivos modificados**:
- `amenazas/weather_openweather_parallel.py`: Mejor logging y manejo de errores
- `README.md`: Nota sobre el tiempo de activación de la API key (hasta 2 horas)
- `.env.example`: Plantilla con la configuración necesaria para OpenWeather

### 3. Comandos y Scripts Corregidos ✓

**Problema**: Los scripts bash hacían referencia a nombres de archivo incorrectos.

**Solución**:
- Actualizados scripts para usar nombres correctos con sufijo `_parallel`
- Los loaders ahora manejan archivos faltantes o vacíos sin fallar
- Scripts incluyen mensajes de advertencia apropiados

**Archivos modificados**:
- `scripts/run_threats.sh`: Referencias actualizadas a `*_parallel_adaptive.py`
- `scripts/run_all_etl_parallel.sh`: Referencias actualizadas y mejor manejo de errores
- `loaders/load_threats_weather.py`: Verifica que el archivo exista antes de cargar
- `loaders/load_threats_calming.py`: Verifica que el archivo exista antes de cargar

### 4. Mejoras Adicionales ✓

**Modelo de Probabilidad Mejorado**:
- Ahora procesa TODAS las fuentes de amenazas (Waze, Weather, Traffic Calming)
- Aplica pesos diferentes según el tipo de amenaza:
  - Waze: probabilidad completa (0.5)
  - Weather: probabilidad escalada por severidad (0.5 * severity/3)
  - Traffic Calming: probabilidad reducida (0.5 * 0.3)
- Maneja intersecciones espaciales para amenazas de clima (polígonos)

**Documentación**:
- Creado `.env.example` con todas las variables de entorno necesarias
- Actualizado README.md con instrucciones más claras
- Agregado script de verificación `scripts/verify_fixes.py`

## Verificación de las Correcciones

Ejecuta el script de verificación:
```bash
cd Redes_Ruteo
python scripts/verify_fixes.py
```

Este script verifica:
- ✓ Consultas de ruteo usan COALESCE para manejar NULL fail_prob
- ✓ Modelo de probabilidad maneja tablas de amenazas faltantes
- ✓ Script de clima reporta problemas de activación de API key
- ✓ Loaders verifican si los archivos existen antes de cargar
- ✓ Todos los scripts necesarios están presentes

## Uso del Sistema

### Sin Amenazas (Solo Distancia)
```bash
# 1. Cargar infraestructura
python infraestructura/osm_roads_overpass_parallel.py
python loaders/load_ways_nodes.py

# 2. Iniciar servidor web
python app.py
```

### Con Amenazas (Rutas Resilientes)
```bash
# 1. Cargar infraestructura (como arriba)

# 2. Configurar .env con OPENWEATHER_KEY
cp .env.example .env
# Editar .env y agregar tu API key

# 3. Cargar amenazas
python amenazas/waze_incidents_parallel_adaptive.py
python loaders/load_threats_waze.py

python amenazas/weather_openweather_parallel.py
python loaders/load_threats_weather.py

python amenazas/traffic_calming_as_threats_parallel.py
python loaders/load_threats_calming.py

# 4. Calcular probabilidades
python scripts/probability_model.py

# 5. Iniciar servidor web
python app.py
```

## Notas Importantes

1. **OpenWeather API Key**: Las nuevas claves pueden tardar hasta 2 horas en activarse. Si ves errores 401, espera la activación.

2. **Amenazas Opcionales**: El sistema funciona perfectamente sin cargar amenazas. En ese caso, todas las rutas se calculan usando solo la distancia.

3. **Modelo de Probabilidad**: Solo necesitas ejecutar `probability_model.py` si cargaste amenazas. Si no hay amenazas, todas las probabilidades permanecen en 0.0.

4. **Waze Fallback**: El script de Waze ya incluye datos de muestra de respaldo si la API falla.

## Archivos Creados/Modificados

### Nuevos Archivos
- `Redes_Ruteo/.env.example` - Plantilla de configuración
- `Redes_Ruteo/scripts/verify_fixes.py` - Script de verificación

### Archivos Modificados
- `README.md` - Documentación actualizada
- `Redes_Ruteo/scripts/probability_model.py` - Procesa todas las amenazas, maneja tablas vacías
- `Redes_Ruteo/amenazas/weather_openweather_parallel.py` - Mejor manejo de errores
- `Redes_Ruteo/loaders/load_threats_weather.py` - Maneja archivos faltantes
- `Redes_Ruteo/loaders/load_threats_calming.py` - Maneja archivos faltantes
- `Redes_Ruteo/scripts/run_threats.sh` - Referencias corregidas
- `Redes_Ruteo/scripts/run_all_etl_parallel.sh` - Referencias corregidas
