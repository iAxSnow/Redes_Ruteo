#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Waze fetcher adaptativo:
- Usa la API moderna de Waze Live Map (tile-based system)
- Si las APIs fallan, intenta scraping del live map webpage usando Selenium
- Sistema de tiles basado en zoom levels
- Si un tile devuelve 404 o error, lo subdivide en 4 (hasta profundidad 2)
- Extrae alerts, jams e irregularities
- Maneja popups y modales automáticamente

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
USE_BROWSER=os.getenv("WAZE_USE_BROWSER","true").lower() in ("true", "1", "yes")

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
    """Fetch Waze data by scraping the live map webpage using browser automation"""
    
    # Only try browser automation if enabled
    if not USE_BROWSER:
        raise RuntimeError("Browser automation disabled (WAZE_USE_BROWSER=false)")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
    except ImportError:
        raise RuntimeError("Selenium not installed. Install with: pip install selenium")
    
    # Calculate center point for the live map URL
    center_lat = (s + n) / 2
    center_lon = (w + e) / 2
    zoom = 13  # Reasonable zoom level for incident visibility
    
    # Construct live map URL
    live_map_url = f"https://www.waze.com/live-map?zoom={zoom}&lat={center_lat}&lon={center_lon}"
    
    # Setup headless Firefox with optimized settings
    firefox_options = Options()
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("--no-sandbox")
    firefox_options.add_argument("--disable-dev-shm-usage")
    firefox_options.add_argument("--disable-gpu")
    firefox_options.add_argument("--disable-software-rasterizer")
    
    # Disable automation detection
    firefox_options.set_preference("dom.webdriver.enabled", False)
    firefox_options.set_preference("useAutomationExtension", False)
    
    # Set custom User-Agent to avoid automation detection
    firefox_options.set_preference("general.useragent.override", UA["User-Agent"])
    
    # Set display if not already set (for headless environments)
    if "DISPLAY" not in os.environ:
        os.environ["DISPLAY"] = ":99"
    
    # Use MOZ_HEADLESS=1 for better headless support
    os.environ["MOZ_HEADLESS"] = "1"
    
    driver = None
    try:
        # Initialize the driver with service
        service = Service(log_path=os.devnull)  # Suppress geckodriver logs
        driver = webdriver.Firefox(options=firefox_options, service=service)
        driver.set_page_load_timeout(max(TIMEOUT, 15))
        driver.set_script_timeout(10)
        
        # Navigate to the live map
        sys.stderr.write(f"[selenium] Loading {live_map_url}...\n")
        driver.get(live_map_url)
        
        # Wait for initial page load
        time.sleep(2)
        
        # Close popups and modals - try multiple strategies
        sys.stderr.write(f"[selenium] Closing popups...\n")
        
        # Strategy 1: Close cookie consent and privacy banners
        popup_selectors = [
            # Common button texts in multiple languages
            ("xpath", "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]"),
            ("xpath", "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'aceptar')]"),
            ("xpath", "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'got it')]"),
            ("xpath", "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'entendido')]"),
            ("xpath", "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]"),
            ("xpath", "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]"),
            
            # Common IDs and classes
            ("id", "onetrust-accept-btn-handler"),
            ("css", "button[class*='cookie']"),
            ("css", "button[class*='consent']"),
            ("css", "button[aria-label='Close']"),
            ("css", "button.modal-close"),
            ("css", ".close-button"),
            ("css", "[class*='close'][class*='button']"),
            
            # X buttons and close icons
            ("xpath", "//button[contains(@aria-label, 'Close')]"),
            ("xpath", "//button[contains(@aria-label, 'Cerrar')]"),
            ("css", "button[aria-label*='close' i]"),
        ]
        
        for selector_type, selector in popup_selectors:
            try:
                if selector_type == "xpath":
                    elements = driver.find_elements(By.XPATH, selector)
                elif selector_type == "id":
                    elements = [driver.find_element(By.ID, selector)] if driver.find_elements(By.ID, selector) else []
                else:  # css
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements[:3]:  # Try first 3 matches
                    try:
                        if element.is_displayed() and element.is_enabled():
                            element.click()
                            time.sleep(0.3)
                            sys.stderr.write(f"[selenium] Closed popup via {selector_type}: {selector}\n")
                    except:
                        continue
            except:
                continue
        
        # Wait for map data to load
        sys.stderr.write(f"[selenium] Waiting for map data...\n")
        time.sleep(5)
        
        # Extract data from JavaScript objects in the page
        extracted_data = {"alerts": [], "jams": [], "irregularities": []}
        
        # Multiple JavaScript extraction strategies
        js_extractors = [
            # Strategy 1: Direct window objects
            """
            (function() {
                try {
                    let result = {alerts: [], jams: [], irregularities: []};
                    
                    // Check common state objects
                    const stateObjects = [
                        window.__REDUX_STATE__,
                        window.__NEXT_DATA__,
                        window.store && window.store.getState ? window.store.getState() : null
                    ];
                    
                    for (let state of stateObjects) {
                        if (state && typeof state === 'object') {
                            // Deep search for our data
                            function search(obj, depth = 0) {
                                if (depth > 5 || !obj || typeof obj !== 'object') return;
                                
                                if (Array.isArray(obj.alerts)) result.alerts.push(...obj.alerts);
                                if (Array.isArray(obj.jams)) result.jams.push(...obj.jams);
                                if (Array.isArray(obj.irregularities)) result.irregularities.push(...obj.irregularities);
                                
                                for (let key in obj) {
                                    if (obj.hasOwnProperty(key) && typeof obj[key] === 'object') {
                                        search(obj[key], depth + 1);
                                    }
                                }
                            }
                            search(state);
                        }
                    }
                    
                    return JSON.stringify(result);
                } catch (e) {
                    return JSON.stringify({error: e.toString()});
                }
            })();
            """,
            
            # Strategy 2: Search all window properties
            """
            (function() {
                try {
                    let result = {alerts: [], jams: [], irregularities: []};
                    let seen = new Set();
                    
                    function extract(obj, depth = 0) {
                        if (depth > 3 || !obj || typeof obj !== 'object') return;
                        if (seen.has(obj)) return;
                        seen.add(obj);
                        
                        if (Array.isArray(obj.alerts)) result.alerts.push(...obj.alerts);
                        if (Array.isArray(obj.jams)) result.jams.push(...obj.jams);
                        if (Array.isArray(obj.irregularities)) result.irregularities.push(...obj.irregularities);
                        
                        for (let key in obj) {
                            try {
                                if (typeof obj[key] === 'object' && obj[key] !== null) {
                                    extract(obj[key], depth + 1);
                                }
                            } catch (e) {}
                        }
                    }
                    
                    // Search window properties
                    for (let key in window) {
                        try {
                            if (key.startsWith('_') || key.includes('state') || key.includes('State') || key.includes('data')) {
                                extract(window[key]);
                            }
                        } catch (e) {}
                    }
                    
                    return JSON.stringify(result);
                } catch (e) {
                    return JSON.stringify({error: e.toString()});
                }
            })();
            """
        ]
        
        sys.stderr.write(f"[selenium] Extracting data...\n")
        for idx, js_code in enumerate(js_extractors):
            try:
                result = driver.execute_script(js_code)
                if result:
                    data = json.loads(result)
                    if isinstance(data, dict) and not data.get("error"):
                        if data.get("alerts"):
                            extracted_data["alerts"].extend(data["alerts"])
                        if data.get("jams"):
                            extracted_data["jams"].extend(data["jams"])
                        if data.get("irregularities"):
                            extracted_data["irregularities"].extend(data["irregularities"])
                        
                        if any(extracted_data.values()):
                            sys.stderr.write(f"[selenium] Extracted data with strategy {idx+1}\n")
                            break
            except Exception as e:
                sys.stderr.write(f"[selenium] Strategy {idx+1} failed: {e}\n")
                continue
        
        # Filter by bounding box
        filtered_data = {"alerts": [], "jams": [], "irregularities": []}
        
        for alert in extracted_data.get("alerts", []):
            if not isinstance(alert, dict):
                continue
            loc = alert.get("location", {})
            lat = loc.get("y") or loc.get("lat") or loc.get("latitude")
            lon = loc.get("x") or loc.get("lon") or loc.get("longitude")
            if lat and lon and s <= lat <= n and w <= lon <= e:
                filtered_data["alerts"].append(alert)
        
        for jam in extracted_data.get("jams", []):
            if not isinstance(jam, dict):
                continue
            line = jam.get("line", [])
            if line and any(s <= p.get("y", 0) <= n and w <= p.get("x", 0) <= e for p in line if isinstance(p, dict)):
                filtered_data["jams"].append(jam)
        
        for irr in extracted_data.get("irregularities", []):
            if not isinstance(irr, dict):
                continue
            seg = irr.get("seg", {}) or irr.get("location", {})
            lat = seg.get("y") or seg.get("lat") or seg.get("latitude")
            lon = seg.get("x") or seg.get("lon") or seg.get("longitude")
            if lat and lon and s <= lat <= n and w <= lon <= e:
                filtered_data["irregularities"].append(irr)
        
        sys.stderr.write(f"[selenium] Filtered: {len(filtered_data['alerts'])} alerts, {len(filtered_data['jams'])} jams, {len(filtered_data['irregularities'])} irregularities\n")
        
        if any(filtered_data.values()):
            return filtered_data
        
        raise Exception("No data extracted from live map")
        
    except WebDriverException as ex:
        raise RuntimeError(f"Browser automation failed (WebDriver): {ex}")
    except Exception as ex:
        raise RuntimeError(f"Live map scraping failed: {ex}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

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
