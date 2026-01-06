"""
Migration script: SQLite to PostgreSQL
Run this script to migrate data from SQLite to PostgreSQL on Railway.

Usage:
    DATABASE_URL=postgresql://... python migrate_to_postgres.py

The script will:
1. Create all tables in PostgreSQL
2. Migrate data from SQLite files
3. Set up sequences for auto-increment IDs
"""
import os
import sys
import sqlite3

# Check for DATABASE_URL
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    print("Usage: DATABASE_URL=postgresql://... python migrate_to_postgres.py")
    sys.exit(1)

import psycopg2
from psycopg2.extras import execute_values

# Fix Railway's postgres:// URL
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# SQLite paths
ACCUBASE_DB = 'accubase.sqlite'
USERS_DB = 'users.sqlite'

# PostgreSQL schema (combined from both SQLite databases)
SCHEMA = """
-- Drop existing tables (in order due to foreign keys)
DROP TABLE IF EXISTS alerts CASCADE;
DROP TABLE IF EXISTS measurements CASCADE;
DROP TABLE IF EXISTS parameter_limits CASCADE;
DROP TABLE IF EXISTS fetch_logs CASCADE;
DROP TABLE IF EXISTS sampling_points CASCADE;
DROP TABLE IF EXISTS parameters CASCADE;
DROP TABLE IF EXISTS admin_audit_log CASCADE;
DROP TABLE IF EXISTS manager_hierarchy CASCADE;
DROP TABLE IF EXISTS vessel_assignments CASCADE;
DROP TABLE IF EXISTS vessel_auth_tokens CASCADE;
DROP TABLE IF EXISTS vessel_details CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS vessels CASCADE;
DROP TABLE IF EXISTS users_parameter_limits CASCADE;

-- ACCUBASE TABLES --

CREATE TABLE vessels (
    id SERIAL PRIMARY KEY,
    vessel_id VARCHAR(50) NOT NULL UNIQUE,
    vessel_name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    labcom_account_id INTEGER,
    auth_token VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE parameters (
    id SERIAL PRIMARY KEY,
    labcom_parameter_id INTEGER,
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20),
    unit VARCHAR(50),
    ideal_low FLOAT,
    ideal_high FLOAT,
    category VARCHAR(50),
    criticality VARCHAR(20),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sampling_points (
    id SERIAL PRIMARY KEY,
    vessel_id INTEGER NOT NULL REFERENCES vessels(id),
    code VARCHAR(10) NOT NULL,
    name VARCHAR(100) NOT NULL,
    system_type VARCHAR(50),
    description TEXT,
    labcom_account_id INTEGER,
    is_active INTEGER DEFAULT 1,
    location_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vessel_id, code),
    UNIQUE(vessel_id, labcom_account_id)
);

CREATE TABLE fetch_logs (
    id SERIAL PRIMARY KEY,
    vessel_id INTEGER REFERENCES vessels(id),
    fetch_start TIMESTAMP NOT NULL,
    fetch_end TIMESTAMP,
    status VARCHAR(20),
    measurements_fetched INTEGER,
    measurements_new INTEGER,
    measurements_duplicate INTEGER,
    date_range_from TIMESTAMP,
    date_range_to TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE measurements (
    id SERIAL PRIMARY KEY,
    labcom_measurement_id INTEGER,
    vessel_id INTEGER NOT NULL REFERENCES vessels(id),
    sampling_point_id INTEGER REFERENCES sampling_points(id),
    parameter_id INTEGER NOT NULL REFERENCES parameters(id),
    value VARCHAR(50) NOT NULL,
    value_numeric FLOAT,
    unit VARCHAR(50),
    ideal_low FLOAT,
    ideal_high FLOAT,
    ideal_status VARCHAR(20),
    measurement_date TIMESTAMP NOT NULL,
    operator_name VARCHAR(100),
    device_serial VARCHAR(100),
    comment TEXT,
    is_valid INTEGER DEFAULT 1,
    sync_status VARCHAR(20),
    fetched_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE parameter_limits (
    id SERIAL PRIMARY KEY,
    sampling_point_id INTEGER NOT NULL REFERENCES sampling_points(id),
    parameter_id INTEGER NOT NULL REFERENCES parameters(id),
    ideal_low FLOAT,
    ideal_high FLOAT,
    warning_low FLOAT,
    warning_high FLOAT,
    critical_low FLOAT,
    critical_high FLOAT,
    effective_from TIMESTAMP,
    effective_to TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sampling_point_id, parameter_id, effective_from)
);

CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    measurement_id INTEGER NOT NULL REFERENCES measurements(id),
    vessel_id INTEGER NOT NULL REFERENCES vessels(id),
    sampling_point_id INTEGER REFERENCES sampling_points(id),
    parameter_id INTEGER NOT NULL REFERENCES parameters(id),
    alert_type VARCHAR(20) NOT NULL,
    alert_reason VARCHAR(50),
    measured_value FLOAT,
    expected_low FLOAT,
    expected_high FLOAT,
    alert_date TIMESTAMP NOT NULL,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- USERS TABLES --

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    role VARCHAR(20) NOT NULL CHECK(role IN ('vessel_manager', 'fleet_manager', 'admin', 'vessel_user')),
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vessel_assignments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    vessel_id INTEGER NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, vessel_id)
);

CREATE TABLE manager_hierarchy (
    id SERIAL PRIMARY KEY,
    fleet_manager_id INTEGER NOT NULL REFERENCES users(id),
    vessel_manager_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fleet_manager_id, vessel_manager_id)
);

CREATE TABLE vessel_auth_tokens (
    id SERIAL PRIMARY KEY,
    vessel_id INTEGER NOT NULL UNIQUE,
    auth_token VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    is_active INTEGER DEFAULT 1
);

CREATE TABLE admin_audit_log (
    id SERIAL PRIMARY KEY,
    admin_user_id INTEGER NOT NULL REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL,
    action_details TEXT,
    target_user_id INTEGER REFERENCES users(id),
    target_vessel_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vessel_details (
    id SERIAL PRIMARY KEY,
    vessel_id INTEGER NOT NULL UNIQUE,
    vessel_name TEXT,
    vessel_type TEXT,
    year_of_build INTEGER,
    imo_number TEXT,
    company_name TEXT,
    me1_make TEXT, me1_model TEXT, me1_serial TEXT, me1_system_oil TEXT, me1_cylinder_oil TEXT, me1_fuel1 TEXT, me1_fuel2 TEXT,
    me2_make TEXT, me2_model TEXT, me2_serial TEXT, me2_system_oil TEXT, me2_cylinder_oil TEXT, me2_fuel1 TEXT, me2_fuel2 TEXT,
    ae_system_oil TEXT, ae_fuel1 TEXT, ae_fuel2 TEXT,
    ae1_make TEXT, ae1_model TEXT, ae1_serial TEXT,
    ae2_make TEXT, ae2_model TEXT, ae2_serial TEXT,
    ae3_make TEXT, ae3_model TEXT, ae3_serial TEXT,
    boiler_system_oil TEXT, boiler_fuel1 TEXT, boiler_fuel2 TEXT,
    ab1_make TEXT, ab1_model TEXT, ab1_serial TEXT,
    ab2_make TEXT, ab2_model TEXT, ab2_serial TEXT,
    ege_make TEXT, ege_model TEXT, ege_serial TEXT,
    bwt_chemical_manufacturer TEXT, bwt_chemicals_in_use TEXT,
    cwt_chemical_manufacturer TEXT, cwt_chemicals_in_use TEXT,
    bwts_make TEXT, bwts_model TEXT, bwts_serial TEXT,
    egcs_make TEXT, egcs_model TEXT, egcs_serial TEXT, egcs_type TEXT,
    stp_make TEXT, stp_model TEXT, stp_serial TEXT, stp_capacity TEXT,
    hotwell_deha TEXT, hotwell_hydrazine TEXT, auth_token TEXT,
    me1_cylinder_oil_tbn TEXT, me1_fuel1_sulphur TEXT, me1_fuel2_sulphur TEXT, me1_fuel3 TEXT, me1_fuel3_sulphur TEXT,
    me2_cylinder_oil_tbn TEXT, me2_fuel1_sulphur TEXT, me2_fuel2_sulphur TEXT, me2_fuel3 TEXT, me2_fuel3_sulphur TEXT,
    ae_fuel1_sulphur TEXT, ae_fuel2_sulphur TEXT, ae_fuel3 TEXT, ae_fuel3_sulphur TEXT,
    bwtc1 TEXT, bwtc2 TEXT, bwtc3 TEXT, bwtc4 TEXT, bwtc5 TEXT,
    vessel_image TEXT, vessel_email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by_user_id INTEGER REFERENCES users(id)
);

CREATE TABLE users_parameter_limits (
    id SERIAL PRIMARY KEY,
    equipment_type TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    lower_limit REAL NOT NULL,
    upper_limit REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(equipment_type, parameter_name)
);

-- Create indexes for performance
CREATE INDEX idx_measurements_vessel ON measurements(vessel_id);
CREATE INDEX idx_measurements_date ON measurements(measurement_date);
CREATE INDEX idx_measurements_sampling_point ON measurements(sampling_point_id);
CREATE INDEX idx_alerts_vessel ON alerts(vessel_id);
CREATE INDEX idx_sampling_points_vessel ON sampling_points(vessel_id);
"""


