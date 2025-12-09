import streamlit as st
import pandas as pd
import sys
import os
import plotly.express as px

# --- SETUP PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.append(BACKEND_DIR)

# Import Backend Services
from ingestion.ingest_assets import (
    ingest_new_asset,
    update_asset_data,
    update_all_assets,
    get_or_create_group,
    add_asset_to_group,
    DB_NAME
)

from data_service import (
    get_all_assets,
    get_all_groups,
    get_groups_for_asset,
    get_price_history,
    get_assets_in_group,
    get_available_assets_for_group,
    get_computed_metrics,
    get_group_metrics,
    get_asset_stats,
    get_group_stats,
    get_overview_data,
    create_group,
    delete_group,
    remove_asset_from_group
)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Korma Analytics", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SESSION STATE FOR NAVIGATION ---
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Overview'

if 'overview_view' not in st.session_state:
    st.session_state.overview_view = 'Assets'

def navigate_to(page):
    st.session_state.current_page = page


# --- HELPER FUNCTIONS ---

def format_overview_dataframe(df, view_type="Assets"):
    """
    Format the overview dataframe with multi-level column headers.
    Returns a styled dataframe ready for display.
    """
    if df.empty:
        return df
    
    # Timeframe label mapping
    tf_labels = {"1d": "Daily", "1w": "Weekly", "1m": "Monthly", "1q": "Quarterly", "1y": "Yearly"}
    
    # Build a new dataframe with renamed columns
    new_df = pd.DataFrame()
    
    # Info columns - ensure both views have same number of info columns for consistent widths
    if view_type == "Assets":
        new_df[("Asset Information", "Name")] = df.get("name", pd.Series(dtype=str))
        new_df[("Asset Information", "Symbol")] = df.get("symbol", pd.Series(dtype=str))
        new_df[("Asset Information", "Class")] = df.get("quoteType", pd.Series(dtype=str))
        new_df[("Asset Information", "Industry")] = df.get("industry", pd.Series(dtype=str))
        new_df[("Asset Information", "Sector")] = df.get("sector", pd.Series(dtype=str))
    else:
        # Groups view
        new_df[("Group Information", "Name")] = df.get("name", pd.Series(dtype=str))
        new_df[("Group Information", "Description")] = df.get("description", pd.Series(dtype=str)).fillna("—")
        new_df[("Group Information", "Count")] = df.get("constituents_count", pd.Series(dtype=int))
    
    # RV columns
    for tf_code, tf_label in tf_labels.items():
        col_name = f"rv_{tf_code}"
        if col_name in df.columns:
            new_df[("Realized Volatility", tf_label)] = df[col_name].apply(
                lambda x: f"{x*100:.2f}%" if pd.notnull(x) else "—"
            )
        else:
            new_df[("Realized Volatility", tf_label)] = "—"
    
    # Simple ATRP columns
    for tf_code, tf_label in tf_labels.items():
        col_name = f"satrp_{tf_code}"
        if col_name in df.columns:
            new_df[("Simple ATRP", tf_label)] = df[col_name].apply(
                lambda x: f"{x*100:.2f}%" if pd.notnull(x) else "—"
            )
        else:
            new_df[("Simple ATRP", tf_label)] = "—"
    
    # Real ATRP columns
    for tf_code, tf_label in tf_labels.items():
        col_name = f"ratrp_{tf_code}"
        if col_name in df.columns:
            new_df[("Real ATRP", tf_label)] = df[col_name].apply(
                lambda x: f"{x*100:.2f}%" if pd.notnull(x) else "—"
            )
        else:
            new_df[("Real ATRP", tf_label)] = "—"
    
    # Set multi-level columns
    new_df.columns = pd.MultiIndex.from_tuples(new_df.columns)
    
    return new_df



