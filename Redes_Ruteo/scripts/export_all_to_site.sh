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

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}EXPORTANDO TODAS LAS AMENAZAS AL SITIO WEB${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Create site/data directory if it doesn't exist
mkdir -p "$SITE_DATA_DIR"

# Check if PostgreSQL connection works
echo -e "${YELLOW}[1/4]${NC} Verificando conexión a la base de datos..."
if ! python3 -c "import psycopg2, os; from dotenv import load_dotenv; load_dotenv(); conn = psycopg2.connect(host=os.getenv('PGHOST','localhost'), port=int(os.getenv('PGPORT','5432')), dbname=os.getenv('PGDATABASE','rr'), user=os.getenv('PGUSER','postgres'), password=os.getenv('PGPASSWORD','postgres')); conn.close()" 2>/dev/null; then
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

load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

OUT = Path(__file__).resolve().parents[1] / "site" / "data" / "waze_threats.geojson"
OUT.parent.mkdir(parents=True, exist_ok=True)

SQL = """
WITH feats AS (
  SELECT jsonb_build_object(
           'type', 'Feature',
           'geometry', ST_AsGeoJSON(geom)::jsonb,
           'properties', jsonb_build_object(
               'id', id,
               'provider', provider,
               'ext_id', ext_id,
               'kind', kind,
               'subtype', subtype,
               'severity', severity,
               'timestamp', timestamp,
               'props', props
           )
         ) AS feature
  FROM rr.amenazas_waze
)
SELECT jsonb_build_object('type', 'FeatureCollection', 'features', coalesce(jsonb_agg(feature), '[]'::jsonb)) AS fc
FROM feats;
"""

try:
    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(SQL)
            row = cur.fetchone()
            fc = row["fc"]
    
    # Get actual script directory from environment
    script_dir = Path(os.environ.get('SCRIPT_DIR', Path(__file__).resolve().parent))
    out_path = script_dir.parent / "site" / "data" / "waze_threats.geojson"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    out_path.write_text(json.dumps(fc, ensure_ascii=False, indent=2), encoding="utf-8")
    count = len(fc.get('features', []))
    print(f"✓ Exportadas {count} amenazas de Waze")
except Exception as e:
    print(f"⚠ No se pudieron exportar amenazas de Waze: {e}")
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

load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

SQL = """
WITH feats AS (
  SELECT jsonb_build_object(
           'type', 'Feature',
           'geometry', ST_AsGeoJSON(geom)::jsonb,
           'properties', jsonb_build_object(
               'id', id,
               'provider', provider,
               'weather_code', weather_code,
               'weather_desc', weather_desc,
               'severity', severity,
               'timestamp', timestamp,
               'props', props
           )
         ) AS feature
  FROM rr.amenazas_clima
)
SELECT jsonb_build_object('type', 'FeatureCollection', 'features', coalesce(jsonb_agg(feature), '[]'::jsonb)) AS fc
FROM feats;
"""

try:
    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(SQL)
            row = cur.fetchone()
            fc = row["fc"]
    
    script_dir = Path(os.environ.get('SCRIPT_DIR', Path(__file__).resolve().parent))
    out_path = script_dir.parent / "site" / "data" / "weather_threats.geojson"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    out_path.write_text(json.dumps(fc, ensure_ascii=False, indent=2), encoding="utf-8")
    count = len(fc.get('features', []))
    print(f"✓ Exportadas {count} amenazas climáticas")
except Exception as e:
    print(f"⚠ No se pudieron exportar amenazas climáticas: {e}")
EOF
echo ""

# Export Traffic Calming threats
echo -e "${YELLOW}[4/4]${NC} Exportando reductores de velocidad (traffic calming)..."
python3 << 'EOF'
import os, json
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

SQL = """
WITH feats AS (
  SELECT jsonb_build_object(
           'type', 'Feature',
           'geometry', ST_AsGeoJSON(geom)::jsonb,
           'properties', jsonb_build_object(
               'id', id,
               'osm_id', osm_id,
               'traffic_calming', traffic_calming,
               'props', props
           )
         ) AS feature
  FROM rr.amenazas_calming
)
SELECT jsonb_build_object('type', 'FeatureCollection', 'features', coalesce(jsonb_agg(feature), '[]'::jsonb)) AS fc
FROM feats;
"""

try:
    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(SQL)
            row = cur.fetchone()
            fc = row["fc"]
    
    script_dir = Path(os.environ.get('SCRIPT_DIR', Path(__file__).resolve().parent))
    out_path = script_dir.parent / "site" / "data" / "calming_threats.geojson"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    out_path.write_text(json.dumps(fc, ensure_ascii=False, indent=2), encoding="utf-8")
    count = len(fc.get('features', []))
    print(f"✓ Exportados {count} reductores de velocidad")
except Exception as e:
    print(f"⚠ No se pudieron exportar reductores de velocidad: {e}")
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
echo ""
echo -e "Estos archivos pueden ser usados por la aplicación web para"
echo -e "visualizar las amenazas en el mapa."
echo ""
