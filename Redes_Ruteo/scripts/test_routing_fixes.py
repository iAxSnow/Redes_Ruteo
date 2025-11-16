#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to validate routing algorithm fixes.

This script tests:
1. Route calculation with all algorithms
2. Proper handling of oneway streets
3. Failure simulation integration
4. GeoJSON output format
5. Error handling

Run this after the database is set up with infrastructure data.
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Database configuration
PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

# Test coordinates (Santiago, Chile area)
TEST_START = (-33.45, -70.65)  # Near Plaza de Armas
TEST_END = (-33.42, -70.61)    # Near Providencia


def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=PGHOST,
            port=PGPORT,
            dbname=PGDATABASE,
            user=PGUSER,
            password=PGPASSWORD,
            connect_timeout=5
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ Could not connect to database: {e}")
        print("\nPlease ensure:")
        print("  1. PostgreSQL is running")
        print("  2. Database 'rr' exists")
        print("  3. Credentials in .env are correct")
        return None


def test_database_setup(conn):
    """Test that the database has the necessary tables and data."""
    print("\n" + "="*60)
    print("TEST 1: Database Setup")
    print("="*60)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check required tables exist
    required_tables = [
        'rr.ways',
        'rr.ways_vertices_pgr',
        'rr.amenazas_waze',
        'rr.amenazas_calming',
        'rr.amenazas_clima'
    ]
    
    all_exist = True
    for table in required_tables:
        schema, table_name = table.split('.')
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = %s
            )
        """, (schema, table_name))
        exists = cur.fetchone()['exists']
        
        if exists:
            cur.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cur.fetchone()['count']
            print(f"✓ {table}: {count:,} rows")
        else:
            print(f"✗ {table}: NOT FOUND")
            all_exist = False
    
    cur.close()
    return all_exist


def test_schema_columns(conn):
    """Test that required columns exist with correct types."""
    print("\n" + "="*60)
    print("TEST 2: Schema Columns")
    print("="*60)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check ways table has required columns
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'rr' AND table_name = 'ways'
        ORDER BY column_name
    """)
    
    columns = cur.fetchall()
    required_cols = ['id', 'source', 'target', 'geom', 'length_m', 'oneway']
    
    found_cols = [col['column_name'] for col in columns]
    
    all_found = True
    for req_col in required_cols:
        if req_col in found_cols:
            col_info = next(c for c in columns if c['column_name'] == req_col)
            print(f"✓ {req_col}: {col_info['data_type']}")
        else:
            print(f"✗ {req_col}: NOT FOUND")
            all_found = False
    
    # Check amenazas tables have English column names
    for table in ['amenazas_waze', 'amenazas_calming', 'amenazas_clima']:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'rr' AND table_name = %s
        """, (table,))
        
        cols = [row['column_name'] for row in cur.fetchall()]
        
        if 'kind' in cols and 'subtype' in cols and 'severity' in cols:
            print(f"✓ {table}: Has English columns (kind, subtype, severity)")
        elif 'tipo' in cols or 'severidad' in cols:
            print(f"⚠ {table}: Has Spanish columns (tipo, severidad) - should be English")
        else:
            print(f"? {table}: Unknown column structure")
    
    cur.close()
    return all_found


def find_nearest_node(conn, lat, lon):
    """Find nearest routing node to coordinates."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, ST_X(the_geom) as lon, ST_Y(the_geom) as lat
        FROM rr.ways_vertices_pgr
        ORDER BY the_geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        LIMIT 1
    """, (lon, lat))
    
    result = cur.fetchone()
    cur.close()
    return result


def test_routing_query(conn, algorithm_name, sql_query, source_node, target_node):
    """Test a single routing algorithm."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Execute the routing query
        cur.execute(sql_query, (source_node, target_node))
        route = cur.fetchall()
        
        if not route:
            print(f"  ✗ {algorithm_name}: No route found")
            return False
        
        # Filter out start/end markers
        edges = [r for r in route if r['edge'] != -1]
        
        if not edges:
            print(f"  ✗ {algorithm_name}: No edges in route")
            return False
        
        # Calculate total cost and distance
        total_cost = sum(r['cost'] for r in route)
        
        # Get geometries
        edge_ids = [r['edge'] for r in edges]
        cur.execute("""
            SELECT SUM(length_m) as total_length
            FROM rr.ways
            WHERE id = ANY(%s)
        """, (edge_ids,))
        
        stats = cur.fetchone()
        total_length_m = stats['total_length'] or 0
        
        print(f"  ✓ {algorithm_name}: {len(edges)} segments, "
              f"{total_length_m/1000:.2f} km, cost={total_cost:.2f}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ {algorithm_name}: Error - {str(e)}")
        return False
    finally:
        cur.close()


