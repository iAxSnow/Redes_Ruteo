# Weather Threats - Fire Truck Emergency Response

## Overview
The weather threat collection system has been specifically tailored to detect conditions that can delay or impede fire truck emergency response. All thresholds and threat types are designed with emergency vehicle operation in mind.

## Threat Types

### 1. HEAVY_RAIN
**Impact:** Reduces visibility and traction, risk of flooding

**Thresholds:**
- Detection: ≥ 3.0 mm/h
- Severity 1: 3-5 mm/h (Moderate-heavy rain)
- Severity 2: 5-10 mm/h (Heavy rain, poor visibility)
- Severity 3: > 10 mm/h (Very heavy rain, high flooding risk)

**Routing Probability:** 0.15 + (severity - 1) × 0.08
- Level 1: 0.15 (15% delay risk)
- Level 2: 0.23 (23% delay risk)
- Level 3: 0.31 (31% delay risk)

### 2. STRONG_WIND
**Impact:** Affects vehicle stability, risk of falling debris (trees, power lines)

**Thresholds:**
- Detection: ≥ 12.0 m/s (43 km/h)
- Severity 1: 12-15 m/s (Moderate strong winds)
- Severity 2: 15-20 m/s (Strong winds)
- Severity 3: > 20 m/s (Gale-force winds, dangerous)

**Routing Probability:** 0.12 + (severity - 1) × 0.08
- Level 1: 0.12 (12% delay risk)
- Level 2: 0.20 (20% delay risk)
- Level 3: 0.28 (28% delay risk)

### 3. LOW_VISIBILITY
**Impact:** Emergency navigation severely impaired

**Thresholds:**
- Detection: ≤ 1500m visibility OR fog/smoke/mist detected
- Severity 1: 500-1500m (Reduced visibility)
- Severity 2: 200-500m (Low visibility, dangerous)
- Severity 3: < 200m (Very low visibility, extremely dangerous)

**Weather Codes Detected:**
- 701: Mist
- 711: Smoke (critical for fire scenarios)
- 721: Haze
- 731: Sand/dust whirls
- 741: Fog
- 751: Sand
- 761: Dust
- 762: Volcanic ash

**Routing Probability:** 0.30 + (severity - 1) × 0.10
- Level 1: 0.30 (30% delay risk)
- Level 2: 0.40 (40% delay risk)
- Level 3: 0.50 (50% delay risk)

### 4. SNOW
**Impact:** Slippery roads, reduced traction

**Thresholds:**
- Detection: ≥ 0.5 mm/h
- Severity 1: 0.5-2 mm/h (Light snow)
- Severity 2: 2-5 mm/h (Moderate snow)
- Severity 3: > 5 mm/h (Heavy snow, very dangerous)

**Routing Probability:** 0.20 + (severity - 1) × 0.10
- Level 1: 0.20 (20% delay risk)
- Level 2: 0.30 (30% delay risk)
- Level 3: 0.40 (40% delay risk)

### 5. FREEZING_CONDITIONS (NEW)
**Impact:** Ice formation risk, extremely slippery roads

**Thresholds:**
- Detection: Temperature ≤ 0°C
- Severity 1: At freezing point (0°C), frost possible
- Severity 2: Below freezing (< -2°C), ice likely
- Severity 3: Freezing with moisture (rain/snow present), ice formation certain

**Routing Probability:** 0.35 + (severity - 1) × 0.15
- Level 1: 0.35 (35% delay risk)
- Level 2: 0.50 (50% delay risk)
- Level 3: 0.65 (65% delay risk)

**Note:** This is one of the most dangerous conditions for emergency vehicles.

### 6. EXTREME_HEAT (NEW)
**Impact:** Equipment stress, reduced operational efficiency

**Thresholds:**
- Detection: Temperature ≥ 35°C
- Severity 1: 35-38°C (High heat)
- Severity 2: > 38°C (Extreme heat)

