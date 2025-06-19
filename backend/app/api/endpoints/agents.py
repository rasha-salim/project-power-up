from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import logging
from app.db.init_db_simple import get_async_db
from app.services.agent_service import AgentService
from app.models.agent import AgentResponse, AgentTask
from app.core.agent_registry import agent_registry, AgentInfo
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize the agent service
agent_service = AgentService()

class AgentInfoResponse(BaseModel):
    """Response model for agent information"""
    id: str
    name: str
    mention_id: str
    role: str
    description: str
    capabilities: List[str]
    example_prompts: List[str]
    avatar: Optional[str] = None
    color: Optional[str] = None
    is_available: bool

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
        analysis_result = await agent_service.get_analysis_status(db, analysis_id)
        
        if not analysis_result:
            raise HTTPException(status_code=404, detail="Analysis not found")
            
        return analysis_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving analysis status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving analysis status: {str(e)}")

@router.get("/catalog", response_model=List[AgentInfoResponse])
async def get_agent_catalog():
    """
    Get the catalog of all available agents
    """
    try:
        all_agents = agent_registry.get_all_agents()
        
        # Convert to response format
        response = []
        for agent in all_agents:
            response.append(AgentInfoResponse(
                id=agent.id,
                name=agent.name,
                mention_id=agent.mention_id,
                role=agent.role,
                description=agent.description,
                capabilities=[cap.value for cap in agent.capabilities],
                example_prompts=agent.example_prompts,
                avatar=agent.avatar,
                color=agent.color,
                is_available="[Coming Soon]" not in agent.description
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting agent catalog: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/catalog/{agent_id}", response_model=AgentInfoResponse)
async def get_agent_info(agent_id: str):
    """
    Get information about a specific agent
    """
    agent = agent_registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    return AgentInfoResponse(
        id=agent.id,
        name=agent.name,
        mention_id=agent.mention_id,
        role=agent.role,
        description=agent.description,
        capabilities=[cap.value for cap in agent.capabilities],
        example_prompts=agent.example_prompts,
        avatar=agent.avatar,
        color=agent.color,
        is_available="[Coming Soon]" not in agent.description
    )

@router.get("/search")
async def search_agents(query: str = Query(..., description="Search query")):
    """
    Search for agents by name, capability, or description
    """
    try:
        results = agent_registry.search_agents(query)
        
        response = []
        for agent in results:
            response.append(AgentInfoResponse(
                id=agent.id,
                name=agent.name,
                mention_id=agent.mention_id,
                role=agent.role,
                description=agent.description,
                capabilities=[cap.value for cap in agent.capabilities],
                example_prompts=agent.example_prompts,
                avatar=agent.avatar,
                color=agent.color,
                is_available="[Coming Soon]" not in agent.description
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Error searching agents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
