# WebDriver Setup for Waze Data Collection

## 🔴 IMPORTANTE: WebDriver es Necesario para Datos Reales

**Para producción, WebDriver NO es opcional**. Las APIs de Waze públicas frecuentemente fallan o están bloqueadas. WebDriver es el método **más confiable** para recolectar datos reales de incidentes de Waze.

El script de recolección de Waze (`amenazas/waze_incidents_parallel_adaptive.py`) usa una estrategia de 3 niveles:

1. **APIs de Waze** (intenta primero, pero a menudo falla)
2. **WebDriver con Selenium (Firefox)** ← **MÉTODO RECOMENDADO PARA DATOS REALES**
3. **Datos de muestra** (solo fallback para desarrollo)

## Diagnóstico Rápido

**ANTES de instalar**, verifica tu configuración actual:

```bash
python scripts/diagnose_webdriver.py
```

Este script te dirá exactamente qué falta y cómo arreglarlo.

## Requisitos

Para usar WebDriver necesitas:

1. **Selenium** (ya incluido en requirements.txt)
2. **Firefox o Firefox ESR** instalado en el sistema
3. **GeckoDriver** compatible con tu versión de Firefox

## Instalación

### 1. Instalar Dependencias Python

```bash
pip install -r requirements.txt
```

### 2. Instalar Firefox y GeckoDriver

#### Ubuntu/Debian

**Opción 1: Firefox estándar** (recomendado para versiones recientes de Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y firefox firefox-geckodriver
```

**Opción 2: Firefox ESR** (Extended Support Release - común en Debian y contenedores)

```bash
sudo apt-get update
sudo apt-get install -y firefox-esr firefox-geckodriver
```

**Nota**: El sistema detecta automáticamente si tienes `firefox` o `firefox-esr` instalado y usa el que encuentre.

#### macOS

```bash
# Instalar Firefox
brew install --cask firefox

# Instalar GeckoDriver
brew install geckodriver
```

#### Windows

1. Descarga Firefox desde https://www.mozilla.org/firefox/
2. Descarga GeckoDriver desde https://github.com/mozilla/geckodriver/releases
3. Extrae geckodriver.exe y agrégalo al PATH del sistema

### 3. Verificar Instalación

```bash
# Verificar Firefox
firefox --version
# O si tienes Firefox ESR:
firefox-esr --version

# Verificar GeckoDriver
geckodriver --version

# Ejecutar diagnóstico completo
python scripts/diagnose_webdriver.py
```

Si el diagnóstico muestra ✅ en todos los checks, estás listo para recolectar datos reales.

## Uso

### Recolectar Datos Reales de Waze

```bash
python amenazas/waze_incidents_parallel_adaptive.py
```

**Identificar si estás usando datos reales**:
- ✅ Datos reales: `[info] Firefox WebDriver started successfully` → `[ok] WebDriver extracted X alerts, Y jams`
- ❌ Datos de muestra: `[OK] Using sample data from amenazas_muestra.geojson`

### Verificar Datos Recolectados

```bash
# Ver estadísticas del archivo generado
python -c "import json; data=json.load(open('amenazas/waze_incidents.geojson')); print(f'Alerts: {len([f for f in data[\"features\"] if f[\"properties\"][\"type\"] == \"alert\"])}, Jams: {len([f for f in data[\"features\"] if f[\"properties\"][\"type\"] == \"jam\"])}')"
```

## Troubleshooting

### Firefox no detectado (pero está instalado)

Si el diagnóstico dice "Firefox no está instalado" pero tienes Firefox ESR:

```bash
# Verificar que firefox-esr está instalado
which firefox-esr
firefox-esr --version
```

El sistema detecta automáticamente `firefox-esr` desde la versión más reciente del código.

### GeckoDriver no encontrado

```bash
# Ubuntu/Debian
sudo apt-get install -y firefox-geckodriver

# Verificar instalación
which geckodriver
geckodriver --version
```

### Error "Firefox WebDriver failed"

Causas comunes:
1. **GeckoDriver no compatible**: Asegúrate que GeckoDriver es compatible con tu versión de Firefox
2. **Firefox no puede ejecutarse en headless**: Algunos entornos (como contenedores) requieren configuración adicional
3. **Permisos**: El usuario debe tener permisos para ejecutar Firefox

**Solución para contenedores**:
```bash
# Instalar dependencias adicionales para Firefox en contenedores
sudo apt-get install -y libgtk-3-0 libdbus-glib-1-2 libxt6 libx11-xcb1
```

### WebDriver tarda mucho

Firefox WebDriver puede tardar 10-30 segundos en iniciar y cargar la página de Waze. Esto es normal. El script muestra mensajes de progreso:

```
[info] API endpoints failed, trying WebDriver scraping...
[info] Found Firefox at: /usr/bin/firefox-esr
[info] Starting Firefox WebDriver for tile ...
[info] Firefox WebDriver started successfully
[ok] WebDriver extracted 45 alerts, 23 jams
```

### Modo de Desarrollo sin WebDriver

Si solo estás desarrollando y no necesitas datos reales, el sistema usa automáticamente datos de muestra sin necesidad de instalar Firefox/GeckoDriver:

```bash
# Esto funciona sin WebDriver
python amenazas/waze_incidents_parallel_adaptive.py

# Verás:
# [info] API endpoints failed, trying WebDriver scraping...
# [info] WebDriver not available. Using fallback data.
# [OK] Using sample data from amenazas_muestra.geojson
```

## Verificación Final

Ejecuta estos comandos para confirmar que todo funciona:

```bash
# 1. Diagnóstico completo
python scripts/diagnose_webdriver.py

# 2. Si el diagnóstico pasa, recolectar datos
python amenazas/waze_incidents_parallel_adaptive.py

# 3. Verificar que se recolectaron datos reales (no muestra)
grep -i "webdriver extracted" amenazas/waze_incidents.geojson
```

Si ves "WebDriver extracted X alerts", ¡estás recolectando datos reales! 🎉

## Soporte

Si tienes problemas:

1. Ejecuta `python scripts/diagnose_webdriver.py` y copia el output completo
2. Verifica qué versión de Firefox/Firefox ESR tienes: `firefox --version` o `firefox-esr --version`
3. Verifica qué versión de GeckoDriver tienes: `geckodriver --version`
4. Incluye esta información cuando reportes el problema