**Routing Probability:** 0.08 + (severity - 1) × 0.04
- Level 1: 0.08 (8% delay risk)
- Level 2: 0.12 (12% delay risk)

### 7. THUNDERSTORM (NEW)
**Impact:** Lightning risk, heavy rain, dangerous conditions

**Weather Codes:**
- 200, 201, 202: Thunderstorm with rain
- 210, 211, 212: Thunderstorm
- 221, 230, 231, 232: Thunderstorm with drizzle

**Routing Probability:** 0.45 (fixed, always high severity)

**Note:** Thunderstorms are always considered high-risk for emergency operations.

## Configuration

All thresholds can be customized via environment variables in `.env`:

```bash
# Weather threat thresholds (fire truck specific)
RAIN_MM_H=3.0           # Heavy rain threshold (mm/h)
WIND_MS=12.0            # Strong wind threshold (m/s)
VISIBILITY_M=1500       # Low visibility threshold (meters)
SNOW_MM_H=0.5           # Snow threshold (mm/h)
TEMP_LOW_C=0.0          # Freezing temperature (°C)
TEMP_HIGH_C=35.0        # Extreme heat threshold (°C)
```

## Usage

### Running the Weather Threat Collector

```bash
cd Redes_Ruteo
python amenazas/weather_openweather_parallel.py
```

### Output
The script generates `amenazas/weather_threats.geojson` with:
- GeoJSON polygon features covering the area grid
- Each threat has:
  - `kind`: "weather"
  - `subtype`: Threat type (e.g., "HEAVY_RAIN")
  - `severity`: 1-3 level
  - `metrics`: Weather measurements
  - `impact`: Description of impact on fire truck operations
  - `ts`: Timestamp

### Example Output
```
[INFO] Collecting weather threats affecting fire truck response...
[INFO] Fetching weather data for 30 grid cells...
[INFO] Thresholds: Rain>=3.0mm/h, Wind>=12.0m/s, Visibility<=1500m
[INFO] Thresholds: Snow>=0.5mm/h, Temp<=0.0°C or >=35.0°C
[OK] Saved amenazas/weather_threats.geojson (15 total threats, 0 errors)
[INFO] Threat breakdown:
  - HEAVY_RAIN: 8
  - LOW_VISIBILITY: 5
  - STRONG_WIND: 2
```

## Integration with Routing

The routing system (`app.py`) uses these threats during failure simulation:

1. Weather threats are spatially joined with road segments (`ST_Intersects`)
2. Each road segment gets assigned the maximum threat probability
3. Routing algorithms use these probabilities to:
   - Weight costs (Dijkstra/A* with probability)
   - Filter dangerous routes (Filtered Dijkstra)

## Rationale for Fire Truck Specific Design

### Lower Thresholds
Fire trucks need to operate in sub-optimal conditions, so threats are detected earlier:
- Rain: 3 mm/h vs typical 5 mm/h
- Wind: 12 m/s vs typical 14 m/s
- Visibility: 1500m vs typical 1000m

### New Threat Types
Emergency-specific conditions:
- **Freezing conditions**: Ice is extremely dangerous for heavy vehicles
- **Extreme heat**: Affects equipment performance and crew safety
- **Thunderstorms**: Lightning risk during outdoor operations

### Higher Severity Granularity
3-level system provides better route differentiation:
- Level 1: Proceed with caution
- Level 2: Significant delay/difficulty
- Level 3: Major hazard, alternative route strongly recommended

### Critical Visibility Focus
Smoke detection (code 711) is essential for fire scenarios, and visibility gets highest base probability (0.30) due to navigation criticality.

## Future Enhancements

Potential improvements:
1. **Road surface temperature**: Detect black ice conditions
2. **Historical flooding areas**: Combine with rain data for flood prediction
3. **Wind direction**: Account for crosswinds on bridges/overpasses
4. **Real-time updates**: Shorter polling intervals during active incidents
5. **Predictive modeling**: Use forecast data to plan ahead