def test_all_routing_algorithms(conn):
    """Test all routing algorithms work correctly."""
    print("\n" + "="*60)
    print("TEST 3: Routing Algorithms")
    print("="*60)
    
    # Find start and end nodes
    start_node_info = find_nearest_node(conn, TEST_START[0], TEST_START[1])
    end_node_info = find_nearest_node(conn, TEST_END[0], TEST_END[1])
    
    if not start_node_info or not end_node_info:
        print("✗ Could not find start or end nodes")
        return False
    
    source_node = start_node_info['id']
    target_node = end_node_info['id']
    
    print(f"\nRouting from node {source_node} to node {target_node}")
    print(f"  Start: ({start_node_info['lat']:.4f}, {start_node_info['lon']:.4f})")
    print(f"  End: ({end_node_info['lat']:.4f}, {end_node_info['lon']:.4f})")
    print()
    
    # Base query for routing (without failure simulation)
    base_query = """
        SELECT 
            w.id, 
            w.source, 
            w.target, 
            w.length_m as cost,
            CASE 
                WHEN w.oneway = true THEN -1
                ELSE w.length_m
            END as reverse_cost
        FROM rr.ways w
        WHERE w.length_m > 0
    """
    
    all_passed = True
    
    # Test 1: Dijkstra with distance only
    dijkstra_dist_sql = f"""
        SELECT * FROM pgr_dijkstra(
            'SELECT id, source, target, cost, reverse_cost FROM ({base_query}) q',
            %s, %s, directed := true
        )
    """
    if not test_routing_query(conn, "Dijkstra (Distance)", dijkstra_dist_sql, source_node, target_node):
        all_passed = False
    
    # Test 2: Check if fail_prob column exists
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'rr' AND table_name = 'ways' 
            AND column_name = 'fail_prob'
        )
    """)
    has_fail_prob = cur.fetchone()['exists']
    cur.close()
    
    if has_fail_prob:
        # Test with probability weighting
        base_query_with_prob = base_query.replace(
            "FROM rr.ways w",
            "FROM rr.ways w"
        ) + ", COALESCE(w.fail_prob, 0) as fail_prob"
        
        dijkstra_prob_sql = f"""
            SELECT * FROM pgr_dijkstra(
                'SELECT id, source, target, 
                        cost * (1 + COALESCE(fail_prob, 0) * 10) AS cost,
                        CASE 
                            WHEN reverse_cost = -1 THEN -1
                            ELSE reverse_cost * (1 + COALESCE(fail_prob, 0) * 10)
                        END AS reverse_cost
                 FROM ({base_query_with_prob}) q',
                %s, %s, directed := true
            )
        """
        if not test_routing_query(conn, "Dijkstra (Probability)", dijkstra_prob_sql, source_node, target_node):
            all_passed = False
    else:
        print("  ⚠ Skipping probability tests (fail_prob column not found)")
    
    return all_passed


def test_failure_simulation(conn):
    """Test failure simulation integration."""
    print("\n" + "="*60)
    print("TEST 4: Failure Simulation")
    print("="*60)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check if threat tables have data
    for table, display_name in [
        ('rr.amenazas_waze', 'Waze'),
        ('rr.amenazas_calming', 'Traffic Calming'),
        ('rr.amenazas_clima', 'Weather')
    ]:
        cur.execute(f"SELECT COUNT(*) as count FROM {table}")
        count = cur.fetchone()['count']
        print(f"  {display_name} threats: {count:,}")
    
    # Test the dynamic failure probability query
    try:
        cur.execute("""
            WITH all_threats AS (
                -- Waze threats
                SELECT 
                    w.id AS way_id,
                    'waze' as source, subtype, severity
                FROM rr.ways w
                JOIN rr.amenazas_waze t ON ST_DWithin(w.geom, t.geom, 0.001)
                UNION ALL
                -- Weather threats
                SELECT 
                    w.id AS way_id,
                    'weather' as source, subtype, severity
                FROM rr.ways w
                JOIN rr.amenazas_clima t ON ST_Intersects(w.geom, t.geom)
                UNION ALL
                -- Traffic Calming threats
                SELECT 
                    w.id AS way_id,
                    'traffic_calming' as source, subtype, severity
                FROM rr.ways w
                JOIN rr.amenazas_calming t ON ST_DWithin(w.geom, t.geom, 0.00015)
            )
            SELECT COUNT(*) as affected_ways
            FROM (
                SELECT DISTINCT way_id FROM all_threats
            ) t
        """)
        
        result = cur.fetchone()
        affected = result['affected_ways']
        print(f"\n✓ Dynamic threat query works: {affected:,} ways affected by threats")
        
    except Exception as e:
        print(f"\n✗ Dynamic threat query failed: {str(e)}")
        cur.close()
        return False
    
    cur.close()
    return True


def test_geojson_output(conn):
    """Test GeoJSON output format."""
    print("\n" + "="*60)
    print("TEST 5: GeoJSON Output")
    print("="*60)
    
    # Find start and end nodes
    start_node_info = find_nearest_node(conn, TEST_START[0], TEST_START[1])
    end_node_info = find_nearest_node(conn, TEST_END[0], TEST_END[1])
    
    if not start_node_info or not end_node_info:
        print("✗ Could not find start or end nodes")
        return False
    
    source_node = start_node_info['id']
    target_node = end_node_info['id']
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Test the GeoJSON generation query
        cur.execute("""
            WITH route AS (
                SELECT * FROM pgr_dijkstra(
                    'SELECT id, source, target, length_m as cost, 
                            CASE WHEN oneway = true THEN -1 ELSE length_m END as reverse_cost
                     FROM rr.ways WHERE length_m > 0',
                    %s, %s, directed := true
                )
            )
            SELECT json_build_object(
                'type', 'Feature',
                'properties', json_build_object(
                    'total_length_m', SUM(w.length_m),
                    'total_cost', SUM(r.cost)
                ),
                'geometry', ST_AsGeoJSON(ST_LineMerge(ST_Union(w.geom ORDER BY r.seq)))::json
            ) AS geojson
            FROM route r
            JOIN rr.ways w ON r.edge = w.id
            WHERE r.edge != -1;
        """, (source_node, target_node))
        
        result = cur.fetchone()
        
        if result and result['geojson']:
            geojson = result['geojson']
            
            # Validate structure
            if 'type' in geojson and geojson['type'] == 'Feature':
                print("✓ GeoJSON has correct type: Feature")
            else:
                print("✗ GeoJSON missing or incorrect type")
                return False
            
            if 'geometry' in geojson and 'coordinates' in geojson['geometry']:
                coords = geojson['geometry']['coordinates']
                print(f"✓ GeoJSON has geometry with {len(coords) if isinstance(coords, list) else 'nested'} coordinates")
            else:
                print("✗ GeoJSON missing geometry or coordinates")
                return False
            
            if 'properties' in geojson:
                props = geojson['properties']
                if 'total_length_m' in props and 'total_cost' in props:
                    print(f"✓ GeoJSON has properties: length={props['total_length_m']:.2f}m, cost={props['total_cost']:.2f}")
                else:
                    print("✗ GeoJSON missing required properties")
                    return False
            
            return True
        else:
            print("✗ No GeoJSON generated")
            return False
            
    except Exception as e:
        print(f"✗ GeoJSON generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cur.close()


def main():
    """Run all tests."""
    print("="*60)
    print("ROUTING ALGORITHM FIXES VALIDATION")
    print("="*60)
    
    conn = get_db_connection()
    if not conn:
        sys.exit(1)
    
    try:
        results = {
            "Database Setup": test_database_setup(conn),
            "Schema Columns": test_schema_columns(conn),
            "Routing Algorithms": test_all_routing_algorithms(conn),
            "Failure Simulation": test_failure_simulation(conn),
            "GeoJSON Output": test_geojson_output(conn)
        }
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        
        all_passed = True
        for test_name, passed in results.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{status}: {test_name}")
            if not passed:
                all_passed = False
        
        print("\n" + "="*60)
        if all_passed:
            print("✓ ALL TESTS PASSED")
            print("="*60)
            sys.exit(0)
        else:
            print("✗ SOME TESTS FAILED")
            print("="*60)
            sys.exit(1)
            
    finally:
        conn.close()


if __name__ == "__main__":
    main()