def render_distribution_analysis(stats_row, metrics_df, title_prefix="", timeframe="1d", metric_label="Return"):
    """Helper to render stats and histogram."""
    if stats_row is None or metrics_df.empty:
        st.warning("No distribution data available.")
        return

    st.markdown(f"### {title_prefix} — {metric_label}")
    
    def fmt_pct(val): return f"{val*100:.2f}%" if pd.notnull(val) else "—"
    def fmt_num(val): return f"{val:.4f}" if pd.notnull(val) else "—"

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Distribution Metrics**")
        s_data = {
            "Mean": fmt_pct(stats_row["mean"]),
            "Median": fmt_pct(stats_row["median"]),
            "Std Dev": fmt_pct(stats_row["std_dev"]),
            "Min": fmt_pct(stats_row["min_ret"]),
            "Max": fmt_pct(stats_row["max_ret"]),
        }
        st.dataframe(pd.DataFrame(s_data.items(), columns=["Metric", "Value"]), width='stretch', hide_index=True)

    with col2:
        st.markdown("**Shape & Coverage**")
        k_data = {
            "Skewness": fmt_num(stats_row["skewness"]),
            "Kurtosis": fmt_num(stats_row["kurtosis"]),
            "Count": str(int(stats_row["count"])),
            "Within 1σ": fmt_pct(stats_row["pct_1sigma"]),
            "Within 2σ": fmt_pct(stats_row["pct_2sigma"]),
            "Within 3σ": fmt_pct(stats_row["pct_3sigma"]),
        }
        st.dataframe(pd.DataFrame(k_data.items(), columns=["Metric", "Value"]), width='stretch', hide_index=True)

    # Histogram
    fig = px.histogram(
        metrics_df, 
        x="return_val", 
        nbins=50, 
        title=f"{metric_label} Distribution",
        labels={"return_val": f"{metric_label}"},
        histnorm='percent',
        color_discrete_sequence=['#3b82f6']
    )
    
    mean = stats_row["mean"]
    std = stats_row["std_dev"]
    if pd.notnull(mean) and pd.notnull(std):
        fig.add_vline(x=mean, line_dash="dash", line_color="#22c55e", annotation_text="Mean")
        fig.add_vline(x=mean + std, line_dash="dot", line_color="#ef4444", annotation_text="+1σ")
        fig.add_vline(x=mean - std, line_dash="dot", line_color="#ef4444", annotation_text="-1σ")
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    st.plotly_chart(fig, width='stretch')


# --- SIDEBAR ---
with st.sidebar:
    st.title("Korma Analytics")
    st.caption("Market Intelligence")
    
    st.divider()
    
    st.subheader("Navigation")
    
    nav_items = ["Overview", "Ingest Asset", "Asset Browser", "Group Management", "Group Metrics"]
    
    for page_name in nav_items:
        is_active = st.session_state.current_page == page_name
        if st.button(
            page_name,
            key=f"nav_{page_name}",
            width='stretch',
            type="primary" if is_active else "secondary"
        ):
            navigate_to(page_name)
            st.rerun()
    
    st.divider()
    
    st.subheader("Quick Actions")
    
    if st.button("Refresh Data", width='stretch', key="refresh_btn"):
        with st.spinner("Updating..."):
            try:
                update_all_assets()
                st.cache_data.clear()
                st.success("Done!")
            except Exception as e:
                st.error(f"Failed: {e}")
    
    if st.button("Run Compute", width='stretch', key="compute_btn"):
        with st.spinner("Computing..."):
            try:
                from compute.compute_engine import run_compute_job
                run_compute_job()
                st.cache_data.clear()
                st.success("Done!")
            except Exception as e:
                st.error(f"Failed: {e}")
    
    st.divider()
    
    st.caption(f"Database: {os.path.basename(DB_NAME)}")


# --- MAIN CONTENT ---

# PAGE: OVERVIEW
if st.session_state.current_page == "Overview":
    st.header("Analytics Overview")
    st.caption("Comprehensive volatility metrics across all assets and groups")
    
    # View Toggle
    col1, col2, col3 = st.columns([1, 1, 6])
    with col1:
        if st.button("Assets", width='stretch', 
                    type="primary" if st.session_state.overview_view == 'Assets' else "secondary",
                    key="assets_toggle"):
            st.session_state.overview_view = 'Assets'
            st.rerun()
    with col2:
        if st.button("Groups", width='stretch',
                    type="primary" if st.session_state.overview_view == 'Groups' else "secondary",
                    key="groups_toggle"):
            st.session_state.overview_view = 'Groups'
            st.rerun()
    
    view_type = st.session_state.overview_view
    
    # Fetch data
    with st.spinner(f"Loading {view_type.lower()}..."):
        df = get_overview_data(view_type)
    
    if df.empty:
        st.info("No data available. Please ingest assets and run the compute engine.")
    else:
        # Stats summary
        metric_cols = st.columns(4)
        with metric_cols[0]:
            st.metric("Total Records", len(df))
        
        if view_type == "Assets":
            with metric_cols[1]:
                unique_sectors = df['sector'].nunique() if 'sector' in df.columns else 0
                st.metric("Sectors", unique_sectors)
            with metric_cols[2]:
                unique_industries = df['industry'].nunique() if 'industry' in df.columns else 0
                st.metric("Industries", unique_industries)
        else:
            with metric_cols[1]:
                total_constituents = df['constituents_count'].sum() if 'constituents_count' in df.columns else 0
                st.metric("Total Constituents", int(total_constituents))
        
        st.divider()
        
        # Format dataframe with multi-level headers and display using native st.dataframe
        formatted_df = format_overview_dataframe(df, view_type)
        st.dataframe(formatted_df, use_container_width=True, hide_index=True)