def migrate_table(pg_conn, sqlite_conn, table_name, columns, pg_table=None):
    """Migrate data from SQLite table to PostgreSQL"""
    pg_table = pg_table or table_name
    print(f"  Migrating {table_name} -> {pg_table}...")

    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT {', '.join(columns)} FROM {table_name}")
    rows = cursor.fetchall()

    if not rows:
        print(f"    No data in {table_name}")
        return 0

    pg_cursor = pg_conn.cursor()

    # Build INSERT statement
    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = f"INSERT INTO {pg_table} ({', '.join(columns)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    for row in rows:
        try:
            pg_cursor.execute(insert_sql, row)
        except Exception as e:
            print(f"    Error inserting row: {e}")

    pg_conn.commit()
    print(f"    Migrated {len(rows)} rows")
    return len(rows)


def update_sequence(pg_conn, table_name, id_column='id'):
    """Update PostgreSQL sequence to max ID + 1"""
    cursor = pg_conn.cursor()
    cursor.execute(f"SELECT MAX({id_column}) FROM {table_name}")
    max_id = cursor.fetchone()[0]
    if max_id:
        cursor.execute(f"SELECT setval(pg_get_serial_sequence('{table_name}', '{id_column}'), {max_id})")
        pg_conn.commit()
        print(f"    Updated {table_name} sequence to {max_id}")


