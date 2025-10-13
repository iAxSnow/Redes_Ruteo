#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loader de ONEWAY con deduplicación por osm_id para evitar
"ON CONFLICT DO UPDATE command cannot affect row a second time".

Entrada:
  metadata/road_oneway.geojson   (props: { osm_id, oneway }, geom LineString)

Tablas requeridas:
  rr.metadata_oneway(osm_id PK, oneway boolean, geom geometry(LineString,4326))
  rr.ways(id=OSM way id) con columna oneway boolean opcional (si se quiere aplicar)

Comportamiento:
  - Deduplica por osm_id manteniendo el registro con oneway no-nulo;
    si ambos nulos o ambos válidos, conserva el primero visto.
  - UPSERT a rr.metadata_oneway
  - UPDATE rr.ways.oneway = m.oneway cuando m.oneway no es nulo
"""

import os, json
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

PGHOST = os.getenv("PGHOST","localhost")
PGPORT = int(os.getenv("PGPORT","5432"))
PGDATABASE = os.getenv("PGDATABASE","rr")
PGUSER = os.getenv("PGUSER","postgres")
PGPASSWORD = os.getenv("PGPASSWORD","postgres")

ROOT = Path(__file__).resolve().parents[1]
GJ_PATH = ROOT / "metadata" / "road_oneway.geojson"

def main():
    data = json.loads(GJ_PATH.read_text(encoding="utf-8"))
    feats = data.get("features") or []

    best = {}  # osm_id -> feature
    for f in feats:
        p = f.get("properties") or {}
        oid = p.get("osm_id")
        if oid is None: continue
        keep = False
        if oid not in best:
            keep = True
        else:
            # preferir oneway no-nulo
            prev = best[oid]
            prev_val = (prev.get("properties") or {}).get("oneway")
            if prev_val is None and p.get("oneway") is not None:
                keep = True
        if keep:
            best[oid] = f

    rows = []
    for oid, f in best.items():
        p = f["properties"]
        g = f["geometry"]
        rows.append((oid, p.get("oneway"), json.dumps(g)))

    print(f"[L] oneway únicos por osm_id: {len(rows)} (de {len(feats)})")

    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor() as cur:
            # Upsert metadata_oneway
            execute_values(cur, """
                INSERT INTO rr.metadata_oneway (osm_id, oneway, geom)
                VALUES %s
                ON CONFLICT (osm_id) DO UPDATE SET
                  oneway = EXCLUDED.oneway,
                  geom   = EXCLUDED.geom;
            """, rows,
            template="(%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s),4326))",
            page_size=1000)

            # Aplicar a rr.ways si existe columna
            try:
                cur.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='rr' AND table_name='ways' AND column_name='oneway'")
                if cur.fetchone():
                    cur.execute("""
                        UPDATE rr.ways w
                           SET oneway = m.oneway
                          FROM rr.metadata_oneway m
                         WHERE w.id = m.osm_id AND m.oneway IS NOT NULL;
                    """)
            except Exception as e:
                print(f"[warn] No se aplicó a rr.ways.oneway: {e}")

        conn.commit()
    print("[OK] ONEWAY cargado y aplicado.")

if __name__ == "__main__":
    main()
