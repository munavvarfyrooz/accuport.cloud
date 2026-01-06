"""
Database connection management for Accuport Dashboard
Supports both SQLite (local development) and PostgreSQL (Railway production)

Environment Variables:
- DATABASE_URL: PostgreSQL connection string (Railway provides this automatically)
- If not set, falls back to SQLite files
"""
import os
import sqlite3
from contextlib import contextmanager

# Check if we're using PostgreSQL (Railway sets DATABASE_URL)
DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    # Railway uses postgres:// but psycopg2 needs postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# SQLite database file paths (for local development)
ACCUBASE_DB = 'accubase.sqlite'
USERS_DB = 'users.sqlite'


class DictRow:
    """Wrapper to make PostgreSQL rows behave like sqlite3.Row"""
    def __init__(self, data):
        self._data = data if data else {}

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data.get(key)

    def keys(self):
        return self._data.keys()

    def __iter__(self):
        return iter(self._data.values())


def dict_from_row(row):
    """Convert database row to dictionary"""
    if row is None:
        return None
    if USE_POSTGRES:
        return dict(row) if row else None
    return dict(zip(row.keys(), row))


def list_from_rows(rows):
    """Convert list of database rows to list of dictionaries"""
    return [dict_from_row(row) for row in rows]


@contextmanager
def get_postgres_connection():
    """Get PostgreSQL connection"""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_postgres_cursor(conn=None):
    """Get PostgreSQL cursor with dict results"""
    if conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
        finally:
            cursor.close()
    else:
        with get_postgres_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cursor
                conn.commit()
            finally:
                cursor.close()


@contextmanager
def get_accubase_connection():
    """
    Get READ-ONLY connection to accubase database
    - PostgreSQL: Uses DATABASE_URL
    - SQLite: Uses accubase.sqlite in read-only mode
    """
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(readonly=True)
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(f'file:{ACCUBASE_DB}?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


@contextmanager
def get_accubase_write_connection():
    """
    Get READ-WRITE connection to accubase database
    Used for admin operations (creating vessels, etc.)
    """
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(ACCUBASE_DB)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


@contextmanager
def get_users_connection():
    """
    Get READ-WRITE connection to users database
    - PostgreSQL: Same database, different tables
    - SQLite: Separate users.sqlite file
    """
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(USERS_DB)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def execute_query(conn, query, params=None):
    """Execute a query and return results, handling both SQLite and PostgreSQL"""
    if USE_POSTGRES:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
    else:
        cursor = conn.cursor()

    # Convert SQLite ? placeholders to PostgreSQL %s
    if USE_POSTGRES and params:
        query = query.replace('?', '%s')

    cursor.execute(query, params or ())
    return cursor


def fetchall_as_dicts(cursor):
    """Fetch all results as list of dictionaries"""
    if USE_POSTGRES:
        return [dict(row) for row in cursor.fetchall()]
    else:
        return [dict(zip(row.keys(), row)) for row in cursor.fetchall()]


def fetchone_as_dict(cursor):
    """Fetch one result as dictionary"""
    row = cursor.fetchone()
    if row is None:
        return None
    if USE_POSTGRES:
        return dict(row)
    else:
        return dict(zip(row.keys(), row))
