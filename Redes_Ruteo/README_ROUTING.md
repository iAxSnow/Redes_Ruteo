# Routing and Probability Model Documentation

## Overview

This document describes the routing functionality and probability model implemented for the resilient routing project. This implements points 4 and 5 from the rubric.

## Components

### 1. Probability Model (`scripts/probability_model.py`)

A standalone script that calculates failure probabilities for network elements based on threat proximity.

#### Features
- **Automatic Column Management**: Creates `fail_prob` columns in `rr.ways` and `rr.ways_vertices_pgr` if they don't exist
- **Reset Functionality**: Clears all failure probabilities before recalculation
- **Threat-Based Calculation**: Assigns probabilities based on proximity to threats
- **Statistics Reporting**: Prints detailed summary of affected network elements

#### Configuration
```python
INFLUENCE_RADIUS_M = 50      # Threat influence radius in meters
FAILURE_PROBABILITY = 0.5     # Probability assigned to affected elements
```

#### Usage
```bash
cd Redes_Ruteo
python scripts/probability_model.py
```

#### Algorithm
1. Connect to database using environment variables (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`)
2. Check/create `fail_prob` columns in network tables
3. Reset all probabilities to 0.0
4. For each threat in `rr.amenazas_waze`:
   - Find all ways within 50m using `ST_DWithin`
   - Find all vertices within 50m using `ST_DWithin`
   - Assign probability 0.5 (keeps highest if multiple threats affect same element)
5. Print statistics of affected elements

#### Output Example
```
============================================================
PROBABILITY MODEL - Failure Assessment
============================================================

✓ Connected to database
✓ Column fail_prob already exists in rr.ways
✓ Column fail_prob already exists in rr.ways_vertices_pgr
✓ Reset 15234 ways and 8912 vertices
Processing 142 Waze threats...
✓ Updated 387 ways with failure probability 0.5
✓ Updated 215 vertices with failure probability 0.5

============================================================
FAILURE PROBABILITY STATISTICS
============================================================

Ways:
  Total: 15234
  Affected (fail_prob > 0): 387
  Average probability: 0.0127
  Maximum probability: 0.5000

Vertices:
  Total: 8912
  Affected (fail_prob > 0): 215
  Average probability: 0.0121
  Maximum probability: 0.5000
============================================================
```

### 2. Route Calculation API

New REST API endpoint for calculating optimal routes using pgRouting's Dijkstra algorithm.

#### Endpoint
```
POST /api/calculate_route
```

#### Request Format
```json
{
  "start": {
    "lat": -33.45,
    "lng": -70.65
  },
  "end": {
    "lat": -33.46,
    "lng": -70.66
  }
}
```

#### Response Format
```json
{
  "route_geojson": {
    "type": "Feature",
    "properties": {
      "total_length_m": 1250.5,
      "segments": 15
    },
    "geometry": {
      "type": "LineString",
      "coordinates": [
        [-70.65, -33.45],
        [-70.651, -33.451],
        ...
      ]
    }
  },
  "compute_time_ms": 45.23
}
```

#### Algorithm
1. Receive start/end coordinates from request
2. Find nearest node in `rr.ways_vertices_pgr` to start point using spatial index (`<->` operator)
3. Find nearest node to end point
4. Execute pgRouting query:
   ```sql
   SELECT * FROM pgr_dijkstra(
     'SELECT id, source, target, length_m as cost FROM rr.ways',
     source_node,
     target_node,
     directed := false
   )
   ```
5. Build GeoJSON LineString from route segments
6. Measure and return computation time

#### Error Handling
- 400: Invalid request format (missing coordinates)
- 404: No route found or nodes not found
- 500: Database error

### 3. Web Interface - Routing Controls

#### New UI Elements

**Control Panel Section:**
```
Ruteo
├── Instruction text (dynamic)
├── "Calcular Ruta Óptima" button (disabled until both points selected)
├── "Limpiar Ruta" button
└── Route information panel (hidden until route calculated)
```

#### User Flow

1. **Select Start Point**
   - Click anywhere on map
   - Green marker appears
   - Instruction updates: "Haz clic en el mapa para seleccionar el punto final"

2. **Select End Point**
   - Click again on map
   - Red marker appears
   - "Calcular Ruta Óptima" button becomes enabled
   - Instruction updates: "Haz clic en 'Calcular Ruta Óptima'"

3. **Calculate Route**
   - Click "Calcular Ruta Óptima" button
   - API request sent to `/api/calculate_route`
   - Route displayed as red polyline on map
   - Map auto-zooms to fit route
   - Route information panel shows:
     * Distance in kilometers
     * Computation time in milliseconds
     * Number of segments

4. **Clear Route**
   - Click "Limpiar Ruta" button
   - Removes all markers and route
   - Resets to initial state
   - "Calcular Ruta Óptima" button disabled

#### Visual Design

**Markers:**
- Start: Green marker
- End: Red marker
- User location: Blue marker (from geolocation)

**Route:**
- Color: Red (#e74c3c)
- Weight: 5px
- Opacity: 0.7

**Buttons:**
- Primary (blue): "Calcular Ruta Óptima"
- Secondary (gray): "Limpiar Ruta"
- Disabled state: Grayed out, cursor not-allowed

## Integration with Database

### Required Tables

1. **rr.ways** - Network edges
   ```sql
   - id (bigint, PK)
   - source (bigint)
   - target (bigint)
   - geom (geometry LineString)
   - length_m (numeric)
   - fail_prob (float8) -- Added by probability model
   ```

2. **rr.ways_vertices_pgr** - Network nodes
   ```sql
   - id (bigint, PK)
   - geom (geometry Point)
   - fail_prob (float8) -- Added by probability model
   ```

3. **rr.amenazas_waze** - Threat data
   ```sql
   - ext_id (text, PK)
   - kind (text)
   - subtype (text)
   - severity (integer)
   - geom (geometry)
   ```

### Database Setup

The `rr.ways_vertices_pgr` table should be created using pgRouting:

```sql
-- Create topology
SELECT pgr_createTopology('rr.ways', 0.0001, 'geom', 'id');

-- Add geometry column
ALTER TABLE rr.ways_vertices_pgr ADD COLUMN geom geometry(Point, 4326);
UPDATE rr.ways_vertices_pgr SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326);

