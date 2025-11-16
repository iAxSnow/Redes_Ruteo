#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Diagnosis Script
Checks for locks, long-running queries, and index usage.
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
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            cursor_factory=RealDictCursor
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"✗ Could not connect to database: {e}", file=sys.stderr)
        sys.exit(1)

def check_locks(conn):
    """Checks for active locks that might block other queries."""
    print("\n--- Checking for Database Locks ---")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                activity.pid,
                activity.usename,
                activity.query,
                blocking.pid AS blocking_pid,
                blocking.query AS blocking_query,
                to_char(activity.query_start, 'YYYY-MM-DD HH24:MI:SS') as query_start
            FROM pg_stat_activity AS activity
            JOIN pg_stat_activity AS blocking ON blocking.pid = ANY(pg_blocking_pids(activity.pid));
        """)
        locks = cur.fetchall()
        if not locks:
            print("✓ No active blocking locks found.")
        else:
            print(f"⚠ Found {len(locks)} blocking lock(s):")
            for lock in locks:
                print(f"  - Blocked PID: {lock['pid']} by PID: {lock['blocking_pid']}")
                print(f"    Blocked Query: {lock['query'][:100]}...")
                print(f"    Blocking Query: {lock['blocking_query'][:100]}...")
    return not locks

def check_long_running_queries(conn):
    """Identifies queries running for more than 1 minute."""
    print("\n--- Checking for Long-Running Queries ( > 1 minute) ---")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                pid,
                usename,
                age(clock_timestamp(), query_start) AS duration,
                state,
                query
            FROM pg_stat_activity
            WHERE state <> 'idle' AND clock_timestamp() - query_start > interval '1 minute'
            ORDER BY duration DESC;
        """)
        long_queries = cur.fetchall()
        if not long_queries:
            print("✓ No queries running for more than 1 minute.")
        else:
            print(f"⚠ Found {len(long_queries)} long-running quer(y/ies):")
            for query in long_queries:
                print(f"  - PID: {query['pid']}, User: {query['usename']}, Duration: {query['duration']}")
                print(f"    State: {query['state']}")
                print(f"    Query: {query['query'][:150]}...")

def main():
    """Main execution function."""
    print("="*60)
    print("Database Diagnosis")
    print("="*60)
    
    conn = get_db_connection()
    
    all_ok = check_locks(conn)
    check_long_running_queries(conn)
    
    conn.close()
    
    if all_ok:
        print("\n✓ Diagnosis complete. No critical blocking issues found.")
    else:
        print("\n✗ Diagnosis complete. Potential blocking issues detected.")

if __name__ == "__main__":
    main()
