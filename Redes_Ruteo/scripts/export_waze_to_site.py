#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

PGHOST=os.getenv("PGHOST","localhost")
PGPORT=int(os.getenv("PGPORT","5432"))
PGDATABASE=os.getenv("PGDATABASE","rr")
PGUSER=os.getenv("PGUSER","postgres")
PGPASSWORD=os.getenv("PGPASSWORD","postgres")

OUT = Path(__file__).resolve().parents[1] / "site" / "data" / "waze_incidents.geojson"
OUT.parent.mkdir(parents=True, exist_ok=True)

SQL = """
WITH feats AS (
  SELECT jsonb_build_object(
           'type','Feature',
           'geometry', ST_AsGeoJSON(geom)::jsonb,
           'properties', jsonb_build_object(
               'provider', 'WAZE',
               'ext_id', ext_id,
               'kind', kind,
               'subtype', subtype,
               'severity', severity,
               'description', props->>'description',
               'street', props->>'street',
               'type_raw', props->>'type_raw',
               'timestamp', props->>'timestamp'
           )
         ) AS feature
  FROM rr.amenazas_waze
)
SELECT jsonb_build_object('type','FeatureCollection','features', coalesce(jsonb_agg(feature), '[]'::jsonb)) AS fc
FROM feats;
"""

def main():
    with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(SQL)
            row = cur.fetchone()
            fc = row["fc"]
    OUT.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Exportado: {OUT}")

if __name__=="__main__":
    main()
