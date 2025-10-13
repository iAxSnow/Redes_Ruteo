#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loader amenazas clima (OpenWeather) con deduplicación por ext_id.
Entrada: amenazas/weather_threats.geojson (Polygon features; props.ext_id)
Tabla: rr.amenazas_clima(ext_id PK, kind, subtype, severity, props jsonb, geom)
"""
import os, json
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values, Json
from dotenv import load_dotenv

load_dotenv()

PGHOST=os.getenv("PGHOST","localhost")
PGPORT=int(os.getenv("PGPORT","5432"))
PGDATABASE=os.getenv("PGDATABASE","rr")
PGUSER=os.getenv("PGUSER","postgres")
PGPASSWORD=os.getenv("PGPASSWORD","postgres")

ROOT=Path(__file__).resolve().parents[1]
GJ=ROOT/"amenazas"/"weather_threats.geojson"

def main():
    gj=json.loads(GJ.read_text(encoding="utf-8"))
    feats=gj.get("features") or []

    best={}
    for f in feats:
        p=f.get("properties") or {}
        ext=p.get("ext_id")
        if not ext: continue
        cur=best.get(ext)
        if (cur is None) or ((p.get("severity") or 0) > ((cur.get("properties") or {}).get("severity") or 0)):
            best[ext]=f

    rows=[]
    for ext,f in best.items():
        p=f["properties"]; g=f["geometry"]
        rows.append((ext, p.get("kind"), p.get("subtype"), p.get("severity") or 1, Json(p), json.dumps(g)))

    print(f"[L] clima únicos: {len(rows)} (de {len(feats)})")

    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO rr.amenazas_clima (ext_id, kind, subtype, severity, props, geom)
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
    print("[OK] Amenazas clima cargadas.")

if __name__=="__main__":
    main()