# PAGE: INGEST ASSET
elif st.session_state.current_page == "Ingest Asset":
    st.header("Ingest Asset")
    st.caption("Add new assets or update existing ones in the database")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Asset Details")
        ticker = st.text_input("Ticker Symbol", placeholder="e.g., MSFT, AAPL").strip().upper()
    
    with col2:
        st.subheader("Group Assignment")
        existing_groups_df = get_all_groups()
        existing_group_list = existing_groups_df["name"].tolist() if not existing_groups_df.empty else []
        
        selected_groups = st.multiselect(
            "Assign to existing groups",
            options=existing_group_list,
            default=[]
        )
        
        new_groups_text = st.text_input("Create new groups (comma separated)", placeholder="e.g., Tech Leaders")
    
    st.divider()
    
    if st.button("Ingest Asset", type="primary"):
        if not ticker:
            st.warning("Please enter a ticker symbol.")
        else:
            final_groups = selected_groups.copy()
            if new_groups_text:
                final_groups.extend([g.strip() for g in new_groups_text.split(",") if g.strip()])
            
            with st.spinner(f"Processing {ticker}..."):
                try:
                    all_assets = get_all_assets()
                    if not all_assets.empty and ticker in all_assets["symbol"].values:
                        st.info(f"Asset {ticker} exists. Updating...")
                        update_asset_data(ticker)
                    else:
                        st.info(f"New asset {ticker}. Fetching data...")
                        ingest_new_asset(ticker)
                    
                    all_assets_refresh = get_all_assets()
                    row = all_assets_refresh[all_assets_refresh["symbol"] == ticker]
                    
                    if not row.empty:
                        asset_id = int(row.iloc[0]["asset_id"])
                        if final_groups:
                            for g_name in final_groups:
                                g_id = get_or_create_group(g_name)
                                add_asset_to_group(asset_id, g_id)
                    
                    st.success(f"Successfully processed {ticker}!")
                    st.cache_data.clear()
                    
                except Exception as e:
                    st.error(f"Error: {e}")


