#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RELAXED extractor de anchos de vía desde OSM (Overpass):
- Trae TODAS las vías (highway) del BBOX (como en infraestructura)
- Incluye en properties los tags si existen: width, maxwidth, lanes
- GeoJSON compatible con loaders/load_widths.py (osm_id, highway, lanes, width_raw, maxwidth_raw)

Robusto:
- Mirrors (fallback): overpass-api.de, kumi.systems, z.overpass-api.de
- Tiling del BBOX (por defecto 4x4)
- Reintentos con backoff

ENV opcionales:
  BBOX_S,BBOX_W,BBOX_N,BBOX_E
  OVERPASS_ROWS, OVERPASS_COLS  (default 4x4)
  OVERPASS_TIMEOUT              (default 60)
  OVERPASS_RETRIES              (default 3)
  OVERPASS_API                  (forzar un mirror)

Salida:
  metadata/road_widths.geojson
"""
import os, json, time, sys
from pathlib import Path
from typing import Dict, Any, Iterable, List, Tuple
import requests

ROOT = Path(__file__).resolve().parent
OUT  = ROOT / "road_widths.geojson"

BBOX_S=float(os.getenv("BBOX_S","-33.8"))
BBOX_W=float(os.getenv("BBOX_W","-70.95"))
BBOX_N=float(os.getenv("BBOX_N","-33.2"))
BBOX_E=float(os.getenv("BBOX_E","-70.45"))

ROWS=int(os.getenv("OVERPASS_ROWS","4"))
COLS=int(os.getenv("OVERPASS_COLS","4"))
TIMEOUT=int(os.getenv("OVERPASS_TIMEOUT","60"))
RETRIES=int(os.getenv("OVERPASS_RETRIES","3"))
FORCED=os.getenv("OVERPASS_API","").strip() or None

MIRRORS = [FORCED] if FORCED else [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
]
UA={"User-Agent":"ruteo-resiliente/1.0 (academic demo)"}

HW = "|".join([
    "motorway","trunk","primary","secondary","tertiary",
    "unclassified","residential","living_street","service"
])

def tiles(s:float,w:float,n:float,e:float, rows:int, cols:int)->Iterable[Tuple[float,float,float,float]]:
    lat_step=(n-s)/rows; lon_step=(e-w)/cols
    for i in range(rows):
        for j in range(cols):
            ss=s+i*lat_step; nn=s+(i+1)*lat_step
            ww=w+j*lon_step; ee=w+(j+1)*lon_step
            pad_lat=lat_step*0.01; pad_lon=lon_step*0.01
            yield max(s, ss-pad_lat), max(w, ww-pad_lon), min(n, nn+pad_lat), min(e, ee+pad_lon)

def build_query(s:float,w:float,n:float,e:float)->str:
    # Todas las vías del tipo 'highway' dentro del BBOX (sin filtrar por width/lanes).
    # Se solicita 'out body geom' para tener coordenadas.
    return f"""
    [out:json][timeout:{TIMEOUT}];
    way["highway"~"^{HW}$"]({s},{w},{n},{e});
    out body geom;
    """

def fetch(q:str)->Dict[str,Any]:
    last=None
    for base in MIRRORS:
        if not base: continue
        for k in range(1,RETRIES+1):
            try:
                r=requests.post(base, data={"data":q}, headers=UA, timeout=TIMEOUT+15)
                if r.status_code!=200:
                    last=Exception(f"{base} -> HTTP {r.status_code}")
                    time.sleep(1.0*k); continue
                try:
                    return r.json()
                except Exception as je:
                    last=je; time.sleep(0.8*k); continue
            except Exception as ex:
                last=ex; time.sleep(1.2*k); continue
    raise RuntimeError(last)

def ways_to_features(data:Dict[str,Any])->List[Dict[str,Any]]:
    feats=[]
    for el in data.get("elements",[]) or []:
        if el.get("type")!="way": continue
        geom = el.get("geometry") or []
        coords = [[p["lon"], p["lat"]] for p in geom if "lon" in p and "lat" in p]
        if len(coords) < 2: continue
        tags = el.get("tags",{}) or {}
        # lanes (entero si se puede)
        lanes = None
        try:
            if "lanes" in tags:
                lanes = int(str(tags["lanes"]).strip())
        except: lanes = None
        props = {
            "osm_id": int(el["id"]),
            "highway": tags.get("highway"),
            "lanes": lanes,
            "width_raw": tags.get("width"),
            "maxwidth_raw": tags.get("maxwidth"),
        }
        feats.append({
            "type":"Feature",
            "geometry":{"type":"LineString","coordinates":coords},
            "properties": props
        })
    return feats

def main():
    all_feats=[]
    print(f"[E] Descargando widths RELAXED OSM… tiles {ROWS}x{COLS}")
    for (s,w,n,e) in tiles(BBOX_S,BBOX_W,BBOX_N,BBOX_E,ROWS,COLS):
        q=build_query(s,w,n,e)
        try:
            data=fetch(q)
        except Exception as ex:
            print(f"[warn] tile {s:.4f},{w:.4f},{n:.4f},{e:.4f} -> {ex}")
            continue
        feats=ways_to_features(data)
        all_feats.extend(feats)
        time.sleep(0.5)
    # Asegurar que nunca sea vacío si Overpass dio algo: si está vacío, es porque todos los tiles fallaron.
    gj={"type":"FeatureCollection","features":all_feats}
    OUT.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] saved {OUT} ({len(all_feats)} features)")

if __name__=="__main__":
    try:
        t0=time.time(); main(); print(f"[Done] en {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"[E] {e}", file=sys.stderr)
        sys.exit(1)
