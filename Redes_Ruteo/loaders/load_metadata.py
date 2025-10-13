import os, json
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

PGHOST=os.getenv("PGHOST","localhost")
PGPORT=int(os.getenv("PGPORT","5432"))
PGDATABASE=os.getenv("PGDATABASE","rr")
PGUSER=os.getenv("PGUSER","postgres")
PGPASSWORD=os.getenv("PGPASSWORD","postgres")

ROOT = Path(__file__).resolve().parents[1]

def load_hydrants():
    fp = ROOT/"metadata"/"hydrants.geojson"
    data = json.loads(fp.read_text(encoding="utf-8"))
    rows = []
    for f in data["features"]:
        x,y = f["geometry"]["coordinates"]
        p = f["properties"]
        rows.append((int(p["osm_id"]), json.dumps(p), f"SRID=4326;POINT({x} {y})"))
    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor() as cur:
            execute_values(cur, """
            INSERT INTO rr.hydrants (osm_id, props, geom, provider)
            VALUES %s
            ON CONFLICT (osm_id) DO NOTHING;
            """, rows, template="(%s, %s::jsonb, ST_GeomFromText(%s), 'OSM')", page_size=2000)
        conn.commit()
    print(f"[OK] Cargados hidrantes: {len(rows)}")

if __name__=="__main__":
    load_hydrants()
