#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for routing algorithms and failure simulation.

This script provides functions to:
- Test a specific route between two coordinates.
- Simulate the impact of threats on the graph.
- Compare routing results with and without threat simulation.
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# --- Database Configuration ---
PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")

# --- Simulation Parameters ---
# Coordinates for a sample route (e.g., from Palacio de La Moneda to Costanera Center)
DEFAULT_START_COORDS = (-33.4430, -70.6530)
DEFAULT_END_COORDS = (-33.45, -70.66)

# Probability threshold to consider an edge "failed"
FAILURE_PROBABILITY_THRESHOLD = 0.75


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
        print(f"❌ Critical Error: Could not connect to the database.", file=sys.stderr)
        print(f"   Details: {e}", file=sys.stderr)
        print(f"   Please ensure the database is running and .env settings are correct.", file=sys.stderr)
        sys.exit(1)


def find_nearest_node(conn, lat, lon):
    """Finds the nearest network node (vertex) to a given lat/lon coordinate."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id
            FROM rr.ways_vertices_pgr
            ORDER BY the_geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            LIMIT 1;
        """, (lon, lat))
        result = cur.fetchone()
        return result['id'] if result else None


def run_routing_algorithm(conn, start_node, end_node, use_fail_prob=False):
    """
    Executes a routing algorithm (Dijkstra with probability) and returns the result.
    
    Args:
        conn: Active database connection.
        start_node (int): The ID of the starting node.
        end_node (int): The ID of the ending node.
        use_fail_prob (bool): If True, uses 'fail_prob' to calculate cost. 
                              Otherwise, uses geometric length.
    
    Returns:
        A dictionary with route details (geojson, length, time) or None if no route is found.
    """
    cost_expression = "(1.0 - COALESCE(fail_prob, 0.0)) * cost" if use_fail_prob else "cost"
    
    query = f"""
        WITH route AS (
            SELECT * FROM pgr_dijkstra(
                'SELECT id, source, target, {cost_expression} AS cost, reverse_cost FROM rr.ways_routing',
                %s, %s,
                directed := true
            )
        ),
        route_geom AS (
            SELECT r.seq, w.geom, w.length_m AS length_m
            FROM route r
            JOIN rr.ways w ON r.edge = w.id
            ORDER BY r.seq
        )
        SELECT
            json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(ST_Collect(geom))::json,
                'properties', json_build_object(
                    'total_length_m', SUM(length_m)
                )
            ) AS geojson,
            SUM(length_m) AS total_length_m
        FROM route_geom;
    """
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (start_node, end_node))
        result = cur.fetchone()
        
        if result and result['geojson']:
            return {
                "geojson": result['geojson'],
                "total_length_m": result['total_length_m']
            }
        return None


def simulate_failures_and_update_graph(conn):
    """

    Applies threat probabilities to the 'ways' table to simulate failures.
    This function should be run within a transaction that can be rolled back.
    """
    print("\n--- Simulating Failures ---")
    print(f"Applying failure probabilities to the graph...")

    with conn.cursor() as cur:
        # This executes the logic from 'probability_model.py' to update fail_prob
        # We assume the 'probability_model.py' script is the source of truth for this logic
        probability_script_path = os.path.join(os.path.dirname(__file__), 'probability_model.py')
        if not os.path.exists(probability_script_path):
            print(f"Error: 'probability_model.py' not found at {probability_script_path}", file=sys.stderr)
            return 0
        
        # We are not actually running the script, but replicating its core logic
        # This avoids a subprocess call and gives us more control
        cur.execute("""
            UPDATE rr.ways w SET fail_prob = COALESCE(t.max_prob, 0)
            FROM (
                SELECT
                    way_id,
                    MAX(
                        CASE
                            WHEN source = 'waze' AND subtype = 'CLOSURE' THEN 0.95
                            WHEN source = 'waze' AND subtype = 'TRAFFIC_JAM' THEN 0.4
                            WHEN source = 'weather' AND subtype = 'HEAVY_RAIN' THEN 0.3 + (severity - 1) * 0.2
                            WHEN source = 'weather' AND subtype = 'STRONG_WIND' THEN 0.25 + (severity - 1) * 0.2
                            WHEN source = 'weather' AND subtype = 'LOW_VISIBILITY' THEN 0.5 + (severity - 1) * 0.2
                            WHEN source = 'traffic_calming' THEN 0.05
                            ELSE 0.1
                        END
                    ) AS max_prob
                FROM rr.way_threat_intersections
                GROUP BY way_id
            ) t
            WHERE w.id = t.way_id;
        """)
        
        updated_rows = cur.rowcount
        print(f"Applied failure probabilities to {updated_rows} ways.")

        # Count how many ways are now considered "failed"
        cur.execute("SELECT COUNT(*) FROM rr.ways WHERE fail_prob >= %s;", (FAILURE_PROBABILITY_THRESHOLD,))
        failed_count = cur.fetchone()[0]
        print(f"Number of ways considered 'failed' (prob >= {FAILURE_PROBABILITY_THRESHOLD}): {failed_count}")
        
        return updated_rows


