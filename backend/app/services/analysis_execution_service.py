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
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.analysis_data_service = AnalysisDataService()
        self.max_retries = 3
        self.retry_delay = 5  # seconds
    
    def _get_llm(self, temperature: float = 0.1) -> ChatAnthropic:
        """Get configured Anthropic LLM instance for analysis"""
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        
        return ChatAnthropic(
            model="claude-3-5-sonnet-20241022",  # Force Sonnet for analysis tasks
            temperature=temperature,
            anthropic_api_key=self.anthropic_api_key,
            max_tokens=6000  # Balanced limit for detailed analysis
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
        additional_context: str = "",
        existing_context: Optional[Any] = None
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
            existing_context: Existing analysis context for incremental updates
            
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
                            # Include the actual analysis data in the completion message
                            await ws_manager.broadcast(
                                project_id,
                                {
                                    "type": "analysis_complete",
                                    "analysis_id": analysis_id,
                                    "result": {
                                        "technical_analysis": existing_analysis.technical_analysis,
                                        "completed_at": str(existing_analysis.created_at)
                                    },
                                    "message": "Using existing analysis results",
                                    "message_id": str(uuid.uuid4())
                                }
                            )
                            
                            # Also send the formatted analysis content as an agent message
                            try:
                                from app.services.analysis_helper import AnalysisDataHelper
                                formatted_message = AnalysisDataHelper.format_analysis_summary(existing_analysis)
                                
                                await ws_manager.broadcast(
                                    project_id,
                                    {
                                        "type": "agent_message",
                                        "sender": "technical_agent",
                                        "sender_name": "Technical Analysis Agent",
                                        "message": formatted_message,
                                        "analysis_id": analysis_id,
                                        "message_id": str(uuid.uuid4())
                                    }
                                )
                                logger.info(f"Successfully sent existing analysis content as agent_message")
                            except Exception as e:
                                logger.error(f"Failed to format existing analysis: {e}")
                                # Send raw analysis as fallback
                                await ws_manager.broadcast(
                                    project_id,
                                    {
                                        "type": "agent_message",
                                        "sender": "technical_agent", 
                                        "sender_name": "Technical Analysis Agent",
                                        "message": str(existing_analysis.technical_analysis),
                                        "analysis_id": analysis_id,
                                        "message_id": str(uuid.uuid4())
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
                    
                    # Create and validate the document search tool
                    document_tool = DocumentSearchTool(project_id)
                    logger.info(f"Created DocumentSearchTool for project {project_id}: {document_tool.name}")
                    print(f"🔧 TOOL CREATED: {document_tool.name} for project {project_id}")
                    
                    # Also try alternative function-based tool
                    from app.tools.alternative_document_search import search_project_documents
                    print(f"🔧 ALTERNATIVE TOOL IMPORTED: search_project_documents")
                    
                    # Create agent with both tools for testing
                    agent_tools = [document_tool, search_project_documents]
                    technical_agent = Agent(
                        role=agent_config["role"],
                        goal=agent_config["goal"],
                        backstory=agent_config["backstory"],
                        verbose=True,
                        allow_delegation=False,
                        llm=llm,
                        tools=agent_tools
                    )
                    
                    logger.info(f"Technical agent created with {len(technical_agent.tools)} tools")
                    print(f"🤖 AGENT CREATED: {len(technical_agent.tools)} tools registered")
                except Exception as config_error:
                    error_msg = f"Agent configuration error: {str(config_error)}"
                    await self._notify_analysis_failure(
                        project_id, analysis_id, error_msg, "configuration_error", ws_manager
                    )
                    raise ValueError(error_msg)
                
                # Check if documents exist for this project
                document_status = await self._check_project_documents(db, project_id)
                
                # Get document content preview for better context
                document_preview = await self._get_document_preview(project_id)
                
                # FORCE document search before building task description
                print(f"🔍 FORCING DOCUMENT SEARCH BEFORE AGENT EXECUTION")
                forced_search_results = await self._force_document_search(project_id)
                
                # Build task description with document information AND forced search results
                task_description = self._build_task_description(project, additional_context, document_status, document_preview, forced_search_results)
                
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
                
                # Execute the crew with timeout
                logger.info("Executing crew for technical analysis")
                print(f"🚀 CREW EXECUTION START: Task description length: {len(task_description)} characters")
                print(f"📋 TASK DESCRIPTION PREVIEW: {task_description[:200]}...")
                print(f"🔑 PROJECT ID BEING USED: {project_id}")
                print(f"🔍 EXPECTED CHROMADB COLLECTION: project_{project_id}")
                try:
                    # Set a timeout for crew execution (5 minutes)
                    crew_result = await asyncio.wait_for(
                        asyncio.to_thread(crew.kickoff),
                        timeout=300.0
                    )
                    print(f"✅ CREW EXECUTION COMPLETE: Result length: {len(str(crew_result))} characters")
                    
                    # DEBUG: Check crew result details
                    print(f"🔍 CREW RESULT TYPE: {type(crew_result)}")
                    print(f"🔍 CREW RESULT REPR: {repr(crew_result)[:500]}...")
                    
                    # Check if crew_result has special attributes or methods
                    if hasattr(crew_result, 'raw'):
                        print(f"🔍 CREW RESULT .raw: {len(str(crew_result.raw))} chars")
                        crew_output = str(crew_result.raw)
                    elif hasattr(crew_result, 'content'):
                        print(f"🔍 CREW RESULT .content: {len(str(crew_result.content))} chars")
                        crew_output = str(crew_result.content)
                    else:
                        print(f"🔍 CREW RESULT direct str(): {len(str(crew_result))} chars")
                        crew_output = str(crew_result)
                    
                    print(f"🔍 FINAL CREW OUTPUT LENGTH: {len(crew_output)} characters")
                    print(f"🔍 FINAL CREW OUTPUT PREVIEW: {crew_output[:500]}...")
                    print(f"🔍 FINAL CREW OUTPUT ENDING: ...{crew_output[-200:]}")
                    
                except asyncio.TimeoutError:
                    raise TimeoutError("Analysis execution timed out after 5 minutes")
                
                # Parse and structure the results
                structured_analysis = self.analysis_data_service.parse_agent_output_to_pydantic(
                    crew_output, analysis_id, project_id
                )
                
                # Debug logging before broadcasts
                logger.info(f"About to broadcast analysis completion for project_id: {project_id} (type: {type(project_id)})")
                logger.info(f"WebSocket manager exists: {ws_manager is not None}")
                logger.info(f"Analysis ID: {analysis_id}")
                logger.info(f"Structured analysis created: {structured_analysis is not None}")
                
                # Prepare structured data safely
                structured_data = None
                if structured_analysis:
                    try:
                        structured_data = structured_analysis.dict()
                        print(f"🔍 SERIALIZING PYDANTIC TO DICT")
                        print(f"🔍 Pydantic dict keys: {list(structured_data.keys())}")
                        print(f"🔍 Tech analysis architecture: {structured_data.get('technical_analysis', {}).get('architecture', 'NOT FOUND')[:100]}...")
                        print(f"🔍 Tech analysis tech_stack: {structured_data.get('technical_analysis', {}).get('tech_stack', 'NOT FOUND')}")
                        print(f"🔍 Project plan timeline: {structured_data.get('project_plan', {}).get('timeline', 'NOT FOUND')[:100]}...")
                        print(f"🔍 Project plan cost: {structured_data.get('project_plan', {}).get('estimated_cost', 'NOT FOUND')}")
                        
                        # Convert datetime objects to strings for JSON serialization
                        if 'created_at' in structured_data:
                            structured_data['created_at'] = str(structured_data['created_at'])
                        if 'updated_at' in structured_data:
                            structured_data['updated_at'] = str(structured_data['updated_at'])
                        logger.info(f"Structured analysis serialized successfully, keys: {list(structured_data.keys())}")
                    except Exception as e:
                        logger.error(f"Failed to serialize structured_analysis: {e}")
                        structured_data = None
                
                # Send completion message with only structured analysis data
                if ws_manager:
                    try:
                        completion_message = {
                            "type": "analysis_complete",
                            "analysis_id": analysis_id,
                            "result": structured_data,  # Only send structured data, not raw text
                            "message": "✅ Technical analysis completed successfully!",
                            "attempts": attempt,
                            "completed_at": str(datetime.now())
                        }
                        
                        print(f"🔍 WEBSOCKET MESSAGE BEING SENT:")
                        print(f"🔍 Message type: {completion_message['type']}")
                        print(f"🔍 Result is None: {structured_data is None}")
                        if structured_data:
                            print(f"🔍 Result keys: {list(structured_data.keys())}")
                            tech_analysis = structured_data.get('technical_analysis', {})
                            print(f"🔍 WS Tech analysis keys: {list(tech_analysis.keys()) if isinstance(tech_analysis, dict) else 'Not a dict'}")
                            if isinstance(tech_analysis, dict):
                                print(f"🔍 WS Architecture length: {len(tech_analysis.get('architecture', '')) if tech_analysis.get('architecture') else 0}")
                                print(f"🔍 WS Tech stack: {tech_analysis.get('tech_stack', 'NOT FOUND')}")
                        
                        logger.info(f"Broadcasting analysis_complete message with structured data only")
                        await ws_manager.broadcast(project_id, completion_message)
                        logger.info(f"Successfully broadcasted analysis_complete message")
                        
                    except Exception as e:
                        logger.error(f"Failed to broadcast analysis_complete message: {e}")
                        logger.error(f"Error type: {type(e).__name__}")
                        import traceback
                        logger.error(f"Full traceback: {traceback.format_exc()}")
                        
                        # If analysis_complete failed, send raw analysis as fallback
                        try:
                            fallback_message = {
                                "type": "analysis_complete",
                                "analysis_id": analysis_id,
                                "result": {"raw_analysis": str(crew_result)},
                                "message": "⚠️ Analysis completed with limited formatting",
                                "attempts": attempt,
                                "completed_at": str(datetime.now())
                            }
                            
                            logger.info(f"Broadcasting fallback analysis_complete message")
                            await ws_manager.broadcast(project_id, fallback_message)
                            logger.info(f"Successfully broadcasted fallback analysis_complete")
                            
                        except Exception as fallback_error:
                            logger.error(f"Failed to broadcast fallback message: {fallback_error}")
                else:
                    logger.error(f"WebSocket manager is None - cannot broadcast messages!")
                
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
            
            # DEBUG: Check regeneration crew result
            print(f"🔍 REGEN CREW RESULT TYPE: {type(crew_result)}")
            if hasattr(crew_result, 'raw'):
                crew_output = str(crew_result.raw)
            elif hasattr(crew_result, 'content'):
                crew_output = str(crew_result.content)
            else:
                crew_output = str(crew_result)
            
            print(f"🔍 REGEN FINAL OUTPUT LENGTH: {len(crew_output)} characters")
            
            # Parse results
            structured_analysis = self.analysis_data_service.parse_agent_output_to_pydantic(
                crew_output, analysis_id, project_id
            )
            
            # Debug logging before broadcasts
            logger.info(f"About to broadcast regeneration completion for project_id: {project_id} (type: {type(project_id)})")
            logger.info(f"WebSocket manager exists: {ws_manager is not None}")
            logger.info(f"Analysis ID: {analysis_id}")
            logger.info(f"Structured analysis created: {structured_analysis is not None}")
            
            # Prepare structured data safely
            structured_data = None
            if structured_analysis:
                try:
                    structured_data = structured_analysis.dict()
                    # Convert datetime objects to strings for JSON serialization
                    if 'created_at' in structured_data:
                        structured_data['created_at'] = str(structured_data['created_at'])
                    if 'updated_at' in structured_data:
                        structured_data['updated_at'] = str(structured_data['updated_at'])
                    logger.info(f"Structured analysis serialized successfully, keys: {list(structured_data.keys())}")
                except Exception as e:
                    logger.error(f"Failed to serialize structured_analysis: {e}")
                    structured_data = None
            
            # Send completion with actual analysis data
            if ws_manager:
                try:
                    completion_message = {
                        "type": "analysis_complete",
                        "analysis_id": analysis_id,
                        "result": {
                            "technical_analysis": str(crew_result),
                            "structured_analysis": structured_data,
                            "completed_at": str(datetime.now())
                        },
                        "message": "✅ Analysis regenerated with your feedback!",
                        "is_regeneration": True
                    }
                    
                    logger.info(f"Broadcasting regeneration analysis_complete message: {completion_message['type']}")
                    await ws_manager.broadcast(project_id, completion_message)
                    logger.info(f"Successfully broadcasted regeneration analysis_complete message")
                    
                except Exception as e:
                    logger.error(f"Failed to broadcast regeneration analysis_complete message: {e}")
                    logger.error(f"Error type: {type(e).__name__}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                
                # Also send the formatted analysis content as an agent message
                try:
                    from app.services.analysis_helper import AnalysisDataHelper
                    
                    if structured_analysis:
                        formatted_message = AnalysisDataHelper.format_analysis_summary(structured_analysis)
                        logger.info(f"Regenerated analysis formatted successfully, length: {len(formatted_message)}")
                    else:
                        formatted_message = str(crew_result)
                        logger.info(f"Using raw regenerated analysis as fallback, length: {len(formatted_message)}")
                    
                    agent_message = {
                        "type": "agent_message",
                        "sender": "technical_agent",
                        "sender_name": "Technical Analysis Agent", 
                        "message": formatted_message,
                        "analysis_id": analysis_id,
                        "message_id": str(uuid.uuid4())
                    }
                    
                    logger.info(f"Broadcasting regenerated agent_message with analysis content")
                    await ws_manager.broadcast(project_id, agent_message)
                    logger.info(f"Successfully broadcasted regenerated agent_message with analysis content")
                    
                except Exception as e:
                    logger.error(f"Failed to format or broadcast regenerated analysis content: {e}")
                    logger.error(f"Error type: {type(e).__name__}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    
                    # Send raw analysis as fallback
                    try:
                        fallback_message = {
                            "type": "agent_message",
                            "sender": "technical_agent",
                            "sender_name": "Technical Analysis Agent",
                            "message": str(crew_result),
                            "analysis_id": analysis_id,
                            "message_id": str(uuid.uuid4())
                        }
                        
                        logger.info(f"Broadcasting fallback regenerated agent_message with raw analysis")
                        await ws_manager.broadcast(project_id, fallback_message)
                        logger.info(f"Successfully broadcasted fallback regenerated agent_message")
                        
                    except Exception as fallback_error:
                        logger.error(f"Failed to broadcast regenerated fallback message: {fallback_error}")
            else:
                logger.error(f"WebSocket manager is None - cannot broadcast regeneration messages!")
            
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
    
    async def _check_project_documents(self, db: AsyncSession, project_id: str) -> Dict[str, Any]:
        """Check if project has uploaded documents"""
        try:
            from app.models.document import Document
            from sqlalchemy import select, func
            
            # Count total documents
            result = await db.execute(
                select(func.count(Document.id)).where(Document.project_id == project_id)
            )
            total_docs = result.scalar() or 0
            
            # Count processed documents
            result = await db.execute(
                select(func.count(Document.id)).where(
                    Document.project_id == project_id,
                    Document.is_processed == True
                )
            )
            processed_docs = result.scalar() or 0
            
            # Get document filenames
            result = await db.execute(
                select(Document.filename).where(Document.project_id == project_id)
            )
            filenames = [row[0] for row in result.fetchall()]
            
            return {
                "total_documents": total_docs,
                "processed_documents": processed_docs,
                "filenames": filenames,
                "has_documents": total_docs > 0,
                "all_processed": total_docs > 0 and processed_docs == total_docs
            }
            
        except Exception as e:
            logger.warning(f"Error checking project documents: {e}")
            return {
                "total_documents": 0,
                "processed_documents": 0,
                "filenames": [],
                "has_documents": False,
                "all_processed": False
            }
    
    async def _get_document_preview(self, project_id: str) -> str:
        """Get a preview of document content to include in task description"""
        try:
            # Use document search tool to get sample content
            search_tool = DocumentSearchTool(project_id)
            
            # Try several search terms to get document overview
            preview_searches = [
                ("requirements", 2),
                ("technical", 2), 
                ("architecture", 2),
                ("overview", 2)
            ]
            
            preview_content = []
            for term, limit in preview_searches:
                try:
                    results = search_tool._run(term, limit)
                    if results and "No documents found" not in results:
                        preview_content.append(f"Search '{term}': {results[:200]}...")
                except Exception as e:
                    logger.warning(f"Error in document preview search for '{term}': {e}")
                    continue
            
            if preview_content:
                return "\n".join(preview_content)
            else:
                return "No document content preview available"
                
        except Exception as e:
            logger.warning(f"Error getting document preview: {e}")
            return "Document preview unavailable"
    
    def _build_task_description(self, project: Project, additional_context: str = "", document_status: Dict[str, Any] = None, document_preview: str = "", forced_search_results: str = "") -> str:
        """Build task description for analysis with document search instructions"""
        
        # Prepare document status information
        doc_info = ""
        if document_status:
            if document_status.get("has_documents"):
                doc_info = f"""
        
        DOCUMENT STATUS:
        - Total Documents: {document_status['total_documents']}
        - Processed Documents: {document_status['processed_documents']}
        - Document Files: {', '.join(document_status['filenames'])}
        - Ready for Analysis: {'Yes' if document_status.get('all_processed') else 'Processing in progress'}
        """
            else:
                doc_info = f"""
        
        DOCUMENT STATUS:
        - No documents have been uploaded for this project yet
        - You should recommend that the team upload project requirements, specifications, or design documents
        """
        
        base_description = f"""
        Analyze the project '{project.name}' and provide a comprehensive technical analysis based on the uploaded project documents.
        
        Project Details:
        - Name: {project.name}
        - Description: {project.description or 'No description provided'}
        - Industry: {getattr(project, 'industry', 'Not specified')}
        - Team Size: {getattr(project, 'team_size', 'Not specified')}
        - Budget: {getattr(project, 'budget', 'Not specified')}
        - Deadline: {getattr(project, 'deadline', 'Not specified')}{doc_info}
        
        EXECUTION PROCESS - FOLLOW THIS ORDER:
        
        STEP 1 - DOCUMENT DISCOVERY: 
        **IMMEDIATELY start by using the document_search tool multiple times with different keywords**
        
        STEP 2 - COMPREHENSIVE SEARCHING:
        Try multiple searches with terms like:
           - "requirements" - to find functional/non-functional requirements
           - "architecture" - to find system design and architecture details
           - "technology" or "tech stack" - to find technology choices
           - "timeline" or "schedule" - to find project timelines
           - "budget" or "cost" - to find financial constraints
           - "security" - to find security requirements
           - "performance" - to find performance requirements
           - "database" - to find data storage requirements
           - "API" - to find integration requirements
        
        STEP 3 - CONTENT ANALYSIS:
        From found documents, extract:
           - Specific technologies, frameworks, languages mentioned
           - Architecture patterns and system design requirements
           - Performance, security, and scalability requirements
           - Integration requirements and external dependencies
           - Timeline constraints and delivery milestones  
           - Budget limitations and resource constraints
        
        STEP 4 - STRUCTURED OUTPUT:
        After completing all document searches and analysis, provide your findings in the required JSON format.
        
        STEP 5 - CITATION:
        Include specific document references and sections where you found information in the explanations.
        
        SEARCH EXECUTION STRATEGY:
        - You have access to document search tools: 'document_search' and 'search_project_documents'
        - Execute multiple document searches with different keywords using either tool
        - Try both tools if one doesn't return results
        - Analyze ALL returned content thoroughly
        - Look for technical specifications, requirements, constraints, and stakeholder expectations
        - If documents mention specific technologies, include them in your recommendations
        - If documents specify timeline or budget constraints, factor them into your analysis
        
        IMPORTANT: If your document searches return no results or minimal content, explicitly state this in your analysis and explain what type of documentation should be gathered to provide a proper technical analysis.
        
        Your analysis must be based on ACTUAL document content, not assumptions. Always cite which documents provided specific information.
        """
        
        # Add document preview if available
        if document_preview and document_preview != "No document content preview available":
            base_description += f"""
        
        DOCUMENT CONTENT PREVIEW:
        The following is a preview of content found in project documents to give you context:
        {document_preview}
        
        Use the document_search tool to find more detailed information beyond this preview.
        """
        
        if additional_context:
            base_description += f"\n\nAdditional Context:\n{additional_context}"
        
        # Add forced search results if available
        if forced_search_results and "No documents found" not in forced_search_results:
            base_description += f"""
        
        DOCUMENT SEARCH RESULTS (Pre-executed):
        The following document search results have been pre-executed for you:
        
        {forced_search_results}
        
        Use this information to provide a comprehensive technical analysis based on the actual document content above.
        DO NOT say there are no documents - the documents are provided above.
        """
        elif forced_search_results:
            base_description += f"""
        
        DOCUMENT SEARCH STATUS:
        Document search was executed but no documents were found for this project.
        {forced_search_results}
        """
        
        return base_description
    
    async def _force_document_search(self, project_id: str) -> str:
        """Force document search execution outside of agent to provide results directly"""
        try:
            print(f"🔍 EXECUTING FORCED DOCUMENT SEARCH for project {project_id}")
            
            # Create document search tool
            search_tool = DocumentSearchTool(project_id)
            
            # Execute multiple searches
            search_queries = ["requirements", "architecture", "technology", "timeline", "budget", "demo"]
            all_results = []
            
            for query in search_queries:
                try:
                    print(f"   🔍 Forced search for: {query}")
                    result = search_tool._run(query, 3)
                    if result and "No documents found" not in result and "No relevant documents found" not in result:
                        all_results.append(f"=== SEARCH: {query} ===\n{result}\n")
                        print(f"   ✅ Found results for: {query}")
                    else:
                        print(f"   ❌ No results for: {query}")
                except Exception as e:
                    print(f"   ❌ Error searching for {query}: {e}")
            
            if all_results:
                combined_results = "\n".join(all_results)
                print(f"🔍 FORCED SEARCH COMPLETE: Found {len(all_results)} result sets, total length: {len(combined_results)}")
                return combined_results
            else:
                print(f"🔍 FORCED SEARCH COMPLETE: No documents found")
                return "No documents found in forced search"
                
        except Exception as e:
            print(f"❌ FORCED SEARCH ERROR: {e}")
            import traceback
            traceback.print_exc()
            return f"Error in forced search: {str(e)}"
    
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
