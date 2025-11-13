# Routing Algorithm Fixes

## Problem Statement
The routing algorithms sometimes failed to calculate routes and never showed them graphically (except for dijkstra_prob). The failure simulation was not properly integrated with route calculation.

## Root Causes Identified

### 1. Invalid Route Geometry Handling
**Issue**: When pgRouting couldn't find a path, `build_route_geojson()` would return a GeoJSON with empty coordinates, which caused display issues on the map.

**Fix**: Added validation in `build_route_geojson()` to check if coordinates are valid (at least 2 points) before returning. Returns `None` if invalid.

```python
# Validate that we have valid coordinates
if not coordinates or len(coordinates) < 2:
    return None
```

### 2. pgRouting "No Path Found" Results Not Filtered
**Issue**: When pgRouting algorithms (pgr_dijkstra, pgr_astar) can't find a path between two nodes, they return a row with `edge = -1`. The code didn't filter these out, causing empty geometry to be processed.

**Fix**: Added `WHERE r.edge != -1` to all routing queries to exclude "no path found" results.

```sql
WHERE r.edge != -1
```

### 3. No Validation Before Adding Routes to Results
**Issue**: Even when `build_route_geojson()` returned invalid data, it was added to the results dictionary without checking.

**Fix**: Check if `route_geojson` is not None before adding to results, with appropriate logging.

```python
route_geojson = build_route_geojson(cur, route_segments)
if route_geojson:
    results['dijkstra_dist'] = {
        "route_geojson": route_geojson,
        ...
    }
else:
    app.logger.warning("dijkstra_dist: No valid geometry for route")
```

### 4. Failure Simulation Not Integrated with Routing
**Issue**: The `/api/simulate_failures` endpoint simulated failures and returned failed edge IDs, but the `/api/calculate_route` endpoint didn't use this information to exclude failed edges.

**Fix**: 
- Added `failed_edges` parameter to `/api/calculate_route` endpoint
- Built a WHERE clause to exclude failed edges from routing queries
- Updated frontend to pass failed edges when calculating routes
- Added visual feedback in the UI showing excluded edges count

```python
# Backend
failed_edges = data.get('failed_edges', [])
failed_edges_clause = ""
if failed_edges and len(failed_edges) > 0:
    failed_edges_str = ','.join(str(int(e)) for e in failed_edges)
    failed_edges_clause = f" AND id NOT IN ({failed_edges_str})"
```

```javascript
// Frontend
if (failedEdges.length > 0) {
    requestBody.failed_edges = failedEdges;
}
```

### 5. Frontend Didn't Handle Missing Routes Gracefully
**Issue**: When a routing algorithm failed to find a path, the frontend would simply not display anything for that algorithm, which was confusing to users.

**Fix**: 
- Updated frontend to iterate through all known algorithms
- Display "No se encontró ruta" for algorithms that didn't return a route
- Show warning when no routes were found at all
- Display count of excluded edges when simulation is active

```javascript
Object.keys(algorithmNames).forEach(algorithmKey => {
    const routeData = data[algorithmKey];
    if (routeData && routeData.route_geojson) {
        // Display route info
    } else {
        // Display "No route found"
    }
});
```

## Files Modified

### Backend (Python)
- **Redes_Ruteo/app.py**
  - `build_route_geojson()`: Added coordinate validation
  - `api_calculate_route()`: Added `failed_edges` parameter and WHERE clause logic
  - All routing queries: Added `WHERE r.edge != -1` filter
  - All routing result builders: Added validation before adding to results
  - Added warning logs for debugging

### Frontend (JavaScript)
- **Redes_Ruteo/static/js/main.js**
  - Updated `failedThreats` to `failedEdges` and added `failedNodes`
  - Modified `calculateRoute()` to include failed edges in API request
  - Enhanced route display to show "No se encontró ruta" for failed algorithms
  - Added check for zero routes and appropriate messaging
  - Updated simulation to show warning about recalculating routes
  - Added visual indicator of excluded edges count

## Testing

### Syntax Validation
✓ Python: Validated with `python3 -m py_compile app.py`
✓ JavaScript: Validated with `node -c main.js`

### Security Scan
✓ CodeQL: No alerts found (0 alerts for Python and JavaScript)

### Manual Testing Required
The following scenarios should be manually tested with a running application and database:

1. **Route Calculation Without Simulation**
   - Select start and end points
   - Click "Calcular Rutas"
   - Verify all 4 algorithms display routes or "No se encontró ruta"
   - Verify routes display graphically on map with correct colors

2. **Route Calculation With Simulation**
   - Enable "Simular Fallas" checkbox
   - Note the number of failed edges
   - Click "Calcular Rutas"
   - Verify routes avoid failed edges
   - Verify warning message shows excluded edges count

3. **Edge Cases**
   - Select disconnected points (should show "No se encontró ruta" for all)
   - Select very close points (should show short routes)
   - Disable route checkboxes and verify routes hide/show correctly

## Impact

### Positive Impact
- All routing algorithms now properly calculate routes or clearly indicate failure
- Routes display graphically when found
- Failure simulation is fully integrated with route calculation
- Better user feedback with clear "No route found" messages
- Improved debugging with warning logs

### Risk Assessment
- **Low Risk**: Changes are surgical and focused on validation and error handling
- No breaking changes to API contracts (added optional parameter)
- Backward compatible (failed_edges parameter is optional)
- No changes to database schema or existing data

## Related Issues
This fixes the issue: "los alguritmos de ruteo a veces fallan pues en la pp no calculan la ruta y nunca muestran la ruta gráficamente a excepción de dijkstra de probabilidad, arregla estos errores incluyendo la simulación de fallas"

Translation: "the routing algorithms sometimes fail because they don't calculate the route and never show the route graphically except for probability dijkstra, fix these errors including the failure simulation"