-- Create spatial index
CREATE INDEX ways_vertices_gix ON rr.ways_vertices_pgr USING GIST (geom);
```

## Testing

### Manual Testing Checklist

#### Probability Model
- [ ] Script runs without errors
- [ ] Creates fail_prob columns if missing
- [ ] Resets probabilities to 0.0
- [ ] Calculates probabilities based on threats
- [ ] Prints statistics correctly

#### Route Calculation API
- [ ] Returns 400 for invalid requests
- [ ] Finds nearest nodes correctly
- [ ] Calculates route using pgr_dijkstra
- [ ] Returns valid GeoJSON
- [ ] Reports computation time
- [ ] Handles database errors gracefully

#### Web Interface
- [ ] Displays routing controls
- [ ] First click creates green marker (start)
- [ ] Second click creates red marker (end)
- [ ] Calculate button enabled after selecting both points
- [ ] Route displays correctly on map
- [ ] Route info shows distance, time, segments
- [ ] Clear button removes markers and route
- [ ] Instructions update dynamically

### Automated Testing

Run the verification script:
```bash
cd Redes_Ruteo
python3 << 'EOF'
import os
os.environ['FLASK_DEBUG'] = '0'

# Import and test all components
from scripts import probability_model
from app import app

# Verify all functions and endpoints exist
assert hasattr(probability_model, 'calculate_failure_probabilities')
assert 'api_calculate_route' in [r.endpoint for r in app.url_map.iter_rules()]

print("✓ All components verified")
EOF
```

## Future Enhancements

1. **Risk-Aware Routing**
   - Modify cost function to include `fail_prob`
   - Example: `cost = length_m * (1 + fail_prob * weight)`
   - Provides balance between distance and safety

2. **Alternative Route Algorithms**
   - A* for faster computation
   - Multiple route options (shortest, safest, fastest)
   - Route comparison interface

3. **Dynamic Updates**
   - Real-time threat updates
   - Automatic route recalculation
   - WebSocket integration

4. **Advanced Probability Models**
   - Time-based probability decay
   - Severity-based probability scaling
   - Multiple threat source integration

## Troubleshooting

### Probability Model Issues

**Problem:** "Table ways_vertices_pgr does not exist"
**Solution:** Run `pgr_createTopology` to create the topology

**Problem:** "Column geom not found in ways_vertices_pgr"
**Solution:** Add geometry column as shown in Database Setup

### Route Calculation Issues

**Problem:** "Could not find start/end node in network"
**Solution:** Ensure nodes are within network bounds and topology is built

**Problem:** "No route found between the specified points"
**Solution:** Check that network is connected, consider increasing search tolerance

### Web Interface Issues

**Problem:** Map not loading
**Solution:** Check browser console, ensure Leaflet CDN is accessible

**Problem:** "Failed to calculate route" error
**Solution:** Check database connection, ensure network tables exist

## Environment Variables

Required environment variables for both components:

```bash
PGHOST=localhost
PGPORT=5432
PGDATABASE=rr
PGUSER=postgres
PGPASSWORD=postgres

# Optional for development
FLASK_DEBUG=1
```

## Performance Considerations

### Probability Model
- Execution time: ~1-5 seconds for 100-200 threats
- Depends on: Number of threats, network size, spatial index performance
- Recommendation: Run periodically (e.g., hourly) rather than real-time

### Route Calculation
- Typical response time: 20-100ms for routes within 10km
- Depends on: Network size, route length, database load
- Spatial indexes are critical for performance

### Optimization Tips
1. Ensure spatial indexes exist: `CREATE INDEX ... USING GIST (geom)`
2. Run `ANALYZE` after loading data
3. Use connection pooling for multiple requests
4. Consider caching frequently requested routes
