import asyncio
import json
from app.db.init_db_simple import get_async_db
from app.services.project_service import ProjectService
from app.models.project import ProjectCreate, ProjectUpdate
import sys

# Force output to be unbuffered
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

async def create_test_project():
    """Create a test project with insights data"""
    
    # Also write to a log file
    with open("test_project_log.txt", "w") as log_file:
        def log(message):
            print(message)
            log_file.write(message + "\n")
            log_file.flush()
        
        # Sample insights data structure
        test_insights = {
            "technical_analysis": {
                "architecture": "Microservices architecture with React frontend and Python/FastAPI backend",
                "tech_stack": {
                    "frontend": ["React", "TypeScript", "Tailwind CSS"],
                    "backend": ["Python", "FastAPI", "SQLAlchemy"],
                    "database": ["PostgreSQL"],
                    "infrastructure": ["Docker", "Kubernetes"]
                },
                "complexity_score": 7.5,
                "maintainability_score": 8.2,
                "scalability_score": 9.0,
                "performance_score": 7.8,
                "security_score": 8.5
            },
            "risk_assessment": {
                "overall_risk_level": "Medium",
                "key_risks": [
                    {
                        "name": "Technical Complexity",
                        "impact": 8,
                        "probability": 6,
                        "level": "High",
                        "mitigation": "Implement comprehensive testing and documentation"
                    },
                    {
                        "name": "Resource Availability", 
                        "impact": 7,
                        "probability": 5,
                        "level": "Medium",
                        "mitigation": "Cross-train team members and maintain buffer"
                    },
                    {
                        "name": "Timeline Constraints",
                        "impact": 6,
                        "probability": 4,
                        "level": "Low",
                        "mitigation": "Build in schedule buffers and prioritize features"
                    }
                ],
                "mitigation_strategies": [
                    "Implement comprehensive testing and documentation",
                    "Cross-train team members and maintain buffer",
                    "Build in schedule buffers and prioritize features",
                    "Regular stakeholder communication and feedback loops",
                    "Establish clear project governance and decision-making processes"
                ]
            },
            "project_plan": {
                "timeline": "6 months",
                "phases": [
                    {"name": "Planning", "duration": "2 weeks", "progress": 100},
                    {"name": "Design", "duration": "3 weeks", "progress": 80},
                    {"name": "Development", "duration": "3 months", "progress": 45},
                    {"name": "Testing", "duration": "1 month", "progress": 0},
                    {"name": "Deployment", "duration": "2 weeks", "progress": 0}
                ],
                "resource_requirements": {
                    "frontend_developers": 2,
                    "backend_developers": 3,
                    "devops": 1,
                    "qa": 2,
                    "project_manager": 1
                },
                "effort_distribution": [
                    {"phase": "Planning", "effort": 10},
                    {"phase": "Design", "effort": 15},
                    {"phase": "Development", "effort": 50},
                    {"phase": "Testing", "effort": 20},
                    {"phase": "Deployment", "effort": 5}
                ],
                "milestones": [
                    {"name": "Project Kickoff", "date": "2024-01-15", "status": "completed"},
                    {"name": "Design Approval", "date": "2024-02-05", "status": "in_progress"},
                    {"name": "MVP Release", "date": "2024-04-30", "status": "upcoming"},
                    {"name": "Beta Testing", "date": "2024-05-31", "status": "upcoming"},
                    {"name": "Production Launch", "date": "2024-06-30", "status": "upcoming"}
                ],
                "estimated_cost": 250000
            }
        }
        
        async for db in get_async_db():
            try:
                project_service = ProjectService()
                
                # Create a new project
                project_data = ProjectCreate(
                    name="Test Project with Insights",
                    description="A test project to demonstrate the insights dashboard functionality"
                )
                
                project = await project_service.create_project(db, project_data)
                print(f"Created project with ID: {project.id}")
                print(f"Project name: {project.name}")
                print(f"Navigate to: http://localhost:3000/projects/{project.id}")
                
                log(f"Created project: {project.id} - {project.name}")
                
                # Update project with insights
                update_data = ProjectUpdate(
                    status="completed",
                    insights=test_insights
                )
                
                updated_project = await project_service.update_project(db, project.id, update_data)
                log(f"Updated project with insights. Status: {updated_project.status}")
                
                # Test the insights endpoint
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://localhost:8000/api/v1/projects/{project.id}/insights")
                    log(f"\nTesting insights endpoint:")
                    log(f"Status: {response.status_code}")
                    if response.status_code == 200:
                        data = response.json()
                        log(f"Response has insights: {'insights' in data}")
                        log(f"Response status: {data.get('status')}")
                        if data.get('insights'):
                            log(f"Insights keys: {list(data['insights'].keys())}")
                    
                log(f"\nProject created successfully!")
                log(f"Project ID: {project.id}")
                log(f"You can now view the insights at: http://localhost:3000/projects/{project.id}")
                
            except Exception as e:
                log(f"Error: {e}")
                import traceback
                traceback.print_exc()
            
            break

if __name__ == "__main__":
    asyncio.run(create_test_project())
