#!/bin/bash
#
# export_all_to_site.sh
# 
# Exporta todas las amenazas (Waze, Weather, Traffic Calming) desde la base de datos
# a archivos GeoJSON en el directorio site/data/ para visualización en el mapa web.
#
# Uso:
#   bash scripts/export_all_to_site.sh
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SITE_DATA_DIR="$PROJECT_ROOT/site/data"

# ----- INICIO DE LA CORRECCIÓN 1: Exportar variables -----
# Exportar variables para que sean visibles por los procesos de Python
export SCRIPT_DIR
export PROJECT_ROOT
# ----- FIN DE LA CORRECCIÓN 1 -----

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}EXPORTANDO TODAS LAS AMENAZAS Y HIDRANTES AL SITIO WEB${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Create site/data directory if it doesn't exist
mkdir -p "$SITE_DATA_DIR"

# Check if PostgreSQL connection works
echo -e "${YELLOW}[1/4]${NC} Verificando conexión a la base de datos..."
if ! python3 -c "import psycopg2, os; from dotenv import load_dotenv; load_dotenv(dotenv_path=os.path.join(os.environ['PROJECT_ROOT'], '.env')); conn = psycopg2.connect(host=os.getenv('PGHOST','localhost'), port=int(os.getenv('PGPORT','5432')), dbname=os.getenv('PGDATABASE','rr'), user=os.getenv('PGUSER','postgres'), password=os.getenv('PGPASSWORD','postgres')); conn.close()" 2>/dev/null; then
    echo -e "${RED}[ERROR]${NC} No se pudo conectar a la base de datos PostgreSQL"
    echo -e "         Verifica tus credenciales en el archivo .env"
    exit 1
fi
echo -e "${GREEN}✓${NC} Conexión exitosa"
echo ""

# Export Waze threats
echo -e "${YELLOW}[2/4]${NC} Exportando amenazas de Waze..."
python3 << 'EOF'
import os, json
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

project_root = os.environ.get('PROJECT_ROOT')
if project_root:
    load_dotenv(dotenv_path=Path(project_root) / '.env')
else:
    load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

script_dir = Path(os.environ.get('SCRIPT_DIR'))
OUT = script_dir.parent / "site" / "data" / "waze_threats.geojson"
OUT.parent.mkdir(parents=True, exist_ok=True)

SQL = """
WITH feats AS (
  SELECT jsonb_build_object(
           'type', 'Feature',
           'geometry', ST_AsGeoJSON(geom)::jsonb,
           'properties', jsonb_build_object(
               'id', ext_id,
               'provider', 'Waze',
               'ext_id', ext_id,
               'kind', kind,
               'subtype', subtype,
               'severity', severity,
               'timestamp', created_at,
               'props', props
           )
         ) AS feature
  FROM rr.amenazas_waze
)
SELECT jsonb_build_object('type', 'FeatureCollection', 'features', coalesce(jsonb_agg(feature), '[]'::jsonb)) AS fc
FROM feats;
"""

try:
    conn = psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(SQL)
    result = cursor.fetchone()
    
    with open(OUT, 'w') as f:
        json.dump(result['fc'], f, indent=2)
    
    count = len(result['fc'].get('features', []))
    print(f"\033[32m✓\033[0m Exportadas {count} amenazas de Waze")

except Exception as e:
    print(f"\033[31m⚠\033[0m No se pudieron exportar amenazas de Waze: {e}")
finally:
    if 'cursor' in locals() and cursor:
        cursor.close()
    if 'conn' in locals() and conn:
        conn.close()
EOF
echo ""

# Export Weather threats
echo -e "${YELLOW}[3/4]${NC} Exportando amenazas climáticas..."
python3 << 'EOF'
import os, json
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

project_root = os.environ.get('PROJECT_ROOT')
if project_root:
    load_dotenv(dotenv_path=Path(project_root) / '.env')
else:
    load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

script_dir = Path(os.environ.get('SCRIPT_DIR'))
OUT = script_dir.parent / "site" / "data" / "weather_threats.geojson"
OUT.parent.mkdir(parents=True, exist_ok=True)

SQL = """
WITH feats AS (
  SELECT jsonb_build_object(
           'type', 'Feature',
           'geometry', ST_AsGeoJSON(geom)::jsonb,
           'properties', jsonb_build_object(
               'id', ext_id,
               'provider', 'OpenWeather',
               'grid_id', ext_id,
               'timestamp', created_at,
               'props', props
           )
         ) AS feature
  FROM rr.amenazas_clima
)
SELECT jsonb_build_object('type', 'FeatureCollection', 'features', coalesce(jsonb_agg(feature), '[]'::jsonb)) AS fc
FROM feats;
"""

try:
    conn = psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(SQL)
    result = cursor.fetchone()
    
    with open(OUT, 'w') as f:
        json.dump(result['fc'], f, indent=2)

    count = len(result['fc'].get('features', []))
    print(f"\033[32m✓\033[0m Exportadas {count} amenazas climáticas")

except Exception as e:
    print(f"\033[31m⚠\033[0m No se pudieron exportar amenazas climáticas: {e}")
finally:
    if 'cursor' in locals() and cursor:
        cursor.close()
    if 'conn' in locals() and conn:
        conn.close()
EOF
echo ""

# Export Traffic Calming threats
echo -e "${YELLOW}[4/5]${NC} Exportando reductores de velocidad (traffic calming)..."
python3 << 'EOF'
import os, json
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

project_root = os.environ.get('PROJECT_ROOT')
if project_root:
    load_dotenv(dotenv_path=Path(project_root) / '.env')
else:
    load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

script_dir = Path(os.environ.get('SCRIPT_DIR'))
OUT = script_dir.parent / "site" / "data" / "calming_threats.geojson"
OUT.parent.mkdir(parents=True, exist_ok=True)

SQL = """
WITH feats AS (
  SELECT jsonb_build_object(
           'type', 'Feature',
           'geometry', ST_AsGeoJSON(geom)::jsonb,
           'properties', jsonb_build_object(
               'id', ext_id,
               'provider', 'OSM',
               'ext_id', ext_id,
               'kind', kind,
               'subtype', subtype,
               'timestamp', created_at,
               'props', props
           )
         ) AS feature
  FROM rr.amenazas_calming
)
SELECT jsonb_build_object('type', 'FeatureCollection', 'features', coalesce(jsonb_agg(feature), '[]'::jsonb)) AS fc
FROM feats;
"""

try:
    conn = psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(SQL)
    result = cursor.fetchone()
    
    with open(OUT, 'w') as f:
        json.dump(result['fc'], f, indent=2)

    count = len(result['fc'].get('features', []))
    print(f"\033[32m✓\033[0m Exportados {count} reductores de velocidad")

except Exception as e:
    print(f"\033[31m⚠\033[0m No se pudieron exportar reductores de velocidad: {e}")
finally:
    if 'cursor' in locals() and cursor:
        cursor.close()
    if 'conn' in locals() and conn:
        conn.close()
EOF
echo ""

# Export Hydrants
echo -e "${YELLOW}[5/5]${NC} Exportando hidrantes..."
python3 << 'EOF'
import os, json
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

project_root = os.environ.get('PROJECT_ROOT')
if project_root:
    load_dotenv(dotenv_path=Path(project_root) / '.env')
else:
    load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

script_dir = Path(os.environ.get('SCRIPT_DIR'))
OUT = script_dir.parent / "site" / "data" / "hydrants.geojson"
OUT.parent.mkdir(parents=True, exist_ok=True)

SQL = """
WITH feats AS (
  SELECT jsonb_build_object(
           'type', 'Feature',
           'geometry', ST_AsGeoJSON(geom)::jsonb,
           'properties', jsonb_build_object(
               'id', ext_id,
               'status', status,
               'provider', provider,
               'props', props
           )
         ) AS feature
  FROM rr.metadata_hydrants
  WHERE geom IS NOT NULL
)
SELECT jsonb_build_object('type', 'FeatureCollection', 'features', coalesce(jsonb_agg(feature), '[]'::jsonb)) AS fc
FROM feats;
"""

try:
    conn = psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(SQL)
    result = cursor.fetchone()
    
    with open(OUT, 'w') as f:
        json.dump(result['fc'], f, indent=2)

    count = len(result['fc'].get('features', []))
    print(f"\033[32m✓\033[0m Exportados {count} hidrantes")

except Exception as e:
    print(f"\033[31m⚠\033[0m No se pudieron exportar hidrantes: {e}")
finally:
    if 'cursor' in locals() and cursor:
        cursor.close()
    if 'conn' in locals() and conn:
        conn.close()
EOF
echo ""

echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}✅ EXPORTACIÓN COMPLETADA${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo -e "Archivos generados en: ${YELLOW}$SITE_DATA_DIR${NC}"
echo -e "  - waze_threats.geojson"
echo -e "  - weather_threats.geojson"
echo -e "  - calming_threats.geojson"
echo -e "  - hydrants.geojson"
echo ""
echo -e "Estos archivos pueden ser usados por la aplicación web para"
echo -e "visualizar las amenazas y hidrantes en el mapa."
echo ""