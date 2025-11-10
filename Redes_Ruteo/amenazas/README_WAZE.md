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
2. If APIs fail, automatically scrape the live map webpage using browser automation (Selenium)
3. Close any popups/modals (cookie consent, welcome messages) automatically
4. Save results to `amenazas/waze_incidents.geojson`
5. Automatically handle failures by subdividing tiles

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
export WAZE_RETRIES=3         # Number of retry attempts
export WAZE_MAX_DEPTH=2       # Maximum subdivision depth
export WAZE_ZOOM=13           # Zoom level for tile requests (12-14 recommended)

# Testing mode
export WAZE_SIMULATE=true     # Enable simulation mode
```

## Requirements

The improved fetcher only requires:

1. **requests**: HTTP library (included in requirements.txt)
2. **Python 3.8+**: Standard library for math and JSON operations

**No browser automation required!** Selenium, Firefox, and geckodriver are no longer needed.

```bash
# Install dependencies
pip install -r requirements.txt
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

## API Approach

The fetcher uses a multi-layered approach to fetch Waze data without browser automation:

### Layer 1: Bounding Box API (Primary)
First tries the bbox-based API endpoints:

1. `https://www.waze.com/live-map/api/georss` - Primary modern API
2. `https://www.waze.com/row-rtserver/web/TGeoRSS` - Rest of World server
3. `https://www.waze.com/partnerhub-api/georss` - Partner Hub API

These endpoints accept bounding box parameters (bottom, left, top, right) and return all incidents in the area.

### Layer 2: Tile-Based API (Fallback)
If bbox API fails, uses a tile-based approach:
- Converts the bounding box to tile coordinates at the configured zoom level
- Requests data for each tile individually
- Supports parameters like `?tk=Livemap&x=X&y=Y&z=ZOOM`
- Limits tile requests to avoid overwhelming the API (max 50 tiles)

### Layer 3: Sample Data (Final Fallback)
If all API methods fail:
- Generates sample data with realistic structure
- Ensures the system can continue operating
- Provides consistent test data for development

**Benefits of this approach:**
- ✅ No browser automation required
- ✅ Faster and more reliable
- ✅ Works in headless environments
- ✅ No Selenium/WebDriver dependencies
- ✅ Lower resource usage
- ✅ Better error handling

### Layer 4: Tile Subdivision
If both APIs and browser automation fail for a region:
- Subdivides the bounding box into 4 smaller tiles
- Retries each tile independently (up to MAX_DEPTH subdivisions)
- Preserves existing data file if no new data is fetched

## Removed: Browser Automation

**Previous versions** used Selenium WebDriver with Firefox for web scraping. This has been **removed** because:
- ❌ Unreliable in CI/CD environments
- ❌ Required display server (Xvfb)
- ❌ Chrome/Firefox compatibility issues
- ❌ High resource usage
- ❌ Complex setup and maintenance

The new implementation uses only HTTP requests to Waze APIs, making it:
- ✅ Simpler to deploy
- ✅ More reliable
- ✅ Easier to maintain
- ✅ Works in any environment

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
