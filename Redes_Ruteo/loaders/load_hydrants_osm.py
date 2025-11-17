#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loader de hidrantes OSM.
Entrada: metadata/hydrants.geojson
Tabla: rr.metadata_hydrants(ext_id PK, status text, provider text, props jsonb, geom Point)
"""
import os, json, math
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values, Json
from dotenv import load_dotenv

load_dotenv()

PGHOST = os.getenv("PGHOST","localhost")
PGPORT = int(os.getenv("PGPORT","5432"))
PGDATABASE = os.getenv("PGDATABASE","rr")
PGUSER = os.getenv("PGUSER","postgres")
PGPASSWORD = os.getenv("PGPASSWORD","postgres")

ROOT = Path(__file__).resolve().parents[1]
GJ_PATH = ROOT / "metadata" / "hydrants.geojson"

def is_nan(v):
    try:
        return isinstance(v, float) and math.isnan(v)
    except:
        return False

def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k,v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if is_nan(obj):
        return None
    return obj

def main():
    if not GJ_PATH.exists():
        raise FileNotFoundError(f"No existe {GJ_PATH}")
    gj = json.loads(GJ_PATH.read_text(encoding="utf-8"))
    feats = gj.get("features") or []

    best = {}
    for f in feats:
        p = f.get("properties") or {}
        ext = f.get("id") or p.get("osm_id")
        if not ext:
            g = f.get("geometry") or {}
            if g.get("type") == "Point":
                c = g.get("coordinates") or []
                if len(c) == 2:
                    ext = f"pt:{c[0]:.6f},{c[1]:.6f}"
        if not ext: continue
        cur = best.get(ext)
        def score(pp):
            s = 0
            # OSM hidrants are assumed functional unless specified
            s += 1
            if pp.get("provider"): s += 1
            return s
        if (cur is None) or (score(p) > score((cur.get("properties") or {}))):
            best[ext] = f

    rows = []
    for ext, f in best.items():
        p = clean(f.get("properties") or {})
        status = "vigente"  # Assume OSM hydrants are functional
        g = f.get("geometry")
        rows.append((ext, status, "OSM", Json(p, dumps=lambda x: json.dumps(x, ensure_ascii=False, allow_nan=False)), json.dumps(g)))

    print(f"[L] hidrantes únicos OSM: {len(rows)} (de {len(feats)})")

    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO rr.metadata_hydrants (ext_id, status, provider, props, geom)
                VALUES %s
                ON CONFLICT (ext_id) DO UPDATE SET
                  status  = EXCLUDED.status,
                  provider= EXCLUDED.provider,
                  props   = EXCLUDED.props,
                  geom    = EXCLUDED.geom;
            """, rows,
            template="(%s,%s,%s,%s, ST_SetSRID(ST_GeomFromGeoJSON(%s),4326))",
            page_size=1000)
        conn.commit()
    print("[OK] Hidrantes OSM cargados.")

if __name__ == "__main__":
    main()