"""
Analysis management service for handling analysis lifecycle and state
"""
import logging
import asyncio
from typing import Dict, Any, Optional, Union
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.analysis import ProjectAnalysis
from app.services.project_service import ProjectService
from app.services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class AnalysisManagementService:
    """Service for managing analysis lifecycle, state, and persistence"""
    
    def __init__(self):
        """Initialize the analysis management service"""
        self.pending_analyses: Dict[str, Dict[str, Any]] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
    
    def store_pending_analysis(
        self, 
        analysis_id: str, 
        project_id: str, 
        analysis_data: Union[ProjectAnalysis, Dict[str, Any]]
    ) -> None:
        """
        Store analysis in pending state
        
        Args:
            analysis_id: ID of the analysis
            project_id: ID of the project
            analysis_data: Analysis data to store (ProjectAnalysis model or dict)
        """
        # Handle different data types properly
        if isinstance(analysis_data, ProjectAnalysis):
            # Extract data from ProjectAnalysis model
            version = analysis_data.version
            result_data = analysis_data.dict()
        elif isinstance(analysis_data, dict):
            # Handle dictionary data
            version = analysis_data.get("version", 1)
            result_data = analysis_data
        else:
            logger.warning(f"Unexpected analysis_data type: {type(analysis_data)}")
            version = 1
            result_data = analysis_data
        
        self.pending_analyses[analysis_id] = {
            "project_id": project_id,
            "result": result_data,
            "version": version,
            "timestamp": datetime.utcnow().isoformat()
        }
        logger.info(f"Stored pending analysis {analysis_id} for project {project_id} (version {version})")
    
    def get_pending_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Get pending analysis by ID
        
        Args:
            analysis_id: ID of the analysis
            
        Returns:
            Dict with analysis data or None if not found
        """
        return self.pending_analyses.get(analysis_id)
    
    def update_pending_analysis(
        self, 
        analysis_id: str, 
        analysis_data: Union[ProjectAnalysis, Dict[str, Any]], 
        increment_version: bool = False
    ) -> None:
        """
        Update pending analysis with new data
        
        Args:
            analysis_id: ID of the analysis
            analysis_data: New analysis data (ProjectAnalysis model or dict)
            increment_version: Whether to increment the version number
        """
        if analysis_id in self.pending_analyses:
            current_data = self.pending_analyses[analysis_id]
            
            # Handle different data types
            if isinstance(analysis_data, ProjectAnalysis):
                # Convert ProjectAnalysis to dict for storage
                updated_data = {
                    "analysis_id": analysis_id,
                    "project_id": analysis_data.project_id,
                    "result": analysis_data.dict(),
                    "version": analysis_data.version,
                    "timestamp": analysis_data.updated_at.isoformat()
                }
            elif isinstance(analysis_data, dict):
                updated_data = current_data.copy()
                updated_data.update(analysis_data)
            else:
                logger.warning(f"Unexpected analysis_data type: {type(analysis_data)}")
                return
            
            if increment_version:
                current_version = current_data.get("version", 1)
                updated_data["version"] = current_version + 1
            
            self.pending_analyses[analysis_id] = updated_data
            logger.info(f"Updated pending analysis {analysis_id}")
        else:
            logger.warning(f"Analysis {analysis_id} not found in pending analyses")
    
    def remove_pending_analysis(self, analysis_id: str) -> bool:
        """
        Remove analysis from pending state
        
        Args:
            analysis_id: ID of the analysis to remove
            
        Returns:
            bool: True if removed, False if not found
        """
        if analysis_id in self.pending_analyses:
            del self.pending_analyses[analysis_id]
            logger.info(f"Removed pending analysis {analysis_id}")
            return True
        return False
    
    def list_pending_analyses(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all pending analyses
        
        Returns:
            Dict: All pending analyses
        """
        return self.pending_analyses.copy()
    
    async def save_analysis_to_project(
        self, 
        db: AsyncSession, 
        analysis_id: str, 
        ws_manager: Optional[WebSocketManager] = None
    ) -> bool:
        """
        Save pending analysis to project insights
        
        Args:
            db: Database session
            analysis_id: ID of the analysis to save
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        logger.info(f"Saving analysis {analysis_id} to project")
        
        try:
            # Check if analysis exists in pending analyses
            if analysis_id not in self.pending_analyses:
                logger.error(f"Analysis {analysis_id} not found in pending analyses")
                logger.error(f"Available pending analyses: {list(self.pending_analyses.keys())}")
                return False
            
            analysis_data = self.pending_analyses[analysis_id]
            project_id = analysis_data.get('project_id')
            
            if not project_id:
                logger.error(f"No project_id found for analysis {analysis_id}")
                return False
            
            # Get the analysis result
            result = analysis_data.get('result')
            if not result:
                logger.error(f"No result found for analysis {analysis_id}")
                return False
            
            # Convert to ProjectAnalysis if it's not already
            if isinstance(result, ProjectAnalysis):
                project_analysis = result
            elif isinstance(result, dict):
                # Try to create ProjectAnalysis from dict
                try:
                    project_analysis = ProjectAnalysis.parse_obj(result)
                except Exception as e:
                    logger.error(f"Could not parse result as ProjectAnalysis: {e}")
                    # Store as raw dict for now
                    project_analysis = result
            else:
                project_analysis = result
            
            # Serialize for database storage
            if hasattr(project_analysis, 'model_dump'):
                insights_data = project_analysis.model_dump(mode='json')
            elif hasattr(project_analysis, 'dict'):
                insights_data = project_analysis.dict()
            else:
                insights_data = project_analysis
            
            # Save to project
            project_service = ProjectService()
            logger.info(f"Attempting to save insights to project {project_id}")
            logger.info(f"Insights data size: {len(str(insights_data))} characters")
            await project_service.store_project_insights(db, project_id, insights_data)
            logger.info(f"Successfully saved insights to project {project_id}")
            
            # Send success message via WebSocket
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_saved",
                        "analysis_id": analysis_id,
                        "message": "✅ Analysis saved successfully!"
                    }
                )
            
            logger.info(f"Successfully saved analysis {analysis_id} to project {project_id}")
            
            # Remove from pending analyses
            self.remove_pending_analysis(analysis_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving analysis {analysis_id}: {str(e)}")
            
            # Send error message via WebSocket
            if ws_manager:
                project_id = None
                analysis_data = self.pending_analyses.get(analysis_id, {})
                
                if isinstance(analysis_data, dict):
                    project_id = analysis_data.get('project_id')
                
                if project_id:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "message": f"Failed to save analysis: {str(e)}"
                        }
                    )
            
            return False
    
    def add_running_task(self, analysis_id: str, task: asyncio.Task) -> None:
        """
        Add a running task for tracking
        
        Args:
            analysis_id: ID of the analysis
            task: Asyncio task to track
        """
        self.running_tasks[analysis_id] = task
        logger.info(f"Added running task for analysis {analysis_id}")
    
    def remove_running_task(self, analysis_id: str) -> bool:
        """
        Remove a running task
        
        Args:
            analysis_id: ID of the analysis
            
        Returns:
            bool: True if removed, False if not found
        """
        if analysis_id in self.running_tasks:
            del self.running_tasks[analysis_id]
            logger.info(f"Removed running task for analysis {analysis_id}")
            return True
        return False
    
    async def cancel_analysis(self, analysis_id: str) -> bool:
        """
        Cancel a running analysis
        
        Args:
            analysis_id: ID of the analysis to cancel
            
        Returns:
            bool: True if cancelled successfully, False otherwise
        """
        try:
            # Check if analysis is in running tasks
            if analysis_id in self.running_tasks:
                task = self.running_tasks[analysis_id]
                
                # Cancel the task
                task.cancel()
                
                # Remove from running tasks
                self.remove_running_task(analysis_id)
                
                # Remove from pending analyses
                self.remove_pending_analysis(analysis_id)
                
                logger.info(f"Successfully cancelled analysis {analysis_id}")
                return True
            else:
                logger.warning(f"Analysis {analysis_id} not found in running tasks")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling analysis {analysis_id}: {e}")
            return False
    
    async def get_analysis_status(self, analysis_id: str) -> Dict[str, Any]:
        """
        Get the status of an analysis
        
        Args:
            analysis_id: ID of the analysis
            
        Returns:
            Dict with analysis status information
        """
        # Check if it's running
        if analysis_id in self.running_tasks:
            task = self.running_tasks[analysis_id]
            if task.done():
                return {
                    "analysis_id": analysis_id,
                    "status": "completed" if not task.cancelled() else "cancelled",
                    "is_running": False
                }
            else:
                return {
                    "analysis_id": analysis_id,
                    "status": "running",
                    "is_running": True
                }
        
        # Check if it's pending
        if analysis_id in self.pending_analyses:
            return {
                "analysis_id": analysis_id,
                "status": "pending",
                "is_running": False,
                "version": self.pending_analyses[analysis_id].get("version", 1)
            }
        
        # Not found
        return {
            "analysis_id": analysis_id,
            "status": "not_found",
            "is_running": False
        }
