#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parallel OSM Roads extractor (ways + nodes) with mirrors, tiling and retries.
Outputs:
  infraestructura/ways.geojson
  infraestructura/nodes.geojson
ENV:
  BBOX_S,BBOX_W,BBOX_N,BBOX_E
  OVERPASS_ROWS, OVERPASS_COLS (default 6x6)
  OVERPASS_TIMEOUT (60), OVERPASS_RETRIES (3)
  OVERPASS_API (force mirror)
  OVERPASS_PARALLEL (default min(16, tiles))
"""
import os, json, time, sys
from pathlib import Path
from typing import Dict, Any, Iterable, Tuple, List, Optional
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent
WAYS_PATH  = ROOT / "ways.geojson"
NODES_PATH = ROOT / "nodes.geojson"

BBOX_S=float(os.getenv("BBOX_S","-33.8"))
BBOX_W=float(os.getenv("BBOX_W","-70.95"))
BBOX_N=float(os.getenv("BBOX_N","-33.2"))
BBOX_E=float(os.getenv("BBOX_E","-70.45"))

ROWS=int(os.getenv("OVERPASS_ROWS","6"))
COLS=int(os.getenv("OVERPASS_COLS","6"))
TIMEOUT=int(os.getenv("OVERPASS_TIMEOUT","60"))
RETRIES=int(os.getenv("OVERPASS_RETRIES","3"))
FORCED=os.getenv("OVERPASS_API","").strip() or None
MAXW=int(os.getenv("OVERPASS_PARALLEL","16"))

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
    (
      way[\"highway\"~\"^{HW}$\"]({s},{w},{n},{e});
      >;
    );
    out body;
    """

def fetch(q):
    last=None
    for base in MIRRORS:
        if not base: continue
        for k in range(1,RETRIES+1):
            try:
                r=requests.post(base, data={"data":q}, headers=UA, timeout=TIMEOUT+15)
                if r.status_code!=200:
                    last=Exception(f"{base} -> HTTP {r.status_code}")
                    time.sleep(0.8*k); continue
                return r.json()
            except Exception as ex:
                last=ex; time.sleep(1.0*k); continue
    raise RuntimeError(last)

def worker(tile):
    s,w,n,e = tile
    q=build_query(s,w,n,e)
    try:
        data=fetch(q)
        return data.get("elements",[])
    except Exception as ex:
        sys.stderr.write(f"[warn] tile {s:.4f},{w:.4f},{n:.4f},{e:.4f} -> {ex}\n")
        return []

def main():
    ts = tiles(BBOX_S,BBOX_W,BBOX_N,BBOX_E,ROWS,COLS)
    max_workers = min(MAXW, len(ts))
    print(f"[OSM] Parallel tiles {ROWS}x{COLS} (workers={max_workers})")

    elems=[]
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs=[ex.submit(worker, t) for t in ts]
        for fut in as_completed(futs):
            elems.extend(fut.result())

    nodes: Dict[int,dict]={}
    ways:  Dict[int,dict]={}
    for el in elems:
        t=el.get("type")
        if t=="node": nodes[el["id"]]=el
        elif t=="way": ways[el["id"]]=el

    # Build nodes GeoJSON
    nf=[]
    for nid,n in nodes.items():
        if "lon" not in n or "lat" not in n: continue
        nf.append({"type":"Feature","id":int(nid),
                   "geometry":{"type":"Point","coordinates":[n["lon"],n["lat"]]},
                   "properties":{"id":int(nid)}})
    nodes_gj={"type":"FeatureCollection","features":nf}

    # Build ways GeoJSON
    wf=[]
    for wid,w in ways.items():
        refs=w.get("nodes") or []
        coords=[]
        for rn in refs:
            nn=nodes.get(rn)
            if nn and "lon" in nn and "lat" in nn:
                coords.append([nn["lon"], nn["lat"]])
        if len(coords)<2: continue
        tags=w.get("tags",{}) or {}
        # normalize
        highway=tags.get("highway")
        oneway_raw=tags.get("oneway")
        oneway=True if oneway_raw in ("yes","-1","true","1") else False if oneway_raw in ("no","false","0") else None
        # lanes and maxspeed
        lanes=None
        try:
            if "lanes" in tags: lanes=int(str(tags["lanes"]).strip())
        except: lanes=None
        maxspeed_kmh=None
        try:
            if "maxspeed" in tags:
                ms=str(tags["maxspeed"]).split()[0].replace("signals","").strip()
                if ms.isdigit(): maxspeed_kmh=int(ms)
        except: maxspeed_kmh=None

        props={
            "id":int(wid),"osm_id":int(wid),
            "source":int(refs[0]),"target":int(refs[-1]),
            "highway":highway,"oneway":oneway,
            "maxspeed_kmh":maxspeed_kmh,"lanes":lanes,
            "width_raw": tags.get("width"),
            "maxwidth_raw": tags.get("maxwidth"),
            "surface": tags.get("surface"),
            "access": tags.get("access"),
            "tags": tags
        }
        wf.append({"type":"Feature","id":int(wid),
                   "geometry":{"type":"LineString","coordinates":coords},
                   "properties":props})
    ways_gj={"type":"FeatureCollection","features":wf}

    (NODES_PATH).write_text(json.dumps(nodes_gj, ensure_ascii=False), encoding="utf-8")
    (WAYS_PATH).write_text(json.dumps(ways_gj, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] nodes={len(nf)} ways={len(wf)} -> {NODES_PATH.name}, {WAYS_PATH.name}")

if __name__=="__main__":
    try:
        main()
    except Exception as e:
        print(f"[E] {e}", file=sys.stderr); sys.exit(1)
