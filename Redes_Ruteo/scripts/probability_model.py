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
import time

load_dotenv()

# Database configuration
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDATABASE", "rr")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASS = os.getenv("PGPASSWORD", "postgres")

# --- Parámetros dinámicos para cálculo de probabilidades ---
# En lugar de valores fijos, usar fórmulas basadas en factores realistas

def calculate_dynamic_probability(threat_type, severity, distance_m, size_m=None, duration_factor=1.0):
    """
    Calculate failure probability using dynamic formulas based on realistic factors.
    
    Args:
        threat_type: 'waze', 'weather', 'calming'
        severity: 1-5 scale
        distance_m: distance from threat to network element
        size_m: size of threat area (for weather)
        duration_factor: how long the threat lasts (0-1)
    
    Returns:
        probability: 0-1 scale
    """
    # Base probabilities por tipo de amenaza
    base_probs = {
        'waze': 0.6,      # Accidentes son comunes
        'weather': 0.4,   # Clima variable
        'calming': 0.15   # Reductores de velocidad son locales
    }
    
    base_prob = base_probs.get(threat_type, 0.3)
    
    # Factor de severidad: amenazas más severas tienen mayor impacto
    severity_factor = 0.5 + (severity - 1) * 0.3  # 0.5-1.7
    
    # Factor de distancia: amenazas más cercanas tienen mayor impacto
    if distance_m <= 50:
        distance_factor = 1.0
    elif distance_m <= 100:
        distance_factor = 0.8
    elif distance_m <= 200:
        distance_factor = 0.6
    else:
        distance_factor = max(0.1, 1.0 - (distance_m / 1000))  # Decae con distancia
    
    # Factor de tamaño (para clima): áreas más grandes afectan más
    size_factor = 1.0
    if size_m and threat_type == 'weather':
        size_factor = min(2.0, 1.0 + (size_m / 2000))  # Hasta 2x para áreas grandes
    
    # Factor temporal: amenazas que duran más son más problemáticas
    time_factor = 0.7 + (duration_factor * 0.6)  # 0.7-1.3
    
    # Factor aleatorio para variabilidad realista (±15%)
    import random
    random_factor = random.uniform(0.85, 1.15)
    
    # Cálculo final de probabilidad
    probability = base_prob * severity_factor * distance_factor * size_factor * time_factor * random_factor
    
    # Limitar al rango 0-0.95
    return min(0.95, max(0.0, probability))


def calculate_dynamic_weather_probability(severity, distance_m, size_m, visibility_factor=1.0):
    """
    Specialized calculation for weather threats considering visibility and precipitation.
    """
    # Clima tiene factores adicionales como visibilidad
    visibility_impact = 1.0
    if severity >= 4:  # Baja visibilidad
        visibility_impact = 1.5  # Mayor impacto
    
    precipitation_factor = 1.0 + (size_m / 3000)  # Lluvia más intensa en áreas grandes
    
    base_prob = calculate_dynamic_probability('weather', severity, distance_m, size_m, 0.6)
    
    return min(0.95, base_prob * visibility_impact * precipitation_factor * visibility_factor)

# Timeout por sentencia (ms) para evitar bloqueos prolongados en consultas pesadas
STATEMENT_TIMEOUT_MS = int(os.getenv("PG_STATEMENT_TIMEOUT_MS", "120000"))


def meters_to_degrees(meters: float) -> float:
    """Convierte metros a grados (aprox. en el ecuador).
    Suficiente para radios pequeños (<= 200 m) y permite usar índices GiST en geometry.
    """
    return meters / 111_320.0


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
    # Esta función se llama ANTES de que se establezca RealDictCursor,
    # por lo que usa cursores estándar (tuplas).
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


