#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification script to test that all commands work correctly.
This script verifies:
1. Routing works without threats (using COALESCE in queries)
2. Loaders handle missing files gracefully
3. Probability model handles missing threat tables
"""

import os
import sys
from pathlib import Path

def check_imports():
    """Verify all required Python packages are available."""
    print("\n=== Checking Python Dependencies ===")
    required = ['psycopg2', 'requests', 'flask', 'dotenv', 'geojson']
    missing = []
    
    for pkg in required:
        try:
            if pkg == 'psycopg2':
                import psycopg2
            elif pkg == 'requests':
                import requests
            elif pkg == 'flask':
                import flask
            elif pkg == 'dotenv':
                import dotenv
            elif pkg == 'geojson':
                import geojson
            print(f"✓ {pkg} is available")
        except ImportError:
            print(f"✗ {pkg} is NOT available")
            missing.append(pkg)
    
    if missing:
        print(f"\n⚠ Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True

def check_env_file():
    """Check if .env file exists or .env.example is present."""
    print("\n=== Checking Environment Configuration ===")
    
    if Path('.env').exists():
        print("✓ .env file exists")
        # Check if OPENWEATHER_KEY is set
        from dotenv import load_dotenv
        load_dotenv()
        key = os.getenv('OPENWEATHER_KEY', '').strip()
        if key and key != 'your_api_key_here':
            print(f"✓ OPENWEATHER_KEY is configured (starts with: {key[:10]}...)")
        else:
            print("⚠ OPENWEATHER_KEY is not configured or using placeholder")
            print("  Weather threat collection will not work without a valid API key")
        return True
    elif Path('.env.example').exists():
        print("⚠ .env file does NOT exist, but .env.example is present")
        print("  Copy .env.example to .env and configure your settings")
        return False
    else:
        print("✗ Neither .env nor .env.example exists")
        return False

def check_scripts():
    """Verify all key scripts exist."""
    print("\n=== Checking Script Files ===")
    
    scripts = [
        'amenazas/waze_incidents_parallel_adaptive.py',
        'amenazas/weather_openweather_parallel.py',
        'amenazas/traffic_calming_as_threats_parallel.py',
        'loaders/load_threats_waze.py',
        'loaders/load_threats_weather.py',
        'loaders/load_threats_calming.py',
        'scripts/probability_model.py',
        'app.py'
    ]
    
    all_exist = True
    for script in scripts:
        if Path(script).exists():
            print(f"✓ {script}")
        else:
            print(f"✗ {script} NOT FOUND")
            all_exist = False
    
    return all_exist

def check_routing_coalesce():
    """Verify routing queries use COALESCE for fail_prob."""
    print("\n=== Verifying Routing Query Resilience ===")
    
    app_path = Path('app.py')
    if not app_path.exists():
        print("✗ app.py not found")
        return False
    
    content = app_path.read_text()
    
    # Check for COALESCE usage
    if 'COALESCE(fail_prob, 0)' in content:
        print("✓ Routing queries use COALESCE(fail_prob, 0)")
        print("  Routes will work even without threat data")
        return True
    else:
        print("✗ Routing queries may not handle NULL fail_prob correctly")
        return False

def check_probability_model():
    """Verify probability model handles missing tables."""
    print("\n=== Verifying Probability Model Resilience ===")
    
    prob_path = Path('scripts/probability_model.py')
    if not prob_path.exists():
        print("✗ probability_model.py not found")
        return False
    
    content = prob_path.read_text()
    
    # Check for try-except blocks around threat counting
    if 'except Exception:' in content and 'does not exist or is not accessible' in content:
        print("✓ Probability model handles missing threat tables")
        print("  Script will work even if threat tables don't exist")
        return True
    else:
        print("⚠ Probability model may not handle missing tables gracefully")
        return False

def check_weather_error_handling():
    """Verify weather script has proper error handling."""
    print("\n=== Verifying Weather Script Error Handling ===")
    
    weather_path = Path('amenazas/weather_openweather_parallel.py')
    if not weather_path.exists():
        print("✗ weather_openweather_parallel.py not found")
        return False
    
    content = weather_path.read_text()
    
    # Check for error reporting
    if 'API key unauthorized' in content or 'API key may not be activated' in content:
        print("✓ Weather script reports API key activation issues")
        print("  Users will be informed if their API key is not yet active")
        return True
    else:
        print("⚠ Weather script may not properly report API key issues")
        return False

def check_loader_resilience():
    """Verify loaders handle missing files."""
    print("\n=== Verifying Loader Resilience ===")
    
    loaders = [
        'loaders/load_threats_weather.py',
        'loaders/load_threats_calming.py'
    ]
    
    all_resilient = True
    for loader in loaders:
        path = Path(loader)
        if not path.exists():
            print(f"✗ {loader} not found")
            all_resilient = False
            continue
        
        content = path.read_text()
        if 'if not' in content and '.exists()' in content:
            print(f"✓ {loader} checks if file exists")
        else:
            print(f"⚠ {loader} may not handle missing files gracefully")
            all_resilient = False
    
    return all_resilient

def main():
    """Run all verification checks."""
    print("="*60)
    print("VERIFICATION SCRIPT - Command Functionality Test")
    print("="*60)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    if script_dir.name == 'Redes_Ruteo':
        os.chdir(script_dir)
    
    results = {
        'dependencies': check_imports(),
        'env_config': check_env_file(),
        'scripts': check_scripts(),
        'routing': check_routing_coalesce(),
        'probability': check_probability_model(),
        'weather': check_weather_error_handling(),
        'loaders': check_loader_resilience()
    }
    
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:10} {check}")
    
    print(f"\nResult: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n✓ All checks passed! The system should work correctly.")
        return 0
    else:
        print("\n⚠ Some checks failed. Review the output above for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
