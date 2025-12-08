import sqlite3
import requests
import yfinance as yf
from datetime import datetime, timedelta, date, timezone
import time
import logging
import sys
import os

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logging_utils.log_config import setup_logging
from database.db_setup import ensure_schema, DB_NAME

# --- LOGGING SETUP ---
logger = setup_logging()

# --- DB HELPERS ---

def get_db_connection():
    return sqlite3.connect(DB_NAME)

def is_symbol_in_db(symbol):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT asset_id FROM assets WHERE symbol = ?", (symbol,))
    row = cursor.fetchone()
    conn.close()
    return bool(row)

def get_asset_id(symbol):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT asset_id FROM assets WHERE symbol = ?", (symbol,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ValueError(f"❌ Asset not found in DB: {symbol}")
    return row[0]

def get_last_price_date(asset_id):
    """Returns the latest date (as a date object) from historical_prices_adj for the given asset."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(date) FROM historical_prices_adj WHERE asset_id = ?", (asset_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0]:
        return datetime.strptime(row[0], "%Y-%m-%d").date()
    return None

def insert_asset_info(asset):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO assets (
            symbol, name, shortName, exchange, fullExchangeName,
            currency, quoteType, sector, industry, country, market,
            firstTradeDate, website, irWebsite, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        asset["symbol"], asset["name"], asset["shortName"], asset["exchange"],
        asset["fullExchangeName"], asset["currency"], asset["quoteType"],
        asset["sector"], asset["industry"], asset["country"], asset["market"],
        asset["firstTradeDate"], asset["website"], asset["irWebsite"], asset["status"],
    ))
    conn.commit()
    conn.close()

def insert_prices(asset_id, rows):
    if not rows:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    
    ingested_at = datetime.now(timezone.utc).isoformat()
    
    for r in rows:
        cursor.execute("""
            INSERT OR IGNORE INTO historical_prices_adj (
                asset_id, date, open, high, low, close, adj_close,
                volume, source, ingested_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            asset_id, r["date"], r["open"], r["high"], r["low"],
            r["close"], r["adj_close"], r["volume"], "yahoo", ingested_at
        ))
    conn.commit()
    conn.close()
    logger.info(f"✅ Inserted {len(rows)} rows for asset_id {asset_id}")

# --- YAHOO DATA FETCHERS ---

def get_symbol_info(symbol):
    try:
        ticker_data = yf.Ticker(symbol)
        info = ticker_data.info
        if not info or "symbol" not in info:
            logger.error(f"❌ Invalid ticker or no data returned for {symbol}.")
            return None
        return info
    except Exception as e:
        logger.error(f"❌ Error fetching info for {symbol}: {e}")
        return None

def extract_asset_info(info: dict):
    first_trade_date = None
    if info.get("firstTradeDateMilliseconds"):
        first_trade_date = datetime.fromtimestamp(info.get("firstTradeDateMilliseconds") / 1000, timezone.utc).date()
        
    return {
        "symbol": info.get("symbol"),
        "name": info.get("longName"),
        "shortName": info.get("shortName"),
        "exchange": info.get("exchange"),
        "fullExchangeName": info.get("fullExchangeName"),
        "currency": info.get("currency"),
        "quoteType": info.get("quoteType") or info.get("typeDisp"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "country": info.get("country"),
        "market": info.get("market"),
        "firstTradeDate": first_trade_date,
        "website": info.get("website"),
        "irWebsite": info.get("irWebsite"),
        "status": "active",
    }

def parse_price_payload(data):
    """
    Parses Yahoo chart JSON.
    Drops the last data point ONLY if the last timestamp matches today's date (UTC).
    """
    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    adjclose = result["indicators"]["adjclose"][0]["adjclose"]
    
    open_ = quote["open"]
    high = quote["high"]
    low = quote["low"]
    close = quote["close"]
    volume = quote["volume"]

    rows = []
    total_points = len(timestamps)
    
    # Check if the last point is today
    if total_points > 0:
        last_ts = timestamps[-1]
        last_date = datetime.fromtimestamp(last_ts, timezone.utc).date()
        today = datetime.now(timezone.utc).date()
        
        if last_date == today:
            logger.debug(f"Dropping last data point (partial day): {last_date}")
            total_points -= 1  # Drop the last point
            
    for i in range(total_points):
        # Skip if any value is None (sometimes happens with Yahoo data)
        if open_[i] is None or close[i] is None:
            logger.debug(f"⚠️ Dropping row at index {i} due to None values. Date: {datetime.fromtimestamp(timestamps[i], timezone.utc).date()}")
            continue
            
        rows.append({
            "date": datetime.fromtimestamp(timestamps[i], timezone.utc).date(),
            "open": open_[i],
            "high": high[i],
            "low": low[i],
            "close": close[i],
            "adj_close": adjclose[i],
            "volume": volume[i],
        })
    return rows

def make_yahoo_request(url, retries=3):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for attempt in range(retries):
        try:
            logger.debug(f"🔎 Fetching (Attempt {attempt+1}/{retries}): {url}")
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                data = r.json()
                if data.get("chart", {}).get("result"):
                    return data
            elif r.status_code == 429:
                logger.warning(f"⚠️ Rate limited (429). Waiting before retry...")
                time.sleep(2 * (attempt + 1))
            else:
                logger.warning(f"⚠️ Status {r.status_code} from {url}")
        except Exception as e:
            logger.error(f"⚠️ Failed: {e}")
        
        if attempt < retries - 1:
            time.sleep(1) # Base wait between retries
            
    logger.error(f"❌ Failed to fetch {url} after {retries} attempts.")
    return None

def fetch_full_history(symbol):
    """Fetches max history (1000y) for a new asset."""
    urls = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1000y&interval=1d",
        f"https://query1.finance.yahoo.com/v7/finance/chart/{symbol}?range=1000y&interval=1d",
    ]
    for url in urls:
        data = make_yahoo_request(url)
        if data:
            return data
    raise RuntimeError("❌ All Yahoo endpoints failed for full history.")

