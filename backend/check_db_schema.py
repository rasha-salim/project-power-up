import asyncio
import sys
import os
from sqlalchemy import inspect

# Add the parent directory to the path so we can import the app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.init_db_simple import async_engine

async def inspect_database():
    """Check the current database schema"""
    inspector = inspect(async_engine)
    
    print("Database Tables:")
    tables = await inspector.get_table_names()
    for table in tables:
        print(f"\n=== Table: {table} ===")
        
        columns = await inspector.get_columns(table)
        print("Columns:")
        for column in columns:
            print(f"  - {column['name']}: {column['type']}")

if __name__ == "__main__":
    asyncio.run(inspect_database())
