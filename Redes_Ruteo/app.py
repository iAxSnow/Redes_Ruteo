#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask server for the routing web interface.
Provides the main interface and API endpoints for threat data.
"""

import os
import json
import time
import random
from flask import Flask, render_template, jsonify, request
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Database configuration
PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")


def get_db_connection():
    """Create and return a database connection."""
    conn = psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD
    )
    # Ensure fail_prob column exists
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = 'rr' AND table_name = 'ways' AND column_name = 'fail_prob'
        """)
        if cur.fetchone() is None:
            app.logger.info("Column 'fail_prob' not found in 'rr.ways'. Adding it now.")
            cur.execute("ALTER TABLE rr.ways ADD COLUMN fail_prob NUMERIC DEFAULT 0")
            conn.commit()
            app.logger.info("Column 'fail_prob' added successfully.")
            
        # Ensure vertices geometries are populated
        cur.execute("""
            SELECT COUNT(*) FROM rr.ways_vertices_pgr WHERE the_geom IS NULL
        """)
        null_geom_count = cur.fetchone()[0]
        if null_geom_count > 0:
            app.logger.info(f"Found {null_geom_count} vertices with NULL geometry. Populating now.")
            cur.execute("""
                UPDATE rr.ways_vertices_pgr 
                SET the_geom = sub.start_geom
                FROM (
                    SELECT DISTINCT ON (v.id) v.id, ST_StartPoint(w.geom) as start_geom
                    FROM rr.ways_vertices_pgr v
                    JOIN rr.ways w ON v.id = w.source
                    WHERE v.the_geom IS NULL
                    UNION
                    SELECT DISTINCT ON (v.id) v.id, ST_EndPoint(w.geom) as start_geom
                    FROM rr.ways_vertices_pgr v
                    JOIN rr.ways w ON v.id = w.target
                    WHERE v.the_geom IS NULL
                ) sub
                WHERE rr.ways_vertices_pgr.id = sub.id
            """)
            conn.commit()
            app.logger.info("Vertices geometries populated successfully.")
            
    return conn


@app.route('/')
def index():
    """Render the main interface."""
    return render_template('index.html')


