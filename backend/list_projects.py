import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import AsyncSession

# Add the parent directory to the path so we can import the app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.project_service import ProjectService
from app.db.init_db_simple import get_async_db

async def list_all_projects():
    """List all projects with their fields"""
    
    # Get database session
    async for db in get_async_db():
        # Now we have a valid AsyncSession
        
        # Create project service
        project_service = ProjectService()
        
        # Get all projects
        projects = await project_service.list_projects(db)
        
        # Print project details
        print(f"Total projects found: {len(projects)}")
        
        for i, project in enumerate(projects):
            print(f"\n--- Project {i+1} ---")
            print(f"ID: {project.id}")
            print(f"Name: {project.name}")
            print(f"Description: {project.description}")
            print(f"Status: {project.status}")
            print(f"Team Size: {project.team_size}")
            print(f"Deadline: {project.deadline}")
            print(f"Goal: {project.goal}")
            print(f"Industry: {project.industry}")
            print(f"Budget: {project.budget}")
            print(f"Created at: {project.created_at}")
            print(f"Updated at: {project.updated_at}")
        
        # Break after one iteration as we only need one session
        break

if __name__ == "__main__":
    asyncio.run(list_all_projects())
