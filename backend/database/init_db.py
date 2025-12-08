from db_setup import ensure_schema, DB_NAME
import os

def init_db():
    # If we want to strictly re-initialize (reset), we might want to delete the file first.
    # But usually init_db just ensures tables exist. 
    # Since the user asked for a reset previously, let's strictly just ensure schema here 
    # to match the current logic of CREATE IF NOT EXISTS.
    # If a full wipe is needed, we should delete the file manually.
    
    print(f"Initializing database at {DB_NAME}...")
    ensure_schema()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()
