from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import logging
from app.db.init_db_simple import get_async_db
from app.services.agent_service import AgentService
from app.services.agent_service_v2 import AgentServiceV2
from app.models.agent import AgentResponse, AgentTask

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/status", response_model=List[AgentResponse])
async def get_agents_status(
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get the status of all AI agents
    """
    try:
        agent_service = AgentService()
        agents_status = await agent_service.get_agents_status(db)
        
        return [
            AgentResponse(
                id=agent["id"],
                name=agent["name"],
                role=agent["role"],
                status=agent["status"],
                last_active=agent["last_active"],
                message="Agent status retrieved successfully"
            ) for agent in agents_status
        ]
        
    except Exception as e:
        logger.error(f"Error retrieving agents status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving agents status: {str(e)}")

@router.post("/task", response_model=AgentResponse)
async def create_agent_task(
    background_tasks: BackgroundTasks,
    task: AgentTask,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Create a new task for an AI agent
    """
    try:
        agent_service = AgentService()
        
        # Validate agent exists
        agent = await agent_service.get_agent(db, task.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Create task
        task_result = await agent_service.create_agent_task(db, task)
        
        # Execute task in background
        background_tasks.add_task(
            agent_service.execute_agent_task,
            task_id=task_result["task_id"],
            db=db
        )
        
        return AgentResponse(
            id=agent["id"],
            name=agent["name"],
            role=agent["role"],
            status="processing",
            message=f"Task created successfully. Task ID: {task_result['task_id']}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating agent task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating agent task: {str(e)}")

@router.get("/task/{task_id}", response_model=Dict[str, Any])
async def get_task_result(
    task_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get the result of an agent task
    """
    try:
        agent_service = AgentService()
        task_result = await agent_service.get_task_result(db, task_id)
        
        if not task_result:
            raise HTTPException(status_code=404, detail="Task not found")
            
        return task_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving task result: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving task result: {str(e)}")

@router.post("/crew/analyze/{project_id}", response_model=Dict[str, Any])
async def start_crew_analysis(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Start a full crew analysis for a project
    """
    try:
        agent_service = AgentService()
        
        # Validate project exists
        # This would typically be done by checking with the project service
        
        # Start crew analysis
        analysis_id = await agent_service.start_crew_analysis(db, project_id)
        
        # Execute analysis in background
        background_tasks.add_task(
            agent_service.execute_crew_analysis,
            analysis_id=analysis_id,
            project_id=project_id,
            db=db
        )
        
        return {
            "analysis_id": analysis_id,
            "project_id": project_id,
            "status": "started",
            "message": "Crew analysis started successfully"
        }
        
    except Exception as e:
        logger.error(f"Error starting crew analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting crew analysis: {str(e)}")

@router.post("/analysis/v2/{project_id}", response_model=Dict[str, Any])
async def start_analysis_v2(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Start a project analysis using the new agent implementation (MVP)
    """
    try:
        logger.info(f"Starting analysis v2 for project {project_id}")
        agent_service = AgentServiceV2()
        
        # Start analysis
        analysis_id = await agent_service.start_analysis(db, project_id)
        
        return {
            "analysis_id": analysis_id,
            "project_id": project_id,
            "status": "started",
            "message": "Analysis started successfully"
        }
        
    except Exception as e:
        logger.error(f"Error starting analysis v2: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting analysis v2: {str(e)}")

@router.get("/crew/analysis/{analysis_id}", response_model=Dict[str, Any])
async def get_analysis_status(
    analysis_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get the status and results of a crew analysis
    """
    try:
        agent_service = AgentService()
        analysis_result = await agent_service.get_analysis_status(db, analysis_id)
        
        if not analysis_result:
            raise HTTPException(status_code=404, detail="Analysis not found")
            
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving analysis status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving analysis status: {str(e)}")

@router.get("/analysis/v2/{analysis_id}", response_model=Dict[str, Any])
async def get_analysis_status_v2(
    analysis_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get the status and results of an analysis using the new agent implementation (MVP)
    """
    try:
        agent_service = AgentServiceV2()
        analysis_result = await agent_service.get_analysis_status(db, analysis_id)
        
        if not analysis_result:
            raise HTTPException(status_code=404, detail="Analysis not found")
            
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving analysis v2 status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving analysis v2 status: {str(e)}")
