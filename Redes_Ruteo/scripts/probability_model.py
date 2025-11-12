#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Probability Model for Failure Assessment
Calculates failure probabilities for network elements based on threat proximity.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDATABASE", "rr")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASS = os.getenv("PGPASSWORD", "postgres")

# Threat parameters
INFLUENCE_RADIUS_M = 50  # meters
FAILURE_PROBABILITY = 0.5  # probability assigned to affected elements


def get_db_connection():
    """Create and return a database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )


def ensure_fail_prob_columns(conn):
    """
    Ensure that fail_prob columns exist in rr.ways and rr.ways_vertices_pgr.
    Creates columns if they don't exist.
    """
    with conn.cursor() as cur:
        # Check and add fail_prob column to rr.ways
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'rr' 
            AND table_name = 'ways' 
            AND column_name = 'fail_prob'
        """)
        
        if not cur.fetchone():
            print("Adding fail_prob column to rr.ways...")
            cur.execute("""
                ALTER TABLE rr.ways 
                ADD COLUMN fail_prob FLOAT8 DEFAULT 0.0
            """)
            conn.commit()
            print("✓ Column fail_prob added to rr.ways")
        else:
            print("✓ Column fail_prob already exists in rr.ways")
        
        # Check if ways_vertices_pgr table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'rr' 
                AND table_name = 'ways_vertices_pgr'
            )
        """)
        
        if cur.fetchone()[0]:
            # Check and add fail_prob column to rr.ways_vertices_pgr
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'rr' 
                AND table_name = 'ways_vertices_pgr' 
                AND column_name = 'fail_prob'
            """)
            
            if not cur.fetchone():
                print("Adding fail_prob column to rr.ways_vertices_pgr...")
                cur.execute("""
                    ALTER TABLE rr.ways_vertices_pgr 
                    ADD COLUMN fail_prob FLOAT8 DEFAULT 0.0
                """)
                conn.commit()
                print("✓ Column fail_prob added to rr.ways_vertices_pgr")
            else:
                print("✓ Column fail_prob already exists in rr.ways_vertices_pgr")
        else:
            print("⚠ Table rr.ways_vertices_pgr does not exist yet")
            print("  Run pgr_createTopology first to create this table")