def main():
    print("=" * 60)
    print("Accuport SQLite to PostgreSQL Migration")
    print("=" * 60)

    # Connect to PostgreSQL
    print("\nConnecting to PostgreSQL...")
    pg_conn = psycopg2.connect(DATABASE_URL)
    print("Connected!")

    # Create schema
    print("\nCreating PostgreSQL schema...")
    pg_cursor = pg_conn.cursor()
    pg_cursor.execute(SCHEMA)
    pg_conn.commit()
    print("Schema created!")

    # Migrate ACCUBASE data
    print("\n--- Migrating ACCUBASE data ---")
    if os.path.exists(ACCUBASE_DB):
        accubase_conn = sqlite3.connect(ACCUBASE_DB)

        migrate_table(pg_conn, accubase_conn, 'vessels',
                     ['id', 'vessel_id', 'vessel_name', 'email', 'labcom_account_id', 'auth_token', 'created_at', 'updated_at'])
        update_sequence(pg_conn, 'vessels')

        migrate_table(pg_conn, accubase_conn, 'parameters',
                     ['id', 'labcom_parameter_id', 'name', 'symbol', 'unit', 'ideal_low', 'ideal_high', 'category', 'criticality', 'description', 'created_at', 'updated_at'])
        update_sequence(pg_conn, 'parameters')

        migrate_table(pg_conn, accubase_conn, 'sampling_points',
                     ['id', 'vessel_id', 'code', 'name', 'system_type', 'description', 'labcom_account_id', 'is_active', 'location_description', 'created_at', 'updated_at'])
        update_sequence(pg_conn, 'sampling_points')

        migrate_table(pg_conn, accubase_conn, 'fetch_logs',
                     ['id', 'vessel_id', 'fetch_start', 'fetch_end', 'status', 'measurements_fetched', 'measurements_new', 'measurements_duplicate', 'date_range_from', 'date_range_to', 'error_message', 'created_at'])
        update_sequence(pg_conn, 'fetch_logs')

        migrate_table(pg_conn, accubase_conn, 'measurements',
                     ['id', 'labcom_measurement_id', 'vessel_id', 'sampling_point_id', 'parameter_id', 'value', 'value_numeric', 'unit', 'ideal_low', 'ideal_high', 'ideal_status', 'measurement_date', 'operator_name', 'device_serial', 'comment', 'is_valid', 'sync_status', 'fetched_at', 'created_at'])
        update_sequence(pg_conn, 'measurements')

        migrate_table(pg_conn, accubase_conn, 'parameter_limits',
                     ['id', 'sampling_point_id', 'parameter_id', 'ideal_low', 'ideal_high', 'warning_low', 'warning_high', 'critical_low', 'critical_high', 'effective_from', 'effective_to', 'created_at', 'updated_at'])
        update_sequence(pg_conn, 'parameter_limits')

        migrate_table(pg_conn, accubase_conn, 'alerts',
                     ['id', 'measurement_id', 'vessel_id', 'sampling_point_id', 'parameter_id', 'alert_type', 'alert_reason', 'measured_value', 'expected_low', 'expected_high', 'alert_date', 'acknowledged_by', 'acknowledged_at', 'resolved_at', 'resolution_notes', 'created_at'])
        update_sequence(pg_conn, 'alerts')

        accubase_conn.close()
    else:
        print(f"  {ACCUBASE_DB} not found, skipping")

    # Migrate USERS data
    print("\n--- Migrating USERS data ---")
    if os.path.exists(USERS_DB):
        users_conn = sqlite3.connect(USERS_DB)

        migrate_table(pg_conn, users_conn, 'users',
                     ['id', 'username', 'password_hash', 'full_name', 'email', 'role', 'is_active', 'created_at', 'updated_at'])
        update_sequence(pg_conn, 'users')

        migrate_table(pg_conn, users_conn, 'vessel_assignments',
                     ['id', 'user_id', 'vessel_id', 'assigned_at'])
        update_sequence(pg_conn, 'vessel_assignments')

        migrate_table(pg_conn, users_conn, 'manager_hierarchy',
                     ['id', 'fleet_manager_id', 'vessel_manager_id', 'created_at'])
        update_sequence(pg_conn, 'manager_hierarchy')

        migrate_table(pg_conn, users_conn, 'vessel_auth_tokens',
                     ['id', 'vessel_id', 'auth_token', 'created_at', 'created_by', 'is_active'])
        update_sequence(pg_conn, 'vessel_auth_tokens')

        migrate_table(pg_conn, users_conn, 'admin_audit_log',
                     ['id', 'admin_user_id', 'action_type', 'action_details', 'target_user_id', 'target_vessel_id', 'created_at'])
        update_sequence(pg_conn, 'admin_audit_log')

        # vessel_details has many columns, get them dynamically
        cursor = users_conn.cursor()
        cursor.execute("PRAGMA table_info(vessel_details)")
        columns = [row[1] for row in cursor.fetchall()]
        migrate_table(pg_conn, users_conn, 'vessel_details', columns)
        update_sequence(pg_conn, 'vessel_details')

        # parameter_limits from users.sqlite -> users_parameter_limits
        migrate_table(pg_conn, users_conn, 'parameter_limits',
                     ['id', 'equipment_type', 'parameter_name', 'lower_limit', 'upper_limit', 'created_at'],
                     pg_table='users_parameter_limits')
        update_sequence(pg_conn, 'users_parameter_limits')

        users_conn.close()
    else:
        print(f"  {USERS_DB} not found, skipping")

    pg_conn.close()

    print("\n" + "=" * 60)
    print("Migration completed successfully!")
    print("=" * 60)


if __name__ == '__main__':
    main()
