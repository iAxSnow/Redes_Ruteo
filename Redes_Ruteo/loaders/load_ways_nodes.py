import os, json, re, time
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from pyproj import Geod

load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

ROOT = Path(__file__).resolve().parents[1]
WAYS_GEOJSON = ROOT / "infraestructura" / "ways.geojson"
NODES_GEOJSON = ROOT / "infraestructura" / "nodes.geojson"

RE_NUM = re.compile(r"([-+]?\d*\.?\d+)")
GEOD = Geod(ellps="WGS84")

def parse_width_to_m(v):
    if not v: return None
    s = str(v).strip().lower()
    m = RE_NUM.search(s)
    if not m: return None
    val = float(m.group(1))
    if "ft" in s or "feet" in s: return val * 0.3048
    if "cm" in s: return val / 100.0
    return val

def default_width_by_highway(hw):
    if not hw: return 7.0
    hw = hw.lower()
    if hw in ("residential","living_street","service"): return 6.0
    if hw in ("tertiary","unclassified"): return 7.0
    if hw in ("secondary","primary"): return 7.5
    if hw in ("trunk","motorway"): return 9.0
    return 7.0

def chunks(iterable, size):
    buf = []
    for it in iterable:
        buf.append(it)
        if len(buf) >= size:
            yield buf; buf = []
    if buf: yield buf

def line_length_m(coords):
    if len(coords) < 2: return 0.0
    total = 0.0
    for (x1,y1),(x2,y2) in zip(coords[:-1], coords[1:]):
        _,_,dist = GEOD.inv(x1,y1,x2,y2)
        total += dist
    return total

def load_nodes(cur, features_iter, chunk_size=10000):
    q = "INSERT INTO rr.nodes (id, geom) VALUES %s ON CONFLICT (id) DO NOTHING;"
    n=0
    for batch in chunks(features_iter, chunk_size):
        execute_values(cur, q, batch,
            template="(%s, ST_SetSRID(ST_MakePoint(%s,%s),4326))",
            page_size=1000
        )
        n += len(batch)
    return n

def load_ways(cur, features_iter, chunk_size=2000):
    q = '''
    INSERT INTO rr.ways
      (id, osm_id, source, target, geom, length_m, highway, oneway, maxspeed_kmh, lanes, surface, access, tags)
    VALUES %s
    ON CONFLICT (id) DO UPDATE SET
      osm_id=EXCLUDED.osm_id,
      source=EXCLUDED.source,
      target=EXCLUDED.target,
      geom=EXCLUDED.geom,
      length_m=EXCLUDED.length_m,
      highway=EXCLUDED.highway,
      oneway=EXCLUDED.oneway,
      maxspeed_kmh=EXCLUDED.maxspeed_kmh,
      lanes=EXCLUDED.lanes,
      surface=EXCLUDED.surface,
      access=EXCLUDED.access,
      tags=EXCLUDED.tags;
    '''
    n=0
    for batch in chunks(features_iter, chunk_size):
        execute_values(cur, q, batch,
            template=("(%s,%s,%s,%s,"
                      " ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),"
                      " %s, %s,%s,%s,%s,%s,%s, %s::jsonb)"),
            page_size=400
        )
        n += len(batch)
    return n

def main():
    print("[L] Cargando GeoJSON → Postgres (lotes, con longitudes y anchos)…")
    nodes_geo = json.loads(NODES_GEOJSON.read_text(encoding="utf-8"))
    ways_geo  = json.loads(WAYS_GEOJSON.read_text(encoding="utf-8"))

    def iter_nodes_rows():
        for f in nodes_geo["features"]:
            nid = int(f["properties"]["id"]); x, y = f["geometry"]["coordinates"]
            yield (nid, x, y)

    def iter_ways_rows():
        for f in ways_geo["features"]:
            p = f["properties"]; geom = f["geometry"]
            coords = geom["coordinates"]
            if geom["type"] == "MultiLineString":
                coords = [pt for seg in coords for pt in seg]
            length_m = line_length_m(coords)
            width_m = parse_width_to_m(p.get("width_raw"))
            maxwidth_m = parse_width_to_m(p.get("maxwidth_raw"))
            if width_m is None:
                lanes = p.get("lanes")
                if lanes:
                    try: width_m = max(float(lanes)*3.2, 3.5)
                    except: pass
            if width_m is None:
                width_m = default_width_by_highway(p.get("highway"))
            yield (
                int(p["id"]), int(p["osm_id"]), int(p["source"]), int(p["target"]),
                json.dumps(geom),
                float(length_m),
                p.get("highway"), bool(p.get("oneway", False)),
                p.get("maxspeed_kmh"), p.get("lanes"),
                p.get("surface"), p.get("access"),
                json.dumps({
                    **(p.get("tags", {}) or {}),
                    "width_m": width_m,
                    "maxwidth_m": maxwidth_m,
                    "width_raw": p.get("width_raw"),
                    "maxwidth_raw": p.get("maxwidth_raw")
                })
            )

    with psycopg2.connect(
        host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD
    ) as conn:
        with conn.cursor() as cur:
            n_nodes = load_nodes(cur, iter_nodes_rows())
            conn.commit()
            print(f"[L] nodes insertados: {n_nodes}")

            n_ways = load_ways(cur, iter_ways_rows())
            conn.commit()
            print(f"[L] ways insertados: {n_ways}")

    print("[OK] Carga completada.")

if __name__ == "__main__":
    t0=time.time(); main(); print(f"[OK] Hecho en {time.time()-t0:.1f}s")