@app.route('/api/threats')
def api_threats():
    """
    API endpoint to retrieve all threats from the database.
    Returns GeoJSON FeatureCollection with threats from multiple sources.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        features = []
        
        # Query Waze threats
        cur.execute("""
            SELECT 
                ext_id,
                kind,
                subtype,
                severity,
                props,
                ST_AsGeoJSON(geom) as geometry
            FROM rr.amenazas_waze
        """)
        
        for row in cur.fetchall():
            feature = {
                "type": "Feature",
                "properties": {
                    "ext_id": row['ext_id'],
                    "kind": row['kind'],
                    "subtype": row['subtype'],
                    "severity": row['severity'],
                    "source": "waze"
                },
                "geometry": json.loads(row['geometry'])
            }
            # Merge additional properties from props JSONB field
            if row['props']:
                feature['properties'].update(row['props'])
            
            features.append(feature)
        
        # Query Traffic Calming threats
        cur.execute("""
            SELECT 
                ext_id,
                kind,
                subtype,
                severity,
                props,
                ST_AsGeoJSON(geom) as geometry
            FROM rr.amenazas_calming
        """)
        
        for row in cur.fetchall():
            feature = {
                "type": "Feature",
                "properties": {
                    "ext_id": row['ext_id'],
                    "kind": row['kind'],
                    "subtype": row['subtype'],
                    "severity": row['severity'],
                    "source": "traffic_calming"
                },
                "geometry": json.loads(row['geometry'])
            }
            if row['props']:
                feature['properties'].update(row['props'])
            
            features.append(feature)
        
        # Query Weather threats
        cur.execute("""
            SELECT 
                ext_id,
                kind,
                subtype,
                severity,
                props,
                ST_AsGeoJSON(geom) as geometry
            FROM rr.amenazas_clima
        """)
        
        for row in cur.fetchall():
            feature = {
                "type": "Feature",
                "properties": {
                    "ext_id": row['ext_id'],
                    "kind": row['kind'],
                    "subtype": row['subtype'],
                    "severity": row['severity'],
                    "source": "weather"
                },
                "geometry": json.loads(row['geometry'])
            }
            if row['props']:
                feature['properties'].update(row['props'])
            
            features.append(feature)
        
        cur.close()
        conn.close()
        
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        return jsonify(geojson)
    
    except Exception as e:
        # Log the error for debugging but don't expose details to clients
        app.logger.error(f"Error loading threats: {str(e)}")
        return jsonify({
            "type": "FeatureCollection",
            "features": [],
            "error": "Failed to load threat data"
        }), 500


def build_route_geojson(cur, route_segments_query, params):
    """
    Helper function to build GeoJSON from a route query.
    This version is more efficient as it builds the geometry in a single SQL query.
    """
    sql_query = f"""
        WITH route AS ({route_segments_query})
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
    """
    cur.execute(sql_query, params)
    result = cur.fetchone()
    if result and result['geojson']:
        return result['geojson']
    return None


@app.route('/api/calculate_route', methods=['POST'])
def api_calculate_route():
    """
    API endpoint to calculate multiple optimal routes using different algorithms.
    Expects JSON body: {"start": {"lat": y1, "lng": x1}, "end": {"lat": y2, "lng": x2}, "algorithm": "all"}
    Returns: Multiple routes with their computation times
    """
    try:
        # Get request data
        data = request.get_json()
        if not data or 'start' not in data or 'end' not in data:
            return jsonify({
                "error": "Invalid request. Expected: {start: {lat, lng}, end: {lat, lng}}"
            }), 400
        
        start = data['start']
        end = data['end']
        algorithm = data.get('algorithm', 'dijkstra_dist')
        simulate_failures = data.get('simulate_failures', False)
        
        if 'lat' not in start or 'lng' not in start or 'lat' not in end or 'lng' not in end:
            return jsonify({
                "error": "Missing lat or lng in start or end coordinates"
            }), 400
        
        # Validate coordinates are not null
        if start['lat'] is None or start['lng'] is None or end['lat'] is None or end['lng'] is None:
            return jsonify({
                "error": "Start or end coordinates cannot be null"
            }), 400
        
        start_lat = float(start['lat'])
        start_lng = float(start['lng'])
        end_lat = float(end['lat'])
        end_lng = float(end['lng'])
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Find nearest node to start point
        cur.execute("""
            SELECT id, ST_X(the_geom) as x, ST_Y(the_geom) as y
            FROM rr.ways_vertices_pgr
            ORDER BY the_geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            LIMIT 1
        """, (start_lng, start_lat))
        
        start_node_row = cur.fetchone()
        if not start_node_row:
            cur.close()
            conn.close()
            return jsonify({
                "error": "Could not find start node in network",
                "details": "No hay nodos de la red cerca del punto de inicio"
            }), 404
        
        source_node = start_node_row['id']
        
        # Find nearest node to end point
        cur.execute("""
            SELECT id, ST_X(the_geom) as x, ST_Y(the_geom) as y
            FROM rr.ways_vertices_pgr
            ORDER BY the_geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            LIMIT 1
        """, (end_lng, end_lat))
        
        end_node_row = cur.fetchone()
        if not end_node_row:
            cur.close()
            conn.close()
            return jsonify({
                "error": "Could not find end node in network",
                "details": "No hay nodos de la red cerca del punto final"
            }), 404
        
        target_node = end_node_row['id']
        target_x = end_node_row['x']
        target_y = end_node_row['y']
        
        results = {}
        
        # --- Base query for routing ---
        # This query will be modified by each algorithm
        if simulate_failures:
            base_routing_query = """
                SELECT 
                    w.id, 
                    w.source, 
                    w.target, 
                    w.length_m as cost,
                    CASE 
                        WHEN w.oneway = true THEN -1
                        ELSE w.length_m
                    END as reverse_cost,
                    COALESCE(t.max_prob, 0) as fail_prob
                FROM rr.ways w
                LEFT JOIN (
                    WITH all_threats AS (
                        -- Waze threats
                        SELECT 
                            w.id AS way_id,
                            'waze' as source, subtype, severity
                        FROM rr.ways w
                        JOIN rr.amenazas_waze t ON ST_DWithin(w.geom, t.geom, 0.001)  -- ~100m
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
                        JOIN rr.amenazas_calming t ON ST_DWithin(w.geom, t.geom, 0.00015)  -- ~15m
                    )
                    SELECT
                        way_id,
                        MAX(
                            CASE
                                WHEN source = 'waze' AND subtype = 'CLOSURE' THEN 0.7
                                WHEN source = 'waze' AND subtype = 'TRAFFIC_JAM' THEN 0.2
                                WHEN source = 'weather' AND subtype = 'HEAVY_RAIN' THEN 0.15 + (severity - 1) * 0.1
                                WHEN source = 'weather' AND subtype = 'STRONG_WIND' THEN 0.12 + (severity - 1) * 0.1
                                WHEN source = 'weather' AND subtype = 'LOW_VISIBILITY' THEN 0.25 + (severity - 1) * 0.1
                                WHEN source = 'traffic_calming' THEN 0.02
                                ELSE 0.05
                            END
                        ) AS max_prob
                    FROM all_threats
                    GROUP BY way_id
                ) t ON w.id = t.way_id
                WHERE w.length_m > 0
            """
            app.logger.info("Using failure-simulated graph for routing (cost-weighted).")
        else:
            base_routing_query = """
                SELECT 
                    w.id, 
                    w.source, 
                    w.target, 
                    w.length_m as cost,
                    CASE 
                        WHEN w.oneway = true THEN -1
                        ELSE w.length_m
                    END as reverse_cost,
                    COALESCE(w.fail_prob, 0) as fail_prob
                FROM rr.ways w
                WHERE w.length_m > 0
            """

        # --- Algorithm Implementations ---

        # Route 1: Dijkstra with distance only
        if algorithm == 'all' or algorithm == 'dijkstra_dist':
            try:
                start_time = time.time()
                sql_for_pgr = f"SELECT id, source, target, cost, reverse_cost FROM ({base_routing_query}) q"
                route_query = f"SELECT * FROM pgr_dijkstra('{sql_for_pgr.replace('%', '%%')}', {source_node}, {target_node}, directed := true)"
                
                geojson = build_route_geojson(cur, route_query, ())
                compute_time_ms = (time.time() - start_time) * 1000
                
                if geojson:
                    results['dijkstra_dist'] = {
                        "route_geojson": geojson,
                        "compute_time_ms": round(compute_time_ms, 2),
                        "algorithm": "Dijkstra (Distancia)"
                    }
            except Exception as e:
                app.logger.error(f"Error calculating dijkstra_dist route: {str(e)}")
                import traceback
                app.logger.error(traceback.format_exc())
        
        # Route 2: Dijkstra with probability-weighted cost
        if algorithm == 'all' or algorithm == 'dijkstra_prob':
            try:
                start_time = time.time()
                sql_for_pgr = f"""
                    SELECT id, source, target, 
                           cost * (1 + COALESCE(fail_prob, 0) * 10) AS cost,
                           CASE 
                               WHEN reverse_cost = -1 THEN -1
                               ELSE reverse_cost * (1 + COALESCE(fail_prob, 0) * 10)
                           END AS reverse_cost
                    FROM ({base_routing_query}) q
                """
                route_query = f"SELECT * FROM pgr_dijkstra('{sql_for_pgr.replace('%', '%%')}', {source_node}, {target_node}, directed := true)"

                geojson = build_route_geojson(cur, route_query, ())
                compute_time_ms = (time.time() - start_time) * 1000
                
                if geojson:
                    results['dijkstra_prob'] = {
                        "route_geojson": geojson,
                        "compute_time_ms": round(compute_time_ms, 2),
                        "algorithm": "Dijkstra (Probabilidad)"
                    }
            except Exception as e:
                app.logger.error(f"Error calculating dijkstra_prob route: {str(e)}")
                import traceback
                app.logger.error(traceback.format_exc())
        
        # Route 3: A* with probability-weighted cost
        if algorithm == 'all' or algorithm == 'astar_prob':
            try:
                start_time = time.time()
                sql_for_pgr = f"""
                    SELECT q.id, q.source, q.target, 
                           q.cost * (1 + COALESCE(q.fail_prob, 0) * 10) AS cost,
                           CASE 
                               WHEN q.reverse_cost = -1 THEN -1
                               ELSE q.reverse_cost * (1 + COALESCE(q.fail_prob, 0) * 10)
                           END AS reverse_cost,
                           ST_X(sv.the_geom) as x1, ST_Y(sv.the_geom) as y1, 
                           ST_X(tv.the_geom) as x2, ST_Y(tv.the_geom) as y2
                    FROM ({base_routing_query}) q
                    JOIN rr.ways_vertices_pgr sv ON q.source = sv.id
                    JOIN rr.ways_vertices_pgr tv ON q.target = tv.id
                """
                route_query = f"SELECT * FROM pgr_astar('{sql_for_pgr.replace('%', '%%')}', {source_node}, {target_node}, directed := true)"

                geojson = build_route_geojson(cur, route_query, ())
                compute_time_ms = (time.time() - start_time) * 1000
                
                if geojson:
                    results['astar_prob'] = {
                        "route_geojson": geojson,
                        "compute_time_ms": round(compute_time_ms, 2),
                        "algorithm": "A* (Probabilidad)"
                    }
            except Exception as e:
                app.logger.error(f"Error calculating astar_prob route: {str(e)}")
                import traceback
                app.logger.error(traceback.format_exc())
        
        # Route 4: Filtered Dijkstra (only safe edges with fail_prob < 0.5)
        if algorithm == 'all' or algorithm == 'filtered_dijkstra':
            try:
                start_time = time.time()
                sql_for_pgr = f"""
                    SELECT id, source, target, cost, reverse_cost
                    FROM ({base_routing_query}) q
                    WHERE COALESCE(fail_prob, 0) < 0.5
                """
                route_query = f"SELECT * FROM pgr_dijkstra('{sql_for_pgr.replace('%', '%%')}', {source_node}, {target_node}, directed := true)"

                geojson = build_route_geojson(cur, route_query, ())
                compute_time_ms = (time.time() - start_time) * 1000
                
                if geojson:
                    results['filtered_dijkstra'] = {
                        "route_geojson": geojson,
                        "compute_time_ms": round(compute_time_ms, 2),
                        "algorithm": "Dijkstra Filtrado (Solo Seguros)"
                    }
                else:
                    app.logger.warning(f"Filtered Dijkstra found no route (may be too restrictive)")
            except Exception as e:
                app.logger.error(f"Error calculating filtered_dijkstra route: {str(e)}")
                import traceback
                app.logger.error(traceback.format_exc())
        
        cur.close()
        conn.close()
        
        if not results:
            return jsonify({
                "error": "No se pudo calcular ninguna ruta entre los puntos especificados",
                "details": "Puede que los puntos no estén conectados en la red o no haya rutas disponibles"
            }), 404
        
        return jsonify(results)
    
    except psycopg2.Error as db_err:
        app.logger.error(f"Database error calculating route: {str(db_err)}")
        return jsonify({
            "error": "Error de base de datos al calcular ruta",
            "details": "Error al conectar con la base de datos. Revisa los logs del servidor para más información."
        }), 500
    except Exception as e:
        app.logger.error(f"Error calculating route: {str(e)}")
        return jsonify({
            "error": "No se pudo calcular la ruta",
            "details": "Error inesperado. Revisa los logs del servidor para más información."
        }), 500


@app.route('/api/simulate_failures', methods=['POST'])
def api_simulate_failures():
    """
    DEPRECATED: This endpoint is no longer used for routing calculation.
    Failure simulation is now integrated into the /api/calculate_route endpoint.
    This can be kept for diagnostic purposes or removed.
    """
    return jsonify({
        "message": "This endpoint is deprecated. Use 'simulate_failures: true' in /api/calculate_route.",
        "failed_edges": [],
        "failed_nodes": [],
        "total_failed": 0
    }), 410


if __name__ == '__main__':
    # Debug mode should be disabled in production
    # Set via environment variable: export FLASK_DEBUG=1 for development
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
