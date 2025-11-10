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

# Crear enlaces simbólicos para compatibilidad
sudo ln -s /snap/bin/chromium /usr/local/bin/chromium-browser
sudo ln -s /snap/bin/chromium.chromedriver /usr/local/bin/chromedriver

# Agregar /snap/bin a PATH si no está
export PATH=/snap/bin:$PATH
```

#### Fedora/RHEL
```bash
sudo dnf install -y chromium chromium-chromedriver
```

#### macOS
```bash
brew install --cask google-chrome
brew install chromedriver
```

#### Windows
Descarga e instala Chrome desde: https://www.google.com/chrome/

### 3. Instalar ChromeDriver

#### Opción A: Instalación Automática (Recomendado)
Selenium 4.x+ puede descargar ChromeDriver automáticamente.

#### Opción B: Instalación Manual

1. Verifica tu versión de Chrome:
   - Abre Chrome → Menú (⋮) → Ayuda → Información de Google Chrome
   
2. Descarga ChromeDriver compatible:
   - https://chromedriver.chromium.org/downloads
   
3. Extrae y mueve a una ubicación en tu PATH:
   ```bash
   # Linux/macOS
   sudo mv chromedriver /usr/local/bin/
   sudo chmod +x /usr/local/bin/chromedriver
   
   # Windows
   # Mueve chromedriver.exe a C:\Windows\System32\ o añade a PATH
   ```

## Verificación

### Método 1: Script de Diagnóstico (Recomendado)

Usa el script de diagnóstico automático:

```bash
python scripts/diagnose_webdriver.py
```

Este script verifica:
- ✓ Chrome/Chromium instalado
- ✓ ChromeDriver instalado
- ✓ Selenium instalado
- ✓ WebDriver puede iniciar
- ✓ Navegación funciona

**Si algo falla, el script te dirá exactamente cómo arreglarlo.**

### Método 2: Prueba Manual

Prueba que WebDriver funciona:

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)
driver.get('https://www.waze.com')
print(driver.title)
driver.quit()
```

Si esto funciona sin errores, WebDriver está configurado correctamente.

## Uso

El script usará automáticamente WebDriver cuando:
1. Las APIs de Waze fallen (404, timeout, etc.)
2. Selenium esté instalado
3. Chrome/ChromeDriver estén disponibles

### Estrategia de Fallback de 3 Niveles

1. **API Endpoints** (preferido, más rápido)
   - Intenta múltiples endpoints de Waze
   
2. **WebDriver Scraping** (respaldo confiable)
   - Usa Chrome headless para contenido dinámico
   - Extrae datos de objetos JavaScript en la página
   
3. **Sample Data** (fallback final)
   - Usa `amenazas_muestra.geojson`
   - Garantiza que el sistema siempre tenga datos

## Troubleshooting

### Error: "Chrome instance exited" o "session not created" con instalación Snap

**Síntoma**: El diagnóstico muestra que Chromium está instalado pero no puede ejecutarse.

**Causa**: Chromium está instalado como snap (Ubuntu 24.04+) y no es accesible desde Python.

**Solución (Opción 1 - Recomendada)**: Usar paquetes tradicionales:
```bash
# Desinstalar snap
sudo snap remove chromium

# Instalar paquetes tradicionales
sudo apt-get update
sudo apt-get install -y chromium-browser chromium-chromedriver

# Verificar
python scripts/diagnose_webdriver.py
```

**Solución (Opción 2)**: Configurar snap para que funcione:
```bash
# Crear enlaces simbólicos
sudo ln -sf /snap/bin/chromium /usr/local/bin/chromium-browser
sudo ln -sf /snap/bin/chromium.chromedriver /usr/local/bin/chromedriver

# Agregar a PATH
export PATH=/snap/bin:$PATH
echo 'export PATH=/snap/bin:$PATH' >> ~/.bashrc

# Verificar
chromedriver --version
chromium-browser --version
```

### Error: "Chrome instance exited" o "session not created" (general)
**Causa**: Chrome/Chromium no está instalado o no puede iniciar.

**Solución**:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y chromium-browser chromium-chromedriver

# Verificar instalación
chromium-browser --version
chromedriver --version

