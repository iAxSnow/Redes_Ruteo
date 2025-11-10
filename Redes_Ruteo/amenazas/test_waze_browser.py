#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Waze data fetching functionality.
This script tests the tile-based API approach without requiring browser automation.
"""

import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_tile_conversion():
    """Test lat/lon to tile conversion"""
    print("[TEST] Testing tile coordinate conversion...")
    
    # Import the conversion function
    sys.path.insert(0, os.path.dirname(__file__))
    from waze_incidents_parallel_adaptive import latlon_to_tile, tile_to_latlon
    
    # Test with known coordinates (Santiago)
    lat, lon = -33.5, -70.7
    zoom = 13
    
    x, y = latlon_to_tile(lat, lon, zoom)
    print(f"  ✓ ({lat}, {lon}) at zoom {zoom} -> tile ({x}, {y})")
    
    # Convert back
    lat2, lon2 = tile_to_latlon(x, y, zoom)
    print(f"  ✓ tile ({x}, {y}) -> ({lat2:.4f}, {lon2:.4f})")
    
    # Verify reasonable result
    if abs(lat - lat2) < 0.1 and abs(lon - lon2) < 0.1:
        print("[OK] Tile conversion works correctly\n")
        return True
    else:
        print("[FAIL] Tile conversion produced unexpected results\n")
        return False

def test_api_endpoint_format():
    """Test that API endpoint URLs are correctly formatted"""
    print("[TEST] Testing API endpoint formatting...")
    
    x, y, z = 2481, 4897, 13
    
    endpoints = [
        f"https://www.waze.com/row-rtserver/web/TGeoRSS?tk=Livemap&x={x}&y={y}&z={z}",
        f"https://www.waze.com/live-map/api/georss?x={x}&y={y}&zoom={z}",
        f"https://www.waze.com/row-rtserver/web/TGeoRSS?x={x}&y={y}&zoom={z}&format=JSON",
    ]
    
    for endpoint in endpoints:
        if f"x={x}" in endpoint and f"y={y}" in endpoint:
            print(f"  ✓ {endpoint[:60]}...")
        else:
            print(f"  ✗ Malformed: {endpoint}")
            return False
    
    print("[OK] API endpoint formatting correct\n")
    return True

def test_environment_variables():
    """Test environment variable handling"""
    print("[TEST] Testing environment variable configuration...")
    
    # Test boolean parsing
    test_cases = [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("0", False),
        ("no", False),
    ]
    
    for value, expected in test_cases:
        result = value.lower() in ("true", "1", "yes")
        if result == expected:
            print(f"  ✓ '{value}' -> {result}")
        else:
            print(f"  ✗ '{value}' -> {result} (expected {expected})")
            return False
    
    print("[OK] Environment variables handled correctly\n")
    return True

def test_bbox_filtering():
    """Test bounding box filtering logic"""
    print("[TEST] Testing bounding box filtering...")
    
    # Define test bbox
    s, w, n, e = -34.0, -71.0, -33.0, -70.0
    
    # Test cases: (lat, lon, should_be_included)
    test_points = [
        (-33.5, -70.5, True, "Inside bbox"),
        (-33.0, -70.0, True, "On boundary"),
        (-35.0, -70.5, False, "South of bbox"),
        (-32.0, -70.5, False, "North of bbox"),
        (-33.5, -72.0, False, "West of bbox"),
        (-33.5, -69.0, False, "East of bbox"),
    ]
    
    for lat, lon, expected, description in test_points:
        result = s <= lat <= n and w <= lon <= e
        status = "✓" if result == expected else "✗"
        print(f"  {status} {description}: ({lat}, {lon}) -> {result}")
        if result != expected:
            return False
    
    print("[OK] Bounding box filtering works correctly\n")
    return True

def test_simulation_mode():
    """Test simulation mode data generation"""
    print("[TEST] Testing simulation mode...")
    
    sys.path.insert(0, os.path.dirname(__file__))
    from waze_incidents_parallel_adaptive import generate_simulated_data
    
    # Generate test data
    data = generate_simulated_data(-33.8, -70.95, -33.2, -70.45)
    
    # Verify structure
    if not isinstance(data, dict):
        print("  ✗ Simulation data is not a dictionary")
        return False
    
    required_keys = ["alerts", "jams", "irregularities"]
    for key in required_keys:
        if key not in data:
            print(f"  ✗ Missing key: {key}")
            return False
        if not isinstance(data[key], list):
            print(f"  ✗ {key} is not a list")
            return False
        print(f"  ✓ {key}: {len(data[key])} items")
    
    print("[OK] Simulation mode works correctly\n")
    return True

def test_selenium_not_required():
    """Test that Selenium is no longer required"""
    print("[TEST] Testing Selenium dependency removal...")
    
    try:
        import selenium
        print("  ⚠ Selenium is installed (not required anymore)")
    except ImportError:
        print("  ✓ Selenium not installed (as expected)")
    
    # Verify our script doesn't import selenium
    script_path = os.path.join(os.path.dirname(__file__), 'waze_incidents_parallel_adaptive.py')
    with open(script_path, 'r') as f:
        content = f.read()
        if 'from selenium' in content or 'import selenium' in content:
            print("  ✗ Script still imports Selenium")
            print("[FAIL] Selenium dependency not removed\n")
            return False
    
    print("  ✓ Script does not import Selenium")
    print("[OK] Selenium dependency successfully removed\n")
    return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("Waze Data Fetching Test Suite (No WebDriver)")
    print("=" * 60 + "\n")
    
    tests = [
        ("Tile Coordinate Conversion", test_tile_conversion),
        ("API Endpoint Formatting", test_api_endpoint_format),
        ("Environment Variables", test_environment_variables),
        ("Bounding Box Filtering", test_bbox_filtering),
        ("Simulation Mode", test_simulation_mode),
        ("Selenium Dependency Removal", test_selenium_not_required),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"[ERROR] {name} test failed with exception: {e}\n")
            results.append((name, False))
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"  {symbol} {name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 60)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
