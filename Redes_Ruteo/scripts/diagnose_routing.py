#!/usr/bin/env python3
"""
Diagnostic script to check routing configuration and database status.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "rr")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")


def check_database_connection():
    """Test database connection."""
    print("\n" + "="*60)
    print("1. Verificando conexión a la base de datos")
    print("="*60)
    
    try:
        conn = psycopg2.connect(
            host=PGHOST,
            port=PGPORT,
            dbname=PGDATABASE,
            user=PGUSER,
            password=PGPASSWORD,
            connect_timeout=5
        )
        print(f"✓ Conexión exitosa a la base de datos '{PGDATABASE}' en {PGHOST}:{PGPORT}")
        return conn
    except psycopg2.OperationalError as e:
        print(f"✗ Error de conexión: {e}")
        print("\nSOLUCIÓN:")
        print("  1. Verifica que PostgreSQL esté ejecutándose")
        print("  2. Verifica las credenciales en el archivo .env")
        print("  3. Verifica que la base de datos 'rr' exista")
        return None
    except Exception as e:
        print(f"✗ Error inesperado: {e}")
        return None


def check_extensions(conn):
    """Check if required extensions are installed."""
    print("\n" + "="*60)
    print("2. Verificando extensiones PostgreSQL")
    print("="*60)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check PostGIS
    cur.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
    postgis_installed = cur.fetchone() is not None
    
    if postgis_installed:
        cur.execute("SELECT PostGIS_Version()")
        version = cur.fetchone() is not None
        print(f"✓ PostGIS instalado: {version}")
    else:
        print("✗ PostGIS NO instalado")
        print("\nSOLUCIÓN:")
        print("  CREATE EXTENSION postgis;")
    
    # Check pgRouting
    cur.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'pgrouting')")
    pgrouting_installed = cur.fetchone() is not None
    
    if pgrouting_installed:
        cur.execute("SELECT pgr_version()")
        version = cur.fetchone() is not None
        print(f"✓ pgRouting instalado: {version}")
    else:
        print("✗ pgRouting NO instalado")
        print("\nSOLUCIÓN:")
        print("  CREATE EXTENSION pgrouting;")
    
    cur.close()
    return postgis_installed and pgrouting_installed


def check_schema(conn):
    """Check if rr schema exists."""
    print("\n" + "="*60)
    print("3. Verificando esquema 'rr'")
    print("="*60)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'rr')")
    schema_exists = cur.fetchone() is not None
    
    if schema_exists:
        print("✓ Esquema 'rr' existe")
    else:
        print("✗ Esquema 'rr' NO existe")
        print("\nSOLUCIÓN:")
        print("  CREATE SCHEMA rr;")
    
    cur.close()
    return schema_exists


def check_tables(conn):
    """Check if required tables exist and have data."""
    print("\n" + "="*60)
    print("4. Verificando tablas y datos")
    print("="*60)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    tables = {
        'rr.ways': 'Tabla de aristas (ways)',
        'rr.ways_vertices_pgr': 'Tabla de vértices (nodos) para pgRouting',
        'rr.nodes': 'Tabla de nodos OSM'
    }
    
    all_ok = True
    
    for table, description in tables.items():
        # Check if table exists
        schema, table_name = table.split('.')
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = %s 
                AND table_name = %s
            )
        """, (schema, table_name))
        
        table_exists = cur.fetchone() is not None
        
        if table_exists:
            # Count rows
            cur.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cur.fetchone()['count']
            
            if count > 0:
                print(f"✓ {description}: {count:,} registros")
            else:
                print(f"⚠ {description}: tabla existe pero SIN DATOS")
                all_ok = False
        else:
            print(f"✗ {description}: tabla NO EXISTE")
            all_ok = False
    
    if not all_ok:
        print("\nSOLUCIÓN:")
        print("  1. Ejecuta: python infraestructura/osm_roads_overpass_parallel.py")
        print("  2. Ejecuta: python loaders/load_ways_nodes.py")
        print("  3. Verifica que schema.sql esté aplicado")
    
    cur.close()
    return all_ok