def fetch_incremental_history(symbol, start_ts, end_ts):
    """Fetches history between two timestamps."""
    p1 = int(start_ts)
    p2 = int(end_ts)
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={p1}&period2={p2}&interval=1d"
    data = make_yahoo_request(url)
    if data:
        return data
    else:
        logger.warning(f"⚠️ Could not fetch incremental data for {symbol}")
        return None


def get_or_create_group(group_name):
    """Gets existing group ID or creates a new group."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if exists
    cursor.execute("SELECT group_id FROM groups WHERE name = ?", (group_name,))
    row = cursor.fetchone()
    
    if row:
        group_id = row[0]
        # logger.info(f"ℹ️ Found existing group: {group_name} (ID: {group_id})")
    else:
        # Create new
        cursor.execute("INSERT INTO groups (name, is_public) VALUES (?, 0)", (group_name,))
        group_id = cursor.lastrowid
        conn.commit()
        logger.info(f"🆕 Created new group: {group_name} (ID: {group_id})")
    
    conn.close()
    return group_id

def add_asset_to_group(asset_id, group_id):
    """Links an asset to a group if not already linked."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO group_assets (group_id, asset_id)
            VALUES (?, ?)
        """, (group_id, asset_id))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"🔗 Linked Asset ID {asset_id} to Group ID {group_id}")
    except Exception as e:
        logger.error(f"❌ Failed to link asset to group: {e}")
    finally:
        conn.close()

# --- WORKFLOW FUNCTIONS ---

def ingest_new_asset(symbol, groups=None):
    logger.info(f"\n🆕 Starting NEW ingestion for {symbol}...")
    
    # 1. Get Info & Insert Asset
    info = get_symbol_info(symbol)
    if not info:
        return
    asset_data = extract_asset_info(info)
    insert_asset_info(asset_data)
    logger.info(f"✅ Created asset record for {symbol}")
    
    # 2. Get ID & Fetch Full History
    asset_id = get_asset_id(symbol)
    
    # 3. Handle Groups (if provided)
    if groups:
        logger.info(f"🏷️ Processing groups: {groups}")
        for g_name in groups:
            g_id = get_or_create_group(g_name.strip())
            add_asset_to_group(asset_id, g_id)
            
    # 4. Fetch & Insert Prices
    raw_data = fetch_full_history(symbol)
    parsed_rows = parse_price_payload(raw_data)
    insert_prices(asset_id, parsed_rows)

def update_asset_data(symbol):
    logger.info(f"\n🔄 Starting UPDATE for {symbol}...")
    
    asset_id = get_asset_id(symbol)
    last_date = get_last_price_date(asset_id)
    
    if not last_date:
        logger.warning("⚠️ No existing price data found. Running full ingestion instead.")
        raw_data = fetch_full_history(symbol)
        parsed_rows = parse_price_payload(raw_data)
        insert_prices(asset_id, parsed_rows)
        return

    # Calculate periods
    start_date = last_date + timedelta(days=1)
    end_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    
    start_ts = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp()
    end_ts_dt = end_date + timedelta(days=1)
    end_ts = datetime.combine(end_ts_dt, datetime.min.time(), tzinfo=timezone.utc).timestamp()

    if start_ts >= end_ts:
        logger.info(f"✅ Data is already up to date (Last: {last_date}, Target End: {end_date})")
        return

    logger.info(f"📅 Fetching data from {start_date} to {end_date}")
    
    raw_data = fetch_incremental_history(symbol, start_ts, end_ts)
    if raw_data:
        parsed_rows = parse_price_payload(raw_data)
        insert_prices(asset_id, parsed_rows)

def update_all_assets():
    """Updates all assets currently in the database."""
    logger.info("\n🚀 Starting GLOBAL UPDATE for all assets...\n")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT symbol FROM assets")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        logger.warning("⚠️ No assets found in the database.")
        return

    total = len(rows)
    logger.info(f"Found {total} assets to update.")

    for i, row in enumerate(rows):
        symbol = row[0]
        logger.info(f"\n[{i+1}/{total}] Processing {symbol}...")
        try:
            update_asset_data(symbol)
            time.sleep(1) 
        except Exception as e:
            logger.error(f"❌ Failed to update {symbol}: {e}")
            
    logger.info("\n✅ Global update complete.")

# --- CRUD / UTILS ---

def delete_asset(symbol):
    """Deletes an asset and all its history with confirmation."""
    if not is_symbol_in_db(symbol):
        logger.warning(f"⚠️ {symbol} not found.")
        return

    confirm = input(f"⚠️ Are you sure you want to DELETE {symbol} and ALL its history? Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        logger.info("❌ Deletion cancelled.")
        return

    asset_id = get_asset_id(symbol)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Delete prices
    cursor.execute("DELETE FROM historical_prices_adj WHERE asset_id = ?", (asset_id,))
    deleted_prices = cursor.rowcount
    
    # 2. Delete asset
    cursor.execute("DELETE FROM assets WHERE asset_id = ?", (asset_id,))
    deleted_asset = cursor.rowcount
    
    conn.commit()
    conn.close()
    logger.info(f"🗑️ Deleted {symbol}: {deleted_asset} asset record, {deleted_prices} price rows.")

def read_asset_data(symbols):
    """Reads asset info and latest price for given symbols. Returns a dict."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row # Enable dict-like access
    cursor = conn.cursor()
    
    results = {}
    for sym in symbols:
        # Get Asset Info
        cursor.execute("SELECT * FROM assets WHERE symbol = ?", (sym,))
        asset_row = cursor.fetchone()
        
        if not asset_row:
            results[sym] = "Not found"
            continue
            
        asset_id = asset_row["asset_id"]
        
        # Get Latest Price
        cursor.execute("""
            SELECT * FROM historical_prices_adj 
            WHERE asset_id = ? 
            ORDER BY date DESC LIMIT 1
        """, (asset_id,))
        price_row = cursor.fetchone()
        
        results[sym] = {
            "info": dict(asset_row),
            "latest_price": dict(price_row) if price_row else None
        }
    
    conn.close()
    return results

