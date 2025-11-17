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
RAIN_MM_H=float(os.getenv("RAIN_MM_H","10.0")) # Heavy rain threshold
WIND_MS=float(os.getenv("WIND_MS","20.0")) # Strong wind (>= 72 km/h)
VISIBILITY_M=int(os.getenv("VISIBILITY_M","500")) # Low visibility threshold
SNOW_MM_H=float(os.getenv("SNOW_MM_H","2.0")) # Snow threshold

# OpenWeather condition codes for fog, mist, haze, etc.
# See: https://openweathermap.org/weather-conditions
FOG_HAZE_CODES = {
    701, # Mist
    711, # Smoke
    721, # Haze
    731, # Sand/dust whirls
    741, # Fog
    751, # Sand
    761, # Dust
    762, # Volcanic ash
}

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

def get_threats(m):
    """
    Analyzes weather data and returns a list of threat dictionaries.
    Each threat corresponds to a specific hazardous condition.
    """
    threats = []
    
    # 1. Heavy Rain
    rain_mm = (m.get("rain", {}).get("1h") or 0.0)
    if rain_mm >= RAIN_MM_H:
        threats.append({
            "subtype": "HEAVY_RAIN",
            "severity": 2 if rain_mm > 10.0 else 1, # Higher severity for very heavy rain
            "metrics": {"rain_mm_h": rain_mm}
        })

    # 2. Strong Wind
    wind_ms = (m.get("wind", {}).get("speed") or 0.0)
    if wind_ms >= WIND_MS:
        threats.append({
            "subtype": "STRONG_WIND",
            "severity": 2 if wind_ms > 17.5 else 1, # Higher severity for gale-force winds
            "metrics": {"wind_ms": wind_ms}
        })

    # 3. Low Visibility (Fog, Mist, etc.)
    visibility_m = m.get("visibility")
    weather_codes = {w.get("id") for w in m.get("weather", [])}
    is_foggy = bool(FOG_HAZE_CODES.intersection(weather_codes))

    if (visibility_m is not None and visibility_m <= VISIBILITY_M) or is_foggy:
        threats.append({
            "subtype": "LOW_VISIBILITY",
            "severity": 2 if visibility_m is not None and visibility_m < 200 else 1,
            "metrics": {"visibility_m": visibility_m or "N/A"}
        })

    # 4. Snow
    snow_mm = (m.get("snow", {}).get("1h") or 0.0)
    if snow_mm >= SNOW_MM_H:
        threats.append({
            "subtype": "SNOW",
            "severity": 2 if snow_mm > 5.0 else 1,
            "metrics": {"snow_mm_h": snow_mm}
        })
        
    return threats

def main():
    cells=list(grid_cells(BBOX_S,BBOX_W,BBOX_N,BBOX_E,GRID))
    print(f"[INFO] Fetching weather data for {len(cells)} grid cells...")
    print(f"[INFO] Using API key: {KEY[:10]}...{KEY[-4:]}")
    
    feats=[]
    errors=[]
    with ThreadPoolExecutor(max_workers=PAR) as ex:
        futs=[ex.submit(fetch, c[4], c[5]) for c in cells]
        for i, (cell,fut) in enumerate(zip(cells, as_completed(futs))):
            try:
                res=fut.result()
                threats = get_threats(res)
                
                poly={"type":"Polygon","coordinates":[
                    [[cell[1],cell[0]],[cell[3],cell[0]],[cell[3],cell[2]],[cell[1],cell[2]],[cell[1],cell[0]]]
                ]}

                for threat in threats:
                    props={
                        "provider": "OpenWeather",
                        "ext_id": f"ow:{cell[4]:.3f},{cell[5]:.3f}:{threat['subtype']}",
                        "kind": "weather",
                        "subtype": threat["subtype"],
                        "severity": threat["severity"],
                        "metrics": threat["metrics"],
                        "ts": res.get("dt")
                    }
                    feats.append({"type":"Feature","geometry":poly,"properties":props})

                if (i + 1) % 10 == 0:
                    print(f"[INFO] Processed {i + 1}/{len(cells)} cells...")
            except Exception as ex:
                error_msg = str(ex)
                # Log first few errors to help diagnose issues
                if len(errors) < 3:
                    print(f"[WARN] Error fetching cell {cell[4]:.3f},{cell[5]:.3f}: {error_msg}", file=sys.stderr)
                errors.append(error_msg)
                continue
    
    if errors:
        print(f"[WARN] Encountered {len(errors)} errors during fetch", file=sys.stderr)
        if "401" in str(errors[0]) or "Unauthorized" in str(errors[0]):
            print("[ERROR] API key unauthorized. The key may not be activated yet.", file=sys.stderr)
            print("[ERROR] New OpenWeather API keys can take up to 2 hours to activate.", file=sys.stderr)
            print("[ERROR] Please wait for activation or check your API key.", file=sys.stderr)
        elif "403" in str(errors[0]) or "Forbidden" in str(errors[0]):
            print("[ERROR] API key forbidden. The key may be invalid or expired.", file=sys.stderr)
        
        # If all cells failed, don't overwrite existing file
        if len(feats) == 0:
            if OUT.exists():
                print(f"[WARN] All fetches failed. Keeping existing {OUT} to preserve data.", file=sys.stderr)
                return
            else:
                print(f"[ERROR] All fetches failed and no existing file. Creating empty file.", file=sys.stderr)
    
    OUT.write_text(json.dumps({"type":"FeatureCollection","features":feats}, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] saved {OUT} ({len(feats)} features, {len(errors)} errors)")

if __name__=="__main__":
    main()
