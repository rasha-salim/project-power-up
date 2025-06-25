"""
Analysis execution service for handling technical analysis with CrewAI
"""
import os
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from crewai import Agent, Task, Crew, Process
from langchain_anthropic import ChatAnthropic

from app.config.config_loader import ConfigLoader
from app.services.project_service import ProjectService
from app.services.analysis_data_service import AnalysisDataService
from app.tools.document_search import DocumentSearchTool
from app.services.websocket_manager import WebSocketManager
from app.models.project import Project
from app.models.analysis import ProjectAnalysis
from app.services.analysis_helper import AnalysisDataHelper
import json

logger = logging.getLogger(__name__)

class AnalysisExecutionService:
    """Service for executing technical analysis using CrewAI agents"""
    
    def __init__(self):
        """Initialize the analysis execution service"""
        self.config_loader = ConfigLoader()
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        self.analysis_data_service = AnalysisDataService()
        self.max_retries = 3
        self.retry_delay = 5  # seconds
    
    def _get_llm(self, temperature: float = 0.1) -> ChatAnthropic:
        """Get configured Anthropic LLM instance for analysis"""
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        
        return ChatAnthropic(
            model=self.anthropic_model,
            temperature=temperature,
            anthropic_api_key=self.anthropic_api_key
        )
    
    async def _notify_analysis_failure(
        self, 
        project_id: str, 
        analysis_id: str, 
        error_message: str, 
        error_type: str,
        ws_manager: Optional[WebSocketManager] = None
    ) -> None:
        """Send standardized failure notification"""
        if ws_manager:
            await ws_manager.broadcast(
                project_id,
                {
                    "type": "analysis_failed",
                    "analysis_id": analysis_id,
                    "error_type": error_type,
                    "message": f"❌ Analysis failed: {error_message}",
                    "timestamp": datetime.now().isoformat()
                }
            )
    
    async def _cleanup_failed_analysis(
        self, 
        analysis_id: str, 
        project_id: str, 
        db: AsyncSession
    ) -> None:
        """Clean up resources after analysis failure"""
        try:
            # Log cleanup attempt
            logger.info(f"Cleaning up failed analysis {analysis_id}")
            
            # TODO: Add cleanup logic for:
            # - Temporary files created during analysis
            # - Database records in inconsistent state
            # - Memory caches
            
            logger.info(f"Cleanup completed for analysis {analysis_id}")
            
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup of analysis {analysis_id}: {str(cleanup_error)}")
    
    async def _should_retry_analysis(self, error: Exception, attempt: int) -> bool:
        """Determine if analysis should be retried based on error type"""
        if attempt >= self.max_retries:
            return False
            
        # Retry for transient errors
        transient_errors = [
            "InternalServerError",
            "RateLimitError", 
            "TimeoutError",
            "ConnectionError",
            "API rate limit",
            "Internal server error"
        ]
        
        error_str = str(error).lower()
        return any(transient_error.lower() in error_str for transient_error in transient_errors)
    
    async def execute_analysis(
        self, 
        analysis_id: str, 
        project_id: str, 
        db: AsyncSession, 
        ws_manager: Optional[WebSocketManager] = None, 
        force: bool = False,
        additional_context: str = ""
    ) -> Dict[str, Any]:
        """
        Execute technical analysis for a project
        
        Args:
            analysis_id: Unique ID for this analysis
            project_id: ID of the project to analyze
            db: Database session
            ws_manager: WebSocket manager for real-time updates
            force: Whether to force new analysis even if one exists
            additional_context: Additional context from user
            
        Returns:
            Dict with analysis results
        """
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                attempt += 1
                logger.info(f"Starting analysis execution attempt {attempt}/{self.max_retries} for {analysis_id}")
                
                # Send status update
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_status",
                            "status": "initializing",
                            "analysis_id": analysis_id,
                            "attempt": attempt,
                            "message": f"🔄 Initializing analysis (attempt {attempt}/{self.max_retries})..."
                        }
                    )
                
                # Get project details with validation
                project_service = ProjectService()
                project = await project_service.get_project(db, project_id)
                if not project:
                    error_msg = f"Project {project_id} not found"
                    await self._notify_analysis_failure(
                        project_id, analysis_id, error_msg, "project_not_found", ws_manager
                    )
                    raise ValueError(error_msg)
                
                # Send initial status
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_status",
                            "status": "starting",
                            "analysis_id": analysis_id
                        }
                    )
                
                # Check for existing analysis if not forced
                if not force:
                    existing_analysis = await self._check_existing_analysis(db, project_id)
                    if existing_analysis:
                        logger.info(f"Found existing analysis for project {project_id}")
                        if ws_manager:
                            await ws_manager.broadcast(
                                project_id,
                                {
                                    "type": "analysis_complete",
                                    "analysis_id": analysis_id,
                                    "message": "Using existing analysis results"
                                }
                            )
                        return {"status": "existing", "analysis": existing_analysis}
                
                # Create technical analysis agent with error handling
                try:
                    llm = self._get_llm()
                    agent_config = self.config_loader.get_agent_config("technical_analyst")
                    task_config = self.config_loader.get_task_config("technical_analysis")
                    
                    if not agent_config:
                        raise ValueError("Technical analyst configuration not found")
                    if not task_config:
                        raise ValueError("Technical analysis task configuration not found")
                    
                    technical_agent = Agent(
                        role=agent_config["role"],
                        goal=agent_config["goal"],
                        backstory=agent_config["backstory"],
                        verbose=True,
                        allow_delegation=False,
                        llm=llm,
                        tools=[DocumentSearchTool(project_id)]
                    )
                except Exception as config_error:
                    error_msg = f"Agent configuration error: {str(config_error)}"
                    await self._notify_analysis_failure(
                        project_id, analysis_id, error_msg, "configuration_error", ws_manager
                    )
                    raise ValueError(error_msg)
                
                # Build task description
                task_description = self._build_task_description(project, additional_context)
                
                # Create analysis task
                task = Task(
                    description=task_description,
                    expected_output=task_config["expected_output"],
                    agent=technical_agent
                )
                
                # Create crew
                crew = Crew(
                    agents=[technical_agent],
                    tasks=[task],
                    verbose=True,
                    process=Process.sequential
                )
                
                # Update status
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_status",
                            "status": "analyzing",
                            "analysis_id": analysis_id,
                            "message": "🤖 AI agents are analyzing your project..."
                        }
                    )
                
                # Execute the crew with timeout
                logger.info("Executing crew for technical analysis")
                try:
                    # Set a timeout for crew execution (5 minutes)
                    crew_result = await asyncio.wait_for(
                        asyncio.to_thread(crew.kickoff),
                        timeout=300.0
                    )
                except asyncio.TimeoutError:
                    raise TimeoutError("Analysis execution timed out after 5 minutes")
                
                # Parse and structure the results
                structured_analysis = self.analysis_data_service.parse_agent_output_to_pydantic(
                    str(crew_result), analysis_id, project_id
                )
                
                # Send completion message
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_complete",
                            "analysis_id": analysis_id,
                            "message": "✅ Technical analysis completed successfully!",
                            "attempts": attempt
                        }
                    )
                
                logger.info(f"Analysis {analysis_id} completed successfully on attempt {attempt}")
                return {
                    "status": "completed",
                    "analysis_id": analysis_id,
                    "raw_output": str(crew_result),
                    "structured_analysis": structured_analysis,
                    "attempts": attempt
                }
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                logger.error(f"Analysis execution attempt {attempt} failed: {error_msg}")
                
                # Determine error type for proper handling
                if "anthropic" in error_msg.lower() or "api" in error_msg.lower():
                    error_type = "api_error"
                elif "timeout" in error_msg.lower():
                    error_type = "timeout_error"
                elif "configuration" in error_msg.lower():
                    error_type = "configuration_error"
                else:
                    error_type = "execution_error"
                
                # Check if we should retry
                should_retry = await self._should_retry_analysis(e, attempt)
                
                if should_retry and attempt < self.max_retries:
                    logger.info(f"Retrying analysis {analysis_id} in {self.retry_delay} seconds...")
                    if ws_manager:
                        await ws_manager.broadcast(
                            project_id,
                            {
                                "type": "analysis_status",
                                "status": "retrying",
                                "analysis_id": analysis_id,
                                "message": f"⚠️ Retrying analysis in {self.retry_delay} seconds... (attempt {attempt + 1}/{self.max_retries})"
                            }
                        )
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    # Final failure - no more retries
                    logger.error(f"Analysis {analysis_id} failed after {attempt} attempts")
                    await self._notify_analysis_failure(
                        project_id, analysis_id, error_msg, error_type, ws_manager
                    )
                    await self._cleanup_failed_analysis(analysis_id, project_id, db)
                    raise
        
        # Should not reach here, but just in case
        if last_error:
            raise last_error
        else:
            raise RuntimeError(f"Analysis {analysis_id} failed after all retry attempts")
    
    async def regenerate_analysis_with_feedback(
        self, 
        analysis_id: str, 
        feedback: str, 
        previous_analysis: Union[ProjectAnalysis, Dict[str, Any]],
        db: AsyncSession,
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Regenerate analysis incorporating user feedback
        
        Args:
            analysis_id: ID of the analysis to regenerate
            feedback: User feedback to incorporate
            previous_analysis: Previous analysis results (ProjectAnalysis model or dict)
            db: Database session
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            Dict with regenerated analysis results
        """
        try:
            # Standardize previous_analysis to ProjectAnalysis model
            if isinstance(previous_analysis, dict):
                # Extract project_id from dict structure
                project_id = previous_analysis.get('project_id')
                # Try to get structured analysis from result
                analysis_result = previous_analysis.get('result', {})
                if isinstance(analysis_result, dict) and 'analysis_id' in analysis_result:
                    try:
                        previous_analysis_model = ProjectAnalysis.parse_obj(analysis_result)
                    except Exception as e:
                        logger.warning(f"Could not parse previous analysis as ProjectAnalysis: {e}")
                        # Create a minimal structure for regeneration
                        previous_analysis_model = None
                else:
                    previous_analysis_model = None
            else:
                previous_analysis_model = previous_analysis
                project_id = previous_analysis_model.project_id
                
            logger.info(f"Regenerating analysis {analysis_id} with feedback")
            
            # Get project details
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Send status update
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_status",
                        "analysis_id": analysis_id,
                        "status": "regenerating",
                        "message": "🔄 Regenerating analysis with your feedback..."
                    }
                )
            
            # Build regeneration task with structured data
            if previous_analysis_model:
                # Use AnalysisDataHelper for consistent formatting
                tech_summary = AnalysisDataHelper.get_tech_stack_summary(previous_analysis_model)
                risk_summary = AnalysisDataHelper.get_risk_summary(previous_analysis_model)
                timeline_summary = AnalysisDataHelper.get_project_timeline_summary(previous_analysis_model)
                
                previous_analysis_text = f"""
                Technical Analysis:
                - Architecture: {previous_analysis_model.technical_analysis.architecture}
                - Tech Stack: {tech_summary}
                - Complexity Score: {previous_analysis_model.technical_analysis.complexity_score}/10
                
                Risk Assessment:
                - Overall Risk Score: {risk_summary['overall_score']}/10
                - Key Risks: {[risk['name'] for risk in risk_summary['key_risks']]}
                
                Project Plan:
                - Timeline: {timeline_summary['timeline']}
                - Estimated Cost: ${timeline_summary['estimated_cost']:,.2f}
                - Total Phases: {timeline_summary['total_phases']}
                
                Recommendations: {', '.join(previous_analysis_model.recommendations)}
                """
            else:
                # Fallback for dictionary-based previous analysis
                analysis_result = previous_analysis.get('result', {}) if isinstance(previous_analysis, dict) else {}
                previous_analysis_text = json.dumps(analysis_result, indent=2)
            
            task_description = f"""
            Based on the previous technical analysis and user feedback, regenerate an improved analysis.
            
            Previous Analysis:
            {previous_analysis_text}
            
            User Feedback:
            {feedback}
            
            Project Details:
            - Name: {project.name}
            - Description: {project.description}
            - Industry: {project.industry}
            - Budget: ${project.budget:,.2f}
            - Team Size: {project.team_size}
            
            Please regenerate the technical analysis incorporating the user's feedback.
            You MUST maintain the exact same structure and format as the previous analysis.
            Focus on addressing the specific feedback while improving the overall analysis quality.
            
            IMPORTANT: Your output MUST be in the exact same format as the original technical analysis.
            """
            
            # Create regeneration agent
            llm = self._get_llm()
            
            regeneration_agent = Agent(
                role="Technical Analysis Regenerator",
                goal="Regenerate technical analysis incorporating user feedback",
                backstory=f"""You are an expert technical analyst who specializes in refining and improving 
                technical analysis based on user feedback. You maintain the same structure and format 
                while incorporating the user's suggestions and improvements.""",
                verbose=True,
                allow_delegation=False,
                llm=llm
            )
            
            # Build regeneration task
            task = Task(
                description=task_description,
                expected_output="Complete technical analysis in the same structured format as before, incorporating user feedback",
                agent=regeneration_agent
            )
            
            # Create crew
            crew = Crew(
                agents=[regeneration_agent],
                tasks=[task],
                verbose=True,
                process=Process.sequential
            )
            
            # Execute regeneration
            crew_result = crew.kickoff()
            
            # Parse results
            structured_analysis = self.analysis_data_service.parse_agent_output_to_pydantic(
                str(crew_result), analysis_id, project_id
            )
            
            # Send completion
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_complete",
                        "analysis_id": analysis_id,
                        "message": "✅ Analysis regenerated with your feedback!",
                        "is_regeneration": True
                    }
                )
            
            return {
                "status": "regenerated",
                "analysis_id": analysis_id,
                "raw_output": str(crew_result),
                "structured_analysis": structured_analysis
            }
            
        except Exception as e:
            logger.error(f"Error regenerating analysis {analysis_id}: {str(e)}")
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "error",
                        "analysis_id": analysis_id,
                        "message": f"Regeneration failed: {str(e)}"
                    }
                )
            raise
    
    def _build_task_description(self, project: Project, additional_context: str = "") -> str:
        """Build task description for analysis"""
        base_description = f"""
        Analyze the project '{project.name}' and provide a comprehensive technical analysis.
        
        Project Details:
        - Name: {project.name}
        - Description: {project.description or 'No description provided'}
        - Industry: {getattr(project, 'industry', 'Not specified')}
        - Team Size: {getattr(project, 'team_size', 'Not specified')}
        - Budget: {getattr(project, 'budget', 'Not specified')}
        - Deadline: {getattr(project, 'deadline', 'Not specified')}
        """
        
        if additional_context:
            base_description += f"\n\nAdditional Context:\n{additional_context}"
        
        return base_description
    
    async def _check_existing_analysis(self, db: AsyncSession, project_id: str) -> Optional[Dict[str, Any]]:
        """Check if project already has analysis"""
        try:
            project_service = ProjectService()
            project_data = await project_service.get_project_with_insights(db, project_id)
            
            if project_data and "insights" in project_data:
                return project_data["insights"]
            return None
        except Exception as e:
            logger.error(f"Error checking existing analysis: {str(e)}")
            return None