# PAGE: ASSET BROWSER
elif st.session_state.current_page == "Asset Browser":
    st.header("Asset Browser")
    st.caption("Explore individual asset data and analytics")
    
    assets_df = get_all_assets()
    
    if assets_df.empty:
        st.info("No assets in database. Please ingest some assets first.")
    else:
        st.metric("Total Assets", len(assets_df))
        
        selected_ticker = st.selectbox("Select Asset", assets_df["symbol"].tolist())
        
        if selected_ticker:
            row = assets_df[assets_df["symbol"] == selected_ticker].iloc[0]
            asset_id = int(row["asset_id"])
            
            st.divider()
            
            info_cols = st.columns(5)
            with info_cols[0]:
                st.markdown(f"**Name**\n\n{row['name']}")
            with info_cols[1]:
                st.markdown(f"**Symbol**\n\n{row['symbol']}")
            with info_cols[2]:
                st.markdown(f"**Sector**\n\n{row.get('sector', '—') or '—'}")
            with info_cols[3]:
                st.markdown(f"**Industry**\n\n{row.get('industry', '—') or '—'}")
            with info_cols[4]:
                current_groups = get_groups_for_asset(asset_id)
                st.markdown(f"**Groups**\n\n{', '.join(current_groups) if current_groups else '—'}")
            
            st.divider()
            
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["Price Chart", "Historical Data", "Returns", "Simple ATRP", "Real ATRP"])
            
            with tab1:
                hist_df = get_price_history(asset_id)
                if not hist_df.empty:
                    fig = px.line(hist_df, x="date", y="adj_close", 
                                 title=f"{row['symbol']} — Adjusted Close",
                                 color_discrete_sequence=['#3b82f6'])
                    fig.update_layout(
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                    )
                    st.plotly_chart(fig, width='stretch')
                else:
                    st.warning("No price history available.")
            
            with tab2:
                hist_df = get_price_history(asset_id)
                if not hist_df.empty:
                    st.dataframe(hist_df, width='stretch', hide_index=True)
                else:
                    st.warning("No historical data available.")
            
            tf_map = {"Daily": "1d", "Weekly": "1w", "Monthly": "1m", "Quarterly": "1q", "Yearly": "1y"}
            
            with tab3:
                sel_tf = st.selectbox("Timeframe", list(tf_map.keys()), key="ret_tf")
                tf_code = tf_map[sel_tf]
                metrics_df = get_computed_metrics(asset_id, timeframe=tf_code, metric_type="return")
                stats_row = get_asset_stats(asset_id, timeframe=tf_code, metric_type="return")
                if not metrics_df.empty and stats_row is not None:
                    render_distribution_analysis(stats_row, metrics_df, title_prefix=row['symbol'], timeframe=sel_tf, metric_label="Return")
                else:
                    st.info("No return metrics. Run compute engine.")
            
            with tab4:
                sel_tf_s = st.selectbox("Timeframe", list(tf_map.keys()), key="satrp_tf")
                tf_code_s = tf_map[sel_tf_s]
                metrics_df = get_computed_metrics(asset_id, timeframe=tf_code_s, metric_type="atrp_simple")
                stats_row = get_asset_stats(asset_id, timeframe=tf_code_s, metric_type="atrp_simple")
                if not metrics_df.empty and stats_row is not None:
                    render_distribution_analysis(stats_row, metrics_df, title_prefix=row['symbol'], timeframe=sel_tf_s, metric_label="Simple ATRP")
                else:
                    st.info("No Simple ATRP metrics. Run compute engine.")
            
            with tab5:
                sel_tf_r = st.selectbox("Timeframe", list(tf_map.keys()), key="ratrp_tf")
                tf_code_r = tf_map[sel_tf_r]
                metrics_df = get_computed_metrics(asset_id, timeframe=tf_code_r, metric_type="atrp_real")
                stats_row = get_asset_stats(asset_id, timeframe=tf_code_r, metric_type="atrp_real")
                if not metrics_df.empty and stats_row is not None:
                    render_distribution_analysis(stats_row, metrics_df, title_prefix=row['symbol'], timeframe=sel_tf_r, metric_label="Real ATRP")
                else:
                    st.info("No Real ATRP metrics. Run compute engine.")


