#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenWeather threats generator - Fire Truck Emergency Response Focus
(loads .env via python-dotenv)

Collects weather threats that can delay or impede fire truck response:
- Heavy rain (reduces visibility, traction; can cause flooding)
- Strong winds (affects vehicle stability, can knock down trees/debris)
- Low visibility (fog, smoke, mist - critical for emergency navigation)
- Snow/ice (makes roads slippery and dangerous)
- Extreme temperatures (can affect equipment and response times)

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

# Fire truck specific thresholds for emergency response
RAIN_MM_H=float(os.getenv("RAIN_MM_H","3.0")) # Moderate-heavy rain (reduces visibility/traction)
WIND_MS=float(os.getenv("WIND_MS","12.0")) # Strong wind (>= 43 km/h, affects stability)
VISIBILITY_M=int(os.getenv("VISIBILITY_M","1500")) # Reduced visibility threshold for safe driving
SNOW_MM_H=float(os.getenv("SNOW_MM_H","0.5")) # Any snow accumulation (slippery conditions)
TEMP_LOW_C=float(os.getenv("TEMP_LOW_C","0.0")) # Freezing conditions (ice risk)
TEMP_HIGH_C=float(os.getenv("TEMP_HIGH_C","35.0")) # Extreme heat (equipment strain)

# OpenWeather condition codes for fog, mist, haze, smoke, etc.
# These are critical for fire truck navigation and emergency response
# See: https://openweathermap.org/weather-conditions
FOG_SMOKE_CODES = {
    701, # Mist (reduces visibility)
    711, # Smoke (hazardous, common in fire scenarios)
    721, # Haze (reduces visibility)
    731, # Sand/dust whirls (reduces visibility)
    741, # Fog (severely reduces visibility)
    751, # Sand (reduces visibility)
    761, # Dust (reduces visibility)
    762, # Volcanic ash (hazardous)
}

