import sqlite3
import logging

import os
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "korma-db.sqlite")

def ensure_schema():
    """Ensures the database schema exists."""
    logger = logging.getLogger("korma_ingest")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")

    # Assets table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        name TEXT,
        shortName TEXT,
        exchange TEXT,
        fullExchangeName TEXT,
        currency TEXT,
        quoteType TEXT,
        sector TEXT,
        industry TEXT,
        country TEXT,
        market TEXT,
        firstTradeDate INTEGER,
        website TEXT,
        irWebsite TEXT,
        status TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Historical prices table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS historical_prices_adj (
        price_id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        adj_close REAL,
        volume INTEGER,
        source TEXT,
        ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(asset_id) REFERENCES assets(asset_id)
    );
    """)

    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Groups table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        created_by INTEGER,
        is_public BOOLEAN DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(created_by) REFERENCES users(user_id)
    );
    """)

    # Group Assets (Junction) table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS group_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        asset_id INTEGER NOT NULL,
        added_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(group_id) REFERENCES groups(group_id),
        FOREIGN KEY(asset_id) REFERENCES assets(asset_id)
    );
    """)

    # Indexes
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_hpa_asset_date ON historical_prices_adj(asset_id, date);")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_hpa_unique ON historical_prices_adj(asset_id, date, source);")
    
    # Indexes for new tables
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_group_assets_unique ON group_assets(group_id, asset_id);")

    conn.commit()
    conn.close()
    logger.debug("Schema check complete.")
