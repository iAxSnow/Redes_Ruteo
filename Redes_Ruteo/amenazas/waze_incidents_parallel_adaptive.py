#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Waze fetcher adaptativo:
- Usa la API moderna de Waze Live Map (tile-based system)
- Si las APIs fallan, intenta scraping del live map webpage
- Sistema de tiles basado en zoom levels
- Si un tile devuelve 404 o error, lo subdivide en 4 (hasta profundidad 2)
- Extrae alerts, jams e irregularities

Salida: amenazas/waze_incidents.geojson
"""
import os, json, sys, time, re
from pathlib import Path
from typing import Dict, Any, List, Tuple
import requests

ROOT = Path(__file__).resolve().parent
OUT  = ROOT / "waze_incidents.geojson"

BBOX_S=float(os.getenv("BBOX_S","-33.8"))
BBOX_W=float(os.getenv("BBOX_W","-70.95"))
BBOX_N=float(os.getenv("BBOX_N","-33.2"))
BBOX_E=float(os.getenv("BBOX_E","-70.45"))
TIMEOUT=int(os.getenv("WAZE_TIMEOUT","30"))
RETRIES=int(os.getenv("WAZE_RETRIES","2"))
MAX_DEPTH=int(os.getenv("WAZE_MAX_DEPTH","2"))
SIMULATE=os.getenv("WAZE_SIMULATE","false").lower() in ("true", "1", "yes")

# Modern Waze Live Map API endpoint
WAZE_API_BASE = "https://www.waze.com/live-map/api/georss"

UA={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer":"https://www.waze.com/live-map",
    "Accept":"*/*",
    "Accept-Language":"es-ES,es;q=0.9,en;q=0.8",
    "Origin":"https://www.waze.com"
}

def generate_simulated_data(s,w,n,e)->Dict[str,Any]:
    """Generate simulated Waze data for testing when API is unavailable"""
    import random
    random.seed(hash((s,w,n,e)))
    
    # Generate 2-5 random incidents in the bbox
    num_incidents = random.randint(2, 5)
    alerts = []
    jams = []
    
    for i in range(num_incidents):
        lat = random.uniform(s, n)
        lon = random.uniform(w, e)
        
        incident_types = ["ACCIDENT", "HAZARD_ON_ROAD", "ROAD_CLOSED", "JAM"]
        incident_type = random.choice(incident_types)
        
        if incident_type == "JAM":
            # Create a traffic jam with a line
            num_points = random.randint(3, 8)
            line = []
            for j in range(num_points):
                offset = j * 0.002
                line.append({"x": lon + offset, "y": lat + offset * 0.5})
            
            jams.append({
                "uuid": f"sim_jam_{hash((s,w,n,e,i))}",
                "line": line,
                "speed": random.randint(5, 30),
                "level": random.randint(1, 5),
                "pubMillis": int(time.time() * 1000)
            })
        else:
            # Create an alert
            alerts.append({
                "uuid": f"sim_alert_{hash((s,w,n,e,i))}",
                "location": {"x": lon, "y": lat},
                "type": incident_type,
                "street": f"Calle Simulada {i+1}",
                "reportDescription": f"Incident simulado tipo {incident_type}",
                "pubMillis": int(time.time() * 1000)
            })
    
    return {"alerts": alerts, "jams": jams, "irregularities": []}

def fetch_from_live_map(s,w,n,e)->Dict[str,Any]:
    """Fetch Waze data by scraping the live map webpage"""
    import re
    
    # Calculate center point for the live map URL
    center_lat = (s + n) / 2
    center_lon = (w + e) / 2
    zoom = 12  # Reasonable zoom level for metropolitan areas
    
    # Construct live map URL
    live_map_url = f"https://www.waze.com/es/live-map?zoom={zoom}&lat={center_lat}&lon={center_lon}"
    
    try:
        # Fetch the live map page
        r = requests.get(live_map_url, headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")
        
        html_content = r.text
        
        # Try to extract JSON data from various patterns in the page
        # Pattern 1: Look for embedded JSON in script tags
        patterns = [
            r'window\.__REDUX_STATE__\s*=\s*({.+?});',
            r'window\.__NEXT_DATA__\s*=\s*({.+?})</script>',
            r'"alerts"\s*:\s*(\[.+?\])',
            r'"jams"\s*:\s*(\[.+?\])',
            r'"irregularities"\s*:\s*(\[.+?\])',
        ]
        
        extracted_data = {"alerts": [], "jams": [], "irregularities": []}
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.DOTALL)
            for match in matches:
                try:
                    # Try to parse as JSON
                    data = json.loads(match)
                    
                    # If it's a dict with our keys, extract them
                    if isinstance(data, dict):
                        if "alerts" in data:
                            extracted_data["alerts"].extend(data.get("alerts", []))
                        if "jams" in data:
                            extracted_data["jams"].extend(data.get("jams", []))
                        if "irregularities" in data:
                            extracted_data["irregularities"].extend(data.get("irregularities", []))
                    # If it's an array, try to determine what type
                    elif isinstance(data, list) and len(data) > 0:
                        # Try to infer type from first element
                        if "reportDescription" in str(data[0]) or "street" in str(data[0]):
                            extracted_data["alerts"].extend(data)
                        elif "line" in str(data[0]) or "speed" in str(data[0]):
                            extracted_data["jams"].extend(data)
                except:
                    continue
        
        # Filter by bounding box
        filtered_data = {"alerts": [], "jams": [], "irregularities": []}
        
        for alert in extracted_data.get("alerts", []):
            loc = alert.get("location", {})
            lat = loc.get("y") or loc.get("lat")
            lon = loc.get("x") or loc.get("lon")
            if lat and lon and s <= lat <= n and w <= lon <= e:
                filtered_data["alerts"].append(alert)
        
        for jam in extracted_data.get("jams", []):
            # Check if any point of the jam is in the bbox
            line = jam.get("line", [])
            if any(s <= p.get("y", 0) <= n and w <= p.get("x", 0) <= e for p in line):
                filtered_data["jams"].append(jam)
        
        for irr in extracted_data.get("irregularities", []):
            seg = irr.get("seg", {})
            lat = seg.get("y") or seg.get("lat")
            lon = seg.get("x") or seg.get("lon")
            if lat and lon and s <= lat <= n and w <= lon <= e:
                filtered_data["irregularities"].append(irr)
        
        if any(filtered_data.values()):
            return filtered_data
        
        raise Exception("No data extracted from live map")
        
    except Exception as ex:
        raise RuntimeError(f"Live map scraping failed: {ex}")

def fetch_box(s,w,n,e)->Dict[str,Any]:
    """Fetch Waze data for a bounding box using modern API endpoints and web scraping"""
    # If simulation mode is enabled, return simulated data
    if SIMULATE:
        return generate_simulated_data(s,w,n,e)
    
    # Try multiple endpoint patterns with proper lat/lon bounds
    params = {
        "bottom": s,
        "left": w, 
        "top": n,
        "right": e,
        "types": "alerts,traffic,irregularities",
        "format": "JSON"
    }
    
    # Modern Waze API endpoints to try
    endpoints = [
        "https://www.waze.com/live-map/api/georss",
        "https://www.waze.com/row-rtserver/web/TGeoRSS",
        "https://www.waze.com/partnerhub-api/georss"
    ]
    
    last_error = None
    for k in range(RETRIES):
        # First try API endpoints
        for base_url in endpoints:
            try:
                r = requests.get(base_url, params=params, headers=UA, timeout=TIMEOUT)
                if r.status_code == 200:
                    try:
                        data = r.json()
                        # Check if we got valid data
                        if data and isinstance(data, dict):
                            return data
                    except Exception as je:
                        last_error = f"JSON parse error: {je}"
                        pass
                elif r.status_code == 404:
                    last_error = f"{base_url} -> HTTP 404"
                else:
                    last_error = f"{base_url} -> HTTP {r.status_code}"
                time.sleep(0.3 * (k + 1))
            except Exception as ex:
                last_error = f"{base_url} -> {str(ex)}"
                time.sleep(0.5 * (k + 1))
        
        # If API endpoints failed, try web scraping as fallback
        try:
            sys.stderr.write(f"[info] API endpoints failed, trying web scraping...\n")
            return fetch_from_live_map(s, w, n, e)
        except Exception as ex:
            last_error = f"Web scraping also failed: {ex}"
            time.sleep(0.5 * (k + 1))
    
    raise RuntimeError(last_error if last_error else "Unknown error")

def to_features(ch:Dict[str,Any])->List[Dict[str,Any]]:
    """Convert Waze API response to GeoJSON features"""
    feats=[]
    
    # Process alerts
    for a in ch.get("alerts",[]) or []:
        loc=a.get("location") or {}
        lon=loc.get("x") or loc.get("lon") or loc.get("longitude")
        lat=loc.get("y") or loc.get("lat") or loc.get("latitude")
        
        if lon is None or lat is None: 
            continue
            
        typ=(a.get("type") or "").upper()
        subtype=(a.get("subtype") or "").upper()
        
        # Determine severity and subtype
        if "CLOS" in typ or "ROAD_CLOSED" in typ:
            subtype="CLOSURE"
            sev=3
        elif "JAM" in typ:
            subtype="TRAFFIC_JAM"
            sev=2
        elif "ACCIDENT" in typ or "CRASH" in typ:
            subtype="ACCIDENT"
            sev=3
        elif "HAZARD" in typ:
            subtype="HAZARD"
            sev=2
        else:
            subtype="INCIDENT"
            sev=1
        
        props={
            "provider":"WAZE",
            "ext_id":a.get("uuid") or a.get("id") or f"alert:{lon},{lat}",
            "kind":"incident",
            "subtype":subtype,
            "severity":sev,
            "description":a.get("reportDescription") or a.get("street") or typ,
            "street":a.get("street"),
            "type_raw":a.get("type"),
            "timestamp":a.get("pubMillis") or a.get("reportTimestamp")
        }
        feats.append({
            "type":"Feature",
            "geometry":{"type":"Point","coordinates":[lon,lat]},
            "properties":props
        })
    
    # Process jams (traffic)
    for j in ch.get("jams",[]) or []:
        line=j.get("line") or []
        coords=[]
        for p in line:
            x = p.get("x") or p.get("lon") or p.get("longitude")
            y = p.get("y") or p.get("lat") or p.get("latitude")
            if x is not None and y is not None:
                coords.append([x, y])
        
        if len(coords)>=2:
            speed_kmh = j.get("speed") or j.get("speedKMH")
            level = j.get("level") or 0
            sev = 1 if level <= 2 else 2 if level <= 4 else 3
            
            props={
                "provider":"WAZE",
                "ext_id":j.get("uuid") or j.get("id") or f"jam:{len(coords)}",
                "kind":"incident",
                "subtype":"TRAFFIC_JAM",
                "severity":sev,
                "metrics":{"speed_kmh":speed_kmh, "level": level},
                "timestamp":j.get("pubMillis") or j.get("updateTimestamp")
            }
            feats.append({
                "type":"Feature",
                "geometry":{"type":"LineString","coordinates":coords},
                "properties":props
            })
    
    # Process irregularities
    for irr in ch.get("irregularities",[]) or []:
        seg=irr.get("seg") or irr.get("location") or {}
        lon=seg.get("x") or seg.get("lon") or seg.get("longitude")
        lat=seg.get("y") or seg.get("lat") or seg.get("latitude")
        
        if lon is not None and lat is not None:
            props={
                "provider":"WAZE",
                "ext_id":irr.get("id") or f"irr:{lon},{lat}",
                "kind":"incident",
                "subtype":"IRREGULARITY",
                "severity":1,
                "metrics":{"speed_kmh":irr.get("speed")},
                "timestamp":irr.get("pubMillis") or irr.get("detectionTime")
            }
            feats.append({
                "type":"Feature",
                "geometry":{"type":"Point","coordinates":[lon,lat]},
                "properties":props
            })
    
    return feats

def subdivide(s,w,n,e):
    mlat=(s+n)/2.0; mlon=(w+e)/2.0
    return [(s,w,mlat,mlon),(s,mlon,mlat,e),(mlat,w,n,mlon),(mlat,mlon,n,e)]

def crawl(s,w,n,e,depth=0)->List[Dict[str,Any]]:
    """Recursively crawl tiles, subdividing on errors"""
    try:
        data=fetch_box(s,w,n,e)
        feats=to_features(data)
        if feats: 
            sys.stderr.write(f"[ok] tile {s:.4f},{w:.4f},{n:.4f},{e:.4f} -> {len(feats)} features\n")
            return feats
        # Si no hay features pero tampoco error, no subdividir indefinidamente
        return []
    except Exception as ex:
        sys.stderr.write(f"[warn] tile {s:.4f},{w:.4f},{n:.4f},{e:.4f} -> {ex}\n")
        if depth>=MAX_DEPTH: return []
        out=[]
        for (ss,ww,nn,ee) in subdivide(s,w,n,e):
            out.extend(crawl(ss,ww,nn,ee,depth+1))
        return out

def dedupe(features):
    seen=set(); out=[]
    for f in features:
        eid=f.get("properties",{}).get("ext_id")
        if eid and eid in seen: continue
        if eid: seen.add(eid)
        out.append(f)
    return out

def main():
    """Main function to fetch Waze data and save as GeoJSON"""
    mode_str = "SIMULATION" if SIMULATE else "LIVE"
    print(f"[INFO] Fetching Waze data ({mode_str} mode) for bbox: S={BBOX_S}, W={BBOX_W}, N={BBOX_N}, E={BBOX_E}")
    
    try:
        feats=crawl(BBOX_S,BBOX_W,BBOX_N,BBOX_E,0)
        uniq=dedupe(feats)
        
        # Don't overwrite existing file if no features were found
        if len(uniq) == 0:
            if OUT.exists():
                print(f"[WARN] No features fetched. Keeping existing {OUT} to preserve data.")
                return
            else:
                print(f"[WARN] No features fetched and no existing file.")
                # Create empty file so loader knows we tried
                OUT.write_text(json.dumps({"type":"FeatureCollection","features":[]}, ensure_ascii=False), encoding="utf-8")
                return
        
        # Save the fetched data
        OUT.write_text(json.dumps({"type":"FeatureCollection","features":uniq}, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] Saved {OUT} ({len(uniq)} features)")
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch Waze data: {e}")
        if OUT.exists():
            print(f"[INFO] Keeping existing {OUT} to preserve data.")
        else:
            print(f"[INFO] Creating empty file at {OUT}")
            OUT.write_text(json.dumps({"type":"FeatureCollection","features":[]}, ensure_ascii=False), encoding="utf-8")

if __name__=="__main__":
    main()