# Thunderstorm codes - dangerous for emergency response
THUNDERSTORM_CODES = {
    200, 201, 202, # Thunderstorm with rain
    210, 211, 212, # Thunderstorm
    221, 230, 231, 232, # Thunderstorm with drizzle
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
    Analyzes weather data and returns threats that can delay or impede fire truck response.
    Prioritizes conditions that affect emergency vehicle operation, visibility, and road safety.
    """
    threats = []
    weather_codes = {w.get("id") for w in m.get("weather", [])}
    
    # 1. Heavy Rain - Reduces visibility and traction, risk of flooding
    rain_mm = (m.get("rain", {}).get("1h") or 0.0)
    if rain_mm >= RAIN_MM_H:
        # Severity increases with rain intensity
        # Level 3: Very heavy rain (>10mm/h) - high risk of flooding, very poor visibility
        # Level 2: Heavy rain (5-10mm/h) - poor visibility, slippery roads
        # Level 1: Moderate-heavy rain (3-5mm/h) - reduced visibility and traction
        severity = 3 if rain_mm > 10.0 else (2 if rain_mm > 5.0 else 1)
        threats.append({
            "subtype": "HEAVY_RAIN",
            "severity": severity,
            "metrics": {"rain_mm_h": rain_mm},
            "impact": "Reduced visibility and traction, potential flooding"
        })

    # 2. Strong Wind - Affects vehicle stability, can knock down trees/power lines
    wind_ms = (m.get("wind", {}).get("speed") or 0.0)
    if wind_ms >= WIND_MS:
        # Severity based on wind speed
        # Level 3: Gale-force winds (>20 m/s / 72 km/h) - dangerous, debris hazard
        # Level 2: Strong winds (15-20 m/s / 54-72 km/h) - vehicle stability affected
        # Level 1: Moderate strong winds (12-15 m/s / 43-54 km/h) - caution needed
        severity = 3 if wind_ms > 20.0 else (2 if wind_ms > 15.0 else 1)
        threats.append({
            "subtype": "STRONG_WIND",
            "severity": severity,
            "metrics": {"wind_ms": wind_ms, "wind_kmh": round(wind_ms * 3.6, 1)},
            "impact": "Vehicle stability affected, risk of falling debris"
        })

    # 3. Low Visibility - Critical for emergency navigation
    visibility_m = m.get("visibility")
    is_foggy_smoky = bool(FOG_SMOKE_CODES.intersection(weather_codes))
    
    if (visibility_m is not None and visibility_m <= VISIBILITY_M) or is_foggy_smoky:
        # Severity based on visibility distance
        # Level 3: Very low visibility (<200m) - extremely dangerous
        # Level 2: Low visibility (200-500m) - dangerous
        # Level 1: Reduced visibility (500-1500m) - caution needed
        if visibility_m is not None:
            severity = 3 if visibility_m < 200 else (2 if visibility_m < 500 else 1)
        else:
            severity = 2  # If visibility not reported but fog/smoke detected
        
        threats.append({
            "subtype": "LOW_VISIBILITY",
            "severity": severity,
            "metrics": {"visibility_m": visibility_m or "N/A"},
            "impact": "Emergency navigation severely impaired"
        })

    # 4. Snow - Makes roads slippery and dangerous
    snow_mm = (m.get("snow", {}).get("1h") or 0.0)
    if snow_mm >= SNOW_MM_H:
        # Severity based on snow accumulation
        # Level 3: Heavy snow (>5mm/h) - roads very dangerous
        # Level 2: Moderate snow (2-5mm/h) - roads slippery
        # Level 1: Light snow (0.5-2mm/h) - reduced traction
        severity = 3 if snow_mm > 5.0 else (2 if snow_mm > 2.0 else 1)
        threats.append({
            "subtype": "SNOW",
            "severity": severity,
            "metrics": {"snow_mm_h": snow_mm},
            "impact": "Slippery roads, reduced traction"
        })
    
    # 5. Freezing Conditions - Ice risk, extremely dangerous
    temp_c = m.get("main", {}).get("temp")
    if temp_c is not None and temp_c <= TEMP_LOW_C:
        # Check if there's also moisture (rain/snow) which creates ice
        has_moisture = rain_mm > 0 or snow_mm > 0
        # Level 3: Freezing with moisture (ice formation likely)
        # Level 2: Below freezing (ice possible)
        # Level 1: At freezing point (frost possible)
        severity = 3 if has_moisture else (2 if temp_c < -2.0 else 1)
        threats.append({
            "subtype": "FREEZING_CONDITIONS",
            "severity": severity,
            "metrics": {"temp_c": round(temp_c, 1)},
            "impact": "Ice formation risk, extremely slippery roads"
        })
    
    # 6. Extreme Heat - Can affect equipment and reduce response efficiency
    if temp_c is not None and temp_c >= TEMP_HIGH_C:
        # Level 2: Extreme heat (>38°C) - equipment strain
        # Level 1: High heat (35-38°C) - reduced efficiency
        severity = 2 if temp_c > 38.0 else 1
        threats.append({
            "subtype": "EXTREME_HEAT",
            "severity": severity,
            "metrics": {"temp_c": round(temp_c, 1)},
            "impact": "Equipment stress, reduced operational efficiency"
        })
    
    # 7. Thunderstorms - Lightning and heavy rain, very dangerous
    is_thunderstorm = bool(THUNDERSTORM_CODES.intersection(weather_codes))
    if is_thunderstorm:
        # Thunderstorms are always high severity for emergency response
        threats.append({
            "subtype": "THUNDERSTORM",
            "severity": 3,
            "metrics": {"rain_mm_h": rain_mm},
            "impact": "Lightning risk, heavy rain, dangerous conditions"
        })
        
    return threats

def main():
    cells=list(grid_cells(BBOX_S,BBOX_W,BBOX_N,BBOX_E,GRID))
    print(f"[INFO] Collecting weather threats affecting fire truck response...")
    print(f"[INFO] Fetching weather data for {len(cells)} grid cells...")
    print(f"[INFO] Using API key: {KEY[:10]}...{KEY[-4:]}")
    print(f"[INFO] Thresholds: Rain>={RAIN_MM_H}mm/h, Wind>={WIND_MS}m/s, Visibility<={VISIBILITY_M}m")
    print(f"[INFO] Thresholds: Snow>={SNOW_MM_H}mm/h, Temp<={TEMP_LOW_C}°C or >={TEMP_HIGH_C}°C")
    
    feats=[]
    errors=[]
    threat_counts = {}
    
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
                    # Track threat types
                    subtype = threat['subtype']
                    threat_counts[subtype] = threat_counts.get(subtype, 0) + 1
                    
                    props={
                        "provider": "OpenWeather",
                        "ext_id": f"ow:{cell[4]:.3f},{cell[5]:.3f}:{threat['subtype']}",
                        "kind": "weather",
                        "subtype": threat["subtype"],
                        "severity": threat["severity"],
                        "metrics": threat["metrics"],
                        "impact": threat.get("impact", ""),
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
    
    # Print summary of threats found
    print(f"[OK] Saved {OUT} ({len(feats)} total threats, {len(errors)} errors)")
    if threat_counts:
        print("[INFO] Threat breakdown:")
        for threat_type, count in sorted(threat_counts.items()):
            print(f"  - {threat_type}: {count}")
    else:
        print("[INFO] No weather threats detected in the area")

if __name__=="__main__":
    main()
