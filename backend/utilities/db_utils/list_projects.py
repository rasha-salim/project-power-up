"""
Script to list projects in the database
"""
import asyncio
from app.db.init_db_simple import get_async_db
from sqlalchemy import text

async def list_projects():
    """List all projects in the database"""
    async for db in get_async_db():
        try:
            result = await db.execute(text('SELECT id, name FROM projects LIMIT 5'))
            projects = result.fetchall()
            print("Available projects:")
            for project in projects:
                print(f"ID: {project[0]}, Name: {project[1]}")
            if not projects:
                print("No projects found in the database.")
        except Exception as e:
            print(f"Error listing projects: {str(e)}")

if __name__ == "__main__":
    asyncio.run(list_projects())
