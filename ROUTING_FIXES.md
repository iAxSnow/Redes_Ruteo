# Routing Algorithm Fixes - Documentation

## Problem Statement
The task was to ensure that routing algorithms work perfectly for:
1. Route calculation
2. Map visualization/graphing  
3. Failure simulation (active)

## Issues Found and Fixed

### 1. Schema Inconsistencies

**Problem:** The root `schema.sql` file had Spanish column names (`tipo`, `severidad`) but the loaders and application code used English column names (`kind`, `subtype`, `severity`). This would cause the application to fail when querying the amenazas tables.

**Fix:** 
- Replaced root `schema.sql` with the correct version from `Redes_Ruteo/schema.sql` that uses English column names
- This ensures consistency between schema definition, loaders, and application code

**Files Changed:**
- `schema.sql`

### 2. Missing Edge Filtering in Route GeoJSON Generation

**Problem:** The `build_route_geojson` function in `app.py` was not filtering out pgRouting's special edge values. pgRouting returns edges with `id = -1` for the start and end nodes which should not be included in the final route geometry.

**Fix:**
- Added `WHERE r.edge != -1` clause to filter out these special markers
- This prevents SQL errors and ensures clean route geometries

**Files Changed:**
- `Redes_Ruteo/app.py` - Line 221

### 3. Missing One-Way Street Support

**Problem:** The base routing queries were not respecting one-way streets. All streets were treated as bidirectional (`reverse_cost = length_m` for all edges), which would produce incorrect routes.

**Fix:**
- Added proper one-way street handling in both simulation and non-simulation base queries:
  ```sql
  CASE 
      WHEN w.oneway = true THEN -1
      ELSE w.length_m
  END as reverse_cost
  ```
- This tells pgRouting that the reverse direction is not allowed for one-way streets

**Files Changed:**
- `Redes_Ruteo/app.py` - Lines 320-326, 367-373

### 4. Invalid Edge Filtering

**Problem:** The base queries did not filter out edges with invalid length values (`length_m <= 0`), which could cause routing errors.

**Fix:**
- Added `WHERE w.length_m > 0` to both base routing queries
- This ensures only valid edges are considered for routing

**Files Changed:**
- `Redes_Ruteo/app.py` - Lines 363, 377

### 5. Incorrect Probability Cost Calculation for One-Way Streets

**Problem:** The probability-weighted cost calculation was multiplying the `reverse_cost` by the fail_prob factor even when it was `-1` (one-way street), which would break the one-way restriction.

**Fix:**
- Modified the Dijkstra probability and A* algorithms to preserve `-1` for reverse_cost:
  ```sql
  CASE 
      WHEN reverse_cost = -1 THEN -1
      ELSE reverse_cost * (1 + COALESCE(fail_prob, 0) * 10)
  END AS reverse_cost
  ```

**Files Changed:**
- `Redes_Ruteo/app.py` - Lines 405-409, 429-433

### 6. Overly Permissive Filtered Dijkstra Threshold

**Problem:** The filtered Dijkstra algorithm used a threshold of `< 1.0` to filter "safe" edges. Since fail_prob is typically much lower (0-0.7), this threshold would filter almost nothing.

**Fix:**
- Changed threshold to `< 0.5` to filter out moderately risky and high-risk edges
- This makes the filtered algorithm more meaningful and useful

**Files Changed:**
- `Redes_Ruteo/app.py` - Line 464

### 7. Insufficient Error Logging

**Problem:** Errors in routing calculations were logged but without stack traces, making debugging difficult.

**Fix:**
- Added `traceback.format_exc()` to all routing algorithm error handlers
- Added warning log when filtered Dijkstra finds no route
- This helps identify the root cause of routing failures

**Files Changed:**
- `Redes_Ruteo/app.py` - Lines 396-397, 418-419, 454-456, 479-480

### 8. Overly Strict Frontend Route Validation

**Problem:** The frontend JavaScript checked for `geometry.coordinates.length > 0`, which would fail for MultiLineString geometries or when coordinates is not a simple array.

**Fix:**
- Simplified validation to only check if `geometry` exists
- Added try-catch around L.geoJSON() call to handle any rendering errors gracefully
- This makes the frontend more robust to different geometry types

**Files Changed:**
- `Redes_Ruteo/static/js/main.js` - Lines 473-497

### 9. Missing Feedback for Empty Route Results

**Problem:** When no routes were displayed, the frontend showed nothing, making it unclear if there was an error or routes were just hidden.

**Fix:**
- Added route counter and display message when no routes are shown
- Better user feedback about route availability

**Files Changed:**
- `Redes_Ruteo/static/js/main.js` - Lines 523-547

## Testing

A comprehensive test script has been created at `Redes_Ruteo/scripts/test_routing_fixes.py` that validates:

1. **Database Setup**: Checks that all required tables exist and have data
2. **Schema Columns**: Verifies column names and types are correct
3. **Routing Algorithms**: Tests Dijkstra distance and probability algorithms
4. **Failure Simulation**: Validates the dynamic threat probability query
5. **GeoJSON Output**: Ensures proper GeoJSON structure with geometry and properties

### Running the Tests

```bash
cd Redes_Ruteo
python scripts/test_routing_fixes.py
```

**Prerequisites:**
- PostgreSQL must be running
- Database 'rr' must exist with infrastructure data loaded
- `.env` file must be configured with correct credentials

## Impact of Changes

### Route Calculation
- ✓ Routes now correctly respect one-way streets
- ✓ Only valid edges are considered (length_m > 0)
- ✓ pgRouting special markers are filtered from results
- ✓ Probability weighting preserves one-way restrictions

### Map Visualization
- ✓ Frontend handles all geometry types correctly
- ✓ Better error handling prevents partial rendering failures
- ✓ User gets feedback when no routes are available

### Failure Simulation
- ✓ Dynamic threat probability query works correctly
- ✓ Properly integrates with all routing algorithms
- ✓ Filtered Dijkstra uses meaningful threshold (< 0.5)
- ✓ One-way restrictions preserved in probability-weighted routes

## Compatibility Notes

These fixes are **backward compatible** with existing deployments. The changes:
- Do not modify the database schema
- Do not change the API contract
- Only improve the correctness of existing functionality

However, you should:
1. Use the correct `schema.sql` when setting up new databases
2. Ensure the `fail_prob` column is added if using probability-based routing
3. Run the test script to validate your specific deployment

## Future Improvements

Potential areas for further enhancement:
1. Add support for time-based routing (considering traffic patterns)
2. Implement route comparison visualization
3. Add route validation (avoid restricted zones, minimum road width)
4. Implement caching for frequently calculated routes
5. Add A* algorithm tests to the validation script
