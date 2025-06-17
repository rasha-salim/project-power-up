from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import logging
from app.db.init_db_simple import get_async_db
from app.services.agent_service import AgentService
from app.models.agent import AgentResponse, AgentTask

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/analysis/{project_id}", response_model=Dict[str, Any])
async def start_analysis(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Start a project analysis using the agent implementation
    """
    try:
        logger.info(f"Starting analysis for project {project_id}")
        
        # Import WebSocketManager here to avoid circular imports
        from app.services.websocket_manager import WebSocketManager
        ws_manager = WebSocketManager()
        
        agent_service = AgentService()
        
        # Start analysis with WebSocket manager for real-time updates
        analysis_id = await agent_service.start_analysis(db, project_id, ws_manager)
        
        return {
            "analysis_id": analysis_id,
            "project_id": project_id,
            "status": "started",
            "message": "Analysis started successfully"
        }
        
    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting analysis: {str(e)}")

@router.get("/analysis/{analysis_id}", response_model=Dict[str, Any])
async def get_analysis_status(
    analysis_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get the status and results of an analysis
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
