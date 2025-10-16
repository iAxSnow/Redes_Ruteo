#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Waze fetcher adaptativo y paralelo:
- Rota endpoints y usa Referer/UA adecuados
- Concurrency por tiles con subdivisión en caso de error (quadtree)
- Retries con backoff y limitador de tasa global (QPS configurable)
- CLI y variables de entorno para bbox, profundidad, tipos, workers, etc.

Salida: amenazas/waze_incidents.geojson (o ruta indicada)
"""
import os, json, sys, time, argparse, threading, random
from pathlib import Path
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import requests
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover - fallback si no está disponible
    HTTPAdapter = None
    Retry = None

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT  = ROOT / "waze_incidents.geojson"

BBOX_S=float(os.getenv("BBOX_S","-33.8"))
BBOX_W=float(os.getenv("BBOX_W","-70.95"))
BBOX_N=float(os.getenv("BBOX_N","-33.2"))
BBOX_E=float(os.getenv("BBOX_E","-70.45"))
TIMEOUT=int(os.getenv("WAZE_TIMEOUT","40"))
RETRIES=int(os.getenv("WAZE_RETRIES","3"))
MAX_DEPTH=int(os.getenv("WAZE_MAX_DEPTH","2"))
FIRST_DEPTH=int(os.getenv("WAZE_FIRST_DEPTH","1"))
WORKERS=int(os.getenv("WAZE_WORKERS","8"))
QPS=float(os.getenv("WAZE_QPS","5"))
TYPES=os.getenv("WAZE_TYPES","alerts,traffic,irregularities")

ENDS=[
    "https://world-georss.waze.com/rtserver/web/TGeoRSS",
    "https://www.waze.com/rtserver/web/TGeoRSS",
    "https://us-georss.waze.com/rtserver/web/TGeoRSS"
]
UA={
    "User-Agent":"Mozilla/5.0",
    "Referer":"https://www.waze.com/"
}

class RateLimiter:
    def __init__(self, qps: float):
        self.min_interval = 1.0/float(qps) if qps and qps > 0 else 0.0
        self._lock = threading.Lock()
        self._next_time = 0.0

    def wait(self):
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.time()
            if now < self._next_time:
                time.sleep(self._next_time - now)
                now = time.time()
            # pequeño jitter para evitar sincronías
            jitter = random.uniform(0, self.min_interval*0.15)
            self._next_time = now + self.min_interval + jitter


def build_session(pool_maxsize: int = 16) -> requests.Session:
    s = requests.Session()
    s.headers.update(UA)
    if HTTPAdapter is not None:
        # No usamos Retry de urllib3 para no duplicar lógica; solo pools
        adapter = HTTPAdapter(pool_connections=pool_maxsize, pool_maxsize=pool_maxsize, max_retries=0)
        s.mount('http://', adapter)
        s.mount('https://', adapter)
    return s


def fetch_box(s: float, w: float, n: float, e: float, session: requests.Session, rate: RateLimiter) -> Dict[str, Any]:
    params = {"types": TYPES, "left": w, "right": e, "top": n, "bottom": s, "format": "JSON"}
    last = None
    for k in range(RETRIES):
        for base in ENDS:
            try:
                rate.wait()
                r = session.get(base, params=params, timeout=TIMEOUT)
                if r.status_code == 200:
                    try:
                        return r.json()
                    except Exception as je:
                        last = je
                        time.sleep(0.5 * (k + 1))
                        continue
                else:
                    last = Exception(f"{base} -> HTTP {r.status_code}")
                    time.sleep(0.6 * (k + 1))
            except Exception as ex:
                last = ex
                time.sleep(0.7 * (k + 1))
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

def crawl(s: float, w: float, n: float, e: float, depth: int, session: requests.Session, rate: RateLimiter) -> List[Dict[str, Any]]:
    try:
        data = fetch_box(s, w, n, e, session, rate)
        feats = to_features(data)
        if feats:
            return feats
        # Si no hay features pero tampoco error, no subdividir indefinidamente
        return []
    except Exception as ex:
        sys.stderr.write(f"[warn] tile {s:.4f},{w:.4f},{n:.4f},{e:.4f} -> {ex}\n")
        if depth >= MAX_DEPTH:
            return []
        out: List[Dict[str, Any]] = []
        for (ss, ww, nn, ee) in subdivide(s, w, n, e):
            out.extend(crawl(ss, ww, nn, ee, depth + 1, session, rate))
        return out


def tiles_at_depth(s: float, w: float, n: float, e: float, depth: int) -> List[Tuple[float, float, float, float]]:
    tiles = [(s, w, n, e)]
    for _ in range(max(0, depth)):
        next_tiles: List[Tuple[float, float, float, float]] = []
        for (ss, ww, nn, ee) in tiles:
            next_tiles.extend(subdivide(ss, ww, nn, ee))
        tiles = next_tiles
    return tiles

def dedupe(features):
    seen=set(); out=[]
    for f in features:
        eid=f.get("properties",{}).get("ext_id")
        if eid and eid in seen: continue
        if eid: seen.add(eid)
        out.append(f)
    return out

def main():
    global BBOX_S, BBOX_W, BBOX_N, BBOX_E, TYPES, TIMEOUT, RETRIES, MAX_DEPTH, FIRST_DEPTH, WORKERS, QPS
    parser = argparse.ArgumentParser(description="Fetch Waze incidents (parallel adaptive)")
    parser.add_argument("--south", type=float, default=BBOX_S)
    parser.add_argument("--west", type=float, default=BBOX_W)
    parser.add_argument("--north", type=float, default=BBOX_N)
    parser.add_argument("--east", type=float, default=BBOX_E)
    parser.add_argument("--types", type=str, default=TYPES)
    parser.add_argument("--timeout", type=int, default=TIMEOUT)
    parser.add_argument("--retries", type=int, default=RETRIES)
    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH)
    parser.add_argument("--first-depth", type=int, default=FIRST_DEPTH)
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--qps", type=float, default=QPS)
    parser.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    args = parser.parse_args()
    BBOX_S, BBOX_W, BBOX_N, BBOX_E = args.south, args.west, args.north, args.east
    TYPES = args.types
    TIMEOUT = args.timeout
    RETRIES = args.retries
    MAX_DEPTH = args.max_depth
    FIRST_DEPTH = max(0, args.first_depth)
    WORKERS = max(1, args.workers)
    QPS = max(0.0, float(args.qps))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    session = build_session(pool_maxsize=max(8, WORKERS * 2))
    rate = RateLimiter(QPS)

    tiles = tiles_at_depth(BBOX_S, BBOX_W, BBOX_N, BBOX_E, FIRST_DEPTH)
    all_feats: List[Dict[str, Any]] = []
    if WORKERS == 1 or len(tiles) == 1:
        # secuencial simple
        all_feats = crawl(BBOX_S, BBOX_W, BBOX_N, BBOX_E, 0, session, rate)
    else:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = [ex.submit(crawl, s, w, n, e, 0, session, rate) for (s, w, n, e) in tiles]
            for fut in as_completed(futs):
                try:
                    part = fut.result()
                    if part:
                        all_feats.extend(part)
                except Exception as exn:
                    sys.stderr.write(f"[warn] worker error: {exn}\n")

    uniq = dedupe(all_feats)
    out_path.write_text(json.dumps({"type": "FeatureCollection", "features": uniq}, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] saved {out_path} ({len(uniq)} features)")

if __name__=="__main__":
    main()
