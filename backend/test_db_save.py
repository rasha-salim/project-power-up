import asyncio
from app.db.init_db_simple import get_async_db
from sqlalchemy import select
from app.models.project import Project

async def check_latest_project():
    async for db in get_async_db():
        try:
            # Get the latest project
            result = await db.execute(
                select(Project).order_by(Project.created_at.desc()).limit(1)
            )
            project = result.scalar_one_or_none()NameError: name 'ConfigLoader' is not defined
            
            if project:
                print(f"Latest project: {project.name}")
                print(f"Project ID: {project.id}")
                print(f"Status: {project.status}")
                print(f"Has insights: {bool(project.insights)}")
                if project.insights:
                    print(f"Insights keys: {list(project.insights.keys())}")
                    # Check if it has the expected structure
                    if 'technical_analysis' in project.insights:
                        print("✓ Technical analysis found in insights")
                    if 'key_findings' in project.insights:
                        print("✓ Key findings found in insights")
            else:
                print("No projects found in database")
                
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(check_latest_project())
