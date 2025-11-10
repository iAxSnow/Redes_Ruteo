#!/bin/bash
# Example script showing how to use the Waze live map scraper with browser automation

# Basic usage with default settings
echo "=== Example 1: Basic Usage ==="
echo "python amenazas/waze_incidents_parallel_adaptive.py"
echo ""

# Using simulation mode for testing
echo "=== Example 2: Simulation Mode ==="
echo "WAZE_SIMULATE=true python amenazas/waze_incidents_parallel_adaptive.py"
echo ""

# Custom bounding box (e.g., Buenos Aires)
echo "=== Example 3: Custom Bounding Box (Buenos Aires) ==="
echo "export BBOX_S=-34.7"
echo "export BBOX_W=-58.5"
echo "export BBOX_N=-34.5"
echo "export BBOX_E=-58.3"
echo "python amenazas/waze_incidents_parallel_adaptive.py"
echo ""

# With increased timeout for slow connections
echo "=== Example 4: Increased Timeout ==="
echo "WAZE_TIMEOUT=60 python amenazas/waze_incidents_parallel_adaptive.py"
echo ""

# Disable browser automation (API only)
echo "=== Example 5: Disable Browser Automation ==="
echo "WAZE_USE_BROWSER=false python amenazas/waze_incidents_parallel_adaptive.py"
echo ""

# Full example with all options
echo "=== Example 6: Full Configuration ==="
cat << 'EOF'
export BBOX_S=-33.8
export BBOX_W=-70.95
export BBOX_N=-33.2
export BBOX_E=-70.45
export WAZE_TIMEOUT=45
export WAZE_RETRIES=3
export WAZE_MAX_DEPTH=2
export WAZE_USE_BROWSER=true
export DISPLAY=:99  # If using Xvfb

python amenazas/waze_incidents_parallel_adaptive.py
EOF
echo ""

# Running with Xvfb in headless environment
echo "=== Example 7: Headless Environment with Xvfb ==="
cat << 'EOF'
# Start virtual display
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
export MOZ_HEADLESS=1

# Run the scraper
python amenazas/waze_incidents_parallel_adaptive.py

# Verify output
cat amenazas/waze_incidents.geojson | python -m json.tool | head -50
EOF