def check_topology(conn):
    """Check if topology is created (source/target columns populated)."""
    print("\n" + "="*60)
    print("5. Verificando topología de pgRouting")
    print("="*60)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Check if ways_vertices_pgr exists and has data
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'rr' 
                AND table_name = 'ways_vertices_pgr'
            )
        """)
        
        vertices_exist = cur.fetchone() is not None
        
        if not vertices_exist:
            print("✗ Tabla ways_vertices_pgr NO EXISTE")
            print("\nSOLUCIÓN:")
            print("  Ejecuta en psql o pgAdmin:")
            print("  SELECT pgr_createTopology('rr.ways', 0.0001, 'geom', 'id');")
            cur.close()
            return False
        
        # Count vertices
        cur.execute("SELECT COUNT(*) as count FROM rr.ways_vertices_pgr")
        vertex_count = cur.fetchone()['count']
        
        # Check if source/target are populated in ways
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM rr.ways 
            WHERE source IS NOT NULL AND target IS NOT NULL
        """)
        populated = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as total FROM rr.ways")
        total = cur.fetchone()['total']
        
        if populated == total and vertex_count > 0:
            print(f"✓ Topología creada: {vertex_count:,} vértices, {populated:,}/{total:,} aristas conectadas")
        elif populated == 0:
            print(f"✗ Topología NO creada: source/target están NULL")
            print("\nSOLUCIÓN:")
            print("  Ejecuta en psql o pgAdmin:")
            print("  SELECT pgr_createTopology('rr.ways', 0.0001, 'geom', 'id');")
            cur.close()
            return False
        else:
            print(f"⚠ Topología parcial: {populated:,}/{total:,} aristas conectadas")
        
        # Check if geom column exists in ways_vertices_pgr
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_schema = 'rr' 
                AND table_name = 'ways_vertices_pgr'
                AND column_name = 'geom'
            )
        """)
        
        geom_exists = cur.fetchone() is not None
        
        if not geom_exists:
            print("⚠ Columna 'geom' NO existe en ways_vertices_pgr")
            print("\nSOLUCIÓN (opcional pero recomendado):")
            print("  ALTER TABLE rr.ways_vertices_pgr ADD COLUMN geom geometry(Point,4326);")
            print("  UPDATE rr.ways_vertices_pgr SET geom = ST_SetSRID(ST_MakePoint(x, y), 4326);")
            print("  CREATE INDEX ways_vertices_gix ON rr.ways_vertices_pgr USING GIST (geom);")
        else:
            # Check if geom is populated
            cur.execute("SELECT COUNT(*) as count FROM rr.ways_vertices_pgr WHERE geom IS NOT NULL")
            geom_count = cur.fetchone()['count']
            
            if geom_count == vertex_count:
                print(f"✓ Geometrías de vértices: {geom_count:,}/{vertex_count:,} pobladas")
            else:
                print(f"⚠ Geometrías de vértices: {geom_count:,}/{vertex_count:,} pobladas")
        
        cur.close()
        return populated > 0
        
    except Exception as e:
        print(f"✗ Error verificando topología: {e}")
        cur.close()
        return False


def test_routing_query(conn):
    """Test a simple routing query."""
    print("\n" + "="*60)
    print("6. Probando consulta de ruteo")
    print("="*60)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get two random nodes
        cur.execute("""
            SELECT id FROM rr.ways_vertices_pgr 
            ORDER BY RANDOM() 
            LIMIT 2
        """)
        
        nodes = cur.fetchall()
        
        if len(nodes) < 2:
            print("✗ No hay suficientes nodos para probar")
            cur.close()
            return False
        
        source = nodes[0]['id']
        target = nodes[1]['id']
        
        print(f"  Probando ruta de nodo {source} a nodo {target}...")
        
        # Try routing query
        cur.execute("""
            SELECT 
                r.seq, r.node, r.edge, r.cost, r.agg_cost
            FROM pgr_dijkstra(
                'SELECT id, source, target, length_m as cost FROM rr.ways',
                %s, %s, directed := false
            ) r
            ORDER BY r.seq
            LIMIT 10
        """, (source, target))
        
        route = cur.fetchall()
        
        if route and len(route) > 0:
            print(f"✓ Consulta de ruteo exitosa: {len(route)} segmentos encontrados")
            print(f"  Costo total: {route[-1]['agg_cost']:.2f} metros")
            cur.close()
            return True
        else:
            print("⚠ Consulta ejecutada pero no encontró ruta")
            print("  Esto puede ser normal si los nodos no están conectados")
            cur.close()
            return True
            
    except Exception as e:
        print(f"✗ Error en consulta de ruteo: {e}")
        cur.close()
        return False


def check_threat_tables(conn):
    """Check threat tables."""
    print("\n" + "="*60)
    print("7. Verificando tablas de amenazas")
    print("="*60)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    threat_tables = {
        'rr.amenazas_waze': 'Amenazas Waze',
        'rr.amenazas_calming': 'Reductores de velocidad',
        'rr.amenazas_clima': 'Amenazas climáticas'
    }
    
    for table, description in threat_tables.items():
        schema, table_name = table.split('.')
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = %s 
                AND table_name = %s
            )
        """, (schema, table_name))
        
        table_exists = cur.fetchone() is not None
        
        if table_exists:
            cur.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cur.fetchone()['count']
            print(f"✓ {description}: {count:,} registros")
        else:
            print(f"⚠ {description}: tabla no existe")
    
    # Check if fail_prob column exists in ways table
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_schema = 'rr' 
            AND table_name = 'ways'
            AND column_name = 'fail_prob'
        )
    """)
    
    fail_prob_exists = cur.fetchone() is not None
    
    if fail_prob_exists:
        cur.execute("SELECT COUNT(*) as count FROM rr.ways WHERE fail_prob IS NOT NULL")
        count = cur.fetchone()['count']
        print(f"\n✓ Columna 'fail_prob' existe en rr.ways: {count:,} aristas con probabilidad")
        
        if count == 0:
            print("\n  NOTA: Para calcular probabilidades, ejecuta:")
            print("  python scripts/probability_model.py")
    else:
        print("\n✗ Columna 'fail_prob' NO existe en rr.ways")
        print("\nSOLUCIÓN:")
        print("  ALTER TABLE rr.ways ADD COLUMN fail_prob NUMERIC;")
    
    cur.close()


def main():
    """Run all diagnostic checks."""
    print("\n" + "="*60)
    print("DIAGNÓSTICO DE CONFIGURACIÓN DE RUTEO")
    print("="*60)
    
    # 1. Check database connection
    conn = check_database_connection()
    if not conn:
        print("\n❌ No se puede continuar sin conexión a la base de datos")
        sys.exit(1)
    
    # 2. Check extensions
    extensions_ok = check_extensions(conn)
    if not extensions_ok:
        print("\n❌ Extensiones faltantes. Instala PostGIS y pgRouting primero")
        conn.close()
        sys.exit(1)
    
    # 3. Check schema
    schema_ok = check_schema(conn)
    if not schema_ok:
        print("\n❌ Esquema 'rr' no existe. Ejecuta schema.sql primero")
        conn.close()
        sys.exit(1)
    
    # 4. Check tables
    tables_ok = check_tables(conn)
    
    # 5. Check topology
    topology_ok = check_topology(conn)
    
    # 6. Test routing
    if tables_ok and topology_ok:
        routing_ok = test_routing_query(conn)
    else:
        routing_ok = False
    
    # 7. Check threats
    check_threat_tables(conn)
    
    # Summary
    print("\n" + "="*60)
    print("RESUMEN")
    print("="*60)
    
    if tables_ok and topology_ok and routing_ok:
        print("✅ SISTEMA CONFIGURADO CORRECTAMENTE")
        print("\nEl sistema de ruteo debería funcionar correctamente.")
        print("Si aún tienes problemas, revisa los logs del servidor Flask.")
    else:
        print("❌ CONFIGURACIÓN INCOMPLETA")
        print("\nSigue las soluciones indicadas arriba para completar la configuración.")
    
    conn.close()


if __name__ == '__main__':
    main()
