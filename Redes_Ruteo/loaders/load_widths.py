#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loader de anchos (widths) con **deduplicación por osm_id** para evitar:
psycopg2.errors.CardinalityViolation: ON CONFLICT DO UPDATE command cannot affect row a second time
Regla: conservar por osm_id el feature "más rico":
- Prefiere aquel que tenga width_raw o maxwidth_raw
- Si empatan, prefiere el que tenga lanes no nulo
- Si sigue el empate, conserva el primero visto

Requiere:
  - metadata/road_widths.geojson (salida de road_widths_osm[_parallel].py)
  - Tabla rr.metadata_widths(osm_id PK, highway, lanes, width_m, maxwidth_m, width_raw, maxwidth_raw, geom)
  - Tabla rr.ways con columna id=osm_id y columnas width_m, maxwidth_m

"""

import os, json, math
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
GJ_PATH = ROOT / "metadata" / "road_widths.geojson"

def score_feat(p):
    """Mayor puntaje = más informativo"""
    s = 0
    if p.get("width_raw"): s += 2
    if p.get("maxwidth_raw"): s += 2
    if p.get("lanes") is not None: s += 1
    return s

def parse_width_to_m(v):
    if not v: return None
    s = str(v).strip().lower()
    num = ""
    for ch in s:
        if ch.isdigit() or ch in ".-":
            num += ch
        elif num and ch in " ,m":
            break
    try:
        val = float(num) if num not in ("","-",".") else None
    except:
        val = None
    if val is None:
        return None
    # unidades
    if "ft" in s or "feet" in s:
        return val * 0.3048
    if "cm" in s:
        return val / 100.0
    return val  # default metros

def main():
    data = json.loads(GJ_PATH.read_text(encoding="utf-8"))
    feats = data.get("features") or []

    # --- Deduplicación por osm_id ---
    best = {}  # osm_id -> (score, feature)
    for f in feats:
        p = f.get("properties") or {}
        oid = p.get("osm_id")
        if oid is None: continue
        sc = score_feat(p)
        prev = best.get(oid)
        if (prev is None) or (sc > prev[0]) or (sc == prev[0] and (p.get("lanes") is not None) and ((prev[1].get("properties") or {}).get("lanes") is None)):
            best[oid] = (sc, f)

    rows = []
    for oid, (_sc, f) in best.items():
        p = f["properties"]
        g = f["geometry"]
        lanes = p.get("lanes")
        width_raw = p.get("width_raw")
        maxwidth_raw = p.get("maxwidth_raw")
        width_m = parse_width_to_m(width_raw)
        maxwidth_m = parse_width_to_m(maxwidth_raw)
        rows.append((
            oid, p.get("highway"), lanes, width_m, maxwidth_m, width_raw, maxwidth_raw,
            json.dumps(g)
        ))

    print(f"[L] widths únicos por osm_id: {len(rows)} (de {len(feats)})")

    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor() as cur:
            # Inserta / upsert en rr.metadata_widths
            execute_values(cur, """
                INSERT INTO rr.metadata_widths
                  (osm_id, highway, lanes, width_m, maxwidth_m, width_raw, maxwidth_raw, geom)
                VALUES %s
                ON CONFLICT (osm_id) DO UPDATE SET
                  highway      = EXCLUDED.highway,
                  lanes        = EXCLUDED.lanes,
                  width_m      = EXCLUDED.width_m,
                  maxwidth_m   = EXCLUDED.maxwidth_m,
                  width_raw    = EXCLUDED.width_raw,
                  maxwidth_raw = EXCLUDED.maxwidth_raw,
                  geom         = EXCLUDED.geom;
            """, rows,
            template="(%s,%s,%s,%s,%s,%s,%s, ST_SetSRID(ST_GeomFromGeoJSON(%s),4326))",
            page_size=1000)

            # Aplica a rr.ways (solo actualiza cuando metadata aporta algo no nulo)
            cur.execute("""
                UPDATE rr.ways w
                   SET width_m    = COALESCE(m.width_m, w.width_m),
                       maxwidth_m = COALESCE(m.maxwidth_m, w.maxwidth_m)
                  FROM rr.metadata_widths m
                 WHERE w.id = m.osm_id;
            """)
        conn.commit()

    print("[OK] Cargada metadata de widths y aplicada a rr.ways.")

if __name__ == "__main__":
    main()
