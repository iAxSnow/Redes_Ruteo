#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kill Active DB Queries Script
Terminates all active connections to the specified database to resolve locks.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Database configuration from environment variables
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDATABASE", "rr")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASS = os.getenv("PGPASSWORD", "postgres")

def get_db_connection():
    """Creates and returns a database connection."""
    try:
        # Connect to the default 'postgres' database to manage other connections
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname="postgres",
            user=DB_USER,
            password=DB_PASS,
            cursor_factory=RealDictCursor
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"✗ Could not connect to database: {e}", file=sys.stderr)
        sys.exit(1)

def terminate_active_connections(conn, db_name):
    """Terminates all active connections to a specific database."""
    print(f"\n--- Terminating active connections to database '{db_name}' ---")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s
              AND pid <> pg_backend_pid()
              AND state = 'active';
        """, (db_name,))
        
        terminated = cur.rowcount
        if terminated > 0:
            print(f"✓ Successfully sent termination signal to {terminated} active process(es).")
        else:
            print("✓ No active processes found to terminate.")
        conn.commit()

def main():
    """Main execution function."""
    print("="*60)
    print(f"Terminating active queries for database: {DB_NAME}")
    print("="*60)
    
    conn = get_db_connection()
    
    terminate_active_connections(conn, DB_NAME)
    
    conn.close()
    
    print("\n✓ Operation complete.")

if __name__ == "__main__":
    main()
