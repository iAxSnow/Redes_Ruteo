#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Waze fetcher adaptativo:
- Usa la API moderna de Waze Live Map (tile-based system)
- Si las APIs fallan, intenta scraping con Selenium WebDriver (Firefox)
- Si WebDriver falla, usa datos de muestra como respaldo final
- Sistema de tiles basado en zoom levels
- Si un tile devuelve 404 o error, lo subdivide en 4 (hasta profundidad 2)
- Extrae alerts, jams e irregularities

Salida: amenazas/waze_incidents.geojson

Requiere: 
  - selenium>=4.15.2 para WebDriver
  - Firefox y GeckoDriver: sudo apt-get install firefox firefox-geckodriver
  (opcional, usa fallback si no está disponible)
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

def load_sample_data()->Dict[str,Any]:
    """Load sample data from amenazas_muestra.geojson as fallback"""
    sample_path = ROOT / "amenazas_muestra.geojson"
    try:
        if sample_path.exists():
            with open(sample_path, 'r', encoding='utf-8') as f:
                sample_geojson = json.load(f)
                # Convert GeoJSON features back to Waze API format
                alerts = []
                jams = []
                for feature in sample_geojson.get("features", []):
                    props = feature.get("properties", {})
                    geom = feature.get("geometry", {})
                    
                    if geom.get("type") == "Point":
                        coords = geom.get("coordinates", [])
                        if len(coords) >= 2:
                            alerts.append({
                                "uuid": props.get("ext_id", f"sample_{len(alerts)}"),
                                "location": {"x": coords[0], "y": coords[1]},
                                "type": props.get("subtype", "INCIDENT"),
                                "street": props.get("description", ""),
                                "reportDescription": props.get("description", ""),
                                "pubMillis": int(time.time() * 1000)
                            })
                    elif geom.get("type") == "LineString":
                        coords = geom.get("coordinates", [])
                        line = [{"x": c[0], "y": c[1]} for c in coords]
                        jams.append({
                            "uuid": props.get("ext_id", f"sample_jam_{len(jams)}"),
                            "line": line,
                            "speed": props.get("metrics", {}).get("speed_kmh", 20),
                            "level": props.get("severity", 2),
                            "pubMillis": int(time.time() * 1000)
                        })
                
                return {"alerts": alerts, "jams": jams, "irregularities": []}
    except Exception as e:
        sys.stderr.write(f"[warn] Could not load sample data: {e}\n")
    
    return {"alerts": [], "jams": [], "irregularities": []}

