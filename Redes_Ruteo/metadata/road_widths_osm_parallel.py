#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parallel RELAXED extractor for OSM road widths
See: docstring in file for ENV variables and behavior.
"""
import os, json, time, sys
from pathlib import Path
from typing import Dict, Any, Iterable, List, Tuple
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent
OUT  = ROOT / "road_widths.geojson"

BBOX_S=float(os.getenv("BBOX_S","-33.8"))
BBOX_W=float(os.getenv("BBOX_W","-70.95"))
BBOX_N=float(os.getenv("BBOX_N","-33.2"))
BBOX_E=float(os.getenv("BBOX_E","-70.45"))

ROWS=int(os.getenv("OVERPASS_ROWS","6"))
COLS=int(os.getenv("OVERPASS_COLS","6"))
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

def tiles(s:float,w:float,n:float,e:float, rows:int, cols:int)->List[Tuple[float,float,float,float]]:
    out=[]
    lat_step=(n-s)/rows; lon_step=(e-w)/cols
    for i in range(rows):
        for j in range(cols):
            ss=s+i*lat_step; nn=s+(i+1)*lat_step
            ww=w+j*lon_step; ee=w+(j+1)*lon_step
            pad_lat=lat_step*0.01; pad_lon=lon_step*0.01
            out.append((max(s, ss-pad_lat), max(w, ww-pad_lon), min(n, nn+pad_lat), min(e, ee+pad_lon)))
    return out

def build_query(s:float,w:float,n:float,e:float)->str:
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
                    time.sleep(0.8*k); continue
                try:
                    return r.json()
                except Exception as je:
                    last=je; time.sleep(0.6*k); continue
            except Exception as ex:
                last=ex; time.sleep(1.0*k); continue
    raise RuntimeError(last)

def ways_to_features(data:Dict[str,Any])->List[Dict[str,Any]]:
    feats=[]
    for el in data.get("elements",[]) or []:
        if el.get("type")!="way": continue
        geom = el.get("geometry") or []
        coords = [[p["lon"], p["lat"]] for p in geom if "lon" in p and "lat" in p]
        if len(coords) < 2: continue
        tags = el.get("tags",{}) or {}
        lanes = None
        try:
            if "lanes" in tags: lanes = int(str(tags["lanes"]).strip())
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

def worker(tile):
    s,w,n,e = tile
    q = build_query(s,w,n,e)
    try:
        data = fetch(q)
        return ways_to_features(data)
    except Exception as ex:
        sys.stderr.write(f"[warn] tile {s:.4f},{w:.4f},{n:.4f},{e:.4f} -> {ex}\n")
        return []

def main():
    t0=time.time()
    ts = tiles(BBOX_S,BBOX_W,BBOX_N,BBOX_E,ROWS,COLS)
    max_workers = min(int(os.getenv("OVERPASS_PARALLEL","12")), len(ts))
    print(f"[E] Descargando widths RELAXED OSM en paralelo… tiles {ROWS}x{COLS} (workers={max_workers})")

    feats_all: List[Dict[str,Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(worker, t) for t in ts]
        for fut in as_completed(futs):
            feats_all.extend(fut.result())

    gj = {"type":"FeatureCollection","features":feats_all}
    OUT.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] saved {OUT} ({len(feats_all)} features)  in {time.time()-t0:.1f}s")

if __name__=="__main__":
    try:
        main()
    except Exception as e:
        print(f"[E] {e}", file=sys.stderr)
        sys.exit(1)
