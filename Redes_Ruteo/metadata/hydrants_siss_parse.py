#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hydrants_siss_parse.py
Lee el Excel de SISS (estado de grifos), detecta coordenadas (WGS84 o UTM) y
genera:
  - metadata/hydrants_siss_inspections.json  (registros crudos + normalizados)
  - metadata/hydrants_siss.geojson           (Point features con status)

ENV opcionales:
  HYDRANTS_XLSX (ruta al .xlsx; default: metadata/hydrants_siss.xlsx)
  HYDRANTS_SHEET (nombre o índice; default: primera hoja)

Requiere:
  pip install pandas openpyxl pyproj
"""
import os, json, math, sys
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

try:
    from pyproj import Transformer
except Exception as e:
    print("[E] Falta pyproj. Instala con: pip install pyproj", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parent
XLSX = os.getenv("HYDRANTS_XLSX", str(ROOT / "hydrants_siss.xlsx"))
SHEET = os.getenv("HYDRANTS_SHEET")  # None -> primera hoja

OUT_JSON = ROOT / "hydrants_siss_inspections.json"
OUT_GEO  = ROOT / "hydrants_siss.geojson"

# --- Helpers ---
def pick_col(cols, candidates):
    """Devuelve el nombre real de la primera columna que coincida (case-insensitive)."""
    lower = {c.lower(): c for c in cols}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None

def to_float(v) -> Optional[float]:
    if v is None or (isinstance(v, float) and math.isnan(v)): return None
    s = str(v).strip().replace(",", ".")
    try:
        return float(s)
    except:
        return None

def detect_coords(df) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Devuelve (lon_col, lat_col, utm_e_col, utm_n_col).
    Si lon/lat están presentes, utm cols serán None.
    """
    cols = list(df.columns)
    # Primero intenta WGS84
    lon = pick_col(cols, ["lon","long","lng","longitud","LONGITUD","x","X"])
    lat = pick_col(cols, ["lat","latitud","LATITUD","y","Y"])
    if lon and lat:
        return (lon, lat, None, None)

    # Intenta UTM (nombres típicos)
    utm_e = pick_col(cols, ["utm_e","utm_easte","utm_este","este","east","e","coord_x","coor_x"])
    utm_n = pick_col(cols, ["utm_n","utm_north","utm_norte","norte","north","n","coord_y","coor_y"])
    if utm_e and utm_n:
        return (None, None, utm_e, utm_n)

    # Algunos archivos usan 'NORTE (m)' 'ESTE (m)'
    utm_e2 = None
    utm_n2 = None
    for c in cols:
        lc = c.lower()
        if "este" in lc or ("east" in lc) or lc in ("e",):
            utm_e2 = c if utm_e2 is None else utm_e2
        if "norte" in lc or ("north" in lc) or lc in ("n",):
            utm_n2 = c if utm_n2 is None else utm_n2
    if utm_e2 and utm_n2:
        return (None, None, utm_e2, utm_n2)

    return (None, None, None, None)

def utm_to_lonlat(e, n, zone=19, south=True):
    epsg = 32700 + zone if south else 32600 + zone
    tr = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    lon, lat = tr.transform(e, n)
    return float(lon), float(lat)

def norm_status(v: str) -> str:
    if not v: return "desconocido"
    s = str(v).strip().lower()
    if any(k in s for k in ["vig", "oper", "bueno", "ok"]):
        return "vigente"
    if any(k in s for k in ["malo", "no oper", "fuera", "inoper"]):
        return "no_operativo"
    return s

def guess_ext_id(row) -> Optional[str]:
    for cand in ["ext_id","id","codigo","código","cod_grifo","n_grifo","nº grifo","numero","número"]:
        if cand in row and pd.notna(row[cand]):
            return str(row[cand]).strip()
    return None

def main():
    xls_path = Path(XLSX)
    if not xls_path.exists():
        print(f"[E] No existe el Excel en {xls_path}. Puedes copiar tu archivo a esa ruta o setear HYDRANTS_XLSX.", file=sys.stderr)
        sys.exit(1)

    df = pd.read_excel(xls_path, sheet_name=SHEET if SHEET else 0)
    # Normaliza nombres de columnas (para búsquedas posteriores)
    df.columns = [str(c).strip() for c in df.columns]

    # Detecta columnas de coordenadas
    lon_col, lat_col, utm_e_col, utm_n_col = detect_coords(df)

    if not any([lon_col and lat_col, utm_e_col and utm_n_col]):
        print("[E] No se detectaron columnas de coordenadas (lon/lat o UTM).", file=sys.stderr)
        print("    Renombra columnas o ajusta el parser.", file=sys.stderr)
        sys.exit(2)

    # Extrae coordenadas
    recs = []
    for _, row in df.iterrows():
        props = row.to_dict()
        lon = lat = None

        if lon_col and lat_col:
            lon = to_float(row.get(lon_col))
            lat = to_float(row.get(lat_col))
        else:
            e = to_float(row.get(utm_e_col))
            n = to_float(row.get(utm_n_col))
            if e is not None and n is not None:
                try:
                    lon, lat = utm_to_lonlat(e, n, zone=int(os.getenv("HYDRANTS_UTM_ZONE","19")), south=True)
                except Exception as ex:
                    lon = lat = None

        if lon is None or lat is None:
            continue  # sin coordenadas, no sirve para GeoJSON

        ext = guess_ext_id(props)
        if not ext:
            ext = f"pt:{lon:.6f},{lat:.6f}"

        status_col = pick_col(df.columns, ["status","estado","situacion","vigente","operativo"])
        status = norm_status(props.get(status_col)) if status_col else "desconocido"

        # Normaliza provider
        provider = props.get("provider") or "SISS"

        recs.append({
            "ext_id": ext,
            "status": status,
            "provider": provider,
            "lon": lon,
            "lat": lat,
            "raw": props
        })

    # Exporta JSON "inspecciones"
    OUT_JSON.write_text(json.dumps(recs, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Inspecciones exportadas: {len(recs)} → {OUT_JSON.name}")

    # Exporta GeoJSON
    feats = [{
        "type":"Feature",
        "geometry":{"type":"Point","coordinates":[r["lon"], r["lat"]]},
        "properties":{
            "ext_id": r["ext_id"],
            "status": r["status"],
            "provider": r["provider"],
            **(r["raw"] or {})
        }
    } for r in recs]

    gj = {"type":"FeatureCollection","features":feats}
    OUT_GEO.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] GeoJSON exportado: {OUT_GEO.name} ({len(feats)} features)")

if __name__ == "__main__":
    main()
