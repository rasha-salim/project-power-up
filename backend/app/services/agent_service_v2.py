"""
Refactored Agent Service V2 - Orchestrates focused services for better maintainability
"""
import logging
import uuid
import asyncio
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.agent_communication_service import AgentCommunicationService
from app.services.analysis_execution_service import AnalysisExecutionService
from app.services.analysis_management_service import AnalysisManagementService
from app.services.user_interaction_service import UserInteractionService
from app.services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class AgentServiceV2:
    """
    Refactored Agent Service that orchestrates focused services
    
    This service acts as a coordinator between:
    - AgentCommunicationService: Basic agent chat
    - AnalysisExecutionService: Technical analysis execution
    - AnalysisManagementService: Analysis state management
    - UserInteractionService: User questions and feedback
    """
    
    def __init__(self):
        """Initialize the orchestrating agent service"""
        # Initialize focused services
        self.analysis_manager = AnalysisManagementService()
        self.communication_service = AgentCommunicationService()
        self.execution_service = AnalysisExecutionService()
        self.interaction_service = UserInteractionService(self.analysis_manager)
        
        logger.info("AgentServiceV2 initialized with focused services")
    
    async def execute_analysis_with_context(
        self, 
        project_id: str, 
        db: AsyncSession, 
        ws_manager: Optional[WebSocketManager] = None, 
        force: bool = False,
        additional_context: str = "",
        existing_analysis_id: Optional[str] = None
    ) -> str:
        """
        Execute analysis with enhanced error handling and state management
        
        Args:
            project_id: ID of the project to analyze
            db: Database session
            ws_manager: WebSocket manager for real-time updates
            force: Whether to force new analysis even if one exists
            additional_context: Additional context for the analysis
            existing_analysis_id: ID of existing analysis for incremental updates
            
        Returns:
            str: Analysis ID
            
        Raises:
            ValueError: If project is not found or invalid
            RuntimeError: If analysis execution fails
        """
        # Use existing analysis ID for incremental updates, otherwise generate new one
        if existing_analysis_id:
            analysis_id = existing_analysis_id
            logger.info(f"Using existing analysis ID {analysis_id} for incremental analysis")
        else:
            analysis_id = str(uuid.uuid4())
        
        try:
            logger.info(f"Starting analysis execution for project {project_id} (ID: {analysis_id})")
            
            # Validate project exists
            from app.services.project_service import ProjectService
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            if not project:
                error_msg = f"Project {project_id} not found"
                logger.error(error_msg)
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "message": f"❌ {error_msg}"
                        }
                    )
                raise ValueError(error_msg)
            
            # Check if analysis is already running for this project
            running_analyses = [
                aid for aid, task in self.analysis_manager.running_tasks.items()
                if not task.done()
            ]
            
            if running_analyses and not force:
                error_msg = f"Analysis already running for project {project_id}: {running_analyses[0]}"
                logger.warning(error_msg)
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_status",
                            "status": "already_running",
                            "analysis_id": running_analyses[0],
                            "message": "⚠️ Analysis is already in progress for this project"
                        }
                    )
                return running_analyses[0]
            
            # Cancel any existing running tasks if forced
            if force and running_analyses:
                logger.info(f"Force analysis requested - cancelling {len(running_analyses)} running tasks")
                for existing_analysis_id in running_analyses:
                    await self.cancel_analysis(existing_analysis_id)
            
            # Create and start analysis task
            task = asyncio.create_task(
                self._execute_analysis_task(
                    analysis_id, project_id, db, ws_manager, force, additional_context, existing_analysis_id
                )
            )
            
            # Store the running task
            self.analysis_manager.add_running_task(analysis_id, task)
            
            # Send initial confirmation
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_started",
                        "analysis_id": analysis_id,
                        "message": "🚀 Analysis started successfully",
                        "project_name": project.name
                    }
                )
            
            logger.info(f"Analysis task {analysis_id} created and started for project {project_id}")
            return analysis_id
            
        except Exception as e:
            logger.error(f"Failed to start analysis for project {project_id}: {str(e)}")
            
            # Clean up any partial state
            try:
                self.analysis_manager.remove_running_task(analysis_id)
                self.analysis_manager.remove_pending_analysis(analysis_id)
            except Exception as cleanup_error:
                logger.error(f"Error during startup cleanup: {str(cleanup_error)}")
            
            # Send error notification
            if ws_manager:
                try:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "message": f"❌ Failed to start analysis: {str(e)}",
                            "error_details": {
                                "analysis_id": analysis_id,
                                "recoverable": self._is_recoverable_error(e)
                            }
                        }
                    )
                except Exception as ws_error:
                    logger.error(f"Failed to send startup error notification: {str(ws_error)}")
            
            raise RuntimeError(f"Analysis execution failed: {str(e)}")
    
    async def _execute_analysis_task(
        self, 
        analysis_id: str, 
        project_id: str, 
        db: AsyncSession, 
        ws_manager: Optional[WebSocketManager], 
        force: bool,
        additional_context: str,
        existing_analysis_id: Optional[str] = None
    ) -> None:
        """Internal task for executing analysis with comprehensive error handling"""
        try:
            logger.info(f"Starting analysis task {analysis_id} for project {project_id}")
            
            # Get existing analysis context if this is an incremental update
            existing_context = None
            if existing_analysis_id:
                existing_analysis = self.analysis_manager.get_pending_analysis(existing_analysis_id)
                if existing_analysis:
                    existing_context = existing_analysis.get('result')
                    logger.info(f"Found existing analysis context for incremental update")
            
            # Execute analysis using execution service
            result = await self.execution_service.execute_analysis(
                analysis_id, project_id, db, ws_manager, force, additional_context, existing_context
            )
            
            # Store result in management service
            if result["status"] in ["completed", "existing"]:
                analysis_data = result.get("structured_analysis") or result.get("analysis")
                if analysis_data:
                    self.analysis_manager.store_pending_analysis(
                        analysis_id, project_id, analysis_data
                    )
                    logger.info(f"Analysis {analysis_id} completed and stored successfully")
            else:
                logger.warning(f"Analysis {analysis_id} completed with unexpected status: {result['status']}")
            
        except Exception as e:
            logger.error(f"Analysis task {analysis_id} failed: {str(e)}")
            
            # Notify about failure via WebSocket
            if ws_manager:
                try:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_failed",
                            "analysis_id": analysis_id,
                            "message": f"❌ Analysis failed: {str(e)}",
                            "error_details": {
                                "error_type": type(e).__name__,
                                "recoverable": self._is_recoverable_error(e)
                            }
                        }
                    )
                except Exception as ws_error:
                    logger.error(f"Failed to send error notification via WebSocket: {str(ws_error)}")
            
            # Clean up analysis state
            try:
                self.analysis_manager.remove_pending_analysis(analysis_id)
                logger.info(f"Cleaned up failed analysis {analysis_id}")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up analysis {analysis_id}: {str(cleanup_error)}")
            
            # Re-raise the original exception
            raise
        finally:
            # Always remove from running tasks, regardless of success/failure
            try:
                self.analysis_manager.remove_running_task(analysis_id)
                logger.info(f"Removed analysis task {analysis_id} from running tasks")
            except Exception as cleanup_error:
                logger.error(f"Failed to remove running task {analysis_id}: {str(cleanup_error)}")
    
    def _is_recoverable_error(self, error: Exception) -> bool:
        """Determine if an error is recoverable (can be retried)"""
        error_str = str(error).lower()
        recoverable_patterns = [
            "internal server error",
            "rate limit",
            "timeout",
            "connection",
            "temporary",
            "unavailable"
        ]
        return any(pattern in error_str for pattern in recoverable_patterns)
    
    async def handle_user_message(
        self, 
        db: AsyncSession, 
        project_id: str, 
        message: str, 
        analysis_id: Optional[str] = None,
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Handle user messages with intelligent routing
        
        Args:
            db: Database session
            project_id: ID of the project
            message: User's message
            analysis_id: Optional analysis ID for context
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            Dict with response information
        """
        try:
            # Route to interaction service
            result = await self.interaction_service.handle_user_message(
                db, project_id, message, analysis_id, ws_manager
            )
            
            # Handle different response types
            if result.get("type") == "analysis_request" and result.get("requires_analysis_execution"):
                # Route to analysis execution with enhanced document search
                request_type = result.get("request_type", "new")
                logger.info(f"Executing {request_type} analysis request for project {project_id}")
                
                # Check if this is an incremental analysis (user has existing analysis)
                existing_analysis_id = result.get("existing_analysis_id")
                additional_context = result.get("message", "")
                
                if existing_analysis_id and request_type in ['update', 'update_with_context']:
                    # Execute incremental analysis with existing context
                    logger.info(f"Executing incremental {request_type} analysis based on existing analysis {existing_analysis_id}")
                    analysis_id = await self.execute_incremental_analysis(
                        project_id=project_id,
                        existing_analysis_id=existing_analysis_id,
                        new_context=additional_context,
                        db=db,
                        ws_manager=ws_manager
                    )
                    
                    return {
                        "type": "analysis_triggered",
                        "analysis_id": analysis_id,
                        "message": f"🔄 {request_type.replace('_', ' ').title()} analysis started with your additional context",
                        "is_incremental": True,
                        "request_type": request_type
                    }
                else:
                    # Execute new analysis with chat context
                    logger.info(f"Executing new analysis from chat request")
                    analysis_id = await self.execute_analysis_with_context(
                        project_id=project_id,
                        db=db,
                        ws_manager=ws_manager,
                        force=True,  # Force new analysis for chat requests
                        additional_context=f"User request via chat: {additional_context}"
                    )
                    
                    return {
                        "type": "analysis_triggered",
                        "analysis_id": analysis_id,
                        "message": "🚀 New analysis started based on your request",
                        "is_incremental": False,
                        "request_type": request_type
                    }
                
            elif result.get("type") == "technical_question" and result.get("requires_technical_response"):
                # Handle technical questions directed to technical agent
                logger.info(f"Handling technical question for project {project_id}")
                return await self.communication_service.chat_with_technical_agent(
                    db, project_id, result["message"], result.get("existing_analysis_id"), ws_manager
                )
                
            elif result.get("type") == "security_question" and result.get("requires_security_response"):
                # Handle security questions directed to security agent
                logger.info(f"Handling security question for project {project_id}")
                return await self.communication_service.chat_with_security_agent(
                    db, project_id, result["message"], result.get("existing_analysis_id"), ws_manager
                )
                
            elif result.get("type") == "project_planning" and result.get("requires_planning_response"):
                # Handle project planning questions directed to project planner agent
                logger.info(f"Handling project planning question for project {project_id}")
                return await self.communication_service.chat_with_project_planner(
                    db, project_id, result["message"], ws_manager
                )
                
            elif result.get("type") == "chat" and result.get("requires_chat_service"):
                # Route to communication service for general chat with project context
                has_context = result.get("has_project_context", False)
                logger.info(f"Routing to general chat {'with' if has_context else 'without'} project context")
                return await self.communication_service.chat_with_project_assistant(
                    db, project_id, result["message"], result.get("existing_analysis_id"), ws_manager
                )
            elif result.get("type") == "feedback" and result.get("requires_regeneration"):
                # Handle feedback and regeneration
                return await self.regenerate_analysis_with_feedback(
                    result["analysis_id"], result["feedback"], db, ws_manager
                )
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error handling user message: {str(e)}")
            raise
    
    async def answer_analysis_question(
        self, 
        db: AsyncSession, 
        project_id: str, 
        analysis_id: str, 
        question: str,
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Answer specific questions about analysis results
        
        Args:
            db: Database session
            project_id: ID of the project
            analysis_id: ID of the analysis
            question: User's question
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            Dict with answer
        """
        return await self.interaction_service.answer_analysis_question(
            db, project_id, analysis_id, question, ws_manager
        )
    
    async def regenerate_analysis_with_feedback(
        self, 
        analysis_id: str, 
        feedback: str, 
        db: AsyncSession,
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Regenerate analysis incorporating user feedback
        
        Args:
            analysis_id: ID of the analysis to regenerate
            feedback: User feedback to incorporate
            db: Database session
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            Dict with regeneration results
        """
        try:
            logger.info(f"Regenerating analysis {analysis_id} with feedback")
            
            # Get current analysis
            current_analysis = self.analysis_manager.get_pending_analysis(analysis_id)
            if not current_analysis:
                raise ValueError(f"Analysis {analysis_id} not found")
            
            # Use execution service to regenerate
            result = await self.execution_service.regenerate_analysis_with_feedback(
                analysis_id, feedback, current_analysis, db, ws_manager
            )
            
            # Update in management service
            if result["status"] == "regenerated":
                updated_data = result.get("structured_analysis")
                if updated_data:
                    self.analysis_manager.update_pending_analysis(
                        analysis_id, updated_data, increment_version=True
                    )
            
            return result
            
        except Exception as e:
            logger.error(f"Error regenerating analysis {analysis_id}: {str(e)}")
            raise
    
    async def chat_with_agent(
        self, 
        db: AsyncSession, 
        project_id: str, 
        message: str, 
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Handle general chat with the project assistant agent
        
        Args:
            db: Database session
            project_id: ID of the project
            message: User's message
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            Dict with response
        """
        return await self.communication_service.chat_with_agent(
            db, project_id, message, ws_manager
        )
    
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
            bool: True if saved successfully
        """
        return await self.analysis_manager.save_analysis_to_project(
            db, analysis_id, ws_manager
        )
    
    async def confirm_and_save_analysis(
        self, 
        db: AsyncSession, 
        analysis_id: str, 
        ws_manager: Optional[WebSocketManager] = None
    ) -> bool:
        """
        Confirm and save analysis to project insights
        This method is called by the WebSocket handler when user clicks save button
        
        Args:
            db: Database session
            analysis_id: ID of the analysis to save
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            bool: True if saved successfully
        """
        try:
            logger.info(f"Confirming and saving analysis {analysis_id}")
            
            # Check if analysis exists in pending analyses
            pending_analysis = self.analysis_manager.get_pending_analysis(analysis_id)
            if not pending_analysis:
                logger.error(f"Analysis {analysis_id} not found in pending analyses")
                if ws_manager:
                    await ws_manager.broadcast(
                        'unknown',
                        {
                            "type": "error",
                            "message": "❌ Analysis not found or already saved"
                        }
                    )
                return False
            
            # Save the analysis
            success = await self.analysis_manager.save_analysis_to_project(
                db, analysis_id, ws_manager
            )
            
            if success:
                logger.info(f"Analysis {analysis_id} confirmed and saved successfully")
            else:
                logger.error(f"Failed to save analysis {analysis_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error confirming and saving analysis {analysis_id}: {str(e)}")
            
            # Send error message via WebSocket if possible
            if ws_manager:
                try:
                    pending_analysis = self.analysis_manager.get_pending_analysis(analysis_id)
                    project_id = pending_analysis.get('project_id', 'unknown') if pending_analysis else 'unknown'
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "message": f"❌ Failed to save analysis: {str(e)}"
                        }
                    )
                except Exception as ws_error:
                    logger.error(f"Failed to send error notification via WebSocket: {str(ws_error)}")
            
            return False
    
    async def execute_incremental_analysis(
        self, 
        project_id: str, 
        existing_analysis_id: str,
        new_context: str,
        db: AsyncSession, 
        ws_manager: Optional[WebSocketManager] = None
    ) -> str:
        """
        Execute incremental analysis with new context based on existing analysis
        
        Args:
            project_id: ID of the project
            existing_analysis_id: ID of the existing analysis to build upon
            new_context: New context or requirements from user
            db: Database session
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            str: New analysis ID for the incremental analysis
        """
        try:
            logger.info(f"Starting incremental analysis for project {project_id} based on {existing_analysis_id}")
            
            # Check if existing analysis exists
            existing_analysis = self.analysis_manager.get_pending_analysis(existing_analysis_id)
            if not existing_analysis:
                # Try to get from project insights/database
                from app.services.project_service import ProjectService
                project_service = ProjectService()
                project = await project_service.get_project(db, project_id)
                if project and project.insights:
                    logger.info(f"Found existing analysis in project insights")
                    # Store it as pending for reference
                    self.analysis_manager.store_pending_analysis(
                        existing_analysis_id, project_id, project.insights
                    )
                else:
                    logger.warning(f"Existing analysis {existing_analysis_id} not found")
            
            # Generate new analysis ID for the incremental analysis
            new_analysis_id = str(uuid.uuid4())
            
            # Send notification about incremental analysis starting
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "incremental_analysis_started",
                        "analysis_id": new_analysis_id,
                        "base_analysis_id": existing_analysis_id,
                        "message": "🔄 Starting incremental analysis with new context...",
                        "new_context": new_context
                    }
                )
            
            # Execute analysis with existing context
            return await self.execute_analysis_with_context(
                project_id=project_id,
                db=db,
                ws_manager=ws_manager,
                force=True,  # Force new analysis even if one exists
                additional_context=f"Previous analysis context exists. New requirements: {new_context}",
                existing_analysis_id=existing_analysis_id
            )
            
        except Exception as e:
            logger.error(f"Error executing incremental analysis: {str(e)}")
            
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "error",
                        "message": f"❌ Failed to start incremental analysis: {str(e)}"
                    }
                )
            
            raise RuntimeError(f"Incremental analysis failed: {str(e)}")
    
    async def cancel_analysis(self, analysis_id: str) -> bool:
        """
        Cancel a running analysis with proper cleanup
        
        Args:
            analysis_id: ID of the analysis to cancel
            
        Returns:
            bool: True if analysis was cancelled, False if not found or already completed
        """
        try:
            logger.info(f"Attempting to cancel analysis {analysis_id}")
            
            # Get the running task
            task = self.analysis_manager.running_tasks.get(analysis_id)
            if not task:
                logger.warning(f"No running task found for analysis {analysis_id}")
                return False
            
            if task.done():
                logger.info(f"Analysis {analysis_id} is already completed")
                self.analysis_manager.remove_running_task(analysis_id)
                return False
            
            # Cancel the task
            task.cancel()
            
            # Wait a bit for graceful cancellation
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                # Expected when cancelling
                pass
            except Exception as e:
                logger.warning(f"Error during task cancellation: {str(e)}")
            
            # Clean up state
            self.analysis_manager.remove_running_task(analysis_id)
            self.analysis_manager.remove_pending_analysis(analysis_id)
            
            logger.info(f"Successfully cancelled analysis {analysis_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling analysis {analysis_id}: {str(e)}")
            return False
    
    def get_pending_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Get pending analysis by ID
        
        Args:
            analysis_id: ID of the analysis
            
        Returns:
            Optional[Dict]: Analysis data if found
        """
        return self.analysis_manager.get_pending_analysis(analysis_id)
    
    async def get_analysis_status(self, analysis_id: str) -> Dict[str, Any]:
        """
        Get the status of an analysis
        
        Args:
            analysis_id: ID of the analysis
            
        Returns:
            Dict with analysis status information
        """
        return await self.analysis_manager.get_analysis_status(analysis_id)
    
    def list_pending_analyses(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all pending analyses
        
        Returns:
            Dict: All pending analyses
        """
        return self.analysis_manager.list_pending_analyses()
    
    # Legacy compatibility methods for existing code
    @property
    def pending_analyses(self) -> Dict[str, Dict[str, Any]]:
        """Legacy property for backward compatibility"""
        return self.analysis_manager.pending_analyses
