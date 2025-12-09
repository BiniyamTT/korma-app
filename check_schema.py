import sqlite3
import pandas as pd
import os

db_path = "backend/database/korma-db.sqlite"
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("PRAGMA table_info(historical_prices_adj)", conn)
    print(df)
    conn.close()
