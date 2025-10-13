#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenWeather threats generator (loads .env via python-dotenv).
Env:
  OPENWEATHER_KEY (required)
  BBOX_S,BBOX_W,BBOX_N,BBOX_E
  WEATHER_GRID (cell size in degrees, default 0.02)
  WEATHER_PARALLEL (default 4)
Outputs:
  amenazas/weather_threats.geojson
"""
import os, sys, json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

KEY=os.getenv("OPENWEATHER_KEY","").strip()
if not KEY:
    print("Falta OPENWEATHER_KEY en .env", file=sys.stderr); sys.exit(1)

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"amenazas"/"weather_threats.geojson"

BBOX_S=float(os.getenv("BBOX_S","-33.8"))
BBOX_W=float(os.getenv("BBOX_W","-70.95"))
BBOX_N=float(os.getenv("BBOX_N","-33.2"))
BBOX_E=float(os.getenv("BBOX_E","-70.45"))
GRID=float(os.getenv("WEATHER_GRID","0.02"))
PAR=int(os.getenv("WEATHER_PARALLEL","4"))
RAIN=float(os.getenv("RAIN_MM_H","3.0"))
WIND=float(os.getenv("WIND_MS","12.0"))

def grid_cells(s,w,n,e,step):
    lat=s
    while lat<n:
        lon=w
        lat2=min(n, lat+step)
        while lon<e:
            lon2=min(e, lon+step)
            yield (lat,lon,lat2,lon2,(lat+lat2)/2.0,(lon+lon2)/2.0)
            lon=lon2
        lat=lat2

def fetch(lat,lon):
    url="https://api.openweathermap.org/data/2.5/weather"
    params={"lat":lat,"lon":lon,"appid":KEY,"units":"metric"}
    r=requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def severity(m):
    sev=0
    rain = (m.get("rain") or {}).get("1h") or (m.get("rain") or {}).get("3h") or 0.0
    wind = (m.get("wind") or {}).get("speed") or 0.0
    if rain and rain>=RAIN: sev+=1
    if wind and wind>=WIND: sev+=1
    return sev, rain or 0.0, wind or 0.0

def main():
    cells=list(grid_cells(BBOX_S,BBOX_W,BBOX_N,BBOX_E,GRID))
    feats=[]
    with ThreadPoolExecutor(max_workers=PAR) as ex:
        futs=[ex.submit(fetch, c[4], c[5]) for c in cells]
        for (cell,fut) in zip(cells, as_completed(futs)):
            try:
                res=fut.result()
                sev,rain,wind=severity(res)
                props={"provider":"OpenWeather","ext_id":f"ow:{cell[4]:.3f},{cell[5]:.3f}",
                       "kind":"weather","subtype":"RAIN_WIND","severity":int(sev),
                       "metrics":{"rain_mm_h":rain,"wind_ms":wind},
                       "ts":res.get("dt")}
                poly={"type":"Polygon","coordinates":[
                    [[cell[1],cell[0]],[cell[3],cell[0]],[cell[3],cell[2]],[cell[1],cell[2]],[cell[1],cell[0]]]
                ]}
                feats.append({"type":"Feature","geometry":poly,"properties":props})
            except Exception as ex:
                continue
    OUT.write_text(json.dumps({"type":"FeatureCollection","features":feats}, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] saved {OUT} ({len(feats)} features)")

if __name__=="__main__":
    main()
