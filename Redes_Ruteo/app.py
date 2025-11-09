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
    return psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD
    )


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


def build_route_geojson(cur, route_segments):
    """Helper function to build GeoJSON from route segments."""
    coordinates = []
    total_length_m = 0
    
    for segment in route_segments:
        if segment['geom']:
            # Parse the geometry
            geom_wkt = segment['geom']
            cur.execute("SELECT ST_AsGeoJSON(%s)", (geom_wkt,))
            geom_json = json.loads(cur.fetchone()[0])
            
            if geom_json['type'] == 'LineString':
                coordinates.extend(geom_json['coordinates'])
            
            if segment['length_m']:
                total_length_m += float(segment['length_m'])
    
    return {
        "type": "Feature",
        "properties": {
            "total_length_m": round(total_length_m, 2),
            "segments": len(route_segments)
        },
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
        }
    }


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
        algorithm = data.get('algorithm', 'dijkstra_dist')  # Default to distance-based Dijkstra
        
        if 'lat' not in start or 'lng' not in start or 'lat' not in end or 'lng' not in end:
            return jsonify({
                "error": "Missing lat or lng in start or end coordinates"
            }), 400
        
        start_lat = float(start['lat'])
        start_lng = float(start['lng'])
        end_lat = float(end['lat'])
        end_lng = float(end['lng'])
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Find nearest node to start point
        cur.execute("""
            SELECT id, ST_X(geom) as x, ST_Y(geom) as y
            FROM rr.ways_vertices_pgr
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            LIMIT 1
        """, (start_lng, start_lat))
        
        start_node_row = cur.fetchone()
        if not start_node_row:
            return jsonify({"error": "Could not find start node in network"}), 404
        
        source_node = start_node_row['id']
        
        # Find nearest node to end point
        cur.execute("""
            SELECT id, ST_X(geom) as x, ST_Y(geom) as y
            FROM rr.ways_vertices_pgr
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            LIMIT 1
        """, (end_lng, end_lat))
        
        end_node_row = cur.fetchone()
        if not end_node_row:
            return jsonify({"error": "Could not find end node in network"}), 404
        
        target_node = end_node_row['id']
        target_x = end_node_row['x']
        target_y = end_node_row['y']
        
        results = {}
        
        # Route 1: Dijkstra with distance only
        if algorithm == 'all' or algorithm == 'dijkstra_dist':
            start_time = time.time()
            cur.execute("""
                SELECT 
                    r.seq, r.node, r.edge, r.cost, r.agg_cost,
                    w.geom, w.highway, w.length_m
                FROM pgr_dijkstra(
                    'SELECT id, source, target, length_m as cost FROM rr.ways',
                    %s, %s, directed := false
                ) r
                LEFT JOIN rr.ways w ON r.edge = w.id
                ORDER BY r.seq
            """, (source_node, target_node))
            route_segments = cur.fetchall()
            compute_time_ms = (time.time() - start_time) * 1000
            
            if route_segments:
                results['dijkstra_dist'] = {
                    "route_geojson": build_route_geojson(cur, route_segments),
                    "compute_time_ms": round(compute_time_ms, 2),
                    "algorithm": "Dijkstra (Distancia)"
                }
        
        # Route 2: Dijkstra with probability-weighted cost
        if algorithm == 'all' or algorithm == 'dijkstra_prob':
            start_time = time.time()
            cur.execute("""
                SELECT 
                    r.seq, r.node, r.edge, r.cost, r.agg_cost,
                    w.geom, w.highway, w.length_m
                FROM pgr_dijkstra(
                    'SELECT id, source, target, 
                     length_m * (1 + (COALESCE(fail_prob, 0) * 100)) as cost 
                     FROM rr.ways',
                    %s, %s, directed := false
                ) r
                LEFT JOIN rr.ways w ON r.edge = w.id
                ORDER BY r.seq
            """, (source_node, target_node))
            route_segments = cur.fetchall()
            compute_time_ms = (time.time() - start_time) * 1000
            
            if route_segments:
                results['dijkstra_prob'] = {
                    "route_geojson": build_route_geojson(cur, route_segments),
                    "compute_time_ms": round(compute_time_ms, 2),
                    "algorithm": "Dijkstra (Probabilidad)"
                }
        
        # Route 3: A* with probability-weighted cost
        if algorithm == 'all' or algorithm == 'astar_prob':
            start_time = time.time()
            cur.execute("""
                SELECT 
                    r.seq, r.node, r.edge, r.cost, r.agg_cost,
                    w.geom, w.highway, w.length_m
                FROM pgr_astar(
                    'SELECT id, source, target, 
                     length_m * (1 + (COALESCE(fail_prob, 0) * 100)) as cost,
                     ST_X(ST_StartPoint(geom)) as x1,
                     ST_Y(ST_StartPoint(geom)) as y1,
                     ST_X(ST_EndPoint(geom)) as x2,
                     ST_Y(ST_EndPoint(geom)) as y2
                     FROM rr.ways',
                    %s, %s, directed := false
                ) r
                LEFT JOIN rr.ways w ON r.edge = w.id
                ORDER BY r.seq
            """, (source_node, target_node))
            route_segments = cur.fetchall()
            compute_time_ms = (time.time() - start_time) * 1000
            
            if route_segments:
                results['astar_prob'] = {
                    "route_geojson": build_route_geojson(cur, route_segments),
                    "compute_time_ms": round(compute_time_ms, 2),
                    "algorithm": "A* (Probabilidad)"
                }
        
        # Route 4: Filtered Dijkstra (only safe edges with fail_prob < 0.5)
        if algorithm == 'all' or algorithm == 'filtered_dijkstra':
            start_time = time.time()
            cur.execute("""
                SELECT 
                    r.seq, r.node, r.edge, r.cost, r.agg_cost,
                    w.geom, w.highway, w.length_m
                FROM pgr_dijkstra(
                    'SELECT id, source, target, length_m as cost 
                     FROM rr.ways 
                     WHERE COALESCE(fail_prob, 0) < 0.5',
                    %s, %s, directed := false
                ) r
                LEFT JOIN rr.ways w ON r.edge = w.id
                ORDER BY r.seq
            """, (source_node, target_node))
            route_segments = cur.fetchall()
            compute_time_ms = (time.time() - start_time) * 1000
            
            if route_segments:
                results['filtered_dijkstra'] = {
                    "route_geojson": build_route_geojson(cur, route_segments),
                    "compute_time_ms": round(compute_time_ms, 2),
                    "algorithm": "Dijkstra Filtrado (Solo Seguros)"
                }
        
        cur.close()
        conn.close()
        
        if not results:
            return jsonify({
                "error": "No routes found between the specified points"
            }), 404
        
        return jsonify(results)
    
    except Exception as e:
        app.logger.error(f"Error calculating route: {str(e)}")
        return jsonify({
            "error": "Failed to calculate route"
        }), 500