def reset_failure_probabilities(conn):
    """Reset all failure probabilities to 0.0."""
    with conn.cursor() as cur:
        print("Resetting failure probabilities to 0.0...")
        
        # Reset ways
        cur.execute("UPDATE rr.ways SET fail_prob = 0.0")
        ways_count = cur.rowcount
        
        # Reset vertices (if table exists)
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'rr' 
                AND table_name = 'ways_vertices_pgr'
            )
        """)
        
        if cur.fetchone()[0]:
            cur.execute("UPDATE rr.ways_vertices_pgr SET fail_prob = 0.0")
            vertices_count = cur.rowcount
            print(f"✓ Reset {ways_count} ways and {vertices_count} vertices")
        else:
            print(f"✓ Reset {ways_count} ways (vertices table doesn't exist)")
        
        conn.commit()


def calculate_failure_probabilities(conn):
    """
    Calculate failure probabilities based on threat proximity.
    Assigns probabilities to network elements within influence radius of threats.
    Processes all threat sources: Waze, Weather, and Traffic Calming.
    """
    with conn.cursor() as cur:
        # Check which threat tables exist and get counts
        waze_count = 0
        weather_count = 0
        calming_count = 0
        
        # Check Waze threats
        try:
            cur.execute("SELECT COUNT(*) FROM rr.amenazas_waze")
            waze_count = cur.fetchone()[0]
        except Exception:
            print("⚠ Table rr.amenazas_waze does not exist or is not accessible")
        
        # Check Weather threats
        try:
            cur.execute("SELECT COUNT(*) FROM rr.amenazas_clima")
            weather_count = cur.fetchone()[0]
        except Exception:
            print("⚠ Table rr.amenazas_clima does not exist or is not accessible")
        
        # Check Traffic Calming threats
        try:
            cur.execute("SELECT COUNT(*) FROM rr.amenazas_calming")
            calming_count = cur.fetchone()[0]
        except Exception:
            print("⚠ Table rr.amenazas_calming does not exist or is not accessible")
        
        total_threats = waze_count + weather_count + calming_count
        
        if total_threats == 0:
            print("\n⚠ No threats found in any table. All failure probabilities will remain at 0.0.")
            print("  This is normal if you haven't loaded threat data yet.")
            print("  Routes will be calculated based on distance only.")
            return
        
        print(f"\nProcessing {total_threats} threats total:")
        print(f"  - Waze: {waze_count}")
        print(f"  - Weather: {weather_count}")
        print(f"  - Traffic Calming: {calming_count}")
        
        # Update ways within influence radius of threats (from all sources)
        print(f"\nCalculating probabilities for ways (radius: {INFLUENCE_RADIUS_M}m)...")
        
        # Process Waze threats (optimized with JOIN)
        if waze_count > 0:
            cur.execute("""
                UPDATE rr.ways w
                SET fail_prob = GREATEST(
                    COALESCE(w.fail_prob, 0.0),
                    %(prob)s
                )
                FROM (
                    SELECT DISTINCT w2.id -- <-- CORRECCIÓN 1: 'gid' cambiado a 'id'
                    FROM rr.ways w2
                    JOIN rr.amenazas_waze t
                    ON ST_DWithin(
                        w2.geom::geography,
                        t.geom::geography,
                        %(radius)s
                    )
                ) AS affected_ways
                WHERE w.id = affected_ways.id -- <-- CORRECCIÓN 1: 'gid' cambiado a 'id'
            """, {
                'prob': FAILURE_PROBABILITY,
                'radius': INFLUENCE_RADIUS_M
            })
            waze_affected = cur.rowcount
            print(f"✓ Updated {waze_affected} ways based on Waze threats")
        
        # Process Weather threats
        if weather_count > 0:
            cur.execute("""
                UPDATE rr.ways w
                SET fail_prob = GREATEST(
                    COALESCE(w.fail_prob, 0.0),
                    %(prob)s * (t.severity / 3.0)
                )
                WHERE EXISTS (
                    SELECT 1
                    FROM rr.amenazas_clima t
                    WHERE ST_Intersects(w.geom, t.geom)
                )
            """, {
                'prob': FAILURE_PROBABILITY
            })
            weather_affected = cur.rowcount
            print(f"✓ Updated {weather_affected} ways based on Weather threats")
        
        # Process Traffic Calming threats
        if calming_count > 0:
            # Use spatial index and batch processing for better performance with many threats
            print(f"  Processing {calming_count} traffic calming threats (this may take a moment)...")
            cur.execute("""
                UPDATE rr.ways w
                SET fail_prob = GREATEST(
                    COALESCE(w.fail_prob, 0.0),
                    %(prob)s * 0.3
                )
                FROM (
                    SELECT DISTINCT w2.id
                    FROM rr.ways w2
                    JOIN rr.amenazas_calming t
                    ON ST_DWithin(
                        w2.geom::geography,
                        t.geom::geography,
                        %(radius)s
                    )
                ) AS affected_ways
                WHERE w.id = affected_ways.id
            """, {
                'prob': FAILURE_PROBABILITY,
                'radius': INFLUENCE_RADIUS_M
            })
            calming_affected = cur.rowcount
            print(f"✓ Updated {calming_affected} ways based on Traffic Calming threats")
        
        # Update vertices within influence radius of threats (if table exists)
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'rr' 
                AND table_name = 'ways_vertices_pgr'
            )
        """)
        
        if cur.fetchone()[0]:
            # Check if geom column exists in ways_vertices_pgr
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'rr' 
                AND table_name = 'ways_vertices_pgr' 
                AND column_name = 'geom'
            """)
            
            if cur.fetchone():
                print(f"\nCalculating probabilities for vertices (radius: {INFLUENCE_RADIUS_M}m)...")
                
                # Process Waze threats for vertices (optimized with JOIN)
                if waze_count > 0:
                    cur.execute("""
                        UPDATE rr.ways_vertices_pgr v
                        SET fail_prob = GREATEST(
                            COALESCE(v.fail_prob, 0.0),
                            %(prob)s
                        )
                        FROM (
                            SELECT DISTINCT v2.id
                            FROM rr.ways_vertices_pgr v2
                            JOIN rr.amenazas_waze t
                            ON ST_DWithin(
                                v2.geom::geography,
                                t.geom::geography,
                                %(radius)s -- <-- CORRECCIÓN 2: 's' extra eliminado
                            )
                        ) AS affected_vertices
                        WHERE v.id = affected_vertices.id
                    """, {
                        'prob': FAILURE_PROBABILITY,
                        'radius': INFLUENCE_RADIUS_M
                    })
                    vertices_waze = cur.rowcount
                    print(f"✓ Updated {vertices_waze} vertices based on Waze threats")
                
                # Process Weather threats for vertices
                if weather_count > 0:
                    cur.execute("""
                        UPDATE rr.ways_vertices_pgr v
                        SET fail_prob = GREATEST(
                            COALESCE(v.fail_prob, 0.0),
                            %(prob)s * (t.severity / 3.0)
                        )
                        WHERE EXISTS (
                            SELECT 1
                            FROM rr.amenazas_clima t
                            WHERE ST_Intersects(v.geom, t.geom)
                        )
                    """, {
                        'prob': FAILURE_PROBABILITY
                    })
                    vertices_weather = cur.rowcount
                    print(f"✓ Updated {vertices_weather} vertices based on Weather threats")
                
                # Process Traffic Calming threats for vertices (optimized with JOIN)
                if calming_count > 0:
                    cur.execute("""
                        UPDATE rr.ways_vertices_pgr v
                        SET fail_prob = GREATEST(
                            COALESCE(v.fail_prob, 0.0),
                            %(prob)s * 0.3
                        )
                        FROM (
                            SELECT DISTINCT v2.id
                            FROM rr.ways_vertices_pgr v2
                            JOIN rr.amenazas_calming t
                            ON ST_DWithin(
                                v2.geom::geography,
                                t.geom::geography,
                                %(radius)s -- <-- CORRECCIÓN 3: 's' extra eliminado
                            )
                        ) AS affected_vertices
                        WHERE v.id = affected_vertices.id
                    """, {
                        'prob': FAILURE_PROBABILITY,
                        'radius': INFLUENCE_RADIUS_M
                    })
                    vertices_calming = cur.rowcount
                    print(f"✓ Updated {vertices_calming} vertices based on Traffic Calming threats")
            else:
                print("⚠ ways_vertices_pgr table exists but geom column not found")
        
        conn.commit()


def print_statistics(conn):
    """Print summary statistics of failure probabilities."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        print("\n" + "="*60)
        print("FAILURE PROBABILITY STATISTICS")
        print("="*60)
        
        # Ways statistics
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE fail_prob > 0) as affected,
                ROUND(AVG(fail_prob)::numeric, 4) as avg_prob,
                ROUND(MAX(fail_prob)::numeric, 4) as max_prob
            FROM rr.ways
        """)
        row = cur.fetchone()
        print(f"\nWays:")
        print(f"  Total: {row['total']}")
        print(f"  Affected (fail_prob > 0): {row['affected']}")
        print(f"  Average probability: {row['avg_prob']}")
        print(f"  Maximum probability: {row['max_prob']}")
        
        # Vertices statistics (if table exists)
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'rr' 
                AND table_name = 'ways_vertices_pgr'
            )
        """)
        
        if cur.fetchone()['exists']:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE fail_prob > 0) as affected,
                    ROUND(AVG(fail_prob)::numeric, 4) as avg_prob,
                    ROUND(MAX(fail_prob)::numeric, 4) as max_prob
                FROM rr.ways_vertices_pgr
            """)
            row = cur.fetchone()
            print(f"\nVertices:")
            print(f"  Total: {row['total']}")
            print(f"  Affected (fail_prob > 0): {row['affected']}")
            print(f"  Average probability: {row['avg_prob']}")
            print(f"  Maximum probability: {row['max_prob']}")
        
        print("="*60 + "\n")


def main():
    """Main execution function."""
    print("\n" + "="*60)
    print("PROBABILITY MODEL - Failure Assessment")
    print("="*60 + "\n")
    
    try:
        # Connect to database
        print("Connecting to database...")
        conn = get_db_connection()
        print("✓ Connected to database")
        
        # Use RealDictCursor for statistic printing
        conn.cursor_factory = RealDictCursor

        # Ensure fail_prob columns exist
        ensure_fail_prob_columns(conn)
        
        # Reset failure probabilities
        reset_failure_probabilities(conn)
        
        # Calculate failure probabilities
        calculate_failure_probabilities(conn)
        
        # Print statistics
        print_statistics(conn)
        
        conn.close()
        print("✓ Probability model execution completed successfully\n")
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())