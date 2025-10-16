#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Waze fetcher adaptativo y paralelo:
- Carga .env si existe para configurar AOI y opciones
- Rota endpoints y usa Referer/UA válidos
- Paraleliza por grilla configurable (WAZE_GRID, WAZE_PARALLEL)
- Si un tile falla: subdivide recursivamente (hasta WAZE_MAX_DEPTH)
- Permite WAZE_TYPES=alerts|traffic|irregularities (por defecto todos)

Salida: amenazas/waze_incidents.geojson
"""
import os, json, sys, time
from pathlib import Path
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load .env first so env reads below include file-based values
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import requests

ROOT = Path(__file__).resolve().parent
OUT  = ROOT / "waze_incidents.geojson"

BBOX_S=float(os.getenv("BBOX_S","-33.8"))
BBOX_W=float(os.getenv("BBOX_W","-70.95"))
BBOX_N=float(os.getenv("BBOX_N","-33.2"))
BBOX_E=float(os.getenv("BBOX_E","-70.45"))
TIMEOUT=int(os.getenv("WAZE_TIMEOUT","40"))
RETRIES=int(os.getenv("WAZE_RETRIES","3"))
MAX_DEPTH=int(os.getenv("WAZE_MAX_DEPTH","2"))
TYPES=os.getenv("WAZE_TYPES","alerts,traffic,irregularities")
GRID=float(os.getenv("WAZE_GRID","0.25"))
PAR=int(os.getenv("WAZE_PARALLEL","8"))

ENDS=[
    "https://world-georss.waze.com/rtserver/web/TGeoRSS",
    "https://www.waze.com/rtserver/web/TGeoRSS",
    "https://us-georss.waze.com/rtserver/web/TGeoRSS",
    "https://na-georss.waze.com/rtserver/web/TGeoRSS",
    "https://row-georss.waze.com/rtserver/web/TGeoRSS",
]
UA={
    "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer":"https://www.waze.com/",
    "Accept":"application/json, text/javascript, */*; q=0.01",
    "Accept-Language":"es-CL,es;q=0.9,en;q=0.8",
    "Origin":"https://www.waze.com",
}

def fetch_box(s,w,n,e)->Dict[str,Any]:
    params={"types":TYPES,"left":w,"right":e,"top":n,"bottom":s,"format":"JSON"}
    last=None
    for k in range(RETRIES):
        for base in ENDS:
            try:
                r=requests.get(base, params=params, headers=UA, timeout=TIMEOUT)
                if r.status_code==200:
                    try:
                        return r.json()
                    except Exception as je:
                        last=je; time.sleep(0.5*(k+1)); continue
                else:
                    last=Exception(f"{base} -> HTTP {r.status_code}")
                    time.sleep(0.6*(k+1))
            except Exception as ex:
                last=ex; time.sleep(0.7*(k+1))
    raise RuntimeError(last)

def to_features(ch:Dict[str,Any])->List[Dict[str,Any]]:
    feats=[]
    for a in ch.get("alerts",[]) or []:
        loc=a.get("location") or {}; lon=loc.get("x"); lat=loc.get("y")
        if lon is None or lat is None: continue
        typ=(a.get("type") or "").upper()
        subtype="CLOSURE" if "CLOS" in typ else "INCIDENT"
        sev=2 if subtype=="CLOSURE" else 1
        props={"provider":"WAZE","ext_id":a.get("uuid") or a.get("id") or f"alert:{lon},{lat}",
               "kind":"incident","subtype":subtype,"severity":sev,
               "description":a.get("reportDescription") or a.get("street"),
               "street":a.get("street"),"type_raw":a.get("type"),
               "timestamp":a.get("pubMillis")}
        feats.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},"properties":props})
    for j in ch.get("jams",[]) or []:
        line=j.get("line") or []; coords=[[p["x"],p["y"]] for p in line if "x" in p and "y" in p]
        if len(coords)>=2:
            props={"provider":"WAZE","ext_id":j.get("uuid") or j.get("id") or f"jam:{len(coords)}",
                   "kind":"incident","subtype":"TRAFFIC_JAM","severity":1,
                   "metrics":{"speed_kmh":j.get("speed")},"timestamp":j.get("pubMillis")}
            feats.append({"type":"Feature","geometry":{"type":"LineString","coordinates":coords},"properties":props})
    for irr in ch.get("irregularities",[]) or []:
        seg=irr.get("seg") or {}; lon=seg.get("x"); lat=seg.get("y")
        if lon is not None and lat is not None:
            props={"provider":"WAZE","ext_id":irr.get("id") or f"irr:{lon},{lat}",
                   "kind":"incident","subtype":"IRREGULARITY","severity":1,
                   "metrics":{"speed_kmh":irr.get("speed")},"timestamp":irr.get("pubMillis")}
            feats.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},"properties":props})
    return feats

def subdivide(s,w,n,e):
    mlat=(s+n)/2.0; mlon=(w+e)/2.0
    return [(s,w,mlat,mlon),(s,mlon,mlat,e),(mlat,w,n,mlon),(mlat,mlon,n,e)]

def crawl(s,w,n,e,depth=0)->List[Dict[str,Any]]:
    try:
        data=fetch_box(s,w,n,e)
        feats=to_features(data)
        if feats: return feats
        # Si no hay features pero tampoco error, no subdividir indefinidamente
        return []
    except Exception as ex:
        sys.stderr.write(f"[warn] tile {s:.4f},{w:.4f},{n:.4f},{e:.4f} -> {ex}\n")
        if depth>=MAX_DEPTH: return []
        out=[]
        for (ss,ww,nn,ee) in subdivide(s,w,n,e):
            out.extend(crawl(ss,ww,nn,ee,depth+1))
        return out

def grid_cells(s,w,n,e,step: float):
    if step <= 0:
        yield (s,w,n,e)
        return
    lat=s
    while lat < n:
        lon=w
        lat2 = min(n, lat + step)
        while lon < e:
            lon2 = min(e, lon + step)
            yield (lat, lon, lat2, lon2)
            lon = lon2
        lat = lat2

def dedupe(features):
    seen=set(); out=[]
    for f in features:
        eid=f.get("properties",{}).get("ext_id")
        if eid and eid in seen: continue
        if eid: seen.add(eid)
        out.append(f)
    return out

def main():
    # Parallel crawl over grid cells
    cells=list(grid_cells(BBOX_S,BBOX_W,BBOX_N,BBOX_E,GRID))
    feats: List[Dict[str,Any]] = []
    if PAR > 1 and len(cells) > 1:
        with ThreadPoolExecutor(max_workers=PAR) as ex:
            futures = {ex.submit(crawl, s,w,n,e,0): (s,w,n,e) for (s,w,n,e) in cells}
            for fut in as_completed(futures):
                try:
                    feats.extend(fut.result())
                except Exception:
                    # Already logged inside crawl
                    pass
    else:
        for (s,w,n,e) in cells:
            feats.extend(crawl(s,w,n,e,0))
    uniq=dedupe(feats)
    OUT.write_text(json.dumps({"type":"FeatureCollection","features":uniq}, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] saved {OUT} ({len(uniq)} features)")

if __name__=="__main__":
    main()