@app.route('/api/simulate_failures', methods=['POST'])
def api_simulate_failures():
    """
    API endpoint to simulate failures in network elements based on their probability.
    Returns IDs of elements that have "failed" in this simulation.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        failed_edges = []
        failed_nodes = []
        
        # Get all edges with fail_prob > 0
        cur.execute("""
            SELECT id, fail_prob
            FROM rr.ways
            WHERE COALESCE(fail_prob, 0) > 0
        """)
        
        edges = cur.fetchall()
        for edge in edges:
            random_value = random.random()
            if random_value < edge['fail_prob']:
                failed_edges.append(edge['id'])
        
        # Get all nodes with fail_prob > 0 (if table exists)
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'rr' 
                AND table_name = 'ways_vertices_pgr'
            )
        """)
        
        if cur.fetchone()[0]:
            cur.execute("""
                SELECT id, fail_prob
                FROM rr.ways_vertices_pgr
                WHERE COALESCE(fail_prob, 0) > 0
            """)
            
            nodes = cur.fetchall()
            for node in nodes:
                random_value = random.random()
                if random_value < node['fail_prob']:
                    failed_nodes.append(node['id'])
        
        cur.close()
        conn.close()
        
        return jsonify({
            "failed_edges": failed_edges,
            "failed_nodes": failed_nodes,
            "total_failed": len(failed_edges) + len(failed_nodes)
        })
    
    except Exception as e:
        app.logger.error(f"Error simulating failures: {str(e)}")
        return jsonify({
            "error": "Failed to simulate failures"
        }), 500


if __name__ == '__main__':
    # Debug mode should be disabled in production
    # Set via environment variable: export FLASK_DEBUG=1 for development
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
