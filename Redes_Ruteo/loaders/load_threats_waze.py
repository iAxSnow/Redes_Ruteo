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
GJ_SAMPLE_PATH = ROOT / "amenazas" / "amenazas_muestra.geojson"

def main():
    # Try to load the main waze_incidents file
    if GJ_PATH.exists() and GJ_PATH.stat().st_size > 0:
        try:
            data=json.loads(GJ_PATH.read_text(encoding="utf-8"))
            feats=data.get("features") or []
            if len(feats) > 0:
                print(f"[L] Loading from {GJ_PATH}")
            else:
                # File exists but is empty, use sample data
                print(f"[WARN] {GJ_PATH} has no features, using sample data")
                if GJ_SAMPLE_PATH.exists():
                    data=json.loads(GJ_SAMPLE_PATH.read_text(encoding="utf-8"))
                    feats=data.get("features") or []
                else:
                    print(f"[ERROR] Sample file {GJ_SAMPLE_PATH} not found")
                    return
        except Exception as e:
            print(f"[ERROR] Failed to read {GJ_PATH}: {e}, using sample data")
            if GJ_SAMPLE_PATH.exists():
                data=json.loads(GJ_SAMPLE_PATH.read_text(encoding="utf-8"))
                feats=data.get("features") or []
            else:
                print(f"[ERROR] Sample file {GJ_SAMPLE_PATH} not found")
                return
    else:
        # Main file doesn't exist, use sample data
        print(f"[WARN] {GJ_PATH} not found, using sample data from {GJ_SAMPLE_PATH}")
        if GJ_SAMPLE_PATH.exists():
            data=json.loads(GJ_SAMPLE_PATH.read_text(encoding="utf-8"))
            feats=data.get("features") or []
        else:
            print(f"[ERROR] Sample file {GJ_SAMPLE_PATH} not found")
            return

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
