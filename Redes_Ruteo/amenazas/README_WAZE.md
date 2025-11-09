# Waze Data Fetcher

## Overview

The Waze incidents fetcher (`waze_incidents_parallel_adaptive.py`) extracts real-time traffic data from Waze, including:
- **Alerts**: Accidents, hazards, road closures
- **Jams**: Traffic congestion with speed and severity
- **Irregularities**: Unusual traffic patterns

## Usage

### Basic Usage

```bash
python amenazas/waze_incidents_parallel_adaptive.py
```

This will:
1. Try to fetch data from Waze API endpoints
2. If APIs fail, automatically scrape the live map webpage
3. Save results to `amenazas/waze_incidents.geojson`
4. Automatically handle failures by subdividing tiles

### Environment Variables

Configure the fetcher using environment variables:

```bash
# Bounding box (default: Santiago, Chile)
export BBOX_S=-33.8
export BBOX_W=-70.95
export BBOX_N=-33.2
export BBOX_E=-70.45

# API settings
export WAZE_TIMEOUT=30        # Request timeout in seconds
export WAZE_RETRIES=2         # Number of retry attempts
export WAZE_MAX_DEPTH=2       # Maximum subdivision depth

# Testing mode
export WAZE_SIMULATE=true     # Enable simulation mode
```

## Simulation Mode

When the Waze API is unavailable or for testing purposes, enable simulation mode:

```bash
WAZE_SIMULATE=true python amenazas/waze_incidents_parallel_adaptive.py
```

This generates realistic sample data that matches the actual API structure, useful for:
- Development and testing
- Demo purposes
- When Waze API is down

## API Endpoints and Web Scraping

The fetcher uses a multi-layered approach to fetch Waze data:

### Layer 1: API Endpoints
Tries multiple Waze API endpoints in order:

1. `https://www.waze.com/live-map/api/georss` - Primary modern API
2. `https://www.waze.com/row-rtserver/web/TGeoRSS` - Rest of World server
3. `https://www.waze.com/partnerhub-api/georss` - Partner Hub API

### Layer 2: Web Scraping Fallback
If all API endpoints fail, automatically falls back to scraping the live map webpage:
- Accesses `https://www.waze.com/es/live-map` with the appropriate coordinates
- Extracts incident data from embedded JSON in the page source
- Filters results by the specified bounding box
- Works even when API endpoints are blocked or unavailable

### Layer 3: Tile Subdivision
If both APIs and web scraping fail for a region:
- Subdivides the bounding box into 4 smaller tiles
- Retries each tile independently (up to MAX_DEPTH subdivisions)
- Preserves existing data file if no new data is fetched

## Output Format

The output is a GeoJSON FeatureCollection with features structured as:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [lon, lat]
      },
      "properties": {
        "provider": "WAZE",
        "ext_id": "unique_id",
        "kind": "incident",
        "subtype": "ACCIDENT|HAZARD|CLOSURE|TRAFFIC_JAM|IRREGULARITY",
        "severity": 1-3,
        "description": "Human readable description",
        "street": "Street name",
        "type_raw": "Original Waze type",
        "timestamp": 1234567890,
        "metrics": {
          "speed_kmh": 25,
          "level": 3
        }
      }
    }
  ]
}
```

### Severity Levels

- **1**: Minor incidents, irregularities
- **2**: Traffic jams, hazards
- **3**: Accidents, road closures

### Geometry Types

- **Point**: Alerts, irregularities
- **LineString**: Traffic jams (congestion along a road segment)

## Troubleshooting

### No data fetched

If you see `[WARN] No features fetched`, the script will:
1. Keep existing `waze_incidents.geojson` if present
2. Create an empty file if none exists
3. The loader will fall back to sample data

### HTTP 404 errors

This indicates the Waze API endpoints have changed. The script tries multiple endpoints automatically. If all fail:
1. Check if Waze service is available
2. Try simulation mode for testing: `WAZE_SIMULATE=true`
3. Update to the latest version of this script

### Timeout errors

Increase the timeout:
```bash
export WAZE_TIMEOUT=60
python amenazas/waze_incidents_parallel_adaptive.py
```

### DNS/Network errors

If running in a restricted environment:
```bash
export WAZE_SIMULATE=true
python amenazas/waze_incidents_parallel_adaptive.py
```

## Integration

The fetched data is loaded into PostgreSQL using:

```bash
python loaders/load_threats_waze.py
```

This loader:
- Reads the GeoJSON file
- Deduplicates by `ext_id`
- Inserts/updates the `rr.amenazas_waze` table
- Falls back to sample data if the GeoJSON is empty

## Development

To test changes without hitting the API:

```bash
# Generate test data
WAZE_SIMULATE=true python amenazas/waze_incidents_parallel_adaptive.py

# Verify output
cat amenazas/waze_incidents.geojson | python -m json.tool | head -50

# Validate structure
python -c "import json; data=json.load(open('amenazas/waze_incidents.geojson')); print(f'{len(data[\"features\"])} features')"
```

## Notes

- The Waze API is unofficial and may change without notice
- Data is provided "as-is" by Waze users
- High traffic times may have more incidents
- Some regions may have limited data coverage
