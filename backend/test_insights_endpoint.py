import asyncio
from app.db.init_db_simple import get_async_db
from app.models.project import Project
from sqlalchemy import select
import json

async def test_insights_endpoint():
    print("Starting test...")
    try:
        async for db in get_async_db():
            print("Connected to database")
            # List all projects
            result = await db.execute(select(Project))
            projects = result.scalars().all()
            
            print(f"Found {len(projects)} projects in database:")
            for p in projects:
                print(f"\n  Project ID: {p.id}")
                print(f"  Name: {p.name}")
                print(f"  Status: {p.status}")
                print(f"  Has Insights: {bool(p.insights)}")
                
                if p.insights:
                    print(f"  Insights keys: {list(p.insights.keys())}")
                    if 'technical_analysis' in p.insights:
                        print("  ✓ Has technical_analysis")
                    if 'risk_assessment' in p.insights:
                        print("  ✓ Has risk_assessment")
                    if 'project_plan' in p.insights:
                        print("  ✓ Has project_plan")
            
            # Test the endpoint with a real project ID if available
            if projects and projects[0].id:
                import httpx
                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.get(f"http://localhost:8000/api/v1/projects/{projects[0].id}/insights")
                        print(f"\n\nTesting insights endpoint with project ID: {projects[0].id}")
                        print(f"Response status: {response.status_code}")
                        if response.status_code == 200:
                            data = response.json()
                            print(f"Response data: {json.dumps(data, indent=2)}")
                    except Exception as e:
                        print(f"Error testing endpoint: {e}")
            else:
                print("\nNo projects found in database to test with")
            
            break
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_insights_endpoint())
