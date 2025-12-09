import sqlite3
import pandas as pd
import duckdb
import os
import streamlit as st

# Paths (Relative to this file or absolute)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # korma-app/backend/..
DB_PATH = os.path.join(BASE_DIR, "backend", "database", "korma-db.sqlite")
DUCK_DB_PATH = os.path.join(BASE_DIR, "backend", "compute", "korma-analytics.duckdb")
SQL_DIR = os.path.join(BASE_DIR, "backend", "sql")

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def read_sql_file(filename):
    path = os.path.join(SQL_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return f.read()
    return ""

# --- CORE FETCHERS ---

def get_all_assets():
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM assets ORDER BY symbol", conn)
    conn.close()
    return df

def get_all_groups():
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM groups ORDER BY name", conn)
    conn.close()
    return df

def get_groups_for_asset(asset_id):
    conn = get_db_connection()
    query = """
    SELECT g.name 
    FROM groups g
    JOIN group_assets ga ON g.group_id = ga.group_id
    WHERE ga.asset_id = ?
    """
    df = pd.read_sql(query, conn, params=(asset_id,))
    conn.close()
    return df["name"].tolist()

@st.cache_data(ttl=86400)
def get_price_history(asset_id):
    conn = get_db_connection()
    query = "SELECT date, open, high, low, close, adj_close, volume FROM historical_prices_adj WHERE asset_id = ? ORDER BY date DESC"
    df = pd.read_sql(query, conn, params=(asset_id,))
    conn.close()
    return df

def get_assets_in_group(group_id):
    conn = get_db_connection()
    query = """
        SELECT a.asset_id, a.symbol, a.name 
        FROM assets a 
        JOIN group_assets ga ON a.asset_id = ga.asset_id 
        WHERE ga.group_id = ?
    """
    df = pd.read_sql(query, conn, params=(group_id,))
    conn.close()
    return df

def get_available_assets_for_group(group_id):
    # This is logic-heavy, implies fetching all and filtering. 
    # Or strict SQL: SELECT * FROM assets WHERE asset_id NOT IN (SELECT asset_id FROM group_assets WHERE group_id=?)
    conn = get_db_connection()
    query = """
        SELECT asset_id, symbol, name 
        FROM assets 
        WHERE asset_id NOT IN (
            SELECT asset_id FROM group_assets WHERE group_id = ?
        )
    """
    df = pd.read_sql(query, conn, params=(group_id,))
    conn.close()
    return df

# --- DUCKDB ANALYTICS FETCHERS ---

@st.cache_data(ttl=86400)
def get_computed_metrics(asset_id, timeframe="1d", metric_type="return"):
    if not os.path.exists(DUCK_DB_PATH):
        return pd.DataFrame()
    
    tf_suffix = timeframe 
    mapping = {
        "return": f"return_{tf_suffix}",
        "atrp_simple": f"atrp_simple_{tf_suffix}",
        "atrp_real": f"atrp_real_{tf_suffix}"
    }
    col_name = mapping.get(metric_type, f"return_{tf_suffix}")

    try:
        conn = duckdb.connect(DUCK_DB_PATH, read_only=True)
        query = f"SELECT date, {col_name} as return_val FROM asset_metrics WHERE asset_id = ? ORDER BY date DESC"
        df = conn.execute(query, [asset_id]).fetchdf()
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def get_group_metrics(group_id, timeframe="1d", metric_type="return"):
    if not os.path.exists(DUCK_DB_PATH):
        return pd.DataFrame()
    
    mapping = {
        "return": f"avg_return_{timeframe}",
        "atrp_simple": f"avg_atrp_simple_{timeframe}",
        "atrp_real": f"avg_atrp_real_{timeframe}"
    }
    col_name = mapping.get(metric_type, f"avg_return_{timeframe}")
    
    try:
        conn = duckdb.connect(DUCK_DB_PATH, read_only=True)
        query = f"SELECT date, {col_name} as return_val, asset_count FROM group_metrics WHERE group_id = ? ORDER BY date DESC"
        df = conn.execute(query, [group_id]).fetchdf()
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def get_asset_stats(asset_id, timeframe="1d", metric_type="return"):
    if not os.path.exists(DUCK_DB_PATH):
        return None
    try:
        conn = duckdb.connect(DUCK_DB_PATH, read_only=True)
        query = "SELECT * FROM asset_stats WHERE asset_id = ? AND timeframe = ? AND metric_type = ?"
        df = conn.execute(query, [asset_id, timeframe, metric_type]).fetchdf()
        conn.close()
        return df.iloc[0] if not df.empty else None
    except Exception as e:
        return None

@st.cache_data(ttl=86400)
def get_group_stats(group_id, timeframe="1d", metric_type="return"):
    if not os.path.exists(DUCK_DB_PATH):
        return None
    try:
        conn = duckdb.connect(DUCK_DB_PATH, read_only=True)
        query = "SELECT * FROM group_stats WHERE group_id = ? AND timeframe = ? AND metric_type = ?"
        df = conn.execute(query, [group_id, timeframe, metric_type]).fetchdf()
        conn.close()
        return df.iloc[0] if not df.empty else None
    except Exception as e:
        return None

@st.cache_data(ttl=86400)
def get_overview_data(view_type="Assets"):
    if not os.path.exists(DUCK_DB_PATH):
        return pd.DataFrame()

    conn = duckdb.connect(DUCK_DB_PATH, read_only=True)
    
    if view_type == "Assets":
        sqlite_conn = get_db_connection()
        assets_base_df = pd.read_sql("SELECT asset_id, name, symbol, quoteType, industry, sector FROM assets", sqlite_conn)
        sqlite_conn.close()
        
        if assets_base_df.empty:
            conn.close()
            return pd.DataFrame()

        conn.register('assets_base_df', assets_base_df)
        query = read_sql_file("fetch_asset_overview.sql")
        if not query:
            conn.close()
            return pd.DataFrame()
            
        stats_df = conn.execute(query).fetchdf()
        final_df = pd.merge(assets_base_df, stats_df, on="asset_id", how="left")
        final_df = final_df.drop(columns=["asset_id"])
        return final_df

    elif view_type == "Groups":
        sqlite_conn = get_db_connection()
        groups_base_df = pd.read_sql("""
            SELECT g.group_id, g.name, g.description, COUNT(ga.asset_id) as constituents_count
            FROM groups g
            LEFT JOIN group_assets ga ON g.group_id = ga.group_id
            GROUP BY g.group_id
        """, sqlite_conn)
        sqlite_conn.close()

        if groups_base_df.empty:
            conn.close()
            return pd.DataFrame()
        
        conn.register('groups_base_df', groups_base_df)
        query = read_sql_file("fetch_group_overview.sql")
        if not query:
            conn.close()
            return pd.DataFrame()

        stats_df = conn.execute(query).fetchdf()
        final_df = pd.merge(groups_base_df, stats_df, on="group_id", how="left")
        final_df = final_df.drop(columns=["group_id"])
        return final_df
    
    conn.close()
    return pd.DataFrame()

# --- CRUD HELPERS ---

def create_group(name, desc=""):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO groups (name, description, is_public) VALUES (?, ?, 0)", (name, desc))
        conn.commit()
        return True, f"Created group '{name}'"
    except Exception as e:
        return False, f"Failed: {e}"
    finally:
        conn.close()

def delete_group(group_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM group_assets WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM groups WHERE group_id = ?", (group_id,))
        conn.commit()
        return True, "Deleted group"
    except Exception as e:
        return False, f"Failed: {e}"
    finally:
        conn.close()

def remove_asset_from_group(group_id, asset_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM group_assets WHERE group_id = ? AND asset_id = ?", (group_id, asset_id))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False