# PAGE: GROUP MANAGEMENT
elif st.session_state.current_page == "Group Management":
    st.header("Group Management")
    st.caption("Create and manage asset groups for portfolio analysis")
    
    with st.expander("Create New Group", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_g_name = st.text_input("Group Name", placeholder="e.g., Tech Giants")
        with col2:
            new_g_desc = st.text_input("Description", placeholder="e.g., Large-cap tech")
        
        if st.button("Create Group", type="primary"):
            if new_g_name:
                success, msg = create_group(new_g_name, new_g_desc)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    
    st.divider()
    
    groups_df = get_all_groups()
    
    if not groups_df.empty:
        selected_g_name = st.selectbox("Select Group to Manage", groups_df["name"].tolist())
        
        if selected_g_name:
            g_row = groups_df[groups_df["name"] == selected_g_name].iloc[0]
            g_id = int(g_row["group_id"])
            
            st.subheader(selected_g_name)
            if g_row['description']:
                st.caption(g_row['description'])
            
            if st.button("Delete Group", type="secondary"):
                success, msg = delete_group(g_id)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            
            st.divider()
            
            in_group_df = get_assets_in_group(g_id)
            all_assets_df = get_all_assets()
            
            current_ids = in_group_df["asset_id"].tolist() if not in_group_df.empty else []
            current_symbols = in_group_df["symbol"].tolist() if not in_group_df.empty else []
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("#### Assets in Group")
                if current_symbols:
                    st.dataframe(in_group_df[["symbol", "name"]], width='stretch', hide_index=True)
                    to_remove = st.selectbox("Remove asset", current_symbols, key="rem_sel")
                    if st.button("Remove"):
                        aid = in_group_df[in_group_df["symbol"] == to_remove].iloc[0]["asset_id"]
                        if remove_asset_from_group(g_id, int(aid)):
                            st.success(f"Removed {to_remove}")
                            st.rerun()
                else:
                    st.info("No assets in this group.")
            
            with col_b:
                st.markdown("#### Add Assets")
                available = all_assets_df[~all_assets_df["asset_id"].isin(current_ids)]
                if not available.empty:
                    to_add = st.selectbox("Add asset", available["symbol"].tolist(), key="add_sel")
                    if st.button("Add"):
                        aid = available[available["symbol"] == to_add].iloc[0]["asset_id"]
                        add_asset_to_group(int(aid), g_id)
                        st.success(f"Added {to_add}")
                        st.rerun()
                else:
                    st.success("All assets are in this group.")
    else:
        st.info("No groups yet. Create one above!")


# PAGE: GROUP METRICS
elif st.session_state.current_page == "Group Metrics":
    st.header("Group Metrics")
    st.caption("Analyze aggregated performance across asset groups")
    
    groups_df = get_all_groups()
    
    if groups_df.empty:
        st.info("No groups available. Create groups first.")
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            target_group = st.selectbox("Select Group", groups_df["name"].tolist())
        with col2:
            tf_map = {"Daily": "1d", "Weekly": "1w", "Monthly": "1m", "Quarterly": "1q", "Yearly": "1y"}
            sel_tf = st.selectbox("Timeframe", list(tf_map.keys()), key="group_tf")
            tf_code = tf_map[sel_tf]
        
        if target_group:
            g_row = groups_df[groups_df["name"] == target_group].iloc[0]
            g_id = int(g_row["group_id"])
            
            st.divider()
            
            tab1, tab2, tab3, tab4 = st.tabs(["Time Series", "Returns", "Simple ATRP", "Real ATRP"])
            
            with tab1:
                st.markdown(f"### Average {sel_tf} Returns")
                if st.checkbox("Load Chart", key="load_chart"):
                    metrics_df_ts = get_group_metrics(g_id, timeframe=tf_code, metric_type="return")
                    if not metrics_df_ts.empty:
                        fig = px.bar(metrics_df_ts, x="date", y="return_val", 
                                    title=f"{target_group} — Avg {sel_tf} Returns",
                                    color_discrete_sequence=['#3b82f6'])
                        fig.update_layout(
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)',
                        )
                        st.plotly_chart(fig, width='stretch')
                    else:
                        st.warning("No data.")
            
            with tab2:
                metrics_df = get_group_metrics(g_id, timeframe=tf_code, metric_type="return")
                stats_row = get_group_stats(g_id, timeframe=tf_code, metric_type="return")
                if not metrics_df.empty and stats_row is not None:
                    render_distribution_analysis(stats_row, metrics_df, title_prefix=target_group, timeframe=sel_tf, metric_label="Return")
                else:
                    st.warning("No return metrics. Run compute engine.")
            
            with tab3:
                metrics_df = get_group_metrics(g_id, timeframe=tf_code, metric_type="atrp_simple")
                stats_row = get_group_stats(g_id, timeframe=tf_code, metric_type="atrp_simple")
                if not metrics_df.empty and stats_row is not None:
                    render_distribution_analysis(stats_row, metrics_df, title_prefix=target_group, timeframe=sel_tf, metric_label="Simple ATRP")
                else:
                    st.warning("No Simple ATRP metrics. Run compute engine.")
            
            with tab4:
                metrics_df = get_group_metrics(g_id, timeframe=tf_code, metric_type="atrp_real")
                stats_row = get_group_stats(g_id, timeframe=tf_code, metric_type="atrp_real")
                if not metrics_df.empty and stats_row is not None:
                    render_distribution_analysis(stats_row, metrics_df, title_prefix=target_group, timeframe=sel_tf, metric_label="Real ATRP")
                else:
                    st.warning("No Real ATRP metrics. Run compute engine.")