def ensure_spatial_indexes(conn):
    """Asegura índices espaciales en columnas geometry para acelerar ST_DWithin/Intersects."""
    with conn.cursor() as cur:
        print("Ensuring spatial indexes (GiST) exist...")

        # rr.ways.geom
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname='rr' AND tablename='ways' AND indexname='idx_ways_geom'
                ) THEN
                    EXECUTE 'CREATE INDEX idx_ways_geom ON rr.ways USING GIST (geom)';
                END IF;
            END$$;
            """
        )

        # rr.ways_vertices_pgr.geom o the_geom (si existe la tabla)
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='rr' AND table_name='ways_vertices_pgr'
            )
            """
        )
        if cur.fetchone()[0]:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='rr' AND table_name='ways_vertices_pgr'
                  AND column_name IN ('geom','the_geom')
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                geom_col = row[0]
                idx_name = f"idx_wvp_{geom_col}_gix"
                cur.execute(
                    f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_indexes
                            WHERE schemaname='rr' AND tablename='ways_vertices_pgr' AND indexname='{idx_name}'
                        ) THEN
                            EXECUTE 'CREATE INDEX {idx_name} ON rr.ways_vertices_pgr USING GIST ({geom_col})';
                        END IF;
                    END$$;
                    """
                )

        # rr.amenazas_waze.geom
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname='rr' AND tablename='amenazas_waze' AND indexname='am_waze_geom_gix'
                ) THEN
                    EXECUTE 'CREATE INDEX am_waze_geom_gix ON rr.amenazas_waze USING GIST (geom)';
                END IF;
            END$$;
            """
        )

        # rr.amenazas_calming.geom
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname='rr' AND tablename='amenazas_calming' AND indexname='am_calming_geom_gix'
                ) THEN
                    EXECUTE 'CREATE INDEX am_calming_geom_gix ON rr.amenazas_calming USING GIST (geom)';
                END IF;
            END$$;
            """
        )

        # rr.amenazas_clima.geom
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname='rr' AND tablename='amenazas_clima' AND indexname='am_clima_geom_gix'
                ) THEN
                    EXECUTE 'CREATE INDEX am_clima_geom_gix ON rr.amenazas_clima USING GIST (geom)';
                END IF;
            END$$;
            """
        )

        # Actualiza estadísticas
        cur.execute("ANALYZE rr.ways;")
        cur.execute("ANALYZE rr.amenazas_waze;")
        cur.execute("ANALYZE rr.amenazas_calming;")
        cur.execute("ANALYZE rr.amenazas_clima;")
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='rr' AND table_name='ways_vertices_pgr'
            )
            """
        )
        if cur.fetchone()[0]:
            cur.execute("ANALYZE rr.ways_vertices_pgr;")
        conn.commit()


def set_statement_timeout(conn, ms: int):
    """Configura statement_timeout en la conexión (ms)."""
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = %s", (ms,))
    conn.commit()


def reset_failure_probabilities(conn):
    """Reset all failure probabilities to 0.0."""
    # Este cursor SÍ es RealDictCursor, configurado en main()
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
        
        if cur.fetchone()['exists']:
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
    # Este cursor SÍ es RealDictCursor, configurado en main()
    with conn.cursor() as cur:
        # Check which threat tables exist and get counts
        waze_count = 0
        weather_count = 0
        calming_count = 0
        
        # Check Waze threats
        try:
            cur.execute("SELECT COUNT(*) as count FROM rr.amenazas_waze")
            waze_count = cur.fetchone()['count']
        except Exception:
            print("⚠ Table rr.amenazas_waze does not exist or is not accessible")
        
        # Check Weather threats
        try:
            cur.execute("SELECT COUNT(*) as count FROM rr.amenazas_clima")
            weather_count = cur.fetchone()['count']
        except Exception:
            print("⚠ Table rr.amenazas_clima does not exist or is not accessible")
        
        # Check Traffic Calming threats
        try:
            cur.execute("SELECT COUNT(*) as count FROM rr.amenazas_calming")
            calming_count = cur.fetchone()['count']
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
        
        # Update ways with dynamic probabilities calculated in Python
        print(f"\nCalculating dynamic probabilities for ways...")
        start_all = time.time()
        
        # Reset probabilities first
        cur.execute("UPDATE rr.ways SET fail_prob = 0.0")
        
        # Process Waze threats
        if waze_count > 0:
            print("  Processing Waze threats...")
            cur.execute("""
                SELECT w.id as way_id, 
                       ST_Distance(w.geom, t.geom) * 111000 as distance_m,
                       t.severity, t.size_m
                FROM rr.ways w
                JOIN rr.amenazas_waze t ON ST_DWithin(w.geom, t.geom, %(radius_deg)s)
            """, {'radius_deg': meters_to_degrees(get_influence_radius('waze'))})
            
            waze_results = cur.fetchall()
            for row in waze_results:
                prob = calculate_dynamic_probability('waze', row['severity'], row['distance_m'], row['size_m'], 0.8)
                cur.execute("UPDATE rr.ways SET fail_prob = GREATEST(fail_prob, %s) WHERE id = %s", (prob, row['way_id']))
        
        # Process Weather threats
        if weather_count > 0:
            print("  Processing Weather threats...")
            cur.execute("""
                SELECT w.id as way_id, 
                       ST_Distance(w.geom, ST_Centroid(t.geom)) * 111000 as distance_m,
                       t.severity, 
                       ST_Area(t.geom::geography) / 1000000 as area_km2  -- Approximate size
                FROM rr.ways w
                JOIN rr.amenazas_clima t ON ST_Intersects(w.geom, t.geom)
            """)
            
            weather_results = cur.fetchall()
            for row in weather_results:
                # Estimate size from area
                size_m = (row['area_km2'] * 1000000) ** 0.5  # Square root of area as rough diameter
                visibility_factor = 1.5 if row['severity'] >= 4 else 1.0  # Higher for low visibility
                prob = calculate_dynamic_weather_probability(row['severity'], row['distance_m'], size_m, visibility_factor)
                cur.execute("UPDATE rr.ways SET fail_prob = GREATEST(fail_prob, %s) WHERE id = %s", (prob, row['way_id']))
        
        # Process Traffic Calming threats
        if calming_count > 0:
            print("  Processing Traffic Calming threats...")
            cur.execute("""
                SELECT w.id as way_id, 
                       ST_Distance(w.geom, t.geom) * 111000 as distance_m,
                       t.severity, t.size_m
                FROM rr.ways w
                JOIN rr.amenazas_calming t ON ST_DWithin(w.geom, t.geom, %(radius_deg)s)
            """, {'radius_deg': meters_to_degrees(get_influence_radius('calming'))})
            
            calming_results = cur.fetchall()
            for row in calming_results:
                prob = calculate_dynamic_probability('calming', row['severity'], row['distance_m'], row['size_m'], 1.0)
                cur.execute("UPDATE rr.ways SET fail_prob = GREATEST(fail_prob, %s) WHERE id = %s", (prob, row['way_id']))
        
        ways_affected = cur.rowcount
        print(f"✓ Updated ways with dynamic probabilities in {time.time()-start_all:.1f}s")

        # Update vertices within influence radius of threats (if table exists)
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'rr' 
                AND table_name = 'ways_vertices_pgr'
            )
        """)
        
        if cur.fetchone()['exists']:
            # Detect geometry column in ways_vertices_pgr (geom or the_geom)
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'rr' 
                AND table_name = 'ways_vertices_pgr' 
                AND column_name IN ('geom','the_geom')
                LIMIT 1
            """)
            col_row = cur.fetchone()
            if col_row:
                geom_col = col_row['column_name'] if isinstance(col_row, dict) else col_row[0]
                print(f"\nCalculating probabilities for vertices (using column '{geom_col}')...")
                step_start = time.time()

                # --- Optimización: Calcular todas las probabilidades en una sola consulta ---
                cur.execute(
                    f"""
                    WITH all_threats AS (
                        -- Waze threats
                        SELECT 
                            v.id AS vertex_id,
                            %(waze_prob)s AS prob
                        FROM rr.ways_vertices_pgr v
                        JOIN rr.amenazas_waze t ON ST_DWithin(v.{geom_col}, t.geom, %(waze_radius_deg)s)
                        WHERE %(waze_count)s > 0

                        UNION ALL

                        -- Weather threats
                        SELECT 
                            v.id AS vertex_id,
                            (%(weather_prob)s * (t.severity / 3.0)) AS prob
                        FROM rr.ways_vertices_pgr v
                        JOIN rr.amenazas_clima t ON ST_Intersects(v.{geom_col}, t.geom)
                        WHERE %(weather_count)s > 0

                        UNION ALL

                        -- Traffic Calming threats
                        SELECT 
                            v.id AS vertex_id,
                            %(calming_prob)s AS prob
                        FROM rr.ways_vertices_pgr v
                        JOIN rr.amenazas_calming t ON ST_DWithin(v.{geom_col}, t.geom, %(calming_radius_deg)s)
                        WHERE %(calming_count)s > 0
                    ),
                    max_probs AS (
                        SELECT 
                            vertex_id,
                            MAX(prob) as max_prob
                        FROM all_threats
                        GROUP BY vertex_id
                    )
                    UPDATE rr.ways_vertices_pgr v
                    SET fail_prob = mp.max_prob
                    FROM max_probs mp
                    WHERE v.id = mp.vertex_id;
                    """,
                    {
                        'waze_prob': WAZE_PROB,
                        'waze_radius_deg': meters_to_degrees(WAZE_RADIUS_M),
                        'waze_count': waze_count,
                        'weather_prob': WEATHER_PROB_FACTOR,
                        'weather_count': weather_count,
                        'calming_prob': CALMING_PROB,
                        'calming_radius_deg': meters_to_degrees(CALMING_RADIUS_M),
                        'calming_count': calming_count,
                    }
                )
                vertices_affected = cur.rowcount
                print(f"✓ Updated {vertices_affected} vertices based on all threats in {time.time()-step_start:.1f}s")
            else:
                print("⚠ ways_vertices_pgr table exists but no geom/the_geom column found")
        
        conn.commit()
        print(f"Total calculation time: {time.time()-start_all:.1f}s")
    
def print_statistics(conn):
    """Print summary statistics of failure probabilities."""
    # Este cursor SÍ es RealDictCursor, configurado en main()
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
        
        # ensure_fail_prob_columns usa cursores estándar (tuplas)
        ensure_fail_prob_columns(conn)

        # Índices espaciales y timeout por sentencia
        ensure_spatial_indexes(conn)
        set_statement_timeout(conn, STATEMENT_TIMEOUT_MS)

        # Ahora, establecer RealDictCursor para el resto del script
        conn.cursor_factory = RealDictCursor
        
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