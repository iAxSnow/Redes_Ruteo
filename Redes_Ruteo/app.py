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
import math
from flask import Flask, render_template, jsonify, request, send_from_directory
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def simulate_random_failures_on_route(cur, route_edges, route_geom):
    """
    Simulate random failures on a calculated route.
    Returns simulated threats that should be visible on the map.
    """
    if not route_edges:
        return []

    # Determine how many failures to simulate (at least 1, up to 30% of route edges)
    num_failures = max(1, min(len(route_edges) // 3, random.randint(1, max(1, len(route_edges) // 2))))

    # Randomly select edges from the route
    selected_edges = random.sample(route_edges, min(num_failures, len(route_edges)))

    simulated_threats = []

    # Threat types and their properties
    threat_types = [
        # Waze incidents
        {
            'type': 'waze',
            'subtypes': ['TRAFFIC_JAM', 'CLOSURE'],
            'severities': [1, 2, 3, 4, 5],
            'probabilities': [0.2, 0.7]  # Corresponding to subtypes
        },
        # Weather threats
        {
            'type': 'weather',
            'subtypes': ['HEAVY_RAIN', 'STRONG_WIND', 'LOW_VISIBILITY', 'SNOW'],
            'severities': [1, 2, 3, 4, 5],
            'probabilities': [0.05, 0.04, 0.08, 0.1]  # Base probabilities
        },
        # Non-functional hydrants (only these are threats)
        {
            'type': 'hydrant',
            'subtypes': ['NON_FUNCTIONAL'],
            'severities': [3, 4, 5],  # Higher severity for non-functional hydrants
            'probabilities': [0.15]  # Probability of being non-functional
        }
    ]

    for edge_id in selected_edges:
        # Get edge geometry and midpoint
        cur.execute("""
            SELECT ST_AsGeoJSON(ST_LineInterpolatePoint(geom, 0.5)) as midpoint,
                   ST_AsGeoJSON(geom) as geom
            FROM rr.ways
            WHERE id = %s
        """, (edge_id,))

        edge_result = cur.fetchone()
        if not edge_result:
            continue

        midpoint_geojson = json.loads(edge_result[0])
        edge_geom = json.loads(edge_result[1])

        # Randomly select threat type
        threat_type = random.choice(threat_types)

        # Select subtype and corresponding probability
        subtype_idx = random.randrange(len(threat_type['subtypes']))
        subtype = threat_type['subtypes'][subtype_idx]
        base_prob = threat_type['probabilities'][subtype_idx]

        # Random severity
        severity = random.choice(threat_type['severities'])

        # Calculate final probability (base_prob + severity adjustment)
        final_probability = min(0.9, base_prob + (severity * 0.1))

        # Create threat feature
        threat_feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': midpoint_geojson['coordinates']
            },
            'properties': {
                'id': f"simulated_{threat_type['type']}_{edge_id}_{random.randint(1000, 9999)}",
                'source': threat_type['type'],
                'subtype': subtype,
                'severity': severity,
                'probability': final_probability,
                'edge_id': edge_id,
                'simulated': True,
                'timestamp': datetime.now().isoformat()
            }
        }

        # Add type-specific properties
        if threat_type['type'] == 'waze':
            threat_feature['properties']['description'] = f"Incidente simulado: {subtype.replace('_', ' ').title()}"
            threat_feature['properties']['street'] = f"Calle simulada {random.randint(1, 1000)}"
        elif threat_type['type'] == 'weather':
            threat_feature['properties']['description'] = f"Condición climática simulada: {subtype.replace('_', ' ').title()}"
            if subtype == 'HEAVY_RAIN':
                threat_feature['properties']['metrics'] = {'rain_mm_h': random.uniform(5, 20)}
            elif subtype == 'STRONG_WIND':
                threat_feature['properties']['metrics'] = {'wind_ms': random.uniform(10, 25)}
        elif threat_type['type'] == 'hydrant':
            threat_feature['properties']['description'] = "Hidrante no funcional simulado"
            threat_feature['properties']['status'] = "non_functional"
            threat_feature['properties']['ext_id'] = f"SIM_H_{random.randint(10000, 99999)}"

        simulated_threats.append(threat_feature)

    return simulated_threats

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
    """Serve the main interface."""
    return send_from_directory('site', 'index.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('site', path)


@app.route('/metadata/<path:filename>')
def metadata_files(filename):
    return send_from_directory('metadata', filename)


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


@app.route('/api/hydrants')
def api_hydrants():
    """
    API endpoint to retrieve all hydrants from the database.
    Returns GeoJSON FeatureCollection with hydrants from multiple sources.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        features = []
        
        # Query Hydrants
        cur.execute("""
            SELECT 
                ext_id,
                status,
                provider,
                props,
                ST_AsGeoJSON(geom) as geometry
            FROM rr.metadata_hydrants
            WHERE geom IS NOT NULL
        """)
        
        for row in cur.fetchall():
            feature = {
                "type": "Feature",
                "properties": {
                    "ext_id": row['ext_id'],
                    "status": row['status'],
                    "provider": row['provider']
                },
                "geometry": json.loads(row['geometry'])
            }
            # Merge additional properties from props JSONB field
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
        app.logger.error(f"Error loading hydrants: {str(e)}")
        return jsonify({
            "type": "FeatureCollection",
            "features": [],
            "error": "Failed to load hydrant data"
        }), 500


def build_route_geojson(cur, route_segments_query, params, start_lng=None, start_lat=None, end_lng=None, end_lat=None):
    """
    Helper function to build GeoJSON from a route query.
    This version uses the actual way geometries to create smooth routes along streets.
    Adds connection segments from start/end points to nearest nodes if coordinates provided.
    """
    # Build the SQL query with proper parameter handling
    start_lng_param = start_lng if start_lng is not None else 'NULL'
    start_lat_param = start_lat if start_lat is not None else 'NULL'
    end_lng_param = end_lng if end_lng is not None else 'NULL'
    end_lat_param = end_lat if end_lat is not None else 'NULL'

    sql_query = f"""
        WITH route AS ({route_segments_query}),
             route_geoms AS (
                SELECT r.seq, w.geom
                FROM route r
                JOIN rr.ways w ON r.edge = w.id
                WHERE r.edge > 0
                ORDER BY r.seq
             ),
             merged_line AS (
                SELECT ST_LineMerge(ST_Collect(geom ORDER BY seq)) as geom
                FROM route_geoms
             ),
             route_line AS (
                SELECT ml.geom,
                       (SELECT COALESCE(SUM(w.length_m), 0)
                        FROM route r JOIN rr.ways w ON r.edge = w.id WHERE r.edge > 0) as total_length,
                       (SELECT COALESCE(SUM(r.cost), 0) FROM route r WHERE r.edge > 0) as total_cost
                FROM merged_line ml
             ),
             full_route AS (
                SELECT rl.geom,
                rl.total_length,
                rl.total_cost
                FROM route_line rl
             )
        SELECT ST_AsGeoJSON(geom)::json as geometry,
               total_length, total_cost
        FROM full_route;
    """

    cur.execute(sql_query, params)
    result = cur.fetchone()

    if result and result['geometry']:
        geojson = {
            'type': 'Feature',
            'properties': {
                'total_length_m': float(result['total_length'] or 0),
                'total_cost': float(result['total_cost'] or 0)
            },
            'geometry': result['geometry']
        }
        coords = geojson.get('geometry', {}).get('coordinates', [])
        print(f"GeoJSON result: coordinates length = {len(coords)}")
        return geojson

    # Fallback: return empty route
    print("Using fallback empty geometry")
    return {
        'type': 'Feature',
        'properties': {'total_length_m': 0, 'total_cost': 0},
        'geometry': {'type': 'LineString', 'coordinates': []}
    }
def simulate_random_failures_on_route(route_geojson, cur):
    """
    Generate random visible threats along a calculated route with dynamic weights.
    Weights are calculated based on realistic factors: distance, threat type, size, density, and response time.
    Weather threats are generated as polygons, while others remain as points.
    Returns a list of simulated threat features that can be displayed on the map.
    """
    simulated_threats = []

    if not route_geojson or not route_geojson.get('geometry', {}).get('coordinates'):
        return simulated_threats

    coordinates = route_geojson['geometry']['coordinates']
    if len(coordinates) < 2:
        return simulated_threats

    # Calculate route characteristics
    route_length_m = route_geojson['properties'].get('total_length_m', 1000)
    route_density_factor = min(1.0, route_length_m / 5000)  # Routes longer than 5km have higher threat density

    # Generate 1-4 random threats along the route (based on route length)
    base_threats = max(1, min(4, int(route_length_m / 2000)))  # 1 threat per 2km
    num_threats = random.randint(base_threats, base_threats + 2)

    # Threat type configurations with realistic base parameters
    threat_configs = {
        'waze': {
            'TRAFFIC_JAM': {
                'base_severity': 2,
                'base_probability': 0.3,
                'size_range_m': (50, 200),
                'duration_factor': 0.7,  # Temporary
                'vehicle_impact': {'car': 0.8, 'truck': 0.9, 'fire_truck': 0.95}
            },
            'CLOSURE': {
                'base_severity': 4,
                'base_probability': 0.1,
                'size_range_m': (10, 50),
                'duration_factor': 0.9,  # Long-lasting
                'vehicle_impact': {'car': 0.6, 'truck': 0.8, 'fire_truck': 1.0}
            }
        },
        'weather': {
            'HEAVY_RAIN': {
                'base_severity': 3,
                'base_probability': 0.4,
                'size_range_m': (500, 2000),
                'duration_factor': 0.5,  # Weather-dependent
                'vehicle_impact': {'car': 0.7, 'truck': 0.8, 'fire_truck': 0.6}
            },
            'STRONG_WIND': {
                'base_severity': 3,
                'base_probability': 0.2,
                'size_range_m': (1000, 5000),
                'duration_factor': 0.6,
                'vehicle_impact': {'car': 0.5, 'truck': 0.9, 'fire_truck': 0.7}
            },
            'LOW_VISIBILITY': {
                'base_severity': 4,  # Increased from 2 - low visibility is very dangerous
                'base_probability': 0.4,  # Increased from 0.3
                'size_range_m': (300, 1500),
                'duration_factor': 0.5,  # Increased from 0.4 - can change but still dangerous
                'vehicle_impact': {'car': 0.9, 'truck': 0.8, 'fire_truck': 0.95}  # Higher impact
            }
        },
        'hydrant': {
            'NON_FUNCTIONAL': {
                'base_severity': 3,
                'base_probability': 0.15,
                'size_range_m': (5, 10),
                'duration_factor': 1.0,  # Permanent until fixed
                'vehicle_impact': {'car': 0.1, 'truck': 0.3, 'fire_truck': 1.0}
            }
        }
    }

    # Generate strategic obstacles that force route alternatives
    # Place 1-2 blocking obstacles on early segments to force algorithm consideration of alternatives
    num_blocking_obstacles = random.randint(1, 2)
    blocking_segments = []

    # Prefer early segments for blocking obstacles (first 30% of route)
    early_segment_count = max(1, int(len(coordinates) * 0.3))
    for _ in range(num_blocking_obstacles):
        if early_segment_count > 0:
            segment_idx = random.randint(0, early_segment_count - 1)
            if segment_idx not in blocking_segments:
                blocking_segments.append(segment_idx)

    for i in range(num_threats):
        # For blocking obstacles, use specific segments
        if i < len(blocking_segments):
            segment_idx = blocking_segments[i]
            is_blocking = True
        else:
            # For regular threats, pick any segment
            segment_idx = random.randint(0, len(coordinates) - 2)
            is_blocking = False

        start_coord = coordinates[segment_idx]
        end_coord = coordinates[segment_idx + 1]

        # Generate a random point along this segment
        t = random.random()  # 0 to 1
        threat_lng = start_coord[0] + t * (end_coord[0] - start_coord[0])
        threat_lat = start_coord[1] + t * (end_coord[1] - start_coord[1])

        # Choose threat type - blocking obstacles should be more severe
        if is_blocking:
            # Blocking obstacles: prefer high-impact threats
            threat_weights = {
                'waze': 0.2,  # CLOSURE is most blocking
                'weather': 0.3,  # Weather can block routes
                'hydrant': 0.5   # Hydrants are critical for fire trucks
            }
        else:
            # Regular threats: normal distribution
            threat_weights = {
                'waze': 0.4 * route_density_factor,
                'weather': 0.3,
                'hydrant': 0.3 * (1 - route_density_factor)
            }

        threat_source = random.choices(
            list(threat_weights.keys()),
            weights=list(threat_weights.values())
        )[0]

        # Choose subtype within the selected source
        if is_blocking:
            # For blocking obstacles, prefer more severe subtypes
            if threat_source == 'waze':
                subtype_weights = [0.1, 0.9]  # Prefer CLOSURE (more blocking)
                subtype = random.choices(['TRAFFIC_JAM', 'CLOSURE'], weights=subtype_weights)[0]
            elif threat_source == 'weather':
                subtype_weights = [0.3, 0.4, 0.3]  # Prefer STRONG_WIND (can block)
                subtype = random.choices(['HEAVY_RAIN', 'STRONG_WIND', 'LOW_VISIBILITY'], weights=subtype_weights)[0]
            else:  # hydrant
                subtype = 'NON_FUNCTIONAL'  # Only one type
        else:
            # Regular threat selection
            subtypes = list(threat_configs[threat_source].keys())
            subtype_weights = [threat_configs[threat_source][st]['base_probability'] for st in subtypes]
            subtype = random.choices(subtypes, weights=subtype_weights)[0]

        config = threat_configs[threat_source][subtype]

        # Calculate dynamic severity based on multiple factors
        base_severity = config['base_severity']
        if is_blocking:
            base_severity = min(5, base_severity * 1.5)  # Increase severity for blocking obstacles

        # Distance factor: closer threats have higher impact
        segment_length = ((end_coord[0] - start_coord[0])**2 + (end_coord[1] - start_coord[1])**2)**0.5 * 111000
        distance_from_segment = random.uniform(0, 100)  # Random distance from route (0-100m)
        distance_factor = max(0.3, 1.0 - (distance_from_segment / 100))  # 0.3 to 1.0

        # Time factor: current time affects threat likelihood
        import datetime
        current_hour = datetime.datetime.now().hour
        if threat_source == 'waze':
            # Traffic peaks during rush hours
            time_factor = 1.0 + 0.5 * (1 if 7 <= current_hour <= 9 or 17 <= current_hour <= 19 else 0)
        elif threat_source == 'weather':
            # Weather more severe during certain hours
            time_factor = 0.8 + 0.4 * random.random()
        else:
            time_factor = 1.0

        # Size factor: larger threats have higher severity
        size_m = random.uniform(*config['size_range_m'])
        size_factor = min(1.5, 1.0 + (size_m / 1000))  # Up to 1.5x for large areas

        # Duration factor: longer-lasting threats are more severe
        duration_factor = config['duration_factor']

        # Random variation (±20%)
        random_factor = random.uniform(0.8, 1.2)

        # Calculate final severity (1-5 scale)
        severity = min(5, max(1, int(base_severity * distance_factor * time_factor * size_factor * duration_factor * random_factor)))

        # Calculate dynamic probability (0-1 scale)
        base_probability = config['base_probability']
        probability = min(0.95, base_probability * distance_factor * time_factor * random_factor)

        # Vehicle-specific impact (assuming fire truck by default)
        vehicle_impact = config['vehicle_impact'].get('fire_truck', 1.0)

        # Adjust probability based on vehicle type
        probability *= vehicle_impact

        if threat_source == 'weather':
            # Create a more realistic weather pattern (not perfect circles)
            try:
                # Simplified: create an irregular polygon manually for better reliability
                num_points = 16  # More points for smoother shape
                angles = [i * (2 * 3.14159 / num_points) for i in range(num_points)]
                coords = []

                for angle in angles:
                    # Add randomness to radius for irregular shape
                    radius_variation = random.uniform(0.6, 1.4)  # More variation
                    actual_radius = size_m * radius_variation

                    # Convert to degrees (rough approximation for lat/lng)
                    radius_deg = actual_radius / 111000  # meters to degrees at equator

                    # Add some offset to center for more irregularity
                    center_offset_x = random.uniform(-radius_deg * 0.2, radius_deg * 0.2)
                    center_offset_y = random.uniform(-radius_deg * 0.2, radius_deg * 0.2)

                    dx = radius_deg * math.cos(angle) + center_offset_x
                    dy = radius_deg * math.sin(angle) + center_offset_y

                    coords.append([threat_lng + dx, threat_lat + dy])

                # Close the polygon
                coords.append(coords[0])
                geometry = {
                    "type": "Polygon",
                    "coordinates": [coords]
                }
            except Exception as e:
                app.logger.warning(f"Error creating weather polygon: {e}")
                # Simple circle as last resort
                geometry = {
                    "type": "Point",
                    "coordinates": [threat_lng, threat_lat]
                }
        else:
            # Point geometry for non-weather threats
            geometry = {
                "type": "Point",
                "coordinates": [threat_lng, threat_lat]
            }

        threat_feature = {
            "type": "Feature",
            "properties": {
                "source": threat_source,
                "subtype": subtype,
                "severity": severity,
                "description": f"{subtype.replace('_', ' ').title()} (Severity {severity})",
                "simulated": True,
                "probability": round(probability, 3),
                "distance_from_route_m": round(distance_from_segment, 1),
                "size_m": round(size_m, 1) if threat_source == 'weather' else None,
                "vehicle_impact": round(vehicle_impact, 2),
                "dynamic_weight": round(severity * probability * vehicle_impact, 3)
            },
            "geometry": geometry
        }

        simulated_threats.append(threat_feature)

    return simulated_threats


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
        constraints = data.get('constraints', {})
        
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
        
        print(f"Received coordinates: start=({start_lat}, {start_lng}), end=({end_lat}, {end_lng})")
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Find nearest node to start point
        cur.execute("""
            SELECT v.id, ST_X(v.the_geom) as x, ST_Y(v.the_geom) as y
            FROM rr.ways_vertices_pgr v
            JOIN rr.components c ON v.id = c.node
            WHERE c.component = 1
            ORDER BY v.the_geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
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
        print(f"Start node found: {source_node}")
        
        # Find nearest node to end point
        cur.execute("""
            SELECT v.id, ST_X(v.the_geom) as x, ST_Y(v.the_geom) as y
            FROM rr.ways_vertices_pgr v
            JOIN rr.components c ON v.id = c.node
            WHERE c.component = 1
            ORDER BY v.the_geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
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
        print(f"End node found: {target_node}")
        
        results = {}
        simulated_threats = []

        # --- Always use normal routing (no threat data from DB) ---
        base_routing_query = """
            SELECT id, source, target, cost_combined as cost
            FROM rr.ways
            WHERE cost_combined > 0
        """

        # Generate simulated threats globally (not route-specific) first
        if simulate_failures:
            # Create a simple straight line route for threat generation
            simple_route = {
                'type': 'Feature',
                'properties': {'total_length_m': 5000},  # Assume 5km for threat density
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [[start_lng, start_lat], [end_lng, end_lat]]
                }
            }
            simulated_threats = simulate_random_failures_on_route(simple_route, cur)
        else:
            simulated_threats = []

        # --- Algorithm Implementations ---

        # Route 1: Dijkstra with distance only
        if algorithm == 'all' or algorithm == 'dijkstra_dist':
            try:
                start_time = time.time()
                # Always use simple distance-based routing
                penalty_clause = f"CASE WHEN w.id IN ({ids_str}) THEN w.length_m * 10 ELSE w.length_m END" if ids_str else "w.length_m"
                sql_for_pgr = f"SELECT w.id, w.source, w.target, {penalty_clause} as cost FROM rr.ways w"
                route_query = "SELECT seq, path_seq, node, edge, cost, agg_cost FROM pgr_dijkstra(%s, %s, %s, directed := false)"
                params = (sql_for_pgr, source_node, target_node)

                app.logger.info(f"Route query: {route_query}")
                geojson = build_route_geojson(cur, route_query, params, start_lng, start_lat, end_lng, end_lat)
                compute_time_ms = (time.time() - start_time) * 1000

                results['dijkstra_dist'] = {
                    "route_geojson": geojson or {"type": "Feature", "properties": {"total_length_m": 0, "total_cost": 0}, "geometry": {"type": "LineString", "coordinates": []}},
                    "compute_time_ms": round(compute_time_ms, 2),
                    "algorithm": "Dijkstra (Distancia)" + (" con Amenazas Simuladas" if simulate_failures else ""),
                    "simulated_threats": []
                }
            except Exception as e:
                app.logger.error(f"Error calculating dijkstra_dist route: {str(e)}")

        # Route 2: Dijkstra with probability-weighted cost
        if algorithm == 'all' or algorithm == 'dijkstra_prob':
            try:
                start_time = time.time()
                # Always use pre-calculated cost_combined (no threat data from DB)
                penalty_clause = f"CASE WHEN w.id IN ({ids_str}) THEN w.cost_combined * 10 ELSE w.cost_combined END" if ids_str else "w.cost_combined"
                sql_for_pgr = f"SELECT w.id, w.source, w.target, {penalty_clause} as cost FROM rr.ways w WHERE w.cost_combined > 0"
                route_query = "SELECT seq, path_seq, node, edge, cost, agg_cost FROM pgr_dijkstra(%s, %s, %s, directed := false)"
                params = (sql_for_pgr, source_node, target_node)

                app.logger.info(f"Route query: {route_query}")
                geojson = build_route_geojson(cur, route_query, params, start_lng, start_lat, end_lng, end_lat)
                compute_time_ms = (time.time() - start_time) * 1000

                results['dijkstra_prob'] = {
                    "route_geojson": geojson or {"type": "Feature", "properties": {"total_length_m": 0, "total_cost": 0}, "geometry": {"type": "LineString", "coordinates": []}},
                    "compute_time_ms": round(compute_time_ms, 2),
                    "algorithm": "Dijkstra (Ponderado)" + (" con Amenazas Simuladas" if simulate_failures else ""),
                    "simulated_threats": []
                }
            except Exception as e:
                app.logger.error(f"Error calculating dijkstra_prob route: {str(e)}")

        # Route 3: A* with probability-weighted cost
        if algorithm == 'all' or algorithm == 'astar_prob':
            try:
                start_time = time.time()
                # A* with slightly different cost function (emphasizes distance more)
                penalty_clause = f"(CASE WHEN w.id IN ({ids_str}) THEN w.cost_combined * 10 ELSE w.cost_combined END) * 0.8 + w.length_m * 0.2" if ids_str else "w.cost_combined * 0.8 + w.length_m * 0.2"
                sql_for_pgr = f"""
                    SELECT w.id, w.source, w.target,
                           {penalty_clause} as cost,
                           ST_X(sv.the_geom) as x1, ST_Y(sv.the_geom) as y1,
                           ST_X(tv.the_geom) as x2, ST_Y(tv.the_geom) as y2
                    FROM rr.ways w
                    JOIN rr.ways_vertices_pgr sv ON w.source = sv.id
                    JOIN rr.ways_vertices_pgr tv ON w.target = tv.id
                    WHERE w.cost_combined > 0
                """
                route_query = "SELECT seq, path_seq, node, edge, cost, agg_cost FROM pgr_astar(%s, %s, %s, directed := false)"
                params = (sql_for_pgr, source_node, target_node)

                app.logger.info(f"Route query: {route_query}")
                geojson = build_route_geojson(cur, route_query, params, start_lng, start_lat, end_lng, end_lat)
                compute_time_ms = (time.time() - start_time) * 1000

                results['astar_prob'] = {
                    "route_geojson": geojson or {"type": "Feature", "properties": {"total_length_m": 0, "total_cost": 0}, "geometry": {"type": "LineString", "coordinates": []}},
                    "compute_time_ms": round(compute_time_ms, 2),
                    "algorithm": "A* (Ponderado)" + (" con Amenazas Simuladas" if simulate_failures else ""),
                    "simulated_threats": []
                }
            except Exception as e:
                app.logger.error(f"Error calculating astar_prob route: {str(e)}")

        # Route 4: CPLEX-like optimization (risk-constrained shortest path)
        if algorithm == 'all' or algorithm == 'cplex':
            try:
                start_time = time.time()

                # CPLEX approximation: use cost that heavily penalizes high-risk edges
                # Instead of excluding high-risk edges, make them very expensive
                threat_penalty = f" * (CASE WHEN w.id IN ({ids_str}) THEN 10 ELSE 1 END)" if ids_str else ""
                sql_for_pgr = f"""
                    SELECT w.id, w.source, w.target,
                           w.cost_combined * (1 + COALESCE(w.fail_prob, 0) * 10){threat_penalty} as cost
                    FROM rr.ways w
                    WHERE w.cost_combined > 0
                """
                route_query = "SELECT seq, path_seq, node, edge, cost, agg_cost FROM pgr_dijkstra(%s, %s, %s, directed := false)"
                params = (sql_for_pgr, source_node, target_node)

                geojson = build_route_geojson(cur, route_query, params, start_lng, start_lat, end_lng, end_lat)
                compute_time_ms = (time.time() - start_time) * 1000

                # Check if route has actual coordinates (not empty)
                has_valid_route = (geojson and geojson.get('geometry', {}).get('coordinates') and
                                 len(geojson['geometry']['coordinates']) > 0)

                if has_valid_route:
                    results['cplex'] = {
                        "route_geojson": geojson,
                        "compute_time_ms": round(compute_time_ms, 2),
                        "algorithm": "CPLEX (Optimizado con Penalización de Riesgo)" + (" con Amenazas Simuladas" if simulate_failures else ""),
                        "simulated_threats": []
                    }
                else:
                    # Fallback: use standard weighted dijkstra
                    penalty_clause = f"CASE WHEN w.id IN ({ids_str}) THEN w.cost_combined * 10 ELSE w.cost_combined END" if ids_str else "w.cost_combined"
                    sql_for_pgr = f"SELECT w.id, w.source, w.target, {penalty_clause} as cost FROM rr.ways w WHERE w.cost_combined > 0"
                    route_query = "SELECT seq, path_seq, node, edge, cost, agg_cost FROM pgr_dijkstra(%s, %s, %s, directed := false)"
                    params = (sql_for_pgr, source_node, target_node)
                    geojson = build_route_geojson(cur, route_query, params, start_lng, start_lat, end_lng, end_lat)
                    if geojson and geojson.get('geometry', {}).get('coordinates') and len(geojson['geometry']['coordinates']) > 0:

                        results['cplex'] = {
                            "route_geojson": geojson,
                            "compute_time_ms": round(compute_time_ms, 2),
                            "algorithm": "CPLEX (Fallback: Ponderado)" + (" con Amenazas Simuladas" if simulate_failures else ""),
                            "simulated_threats": []
                        }
            except Exception as e:
                app.logger.error(f"Error calculating cplex route: {str(e)}")
        
        cur.close()
        conn.close()
        
        if not results:
            return jsonify({
                "error": "No se pudo calcular ninguna ruta entre los puntos especificados",
                "details": "Puede que los puntos no estén conectados en la red o no haya rutas disponibles"
            }), 404
        
        # Add global simulated threats if requested
        if simulate_failures and simulated_threats:
            results['simulated_threats'] = simulated_threats
        
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
    app.run(debug=debug_mode, host='0.0.0.0', port=5001)
