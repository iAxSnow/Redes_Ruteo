import os, json
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

load_dotenv()

PGHOST=os.getenv("PGHOST","localhost")
PGPORT=int(os.getenv("PGPORT","5432"))
PGDATABASE=os.getenv("PGDATABASE","rr")
PGUSER=os.getenv("PGUSER","postgres")
PGPASSWORD=os.getenv("PGPASSWORD","postgres")
START_NODE=int(os.getenv("START_NODE","0"))
END_NODE=int(os.getenv("END_NODE","0"))

OUT = Path(__file__).resolve().parents[1] / "site" / "data" / "route.geojson"

def pick_two_nodes(cur):
    cur.execute("SELECT source FROM rr.ways ORDER BY random() LIMIT 1")
    s = cur.fetchone()[0]
    cur.execute("SELECT target FROM rr.ways ORDER BY random() LIMIT 1")
    t = cur.fetchone()[0]
    return int(s), int(t)

def export_route():
    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor() as cur:
            s, t = (START_NODE, END_NODE)
            if s==0 or t==0:
                s, t = pick_two_nodes(cur)
                print(f"[i] START_NODE/END_NODE no definidos. Usando aleatorios: {s} -> {t}")
            sql = """
            WITH route AS (
              SELECT w.geom
              FROM pgr_dijkstra(
                'SELECT id, source, target, cost, reverse_cost FROM rr.ways_cost_length',
                %s, %s, true
              ) AS dj
              JOIN rr.ways w ON dj.edge = w.id
              ORDER BY dj.seq
            )
            SELECT ST_AsGeoJSON(ST_LineMerge(ST_Union(geom)));
            """
            cur.execute(sql, (s, t))
            g = cur.fetchone()[0]
            if not g:
                raise RuntimeError("No se pudo construir ruta. Prueba con otros nodos.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"type":"FeatureCollection","features":[{"type":"Feature","geometry":json.loads(g),"properties":{}}]}, f)
    print(f"[OK] Ruta exportada a {OUT}")

if __name__=="__main__":
    export_route()