def main():
    ensure_schema()
    
    print("\n--- ASSET INGESTION TOOL (MODULAR) ---\n")
    print("Commands:")
    print("  - Enter a TICKER to ingest/update a single asset (e.g. AAPL)")
    print("  - Optionally, specify GROUPS separated by commas: TICKER, Group1, Group2")
    print("    Example: MSFT, S&P500, Tech, AI")
    print("  - Enter 'UPDATE_ALL' to update all existing assets")
    print("  - Enter 'DELETE <TICKER>' to delete an asset")
    
    user_input = input("\nEnter command: ").strip()
    if not user_input:
        return

    # Handle UPDATE_ALL
    if user_input.upper() == "UPDATE_ALL":
        update_all_assets()
        return

    # Handle DELETE
    if user_input.upper().startswith("DELETE "):
        symbol_to_delete = user_input.split(" ")[1].upper()
        delete_asset(symbol_to_delete)
        return

    # Handle INGEST / UPDATE
    # Parse input: "MSFT, S&P500, Tech" -> symbol="MSFT", groups=["S&P500", "Tech"]
    parts = [p.strip() for p in user_input.split(",")]
    symbol = parts[0].upper()
    groups = parts[1:] if len(parts) > 1 else None

    if is_symbol_in_db(symbol):
        # Even if updating, we might want to Add groups?
        # For now, just update data. Logic can be expanded later to just add groups.
        if groups:
            logger.info(f"ℹ️ Asset {symbol} exists. Adding to new groups: {groups}")
            asset_id = get_asset_id(symbol)
            for g in groups:
                gid = get_or_create_group(g)
                add_asset_to_group(asset_id, gid)
        
        update_asset_data(symbol)
    else:
        ingest_new_asset(symbol, groups=groups)

if __name__ == "__main__":
    main()