def run_test(start_coords, end_coords):
    """
    Runs a full routing test, comparing a standard route with a route calculated
    after simulating failures.
    """
    conn = get_db_connection()
    
    try:
        # 1. Find nearest start and end nodes
        start_node = find_nearest_node(conn, start_coords[0], start_coords[1])
        end_node = find_nearest_node(conn, end_coords[0], end_coords[1])

        if not start_node or not end_node:
            print("Error: Could not find nearest nodes for the given coordinates.", file=sys.stderr)
            return

        print(f"Testing route from node {start_node} to {end_node}")

        # 2. Calculate baseline route (no failures)
        print("\n--- Baseline Route (by distance) ---")
        baseline_route = run_routing_algorithm(conn, start_node, end_node, use_fail_prob=False)
        if baseline_route:
            print(f"  Route found. Length: {baseline_route['total_length_m'] / 1000:.2f} km")
            with open("route_baseline.geojson", "w") as f:
                json.dump(baseline_route['geojson'], f, indent=2)
            print("  Saved to route_baseline.geojson")
        else:
            print("  No baseline route found.")

        # 3. Simulate failures and calculate resilient route
        conn.autocommit = False # Start a transaction
        
        simulate_failures_and_update_graph(conn)
        
        print("\n--- Resilient Route (with failure simulation) ---")
        resilient_route = run_routing_algorithm(conn, start_node, end_node, use_fail_prob=True)
        
        if resilient_route:
            print(f"  Route found. Length: {resilient_route['total_length_m'] / 1000:.2f} km")
            with open("route_resilient.geojson", "w") as f:
                json.dump(resilient_route['geojson'], f, indent=2)
            print("  Saved to route_resilient.geojson")
        else:
            print("  No resilient route found after simulation.")

        # 4. Compare results
        print("\n--- Comparison ---")
        if baseline_route and resilient_route:
            length_diff = resilient_route['total_length_m'] - baseline_route['total_length_m']
            print(f"The resilient route is {abs(length_diff / 1000):.2f} km {'longer' if length_diff > 0 else 'shorter'} than the baseline route.")
            if baseline_route['geojson'] == resilient_route['geojson']:
                print("The route geometry is identical.")
            else:
                print("The route geometry is different.")
        else:
            print("Could not perform comparison as one or both routes were not found.")

    finally:
        # Rollback changes to the database to leave it in a clean state
        print("\nRolling back simulation changes from the database...")
        conn.rollback()
        conn.close()
        print("Done.")


if __name__ == "__main__":
    print("========================================")
    print("  Routing Algorithm and Failure Test  ")
    print("========================================")
    
    # You can customize coordinates here if needed
    start_lat, start_lon = DEFAULT_START_COORDS
    end_lat, end_lon = DEFAULT_END_COORDS
    
    print(f"Using default route from {start_lat},{start_lon} to {end_lat},{end_lon}")
    
    run_test(start_coords=(start_lat, start_lon), end_coords=(end_lat, end_lon))
