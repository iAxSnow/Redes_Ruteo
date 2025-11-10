#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loader para traffic_calming OSM con deduplicación por ext_id.
Entrada: amenazas/traffic_calming_threats.geojson (Point, props.ext_id)
Tabla: rr.amenazas_calming(ext_id PK, kind, subtype, severity, props jsonb, geom)
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
GJ=ROOT/"amenazas"/"traffic_calming_threats.geojson"

def main():
    if not GJ.exists():
        print(f"[WARN] {GJ} no existe. Ejecuta primero traffic_calming_as_threats_parallel.py")
        print("[INFO] No se cargaron amenazas de traffic calming.")
        return
    
    try:
        gj=json.loads(GJ.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[ERROR] No se pudo leer {GJ}: {e}")
        return
    
    feats=gj.get("features") or []
    
    if len(feats) == 0:
        print(f"[WARN] {GJ} no contiene amenazas.")
        return

    best={}
    for f in feats:
        p=f.get("properties") or {}
        ext=p.get("ext_id") or None
        if not ext: continue
        best.setdefault(ext, f)  # todos severidad 1; mantiene primero

    rows=[]
    for ext,f in best.items():
        p=f["properties"]; g=f["geometry"]
        rows.append((ext, p.get("kind"), p.get("subtype"), p.get("severity") or 1, Json(p), json.dumps(g)))

    print(f"[L] calming únicos: {len(rows)} (de {len(feats)})")
    
    if len(rows) == 0:
        print("[WARN] No hay amenazas de traffic calming válidas para cargar.")
        return

    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO rr.amenazas_calming (ext_id, kind, subtype, severity, props, geom)
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
    print("[OK] Amenazas calming cargadas.")

if __name__=="__main__":
    main()