def fetch_with_webdriver(s,w,n,e)->Dict[str,Any]:
    """Fetch Waze data using Selenium WebDriver (Firefox) for dynamic content"""
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, WebDriverException, SessionNotCreatedException
        
        # Calculate center point for the live map URL
        center_lat = (s + n) / 2
        center_lon = (w + e) / 2
        zoom = 13  # Good zoom level for data collection
        
        # Configure Firefox options for headless mode
        firefox_options = Options()
        firefox_options.add_argument('-headless')  # Headless mode for containers
        firefox_options.set_preference('general.useragent.override', UA["User-Agent"])
        firefox_options.set_preference('permissions.default.image', 2)  # Disable images for faster loading
        firefox_options.set_preference('dom.webnotifications.enabled', False)  # Disable notifications
        
        sys.stderr.write(f"[info] Starting Firefox WebDriver for tile {s:.4f},{w:.4f},{n:.4f},{e:.4f}\n")
        
        # Initialize Firefox WebDriver with better error handling
        try:
            driver = webdriver.Firefox(options=firefox_options)
            driver.set_page_load_timeout(TIMEOUT)
            sys.stderr.write(f"[info] Firefox WebDriver started successfully\n")
        except SessionNotCreatedException as e:
            error_msg = str(e)
            if "geckodriver" in error_msg.lower():
                sys.stderr.write(f"[ERROR] GeckoDriver not found or incompatible.\n")
                sys.stderr.write(f"[ERROR] Install: sudo apt-get install firefox-geckodriver\n")
            elif "Firefox" in error_msg or "firefox" in error_msg.lower():
                sys.stderr.write(f"[ERROR] Firefox not properly installed or can't start.\n")
                sys.stderr.write(f"[ERROR] Install Firefox: sudo apt-get install firefox\n")
            else:
                sys.stderr.write(f"[ERROR] WebDriver session error: {error_msg}\n")
            raise RuntimeError(f"Firefox not available or misconfigured. Using fallback data.")
        except WebDriverException as e:
            error_msg = str(e)
            sys.stderr.write(f"[ERROR] Firefox WebDriver error: {error_msg}\n")
            if "geckodriver" in error_msg.lower():
                sys.stderr.write(f"[ERROR] Install GeckoDriver: sudo apt-get install firefox-geckodriver\n")
            raise RuntimeError(f"Firefox WebDriver failed. Using fallback data.")
        
        try:
            # Navigate to Waze live map
            live_map_url = f"https://www.waze.com/live-map?zoom={zoom}&lat={center_lat}&lon={center_lon}"
            driver.get(live_map_url)
            
            # Wait for the map to load and data to be available
            wait = WebDriverWait(driver, 15)
            time.sleep(3)  # Additional wait for dynamic data loading
            
            # Try to extract data from the page
            # Method 1: Check for embedded JSON in script tags or window objects
            script = """
                try {
                    // Try to find data in various places
                    if (window.__NEXT_DATA__ && window.__NEXT_DATA__.props) {
                        return JSON.stringify(window.__NEXT_DATA__.props);
                    }
                    if (window.__REDUX_STATE__) {
                        return JSON.stringify(window.__REDUX_STATE__);
                    }
                    // Try to get from any exposed data objects
                    if (window.WazeData) {
                        return JSON.stringify(window.WazeData);
                    }
                    return null;
                } catch(e) {
                    return null;
                }
            """
            
            data_json = driver.execute_script(script)
            
            if data_json:
                data = json.loads(data_json)
                
                # Extract alerts, jams, and irregularities from the data structure
                extracted_data = {"alerts": [], "jams": [], "irregularities": []}
                
                # Navigate through the data structure to find alerts/jams
                def extract_from_dict(obj, depth=0):
                    if depth > 10:  # Prevent infinite recursion
                        return
                    
                    if isinstance(obj, dict):
                        # Look for arrays that might contain alerts or jams
                        if "alerts" in obj and isinstance(obj["alerts"], list):
                            extracted_data["alerts"].extend(obj["alerts"])
                        if "jams" in obj and isinstance(obj["jams"], list):
                            extracted_data["jams"].extend(obj["jams"])
                        if "irregularities" in obj and isinstance(obj["irregularities"], list):
                            extracted_data["irregularities"].extend(obj["irregularities"])
                        
                        # Recursively search
                        for value in obj.values():
                            extract_from_dict(value, depth + 1)
                    elif isinstance(obj, list):
                        for item in obj:
                            extract_from_dict(item, depth + 1)
                
                extract_from_dict(data)
                
                # Filter by bounding box
                filtered_data = {"alerts": [], "jams": [], "irregularities": []}
                
                for alert in extracted_data.get("alerts", []):
                    loc = alert.get("location", {})
                    lat = loc.get("y") or loc.get("lat")
                    lon = loc.get("x") or loc.get("lon")
                    if lat and lon and s <= lat <= n and w <= lon <= e:
                        filtered_data["alerts"].append(alert)
                
                for jam in extracted_data.get("jams", []):
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
                    sys.stderr.write(f"[ok] WebDriver extracted {len(filtered_data['alerts'])} alerts, {len(filtered_data['jams'])} jams\n")
                    return filtered_data
            
            # If no data found, return empty
            sys.stderr.write(f"[warn] WebDriver could not extract data from page\n")
            raise RuntimeError("No data extracted via WebDriver")
            
        finally:
            driver.quit()
    
    except ImportError as e:
        sys.stderr.write(f"[info] Selenium not installed. Install with: pip install selenium\n")
        raise RuntimeError(f"Selenium not available. Using fallback data.")
    except (WebDriverException, SessionNotCreatedException) as e:
        # More specific error message already logged above
        raise RuntimeError(f"WebDriver unavailable. Using fallback data.")
    except Exception as e:
        sys.stderr.write(f"[warn] WebDriver fetch failed: {e}\n")
        raise RuntimeError(f"WebDriver failed. Using fallback data.")

def fetch_box(s,w,n,e)->Dict[str,Any]:
    """Fetch Waze data for a bounding box using modern API endpoints, WebDriver, and sample data as fallback"""
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
        # Try API endpoints
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
    
    # If all API endpoints failed, try WebDriver scraping
    sys.stderr.write(f"[info] API endpoints failed, trying WebDriver scraping...\n")
    try:
        webdriver_data = fetch_with_webdriver(s, w, n, e)
        if webdriver_data and (webdriver_data.get("alerts") or webdriver_data.get("jams")):
            return webdriver_data
    except Exception as ex:
        last_error = str(ex)
        # Error messages already logged in fetch_with_webdriver
        if "Chrome not available" in last_error or "WebDriver unavailable" in last_error:
            sys.stderr.write(f"[info] WebDriver not available (Chrome/ChromeDriver issue). Falling back to sample data.\n")
        elif "Selenium not available" in last_error:
            sys.stderr.write(f"[info] Selenium not installed. Falling back to sample data.\n")
        else:
            sys.stderr.write(f"[info] WebDriver scraping failed. Falling back to sample data.\n")
    
    # If WebDriver also failed, use sample data as final fallback
    sys.stderr.write(f"[OK] Using sample data from amenazas_muestra.geojson\n")
    sample_data = load_sample_data()
    if sample_data and (sample_data.get("alerts") or sample_data.get("jams")):
        sys.stderr.write(f"[OK] Loaded {len(sample_data.get('alerts', []))} sample alerts, {len(sample_data.get('jams', []))} sample jams\n")
        return sample_data
    
    sys.stderr.write(f"[ERROR] All data sources failed and no sample data available\n")
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
