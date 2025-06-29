"""
Simple script to get a project ID from the database
"""
import asyncio
from sqlalchemy import text
from app.db.init_db_simple import get_async_db

async def get_project_id():
    """Get a project ID from the database"""
    async for db in get_async_db():
        try:
            result = await db.execute(text("SELECT id FROM projects LIMIT 1"))
            return result.scalar()
        except Exception as e:
            print(f"Error getting project ID: {e}")
            return None

if __name__ == "__main__":
    project_id = asyncio.run(get_project_id())
    if project_id:
        print(f"Project ID: {project_id}")
    else:
        print("No projects found in the database")
