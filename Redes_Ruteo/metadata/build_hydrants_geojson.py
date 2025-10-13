#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_hydrants_geojson.py
Convierte el archivo de inspecciones (JSON) en un GeoJSON listo para el loader:
  IN : metadata/hydrants_siss_inspections.json
  OUT: metadata/hydrants_siss.geojson

Detecta automáticamente las columnas de coordenadas más comunes:
  - (lon, lat)  ó  (lng, lat)
  - (x, y)      (asumiendo WGS84 en grados)
  - (LONGITUD, LATITUD) / (Longitud, Latitud)
y el estado:
  - status, estado, situacion, vigente, operativo, etc.

Uso:
  python metadata/build_hydrants_geojson.py \
    --in metadata/hydrants_siss_inspections.json \
    --out metadata/hydrants_siss.geojson
"""

import json, argparse, sys
from pathlib import Path

def find_key(d, candidates):
    for k in candidates:
        if k in d: return k
    # busca case-insensitive
    lower = {k.lower(): k for k in d.keys()}
    for k in candidates:
        if k.lower() in lower: return lower[k.lower()]
    return None

def guess_coords(p):
    # candidatos (lon, lat)
    lonk = find_key(p, ["lon","lng","long","x","LONGITUD","Longitud","longitud"])
    latk = find_key(p, ["lat","y","LATITUD","Latitud","latitud"])
    if lonk and latk:
        try:
            lon = float(str(p[lonk]).replace(",", "."))
            lat = float(str(p[latk]).replace(",", "."))
            # valid quick range
            if -180 <= lon <= 180 and -90 <= lat <= 90:
                return lon, lat
        except:
            return None
    return None

def guess_status(p):
    sk = find_key(p, ["status","estado","situacion","vigente","operativo","en_servicio"])
    if not sk: return None
    v = str(p.get(sk, "")).strip()
    return v

def guess_id(p):
    # prueba id, codigo, codigo_grifo, etc.
    for cand in ["ext_id","id","codigo","codigo_grifo","n_grifo","identificador"]:
        k = find_key(p, [cand])
        if k and p.get(k): return str(p[k])
    # fallback por coordenadas
    c = guess_coords(p)
    if c: return f"pt:{c[0]:.6f},{c[1]:.6f}"
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="metadata/hydrants_siss_inspections.json")
    ap.add_argument("--out", dest="out", default="metadata/hydrants_siss.geojson")
    args = ap.parse_args()

    src = Path(args.inp)
    if not src.exists():
        print(f"[E] No existe {src}", file=sys.stderr); sys.exit(1)

    data = json.loads(src.read_text(encoding="utf-8"))
    # soporta lista simple o objeto con 'rows'/'data'
    if isinstance(data, dict):
        rows = data.get("rows") or data.get("data") or data.get("items") or []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []

    feats = []
    miss_coords = 0
    miss_ids = 0

    for p in rows:
        coords = guess_coords(p)
        if not coords:
            miss_coords += 1
            continue
        ext_id = guess_id(p)
        if not ext_id:
            miss_ids += 1
            continue
        status = guess_status(p)
        props = dict(p)
        props.update({"ext_id": ext_id, "status": status, "provider": props.get("provider") or "SISS"})
        feats.append({
            "type":"Feature",
            "geometry":{"type":"Point","coordinates":[coords[0], coords[1]]},
            "properties": props
        })

    gj = {"type":"FeatureCollection","features":feats}
    Path(args.out).write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] GeoJSON {args.out} generado con {len(feats)} features "
          f"(omitidos sin coords: {miss_coords}, sin id: {miss_ids})")

if __name__ == "__main__":
    main()
