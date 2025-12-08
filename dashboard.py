import streamlit as st
import pandas as pd
import sqlite3
import sys
import os
import plotly.express as px

import duckdb

# --- SETUP PATHS ---
# Add backend directory to sys.path to allow imports
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
DUCK_DB_PATH = os.path.join(BACKEND_DIR, "compute", "korma-analytics.duckdb")
sys.path.append(BACKEND_DIR)

# Import existing backend logic
from ingestion.ingest_assets import (
    ingest_new_asset,
    update_asset_data,
    update_all_assets,
    delete_asset,
    get_or_create_group,
    add_asset_to_group,
    DB_NAME
)

# --- CONFIG ---
st.set_page_config(page_title="Korma Admin", page_icon="📈", layout="wide")

# --- HELPERS ---
def get_db_connection():
    return sqlite3.connect(DB_NAME)

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


# ----------------------------------------
# DATA FETCHING HELPERS
# ----------------------------------------

@st.cache_data(ttl=86400)
def get_computed_metrics(asset_id, timeframe="1d"):
    """Fetches computed metrics for a specific timeframe."""
    if not os.path.exists(DUCK_DB_PATH):
        return pd.DataFrame()
    
    col_map = {
        "1d": "return_1d", "1w": "return_1w", "1m": "return_1m", 
        "1q": "return_1q", "1y": "return_1y"
    }
    col_name = col_map.get(timeframe, "return_1d")
    
    try:
        conn = duckdb.connect(DUCK_DB_PATH, read_only=True)
        # Select specific return column
        query = f"SELECT date, {col_name} as return_val FROM asset_metrics WHERE asset_id = ? ORDER BY date DESC"
        df = conn.execute(query, [asset_id]).fetchdf()
        conn.close()
        return df
    except Exception as e:
        st.error(f"DuckDB Error: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=86400)
def get_group_metrics(group_id, timeframe="1d"):
    """Fetches group metrics for specific timeframe."""
    if not os.path.exists(DUCK_DB_PATH):
        return pd.DataFrame()
    
    col_map = {
        "1d": "avg_return_1d", "1w": "avg_return_1w", "1m": "avg_return_1m", 
        "1q": "avg_return_1q", "1y": "avg_return_1y"
    }
    col_name = col_map.get(timeframe, "avg_return_1d")
    
    try:
        conn = duckdb.connect(DUCK_DB_PATH, read_only=True)
        query = f"SELECT date, {col_name} as return_val, asset_count FROM group_metrics WHERE group_id = ? ORDER BY date DESC"
        df = conn.execute(query, [group_id]).fetchdf()
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()


@st.cache_data(ttl=86400)
def get_asset_stats(asset_id, timeframe="1d"):
    """Fetches stats for a specific asset and timeframe."""
    if not os.path.exists(DUCK_DB_PATH):
        return None
    try:
        conn = duckdb.connect(DUCK_DB_PATH, read_only=True)
        # Filter by timeframe
        query = "SELECT * FROM asset_stats WHERE asset_id = ? AND timeframe = ?"
        df = conn.execute(query, [asset_id, timeframe]).fetchdf()
        conn.close()
        return df.iloc[0] if not df.empty else None
    except Exception as e:
        return None


@st.cache_data(ttl=86400)
def get_group_stats(group_id, timeframe="1d"):
    """Fetches stats for a specific group and timeframe."""
    if not os.path.exists(DUCK_DB_PATH):
        return None
    try:
        conn = duckdb.connect(DUCK_DB_PATH, read_only=True)
        query = "SELECT * FROM group_stats WHERE group_id = ? AND timeframe = ?"
        df = conn.execute(query, [group_id, timeframe]).fetchdf()
        conn.close()
        return df.iloc[0] if not df.empty else None
    except Exception as e:
        return None


def render_distribution_analysis(stats_row, metrics_df, title_prefix="", timeframe="1d"):
    """Helper to render stats and histogram."""
    if stats_row is None or metrics_df.empty:
        st.warning("No distribution data available.")
        return

    st.subheader(f"{title_prefix} Statistics ({timeframe})")
    
    def fmt_pct(val): return f"{val*100:.2f}%" if pd.notnull(val) else "-"
    def fmt_num(val): return f"{val:.4f}" if pd.notnull(val) else "-"

    col1, col2 = st.columns(2)
    with col1:
        s_data = {
            "Mean": fmt_pct(stats_row["mean"]),
            "Median": fmt_pct(stats_row["median"]),
            "Std Dev": fmt_pct(stats_row["std_dev"]),
            "Min": fmt_pct(stats_row["min_ret"]),
            "Max": fmt_pct(stats_row["max_ret"]),
        }
        st.dataframe(pd.DataFrame(s_data.items(), columns=["Metric", "Value"]), width='stretch')

    with col2:
        k_data = {
            "Skewness": fmt_num(stats_row["skewness"]),
            "Kurtosis": fmt_num(stats_row["kurtosis"]),
            "Count": str(int(stats_row["count"])),
            "Within 1σ": fmt_pct(stats_row["pct_1sigma"]),
            "Within 2σ": fmt_pct(stats_row["pct_2sigma"]),
            "Within 3σ": fmt_pct(stats_row["pct_3sigma"]),
        }
        st.dataframe(pd.DataFrame(k_data.items(), columns=["Metric", "Value"]), width='stretch')

    st.subheader(f"{title_prefix} Distribution ({timeframe})")
    fig = px.histogram(
        metrics_df, 
        x="return_val", 
        nbins=50, 
        title=f"Return Distribution ({timeframe})",
        labels={"return_val": f"Return ({timeframe})"},
        histnorm='percent'
    )
    mean = stats_row["mean"]
    std = stats_row["std_dev"]
    if pd.notnull(mean) and pd.notnull(std):
        fig.add_vline(x=mean, line_dash="dash", line_color="green", annotation_text="Mean")
        fig.add_vline(x=mean + std, line_dash="dot", line_color="red", annotation_text="+1σ")
        fig.add_vline(x=mean - std, line_dash="dot", line_color="red", annotation_text="-1σ")
    
    st.plotly_chart(fig, width='stretch')


def create_group(name, desc=""):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO groups (name, description, is_public) VALUES (?, ?, 0)", (name, desc))
        conn.commit()
        st.success(f"Created group '{name}'")
    except Exception as e:
        st.error(f"Failed: {e}")
    finally:
        conn.close()

def delete_group(group_id):
    conn = get_db_connection()
    try:
        # Cascade delete from junction table
        conn.execute("DELETE FROM group_assets WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM groups WHERE group_id = ?", (group_id,))
        conn.commit()
        st.success("Deleted group")
    except Exception as e:
        st.error(f"Failed: {e}")
    finally:
        conn.close()

def remove_asset_from_group(group_id, asset_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM group_assets WHERE group_id = ? AND asset_id = ?", (group_id, asset_id))
    conn.commit()
    conn.close()

# --- SIDEBAR: NAVIGATION & GLOBAL ACTIONS ---
st.sidebar.title("Korma Admin 🚀")
st.sidebar.markdown("---")

# Navigation
page = st.sidebar.radio("Navigation", 
    ["🆕 Ingest Asset", "📂 Asset Browser", "📊 Groups Management", "📈 Group Metrics"]
)

st.sidebar.markdown("---")

if st.sidebar.button("🔄 Update ALL Assets"):
    with st.spinner("Running global update..."):
        try:
            update_all_assets()
            st.cache_data.clear()
            st.sidebar.success("Global update triggered & cache cleared!")
        except Exception as e:
            st.sidebar.error(f"Update failed: {e}")

if st.sidebar.button("🧮 Run Compute Engine"):
    with st.spinner("Calculating metrics..."):
        try:
            from compute.compute_engine import run_compute_job
            run_compute_job()
            st.cache_data.clear()
            st.sidebar.success("Compute Complete! Cache cleared.")
        except Exception as e:
            st.sidebar.error(f"Compute failed: {e}")

st.sidebar.markdown("---")
st.sidebar.info(f"Database: `{os.path.basename(DB_NAME)}`")


# --- PAGE: INGESTION ---
if page == "🆕 Ingest Asset":
    st.header("Ingest New Asset")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        ticker = st.text_input("Ticker Symbol (e.g. MSFT)", "").strip().upper()
    
    with col2:
        # Fetch existing groups for easy selection
        existing_groups_df = get_all_groups()
        existing_group_list = existing_groups_df["name"].tolist() if not existing_groups_df.empty else []
        
        selected_groups = st.multiselect(
            "Assign to Groups (Type to create new)",
            options=existing_group_list,
            default=[]
        )
        
        # User might want to type a brand new group that isn't in the list
        new_groups_text = st.text_input("Or add NEW groups (comma separated)", "")

    if st.button("🚀 Ingest / Update Asset", type="primary"):
        if not ticker:
            st.warning("Please enter a ticker.")
        else:
            # Merge existing and new groups
            final_groups = selected_groups.copy()
            if new_groups_text:
                final_groups.extend([g.strip() for g in new_groups_text.split(",") if g.strip()])
            
            with st.spinner(f"Ingesting {ticker}..."):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT asset_id FROM assets WHERE symbol = ?", (ticker,))
                    row = cursor.fetchone()
                    conn.close()
                    
                    asset_id = None
                    if row:
                        st.info(f"Asset {ticker} found. Updating prices...")
                        update_asset_data(ticker)
                        asset_id = row[0]
                    else:
                        st.info(f"Asset {ticker} is NEW. Fetching full history...")
                        ingest_new_asset(ticker) 
                        
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT asset_id FROM assets WHERE symbol = ?", (ticker,))
                        row_new = cursor.fetchone()
                        conn.close()
                        if row_new:
                            asset_id = row_new[0]
                    
                    # Add Groups
                    if asset_id and final_groups:
                        st.write(f"Linking groups: {final_groups}")
                        for g_name in final_groups:
                            g_id = get_or_create_group(g_name)
                            add_asset_to_group(asset_id, g_id)
                    
                    st.success(f"✅ Successfully processed {ticker}!")
                    
                except Exception as e:
                    st.error(f"Error: {e}")

# --- PAGE: ASSET BROWSER ---
elif page == "📂 Asset Browser":
    st.header("Asset Browser")
    
    assets_df = get_all_assets()
    
    if assets_df.empty:
        st.info("No assets in database.")
    else:
        # Simple stats
        st.metric("Total Assets", len(assets_df))
        
        # Selection
        selected_ticker_row = st.selectbox("Select Asset to Inspect", assets_df["symbol"])
        
        if selected_ticker_row:
            row = assets_df[assets_df["symbol"] == selected_ticker_row].iloc[0]
            asset_id = int(row["asset_id"])
            
            # Details Column
            c1, c2 = st.columns([1, 2])
            
            with c1:
                st.subheader(row["name"])
                st.write(f"**Symbol:** {row['symbol']}")
                st.write(f"**Sector:** {row['sector']}")
                st.write(f"**Industry:** {row['industry']}")
                st.write(f"**First Trade:** {row['firstTradeDate']}")
                
                current_groups = get_groups_for_asset(asset_id)
                st.write(f"**Groups:** {', '.join(current_groups) if current_groups else 'None'}")
                
            with c2:
                # Main Views: Chart vs Table vs Analytics
                view_tab1, view_tab2, view_tab3 = st.tabs(["📈 Price Chart", "🔢 Historical Data", "📊 Analytics"])
                
                with st.spinner("Loading price history..."):
                    hist_df = get_price_history(asset_id)
                    
                    with view_tab1: # Price Chart (Unchanged)
                        if not hist_df.empty:
                            fig = px.line(hist_df, x="date", y="adj_close", title=f"{row['symbol']} Price History (Adj Close)")
                            st.plotly_chart(fig, width='stretch')
                        else:
                            st.warning("No price history found.")
                            
                    with view_tab2: # Table (Unchanged)
                        if not hist_df.empty:
                            st.dataframe(hist_df, width='stretch')
                        else:
                            st.warning("No price history found.")
                            
                    with view_tab3: # Analytics (UPDATED)
                        # Timeframe Selector
                        tf_map = {"Daily": "1d", "Weekly": "1w", "Monthly": "1m", "Quarterly": "1q", "Yearly": "1y"}
                        sel_tf = st.selectbox("Select Timeframe", list(tf_map.keys()), key="asset_tf")
                        tf_code = tf_map[sel_tf]
                        
                        metrics_df = get_computed_metrics(asset_id, timeframe=tf_code)
                        stats_row = get_asset_stats(asset_id, timeframe=tf_code)
                        
                        if not metrics_df.empty and stats_row is not None:
                            render_distribution_analysis(stats_row, metrics_df, title_prefix=f"{row['symbol']}", timeframe=sel_tf)
                        else:
                            st.info("No metrics found. Run Compute Engine.")

# --- PAGE: GROUPS MANAGEMENT ---
elif page == "📊 Groups Management":
    st.header("Group Management")
    
    # 1. Create Group
    with st.expander("➕ Create New Group"):
        new_g_name = st.text_input("Group Name")
        new_g_desc = st.text_input("Description")
        if st.button("Create Group"):
            if new_g_name:
                create_group(new_g_name, new_g_desc)
                st.rerun()

    groups_df = get_all_groups()
    
    if not groups_df.empty:
        # Select Group to Manage
        g_names = groups_df["name"].tolist()
        selected_g_name = st.selectbox("Select Group to Manage", g_names)
        
        if selected_g_name:
            # Get ID
            g_row = groups_df[groups_df["name"] == selected_g_name].iloc[0]
            g_id = int(g_row["group_id"])
            
            st.subheader(f"Managing: {selected_g_name}")
            st.write(f"_{g_row['description']}_")
            
            # Delete Button
            if st.button("🗑️ Delete Group", type="primary"):
                delete_group(g_id)
                st.rerun()
            
            st.markdown("---")
            
            # Manage Assets
            conn = get_db_connection()
            # Get assets IN group
            in_group_df = pd.read_sql("""
                SELECT a.asset_id, a.symbol, a.name 
                FROM assets a 
                JOIN group_assets ga ON a.asset_id = ga.asset_id 
                WHERE ga.group_id = ?
            """, conn, params=(g_id,))
            
            # Get All assets (for adding)
            all_assets_df = pd.read_sql("SELECT asset_id, symbol, name FROM assets", conn)
            conn.close()
            
            current_ids = in_group_df["asset_id"].tolist()
            current_symbols = in_group_df["symbol"].tolist()
            current_names = in_group_df["name"].tolist()

            col_a, col_b = st.columns(2)
            
            with col_a:
                st.write("### Assets in Group")
                if current_symbols:
                    st.dataframe(in_group_df)
                    # Remove functionality
                    to_remove = st.selectbox("Remove Asset", current_symbols, key="rem_sel")
                    if st.button("Remove"):
                        # Find ID
                        aid = in_group_df[in_group_df["symbol"] == to_remove].iloc[0]["asset_id"]
                        remove_asset_from_group(g_id, int(aid))
                        st.success(f"Removed {to_remove}")
                        st.rerun()
                else:
                    st.info("No assets in this group.")

            with col_b:
                st.write("### Add Asset")
                # Filter out already added
                available = all_assets_df[~all_assets_df["asset_id"].isin(current_ids)]
                if not available.empty:
                    to_add = st.selectbox("Select Asset to Add", available["symbol"].tolist(), key="add_sel")
                    if st.button("Add to Group"):
                        aid = available[available["symbol"] == to_add].iloc[0]["asset_id"]
                        add_asset_to_group(int(aid), g_id)
                        st.success(f"Added {to_add}")
                        st.rerun()
                else:
                    st.success("All available assets are in this group.")


# --- PAGE: GROUP METRICS ---
elif page == "📈 Group Metrics":
    st.header("Group Market Analytics")
    
    groups_df = get_all_groups()
    if groups_df.empty:
        st.info("No groups found.")
    else:
        g_names = groups_df["name"].tolist()
        col_g1, col_g2 = st.columns([2, 1])
        with col_g1:
            target_group = st.selectbox("Select Group", g_names)
        with col_g2:
            tf_map = {"Daily": "1d", "Weekly": "1w", "Monthly": "1m", "Quarterly": "1q", "Yearly": "1y"}
            sel_tf = st.selectbox("Select Timeframe", list(tf_map.keys()), key="group_tf")
            tf_code = tf_map[sel_tf]
        
        if target_group:
            g_row = groups_df[groups_df["name"] == target_group].iloc[0]
            g_id = int(g_row["group_id"])
            
            metrics_df = get_group_metrics(g_id, timeframe=tf_code)
            stats_row = get_group_stats(g_id, timeframe=tf_code)
            
            if not metrics_df.empty and stats_row is not None:
                # Tabs
                g_tab1, g_tab2 = st.tabs(["TimeSeries", "Distribution"])
                
                with g_tab1:
                     st.subheader(f"Average {sel_tf} Return (Equal Weighted)")
                     fig = px.bar(metrics_df, x="date", y="return_val", title=f"{target_group} Avg {sel_tf} Returns")
                     st.plotly_chart(fig, width='stretch')
                
                with g_tab2:
                    render_distribution_analysis(stats_row, metrics_df, title_prefix=f"{target_group}", timeframe=sel_tf)
            else:
                st.warning("No metrics. Run Compute Engine.")
