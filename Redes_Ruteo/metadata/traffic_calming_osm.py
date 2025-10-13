import os, json, time
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

OUT = Path(__file__).resolve().parent / "traffic_calming.geojson"

BBOX_S = float(os.getenv("BBOX_S", "-34.3"))
BBOX_W = float(os.getenv("BBOX_W", "-71.8"))
BBOX_N = float(os.getenv("BBOX_N", "-32.6"))
BBOX_E = float(os.getenv("BBOX_E", "-70.2"))

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

Q = f"""
[out:json][timeout:120];
node["traffic_calming"]({BBOX_S},{BBOX_W},{BBOX_N},{BBOX_E});
out body;
"""

def main():
    print("[E] Descargando reductores (traffic_calming) desde OSM…")
    r = requests.post(OVERPASS_URL, data={"data": Q})
    r.raise_for_status()
    data = r.json()

    features = []
    for el in data.get("elements", []):
        if el["type"] == "node":
            features.append({
                "type": "Feature",
                "id": el["id"],
                "geometry": {
                    "type": "Point",
                    "coordinates": [el["lon"], el["lat"]]
                },
                "properties": {
                    "osm_id": el["id"],
                    "kind": el.get("tags", {}).get("traffic_calming"),
                    "tags": el.get("tags", {})
                }
            })

    geo = {"type": "FeatureCollection", "features": features}
    OUT.write_text(json.dumps(geo, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Guardado {OUT} con {len(features)} reductores.")

if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"[Done] en {time.time()-t0:.1f}s")
