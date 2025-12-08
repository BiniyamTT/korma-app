import duckdb
import os
import logging
import sys

# Setup basic logging locally for compute engine
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("korma_compute")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "database", "korma-db.sqlite")
DUCK_DB_PATH = os.path.join(BASE_DIR, "compute", "korma-analytics.duckdb")
SQL_DIR = os.path.join(BASE_DIR, "sql")

def verify_paths():
    if not os.path.exists(SQLITE_DB_PATH):
        raise FileNotFoundError(f"SQLite DB not found at: {SQLITE_DB_PATH}")
    logger.info(f"Targeting SQLite DB: {SQLITE_DB_PATH}")
    logger.info(f"Persisting DuckDB at: {DUCK_DB_PATH}")

def load_sql(filename):
    path = os.path.join(SQL_DIR, filename)
    with open(path, "r") as f:
        return f.read()

def compute_asset_metrics(conn):
    logger.info("Computing asset metrics (1d, 1w, 1m, 1q, 1y)...")
    sql = load_sql("compute_asset_metrics.sql")
    conn.execute(sql)
    
    # Validation
    row_count = conn.execute("SELECT COUNT(*) FROM asset_metrics").fetchone()[0]
    logger.info(f"✅ Asset Metrics Computed. Rows: {row_count}")

def compute_group_metrics(conn):
    logger.info("Computing group metrics...")
    sql = load_sql("compute_group_metrics.sql")
    conn.execute(sql)
    
    # Validation
    row_count = conn.execute("SELECT COUNT(*) FROM group_metrics").fetchone()[0]
    logger.info(f"✅ Group Metrics Computed. Rows: {row_count}")

def compute_stats(conn):
    logger.info("Computing distribution statistics (Asset & Group)...")
    
    # Asset Stats
    conn.execute(load_sql("compute_asset_stats.sql"))
    ac = conn.execute("SELECT COUNT(*) FROM asset_stats").fetchone()[0]
    
    # Group Stats
    conn.execute(load_sql("compute_group_stats.sql"))
    gc = conn.execute("SELECT COUNT(*) FROM group_stats").fetchone()[0]
    
    logger.info(f"✅ Stats Computed. Assets: {ac}, Groups: {gc}")

def run_compute_job():
    """
    Main entry point for the compute engine.
    """
    verify_paths()
    
    conn = duckdb.connect(DUCK_DB_PATH)
    
    try:
        # 1. Install & Attach
        logger.info("Initializing DuckDB...")
        conn.execute("INSTALL sqlite; LOAD sqlite;")
        conn.execute(f"ATTACH '{SQLITE_DB_PATH}' AS raw_db (TYPE SQLITE, READ_ONLY);")
        
        # 2. Run Computations
        compute_asset_metrics(conn)
        compute_group_metrics(conn)
        compute_stats(conn)
        
    except Exception as e:
        logger.error(f"Compute job failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    run_compute_job()
