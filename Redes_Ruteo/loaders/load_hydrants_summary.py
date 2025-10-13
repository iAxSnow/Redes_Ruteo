# loaders/load_hydrants_summary.py
import os, json
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

PGHOST=os.getenv("PGHOST","localhost")
PGPORT=int(os.getenv("PGPORT","5432"))
PGDATABASE=os.getenv("PGDATABASE","rr")
PGUSER=os.getenv("PGUSER","postgres")
PGPASSWORD=os.getenv("PGPASSWORD","postgres")

DATA = Path(__file__).resolve().parents[1] / "metadata" / "hydrants_siss_summary.json"

DDL = """
CREATE TABLE IF NOT EXISTS rr.hydrant_status_muni (
  id                BIGSERIAL PRIMARY KEY,
  periodo           integer,
  codigo_comuna     integer,
  nombre_comuna     text,
  codigo_localidad  integer,
  nombre_localidad  text,
  grifos_existente  integer,
  grifos_no_operativos integer,
  grifos_reparados  integer,
  grifos_reemplazados integer,
  grifos_reparar    integer,
  grifos_reemplazar integer,
  inversion_total   numeric,
  inversion_programada numeric,
  tasa_no_operativos numeric,
  tasa_a_reparar    numeric,
  tasa_a_reemplazar numeric,
  raw               jsonb
);
CREATE INDEX IF NOT EXISTS hydrant_status_muni_comuna_idx ON rr.hydrant_status_muni (codigo_comuna);
"""

def main():
  with psycopg2.connect(host=PGHOST, port=PGPORT, dbname=PGDATABASE, user=PGUSER, password=PGPASSWORD) as conn:
    with conn.cursor() as cur:
      cur.execute(DDL)
      data = json.loads(DATA.read_text(encoding="utf-8"))
      rows = []
      for r in data:
        rows.append((
          r.get("PERIODO_INFORMADO"),
          r.get("CODIGO_COMUNA"),
          r.get("NOMBRE_COMUNA"),
          r.get("CODIGO_LOCALIDAD"),
          r.get("NOMBRE_LOCALIDAD"),
          r.get("GRIFOS_EXISTENTE"),
          r.get("GRIFOS_NO_OPERATIVOS"),
          r.get("GRIFOS_REPARADOS"),
          r.get("GRIFOS_REEMPLAZADOS"),
          r.get("GRIFOS_REPARAR"),
          r.get("GRIFOS_REEMPLAZAR"),
          r.get("INVERSION_TOTAL"),
          r.get("INVERSION_PROGRAMADA"),
          r.get("tasa_no_operativos"),
          r.get("tasa_a_reparar"),
          r.get("tasa_a_reemplazar"),
          json.dumps(r, ensure_ascii=False)
        ))
      execute_values(cur, """
        INSERT INTO rr.hydrant_status_muni
        (periodo,codigo_comuna,nombre_comuna,codigo_localidad,nombre_localidad,
         grifos_existente, grifos_no_operativos, grifos_reparados, grifos_reemplazados,
         grifos_reparar, grifos_reemplazar, inversion_total, inversion_programada,
         tasa_no_operativos, tasa_a_reparar, tasa_a_reemplazar, raw)
        VALUES %s
      """, rows, page_size=500)
    conn.commit()
  print(f"[OK] Cargado resumen por comuna: {len(rows)}")

if __name__=="__main__":
  main()