# Si los comandos no funcionan, puede que necesites:
which chromium-browser  # Buscar ubicación de Chrome
which chromedriver      # Buscar ubicación de ChromeDriver
```

**Alternativa**: El sistema automáticamente usará datos de muestra si WebDriver falla. No es necesario arreglarlo para usar el sistema.

### Error: "WebDriver executable not found"
**Solución**: Instala ChromeDriver o añádelo a tu PATH
```bash
# Debian/Ubuntu
sudo apt-get install chromium-chromedriver

# O descarga manualmente desde:
# https://chromedriver.chromium.org/downloads
```

### Error: "Chrome binary not found"
**Solución**: Instala Chrome/Chromium
```bash
# Ubuntu/Debian
sudo apt-get install chromium-browser

# Fedora
sudo dnf install chromium

# macOS
brew install --cask google-chrome
```

### Error: "Chrome version mismatch"
**Solución**: Actualiza Chrome y ChromeDriver a versiones compatibles
```bash
# Ubuntu: actualizar ambos
sudo apt-get update
sudo apt-get upgrade chromium-browser chromium-chromedriver
```

### WebDriver es muy lento
**Solución**: 
- Reduce `WAZE_RETRIES` en .env (default: 2)
- Usa `WAZE_SIMULATE=true` para testing
- El sistema automáticamente usará sample data si WebDriver toma demasiado tiempo

### "El sistema funciona pero no recoge datos de Waze en tiempo real"

**🔴 IMPORTANTE**: Si ves este mensaje en los logs:
```
[OK] Using sample data from amenazas_muestra.geojson
```

**Esto significa que NO estás recolectando datos reales**. Causas comunes:
- Chrome/ChromeDriver no están instalados
- Chrome/ChromeDriver tienen versiones incompatibles
- APIs de Waze están caídas Y WebDriver falla

**Para PRODUCCIÓN, DEBES arreglar WebDriver**. Los datos de muestra son solo para desarrollo/testing.

**Acción requerida**:
1. Ejecuta: `python scripts/diagnose_webdriver.py`
2. Sigue las soluciones indicadas
3. Verifica que el diagnóstico pase todos los checks
4. Ejecuta nuevamente el script de Waze

### "Quiero solo desarrollo/testing (sin datos reales)"

Si solo necesitas probar el sistema sin datos reales:
- El sistema automáticamente usará sample data si WebDriver falla
- Puedes usar `WAZE_SIMULATE=true` en .env para generar datos simulados
- Esto es SOLO para desarrollo, NO para producción

## Variables de Entorno

```bash
# .env
WAZE_TIMEOUT=30        # Timeout para cada request (segundos)
WAZE_RETRIES=2         # Intentos antes de usar WebDriver
WAZE_MAX_DEPTH=2       # Profundidad de subdivisión de tiles
WAZE_SIMULATE=false    # true para usar datos simulados
```

## Modo Sin WebDriver

Si no quieres instalar WebDriver, el script funcionará con sample data:

1. No instales selenium (o desinstálalo)
2. El script automáticamente saltará el paso de WebDriver
3. Usará `amenazas_muestra.geojson` como datos de respaldo

## Logs

El script muestra el progreso:

```
[info] API endpoints failed, trying WebDriver scraping...
[info] Starting WebDriver for tile -33.8000,-70.9500,-33.2000,-70.4500
[ok] WebDriver extracted 5 alerts, 3 jams
```

O si falla:

```
[warn] WebDriver also failed: Browser automation failed (WebDriver): ...
[info] Using sample data as final fallback
```

## Producción

Para entornos de producción:

1. **Docker**: Incluye Chrome en tu Dockerfile
   ```dockerfile
   RUN apt-get update && apt-get install -y \
       chromium-browser \
       chromium-chromedriver
   ```

2. **Cron Jobs**: Asegúrate que DISPLAY esté configurado para headless
   ```bash
   DISPLAY=:99 python amenazas/waze_incidents_parallel_adaptive.py
   ```

3. **CI/CD**: Usa imágenes con Chrome preinstalado
   ```yaml
   # GitHub Actions example
   - uses: browser-actions/setup-chrome@latest
   ```
