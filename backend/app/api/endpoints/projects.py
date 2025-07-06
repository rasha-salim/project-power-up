from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging
import uuid
import os
from app.db.init_db_simple import get_async_db
from app.models.project import Project, ProjectCreate, ProjectUpdate, ProjectResponse
from app.services.project_service import ProjectService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_create: ProjectCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Create a new project
    """
    try:
        project_service = ProjectService()
        project = await project_service.create_project(db, project_create)
        
        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
            team_size=project.team_size,
            deadline=project.deadline,
            goal=project.goal,
            industry=project.industry,
            budget=project.budget,
            planning_status=project.planning_status,
            brief_sections=project.brief_sections,
            generated_documents=project.generated_documents,
            created_at=project.created_at,
            updated_at=project.updated_at,
            message="Project created successfully"
        )
        
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating project: {str(e)}")

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get project details by ID
    """
    try:
        project_service = ProjectService()
        project = await project_service.get_project(db, project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
            team_size=project.team_size,
            deadline=project.deadline,
            goal=project.goal,
            industry=project.industry,
            budget=project.budget,
            insights=project.insights,
            planning_status=project.planning_status,
            brief_sections=project.brief_sections,
            generated_documents=project.generated_documents,
            created_at=project.created_at,
            updated_at=project.updated_at,
            message="Project retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving project: {str(e)}")

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_async_db)
):
    """
    List all projects
    """
    try:
        logger.info("Starting list_projects request")
        project_service = ProjectService()
        
        logger.info("Calling project_service.list_projects")
        projects = await project_service.list_projects(db)
        logger.info(f"Retrieved {len(projects)} projects from database")
        
        # Handle empty case
        if not projects:
            logger.info("No projects found, returning empty list")
            return []
        
        # Convert projects to response format
        result = []
        for project in projects:
            logger.debug(f"Processing project: {project.id}")
            project_response = ProjectResponse(
                id=project.id,
                name=project.name,
                description=project.description,
                status=project.status,
                team_size=project.team_size,
                deadline=project.deadline,
                goal=project.goal,
                industry=project.industry,
                budget=project.budget,
                insights=project.insights,
                planning_status=project.planning_status,
                brief_sections=project.brief_sections,
                generated_documents=project.generated_documents,
                created_at=project.created_at,
                updated_at=project.updated_at,
                message="Project retrieved successfully"
            )
            result.append(project_response)
        
        logger.info(f"Successfully processed {len(result)} projects")
        return result
        
    except Exception as e:
        logger.error(f"Error listing projects: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Railway ENV: {os.getenv('RAILWAY_ENVIRONMENT')}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error listing projects: {str(e)}")

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Update a project by ID
    """
    try:
        project_service = ProjectService()
        project = await project_service.get_project(db, project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        updated_project = await project_service.update_project(db, project_id, project_update)
        
        return ProjectResponse(
            id=updated_project.id,
            name=updated_project.name,
            description=updated_project.description,
            status=updated_project.status,
            team_size=updated_project.team_size,
            deadline=updated_project.deadline,
            goal=updated_project.goal,
            industry=updated_project.industry,
            budget=updated_project.budget,
            insights=updated_project.insights,
            planning_status=updated_project.planning_status,
            brief_sections=updated_project.brief_sections,
            generated_documents=updated_project.generated_documents,
            created_at=updated_project.created_at,
            updated_at=updated_project.updated_at,
            message="Project updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating project: {str(e)}")

@router.delete("/{project_id}", response_model=ProjectResponse)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Delete a project by ID
    """
    try:
        project_service = ProjectService()
        project = await project_service.get_project(db, project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        await project_service.delete_project(db, project_id)
        
        return ProjectResponse(
            id=project_id,
            name=project.name,
            status="deleted",
            message="Project deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting project: {str(e)}")

@router.post("/{project_id}/analyze", response_model=ProjectResponse)
async def analyze_project(
    project_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Trigger AI agent analysis for a project
    """
    try:
        project_service = ProjectService()
        project = await project_service.get_project(db, project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        # Update project status to indicate analysis is in progress
        project_update = ProjectUpdate(status="analyzing")
        updated_project = await project_service.update_project(db, project_id, project_update)
        
        # Trigger agent analysis in background
        # This will be implemented with CrewAI
        await project_service.trigger_agent_analysis(db, project_id)
        
        return ProjectResponse(
            id=updated_project.id,
            name=updated_project.name,
            description=updated_project.description,
            status=updated_project.status,
            team_size=updated_project.team_size,
            deadline=updated_project.deadline,
            goal=updated_project.goal,
            industry=updated_project.industry,
            budget=updated_project.budget,
            insights=updated_project.insights,
            planning_status=updated_project.planning_status,
            brief_sections=updated_project.brief_sections,
            generated_documents=updated_project.generated_documents,
            created_at=updated_project.created_at,
            updated_at=updated_project.updated_at,
            message="Project analysis started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting project analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting project analysis: {str(e)}")

@router.get("/{project_id}/insights")
async def get_project_insights(
    project_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get project insights from analysis
    """
    try:
        project_service = ProjectService()
        project = await project_service.get_project(db, project_id)
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Return insights data in the format expected by frontend
        response = {
            "status": project.status,
            "insights": project.insights if project.insights else None
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving project insights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving project insights: {str(e)}")
