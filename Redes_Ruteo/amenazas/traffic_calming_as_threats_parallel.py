#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parallel extractor for OSM traffic_calming nodes.
Output: amenazas/traffic_calming_threats.geojson
"""
import os, json, time, sys
from pathlib import Path
from typing import Dict, Any, Iterable, Tuple, List
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent
OUT  = ROOT / "traffic_calming_threats.geojson"

BBOX_S=float(os.getenv("BBOX_S","-33.8"))
BBOX_W=float(os.getenv("BBOX_W","-70.95"))
BBOX_N=float(os.getenv("BBOX_N","-33.2"))
BBOX_E=float(os.getenv("BBOX_E","-70.45"))

ROWS=int(os.getenv("OVERPASS_ROWS","6"))
COLS=int(os.getenv("OVERPASS_COLS","6"))
TIMEOUT=int(os.getenv("OVERPASS_TIMEOUT","50"))
RETRIES=int(os.getenv("OVERPASS_RETRIES","3"))
FORCED=os.getenv("OVERPASS_API","").strip() or None
MAXW=int(os.getenv("OVERPASS_PARALLEL","16"))

MIRRORS = [FORCED] if FORCED else [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
]
UA={"User-Agent":"ruteo-resiliente/1.0 (academic demo)"}

def tiles(s,w,n,e,rows,cols):
    out=[]
    lat_step=(n-s)/rows; lon_step=(e-w)/cols
    for i in range(rows):
        for j in range(cols):
            ss=s+i*lat_step; nn=s+(i+1)*lat_step
            ww=w+j*lon_step; ee=w+(j+1)*lon_step
            pad_lat=lat_step*0.01; pad_lon=lon_step*0.01
            out.append((max(s, ss-pad_lat), max(w, ww-pad_lon), min(n, nn+pad_lat), min(e, ee+pad_lon)))
    return out

def build_query(s,w,n,e):
    return f"""
    [out:json][timeout:{TIMEOUT}];
    node["traffic_calming"]({s},{w},{n},{e});
    out body;
    """

def fetch(q):
    last=None
    for base in MIRRORS:
        if not base: continue
        for k in range(1,RETRIES+1):
            try:
                r=requests.post(base, data={"data":q}, headers=UA, timeout=TIMEOUT+10)
                if r.status_code!=200:
                    last=Exception(f"{base} -> HTTP {r.status_code}")
                    time.sleep(0.8*k); continue
                return r.json()
            except Exception as ex:
                last=ex; time.sleep(1.0*k); continue
    raise RuntimeError(last)

def nodes_to_features(data:Dict[str,Any])->List[Dict[str,Any]]:
    feats=[]
    for el in data.get("elements",[]) or []:
        if el.get("type")!="node": continue
        lon=el.get("lon"); lat=el.get("lat")
        if lon is None or lat is None: continue
        tags=el.get("tags",{}) or {}
        props={"provider":"OSM","ext_id":str(el.get("id")),
               "kind":"incident","subtype":"TRAFFIC_CALMING","severity":1,
               "props":tags}
        feats.append({"type":"Feature",
                      "geometry":{"type":"Point","coordinates":[lon,lat]},
                      "properties":props})
    return feats

def worker(tile):
    s,w,n,e=tile
    q=build_query(s,w,n,e)
    try:
        data=fetch(q)
        return nodes_to_features(data)
    except Exception as ex:
        sys.stderr.write(f"[warn] tile {s:.4f},{w:.4f},{n:.4f},{e:.4f} -> {ex}\n"); return []

def main():
    ts=tiles(BBOX_S,BBOX_W,BBOX_N,BBOX_E,ROWS,COLS)
    max_workers=min(MAXW,len(ts))
    print(f"[Calming] Parallel tiles {ROWS}x{COLS} (workers={max_workers})")
    feats_all=[]
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs=[ex.submit(worker,t) for t in ts]
        for fut in as_completed(futs):
            feats_all.extend(fut.result())
    gj={"type":"FeatureCollection","features":feats_all}
    OUT.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] saved {OUT} ({len(feats_all)} features)")

if __name__=="__main__":
    try: main()
    except Exception as e: print(f"[E] {e}", file=sys.stderr); sys.exit(1)
