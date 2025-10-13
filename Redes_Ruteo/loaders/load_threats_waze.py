#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loader amenazas Waze con deduplicación por ext_id.
Entrada:
  amenazas/waze_incidents.geojson (features: Point/LineString, props.ext_id, kind='incident')
Tabla:
  rr.amenazas_waze(ext_id PK, kind text, subtype text, severity int, props jsonb, geom geometry)
"""

import os, json
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
GJ_PATH = ROOT / "amenazas" / "waze_incidents.geojson"

def main():
    data=json.loads(GJ_PATH.read_text(encoding="utf-8"))
    feats=data.get("features") or []

    best={}
    for f in feats:
        p=f.get("properties") or {}
        ext=p.get("ext_id")
        if not ext: continue
        # preferir severidad más alta
        cur=best.get(ext)
        if (cur is None) or ((p.get("severity") or 0) > ((cur.get("properties") or {}).get("severity") or 0)):
            best[ext]=f

    rows=[]
    for ext,f in best.items():
        p=f["properties"]; g=f["geometry"]
        rows.append((ext, p.get("kind"), p.get("subtype"), p.get("severity") or 0, Json(p), json.dumps(g)))

    print(f"[L] Waze únicos: {len(rows)} (de {len(feats)})")

    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO rr.amenazas_waze (ext_id, kind, subtype, severity, props, geom)
                VALUES %s
                ON CONFLICT (ext_id) DO UPDATE SET
                  kind     = EXCLUDED.kind,
                  subtype  = EXCLUDED.subtype,
                  severity = EXCLUDED.severity,
                  props    = EXCLUDED.props,
                  geom     = EXCLUDED.geom;
            """, rows,
            template="(%s,%s,%s,%s,%s, ST_SetSRID(ST_GeomFromGeoJSON(%s),4326))",
            page_size=1000)
        conn.commit()
    print("[OK] Amenazas Waze cargadas.")

if __name__ == "__main__":
    main()
