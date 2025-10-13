#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parsea **todas** las hojas del Excel SISS y fusiona registros.
- Detecta lon/lat o UTM (zona configurable, por defecto 19S).
- Permite forzar nombres de columnas por ENV.
- Genera:
    metadata/hydrants_siss_inspections.json
    metadata/hydrants_siss.geojson

ENV principales (opcionales):
  HYDRANTS_XLSX           ruta al .xlsx (default metadata/hydrants_siss.xlsx)
  HYDRANTS_SHEETS         coma-separada, si quieres limitar a hojas específicas
  HYDRANTS_UTM_ZONE       (default 19)
  # Forzar columnas (preferidas si existen):
  HYDRANTS_LON_COL, HYDRANTS_LAT_COL
  HYDRANTS_UTM_E_COL, HYDRANTS_UTM_N_COL

Requiere: pandas, openpyxl, pyproj
"""
import os, json, math, sys
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent
XLSX = os.getenv("HYDRANTS_XLSX", str(ROOT / "hydrants_siss.xlsx"))
SHEETS_ENV = os.getenv("HYDRANTS_SHEETS")  # "Hoja1,Hoja2"
ZONE = int(os.getenv("HYDRANTS_UTM_ZONE","19"))

OUT_JSON = ROOT / "hydrants_siss_inspections.json"
OUT_GEO  = ROOT / "hydrants_siss.geojson"

FORCE_LON = os.getenv("HYDRANTS_LON_COL")
FORCE_LAT = os.getenv("HYDRANTS_LAT_COL")
FORCE_E   = os.getenv("HYDRANTS_UTM_E_COL")
FORCE_N   = os.getenv("HYDRANTS_UTM_N_COL")

def to_float(v):
    if v is None or (isinstance(v, float) and math.isnan(v)): return None
    s = str(v).strip().replace(",", ".")
    try: return float(s)
    except: return None

def utm_to_lonlat(e, n, zone=19, south=True):
    epsg = 32700 + zone if south else 32600 + zone
    tr = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    lon, lat = tr.transform(e, n)
    return float(lon), float(lat)

def pick_col(cols, candidates):
    lower = {c.lower(): c for c in cols}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None

def detect_coords(df):
    # 1) Forced columns, if exist
    cols = list(df.columns)
    if FORCE_LON and FORCE_LAT and FORCE_LON in cols and FORCE_LAT in cols:
        return ("lonlat", FORCE_LON, FORCE_LAT)
    if FORCE_E and FORCE_N and FORCE_E in cols and FORCE_N in cols:
        return ("utm", FORCE_E, FORCE_N)

    # 2) Try lon/lat common names
    lon = pick_col(cols, ["lon","long","lng","longitud","x","LONGITUD","Longitud"])
    lat = pick_col(cols, ["lat","latitud","y","LATITUD","Latitud"])
    if lon and lat: return ("lonlat", lon, lat)

    # 3) Try UTM common names
    e = pick_col(cols, ["utm_e","utm_este","este","east","e","coord_x","coor_x","x"])
    n = pick_col(cols, ["utm_n","utm_norte","norte","north","n","coord_y","coor_y","y"])
    if e and n: return ("utm", e, n)

    return (None, None, None)

def norm_status(v: str) -> str:
    if v is None: return "desconocido"
    s = str(v).strip().lower()
    if any(k in s for k in ["vig", "oper", "bueno", "ok"]): return "vigente"
    if any(k in s for k in ["malo", "no oper", "fuera", "inoper"]): return "no_operativo"
    return s

def guess_ext_id(row) -> Optional[str]:
    for cand in ["ext_id","id","codigo","código","cod_grifo","n_grifo","nº grifo","numero","número"]:
        if cand in row and pd.notna(row[cand]):
            return str(row[cand]).strip()
    return None

def parse_sheet(df, sheet_name):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    mode, c1, c2 = detect_coords(df)
    if not mode:
        return [], {"sheet": sheet_name, "rows": len(df), "coords_ok":0, "coords_missing":len(df), "ids_missing":0}

    # status column guess
    status_col = pick_col(df.columns, ["status","estado","situacion","vigente","operativo"])

    recs = []
    miss_coords = 0
    miss_ids = 0
    for _, row in df.iterrows():
        props = row.to_dict()
        lon=lat=None

        if mode=="lonlat":
            lon = to_float(row.get(c1)); lat = to_float(row.get(c2))
        else:
            e = to_float(row.get(c1)); n = to_float(row.get(c2))
            if e is not None and n is not None:
                try:
                    lon, lat = utm_to_lonlat(e, n, zone=ZONE, south=True)
                except: lon = lat = None

        if lon is None or lat is None:
            miss_coords += 1
            continue

        ext = guess_ext_id(props)
        if not ext:
            ext = f"pt:{lon:.6f},{lat:.6f}"

        status = norm_status(props.get(status_col)) if status_col else "desconocido"
        provider = props.get("provider") or "SISS"

        recs.append({
            "ext_id": ext,
            "status": status,
            "provider": provider,
            "lon": lon,
            "lat": lat,
            "raw": props,
            "sheet": sheet_name
        })

    stats = {"sheet": sheet_name, "rows": len(df), "coords_ok": len(recs), "coords_missing": miss_coords, "ids_missing": miss_ids}
    return recs, stats

def main():
    xls_path = Path(XLSX)
    if not xls_path.exists():
        print(f"[E] No existe el Excel en {xls_path}", file=sys.stderr); sys.exit(1)

    xl = pd.ExcelFile(xls_path)
    sheets = xl.sheet_names
    if SHEETS_ENV:
        sel = [s.strip() for s in SHEETS_ENV.split(",") if s.strip() in sheets]
        if sel: sheets = sel

    all_recs = []
    report = []
    for s in sheets:
        try:
            df = pd.read_excel(xls_path, sheet_name=s)
            recs, stats = parse_sheet(df, s)
            all_recs.extend(recs)
            report.append(stats)
        except Exception as ex:
            report.append({"sheet": s, "error": str(ex)})

    # Export JSON de inspecciones (lista de dicts)
    OUT_JSON.write_text(json.dumps(all_recs, ensure_ascii=False), encoding="utf-8")
    # Export GeoJSON
    feats = [{
        "type":"Feature",
        "geometry":{"type":"Point","coordinates":[r["lon"], r["lat"]]},
        "properties":{
            "ext_id": r["ext_id"],
            "status": r["status"],
            "provider": r["provider"],
            "sheet": r["sheet"],
            **(r["raw"] or {})
        }
    } for r in all_recs]
    gj = {"type":"FeatureCollection","features":feats}
    OUT_GEO.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")

    # Print summary
    total = sum(s.get("coords_ok",0) for s in report if isinstance(s, dict))
    miss  = sum(s.get("coords_missing",0) for s in report if isinstance(s, dict))
    print(f"[OK] Hojas procesadas: {len(sheets)}")
    for s in report: print("[INFO]", s)
    print(f"[OK] GeoJSON exportado: {OUT_GEO.name} ({total} puntos; omitidos por coords: {miss})")

if __name__ == "__main__":
    main()
