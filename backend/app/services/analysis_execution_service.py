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
from app.utils.message_formatter import MessageFormatter
from pydantic import ValidationError
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
        # Remove dependency on AnalysisDataService - use direct Pydantic validation instead
        
        # Separate retry limits for different error types
        self.max_api_retries = 3
        self.max_constraint_retries = 2
        
        # Exponential backoff configuration for API errors
        self.base_api_delay = 10  # seconds
        self.overload_base_delay = 60  # seconds for overloaded errors
        self.max_api_delay = 300  # 5 minutes max delay
    
    def _validate_analysis_with_pydantic(self, result_text: str, analysis_id: str, project_id: str) -> tuple[bool, Optional[ProjectAnalysis], str]:
        """
        Validate agent response using Pydantic models for guaranteed structure consistency
        
        Args:
            result_text: Raw JSON response from agent
            analysis_id: ID of the analysis
            project_id: ID of the project
            
        Returns:
            tuple: (is_valid, validated_pydantic_object, error_message)
        """
        try:
            # Clean the result text
            cleaned_text = result_text.strip()
            
            # Check if it starts and ends with braces
            if not (cleaned_text.startswith('{') and cleaned_text.endswith('}')):
                return False, None, "Response is not valid JSON (must start with { and end with })"
            
            # Check for wrong format patterns (indicates agent not following template)
            wrong_format_indicators = [
                "Technical Analysis Update",  # Wrong header format
                "Start Date:",               # Wrong date format  
                "End Date:",                 # Wrong date format
                "Architecture Overview:",    # Wrong section name
                "Primary Framework:",        # Wrong tech stack format
                "UI Components:",           # Wrong tech stack format
                "Key Technical Components:", # Wrong section name
                "Content Ingestion Pipeline:", # Wrong section structure
                "Technical Analysis\nTechnical Analysis &",  # Pattern from broken output
                "Timeline:  July",           # Pattern from broken output  
                "Week 1-2:",                # Broken week format
                "Week 3-4:",                # Broken week format
                "Given the client's",       # Narrative text pattern
                "here is a detailed",       # Narrative text pattern
                "Validation Architecture Components",  # Wrong section pattern
                "Core Validation Layer:",   # Wrong subsection pattern
            ]
            
            if any(indicator in cleaned_text for indicator in wrong_format_indicators):
                return False, None, f"Response uses wrong format - detected forbidden patterns. Must use exact JSON structure from template."
            
            # Check if response contains raw document content (indicates agent confusion)
            if len(cleaned_text) > 15000:  # Very long responses might contain raw docs
                return False, None, "Response too long - likely contains raw document content instead of structured analysis"
            
            # Parse JSON first to check basic structure
            try:
                parsed_json = json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                return False, None, f"Invalid JSON format: {str(e)}"
            
            # Validate required structure sections
            required_sections = ["technical_analysis", "risk_assessment", "project_plan", "recommendations"]
            missing_sections = [section for section in required_sections if section not in parsed_json]
            if missing_sections:
                return False, None, f"Missing required sections: {', '.join(missing_sections)}. Must include all: {', '.join(required_sections)}"
            
            # Validate technical_analysis subsections
            tech_analysis = parsed_json.get("technical_analysis", {})
            required_tech_fields = ["architecture", "tech_stack", "complexity_score", "maintainability_score", "scalability_score", "security_score"]
            missing_tech_fields = [field for field in required_tech_fields if field not in tech_analysis]
            if missing_tech_fields:
                return False, None, f"Missing technical_analysis fields: {', '.join(missing_tech_fields)}"
            
            # Validate tech_stack structure
            tech_stack = tech_analysis.get("tech_stack", {})
            required_stack_fields = ["frontend", "backend", "infrastructure", "tools"]
            missing_stack_fields = [field for field in required_stack_fields if field not in tech_stack]
            if missing_stack_fields:
                return False, None, f"Missing tech_stack fields: {', '.join(missing_stack_fields)}"
            
            # Validate project_plan structure
            project_plan = parsed_json.get("project_plan", {})
            required_plan_fields = ["timeline", "estimated_cost", "phases"]
            missing_plan_fields = [field for field in required_plan_fields if field not in project_plan]
            if missing_plan_fields:
                return False, None, f"Missing project_plan fields: {', '.join(missing_plan_fields)}"
            
            # Add required fields for ProjectAnalysis model
            analysis_data = {
                "analysis_id": analysis_id,
                "project_id": project_id,
                "version": 1,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                **parsed_json
            }
            
            # Validate using Pydantic model
            try:
                # Use Pydantic to validate the complete structure
                validated_analysis = ProjectAnalysis.model_validate(analysis_data)
                
                logger.info(f"Pydantic validation successful for analysis {analysis_id}")
                return True, validated_analysis, ""
                
            except ValidationError as e:
                # Extract specific validation errors
                error_details = []
                for error in e.errors():
                    field_path = " -> ".join(str(x) for x in error['loc'])
                    error_msg = error['msg']
                    error_details.append(f"{field_path}: {error_msg}")
                
                detailed_error = f"Pydantic validation failed:\n" + "\n".join(error_details)
                logger.error(f"Pydantic validation failed for analysis {analysis_id}: {detailed_error}")
                return False, None, detailed_error
                
        except Exception as e:
            logger.error(f"Unexpected error during Pydantic validation: {str(e)}")
            return False, None, f"Validation error: {str(e)}"
    
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
                    "message": f"Analysis failed: {error_message}",
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
    
    def _classify_error(self, error: Exception) -> str:
        """Classify error type for appropriate retry strategy"""
        error_str = str(error).lower()
        
        # Anthropic specific errors
        if "overloaded_error" in error_str or "overloaded" in error_str:
            return "overload_error"
        elif "rate_limit" in error_str or "ratelimiterror" in error_str:
            return "rate_limit_error"
        elif "anthropic" in error_str and ("api" in error_str or "internalservererror" in error_str):
            return "api_error"
        elif "timeout" in error_str or "timeouterror" in error_str:
            return "timeout_error"
        elif "connection" in error_str or "connectionerror" in error_str:
            return "connection_error"
        else:
            return "other_error"
    
    def _calculate_api_retry_delay(self, attempt: int, error_type: str) -> int:
        """Calculate exponential backoff delay for API errors"""
        if error_type == "overload_error":
            # Longer delays for overload errors: 60s, 180s, 300s
            delay = self.overload_base_delay * (3 ** (attempt - 1))
        else:
            # Standard exponential backoff: 10s, 30s, 90s
            delay = self.base_api_delay * (3 ** (attempt - 1))
        
        # Cap at maximum delay
        return min(delay, self.max_api_delay)
    
    async def _should_retry_api_error(self, error: Exception, api_attempt: int) -> tuple[bool, int]:
        """Determine if API error should be retried and calculate delay"""
        if api_attempt >= self.max_api_retries:
            return False, 0
            
        error_type = self._classify_error(error)
        
        # Retry transient API errors
        retryable_errors = ["overload_error", "rate_limit_error", "api_error", "timeout_error", "connection_error"]
        
        if error_type in retryable_errors:
            delay = self._calculate_api_retry_delay(api_attempt, error_type)
            return True, delay
        
        return False, 0
    
    def _validate_constraint_compliance(
        self, 
        project: Project, 
        analysis_result: Dict[str, Any], 
        existing_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate that the analysis respects original project constraints.
        
        Args:
            project: Original project with constraints
            analysis_result: New analysis result to validate
            existing_analysis: Previous analysis for comparison in update mode
            
        Returns:
            Dict with validation results and any violations found
        """
        validation_result = {
            "is_valid": True,
            "violations": [],
            "warnings": [],
            "constraint_compliance": {
                "deadline_preserved": True,
                "budget_respected": True,
                "team_size_maintained": True,
                "goals_preserved": True
            }
        }
        
        try:
            project_plan = analysis_result.get('project_plan', {})
            
            # Check deadline compliance
            if project.deadline:
                analysis_timeline = project_plan.get('timeline', '')
                estimated_cost = project_plan.get('estimated_cost', 0)
                
                # For updates, check if timeline was extended beyond original deadline
                if existing_analysis and 'project_plan' in existing_analysis:
                    existing_timeline = existing_analysis['project_plan'].get('timeline', '')
                    # Simple check - if timeline mentions extending beyond original deadline
                    if 'extend' in analysis_timeline.lower() or 'longer' in analysis_timeline.lower():
                        validation_result["constraint_compliance"]["deadline_preserved"] = False
                        validation_result["violations"].append(
                            f"Timeline appears to extend beyond original deadline: {project.deadline}"
                        )
            
            # Check budget compliance
            if project.budget:
                estimated_cost = project_plan.get('estimated_cost', 0)
                if isinstance(estimated_cost, (int, float)) and estimated_cost > 0:
                    # Simple budget check - if budget is specified as a number, compare
                    if project.budget.isdigit() and int(project.budget) < estimated_cost:
                        validation_result["constraint_compliance"]["budget_respected"] = False
                        validation_result["violations"].append(
                            f"Estimated cost ${estimated_cost} exceeds budget ${project.budget}"
                        )
            
            # Check team size compliance - STRICT VALIDATION
            if project.team_size:
                resource_reqs = project_plan.get('resource_requirements', {})
                total_team_members = 0
                
                # Count all team members including "other" field
                for role, count in resource_reqs.items():
                    if role == 'other' and isinstance(count, dict):
                        # Sum up all values in the "other" dictionary
                        total_team_members += sum(count.values()) if count else 0
                    elif isinstance(count, (int, float)):
                        total_team_members += int(count)
                
                logger.info(f"🔍 TEAM SIZE VALIDATION:")
                logger.info(f"   - Project team size limit: {project.team_size}")
                logger.info(f"   - Resource requirements: {resource_reqs}")
                logger.info(f"   - Calculated total team members: {total_team_members}")
                
                if total_team_members > project.team_size:
                    validation_result["constraint_compliance"]["team_size_maintained"] = False
                    validation_result["violations"].append(
                        f"CRITICAL: Required team size {total_team_members} exceeds constraint {project.team_size}. "
                        f"Resource breakdown: {resource_reqs}"
                    )
                    logger.error(f"🚨 TEAM SIZE CONSTRAINT VIOLATION: {total_team_members} > {project.team_size}")
                elif total_team_members == 0:
                    validation_result["warnings"].append(
                        f"No team members specified in resource requirements"
                    )
                else:
                    logger.info(f"✅ Team size constraint satisfied: {total_team_members} <= {project.team_size}")
            
            # Check for timeline preservation in update mode
            if existing_analysis and 'project_plan' in existing_analysis:
                existing_phases = existing_analysis['project_plan'].get('phases', [])
                new_phases = project_plan.get('phases', [])
                
                # Check if major phases were removed or completely restructured
                if len(existing_phases) > 0 and len(new_phases) == 0:
                    validation_result["warnings"].append(
                        "All existing phases were removed - this may not preserve timeline structure"
                    )
                elif len(existing_phases) > len(new_phases):
                    validation_result["warnings"].append(
                        f"Phase count reduced from {len(existing_phases)} to {len(new_phases)} - verify timeline preservation"
                    )
            
            # Set overall validity
            validation_result["is_valid"] = len(validation_result["violations"]) == 0
            
            # Log validation results
            if not validation_result["is_valid"]:
                logger.warning(f"Constraint violations found: {validation_result['violations']}")
            if validation_result["warnings"]:
                logger.info(f"Constraint warnings: {validation_result['warnings']}")
            
        except Exception as e:
            logger.error(f"Error validating constraints: {e}")
            validation_result["is_valid"] = False
            validation_result["violations"].append(f"Validation error: {str(e)}")
        
        return validation_result
    
    async def execute_analysis(
        self, 
        analysis_id: str, 
        project_id: str, 
        db: AsyncSession, 
        ws_manager: Optional[WebSocketManager] = None,
        user_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute unified technical analysis for a project
        
        Args:
            analysis_id: Unique ID for this analysis
            project_id: ID of the project to analyze
            db: Database session
            ws_manager: WebSocket manager for real-time updates
            user_context: Optional user context for the analysis
            
        Returns:
            Dict with analysis results
        """
        api_attempt = 0
        constraint_attempt = 0
        total_attempts = 0
        last_error = None
        
        max_total_attempts = self.max_api_retries + self.max_constraint_retries + 1
        
        while total_attempts < max_total_attempts:
            try:
                total_attempts += 1
                logger.info(f"Starting analysis execution attempt {total_attempts} (API: {api_attempt + 1}, Constraint: {constraint_attempt}) for {analysis_id}")
                
                # Send status update
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_status",
                            "status": "initializing",
                            "analysis_id": analysis_id,
                            "attempt": total_attempts,
                            "message": f"🔄 Initializing analysis (attempt {total_attempts})..."
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
                
                # Unified approach: Always execute fresh analysis, no existing analysis checks
                logger.info(f"Starting fresh analysis execution for project {project_id} (unified approach)")
                
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
                    print(f"TOOL CREATED: {document_tool.name} for project {project_id}")
                    
                    # Create agent with document search tool
                    agent_tools = [document_tool]
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
                    print(f"AGENT CREATED: {len(technical_agent.tools)} tools registered")
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
                print(f"FORCING DOCUMENT SEARCH BEFORE AGENT EXECUTION")
                forced_search_results = await self._force_document_search(project_id)
                
                # TEMPORARILY DISABLED: Get existing analysis context for update mode
                # This was causing database session conflicts
                existing_analysis = None
                logger.info(f"Existing analysis context disabled to prevent database conflicts")
                
                # Build task description with document information, forced search results, and existing analysis context
                # Include constraint violation feedback for retry attempts
                constraint_violation_feedback = ""
                if constraint_attempt > 0:
                    constraint_violation_feedback = f"""
                    
                    🚨🚨🚨 RETRY ATTEMPT {constraint_attempt + 1}/{self.max_constraint_retries + 1} 🚨🚨🚨
                    Previous attempt failed validation. CRITICAL REQUIREMENTS:
                    
                    1. JSON FORMAT MANDATORY:
                    - RETURN ONLY VALID JSON - NO TEXT, NO MARKDOWN, NO EXPLANATIONS
                    - Response MUST start with {{ and end with }}
                    - NO explanatory text before or after the JSON
                    - DO NOT use "Technical Analysis Update" or narrative format
                    
                    2. CONSTRAINT COMPLIANCE:
                    - Team size constraint: MUST NOT exceed {getattr(project, 'team_size', 'specified')} people total
                    - Budget constraint: MUST NOT exceed ${getattr(project, 'budget', 'specified')} budget
                    - Resource allocation MUST sum to team_size or less
                    
                    3. STRUCTURE REQUIREMENT:
                    - Follow the exact JSON structure provided in the task
                    - Include all required sections: technical_analysis, risk_assessment, project_plan, recommendations
                    
                    This is a RETRY - follow ALL requirements exactly or analysis will be rejected.
                    """
                
                task_description = self._build_task_description(
                    project, 
                    user_context or "", 
                    document_status, 
                    document_preview, 
                    forced_search_results,
                    constraint_violation_feedback,
                    existing_analysis
                )
                
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
                print(f"CREW EXECUTION START: Task description length: {len(task_description)} characters")
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
                
                # Debug logging for analysis with user context
                if user_context:
                    logger.info(f"🔍 ANALYSIS WITH USER CONTEXT DEBUG:")
                    logger.info(f"   - Analysis ID: {analysis_id}")
                    logger.info(f"   - User context: {user_context}")
                    logger.info(f"   - Raw crew output length: {len(crew_output)} chars")
                    logger.info(f"   - Raw crew output preview: {crew_output[:500]}...")
                    logger.info(f"   - Raw crew output ending: ...{crew_output[-200:]}")
                
                # Parse and structure the results using Pydantic validation
                is_valid, structured_analysis, validation_error = self._validate_analysis_with_pydantic(
                    crew_output, analysis_id, project_id
                )
                
                if not is_valid:
                    logger.error(f"Analysis validation failed: {validation_error}")
                    # Debug: Log the raw output that failed validation with user context
                    if user_context:
                        logger.error(f"🔍 USER CONTEXT VALIDATION FAILURE:")
                        logger.error(f"   - Validation error: {validation_error}")
                        logger.error(f"   - User context: {user_context}")
                        logger.error(f"   - Raw output that failed: {crew_output}")
                    
                    # Check if this is a JSON format issue (agent returned formatted text)
                    if "Response is not valid JSON" in validation_error or "detected forbidden patterns" in validation_error:
                        # This is a format error, not an API error - handle it with constraint retry logic
                        if constraint_attempt < self.max_constraint_retries:
                            constraint_attempt += 1
                            logger.warning(f"JSON format validation failed. Retrying with enhanced JSON instructions (constraint attempt {constraint_attempt}/{self.max_constraint_retries})")
                            
                            # Send format retry notification
                            if ws_manager:
                                await ws_manager.broadcast(
                                    project_id,
                                    {
                                        "type": "format_validation_retry",
                                        "analysis_id": analysis_id,
                                        "validation_error": validation_error,
                                        "message": f"🔄 Agent returned formatted text instead of JSON. Retrying with enhanced instructions (attempt {constraint_attempt}/{self.max_constraint_retries})...",
                                        "timestamp": datetime.now().isoformat(),
                                        "attempt": constraint_attempt
                                    }
                                )
                            
                            # Skip to next attempt with enhanced JSON instructions
                            continue
                        else:
                            # Final format attempt failed - send formatted fallback
                            logger.error(f"Final JSON format attempt failed - sending formatted fallback")
                            if ws_manager:
                                try:
                                    formatted_output = f"""# Technical Analysis

{str(crew_output)[:2000]}

---
*Note: Agent returned formatted text instead of required JSON structure after multiple retry attempts.*"""
                                    
                                    formatted_message = {
                                        "type": "agent_message",
                                        "sender": "technical_agent", 
                                        "sender_name": "Technical Analysis Agent",
                                        "message": formatted_output,
                                        "analysis_id": analysis_id,
                                        "timestamp": str(datetime.now())
                                    }
                                    
                                    await ws_manager.broadcast(project_id, formatted_message)
                                    logger.info(f"Sent formatted fallback after JSON validation failures")
                                    
                                except Exception as format_error:
                                    logger.error(f"Failed to send formatted fallback: {format_error}")
                    
                    raise ValueError(f"Analysis validation failed: {validation_error}")
                
                if not structured_analysis:
                    raise ValueError("Analysis validation returned no structured data")
                
                # Validate constraint compliance
                validation_result = None
                if structured_analysis:
                    try:
                        analysis_dict = structured_analysis.model_dump(mode='json')
                        validation_result = self._validate_constraint_compliance(
                            project, analysis_dict, None  # Simplified - no existing analysis context
                        )
                        
                        if not validation_result["is_valid"]:
                            logger.error(f"Analysis violates constraints: {validation_result['violations']}")
                            
                            # Check if we should retry due to constraint violation
                            if constraint_attempt < self.max_constraint_retries:
                                constraint_attempt += 1
                                logger.warning(f"Retrying analysis due to constraint violation (constraint attempt {constraint_attempt}/{self.max_constraint_retries})")
                                
                                # Send constraint violation retry notification
                                if ws_manager:
                                    await ws_manager.broadcast(
                                        project_id,
                                        {
                                            "type": "constraint_violation_retry",
                                            "analysis_id": analysis_id,
                                            "violations": validation_result["violations"],
                                            "warnings": validation_result["warnings"],
                                            "message": f"🔄 Analysis violates constraints. Retrying with enhanced instructions (constraint attempt {constraint_attempt}/{self.max_constraint_retries})...",
                                            "timestamp": datetime.now().isoformat(),
                                            "attempt": constraint_attempt
                                        }
                                    )
                                
                                # Skip to next attempt with enhanced constraint instructions
                                continue
                            else:
                                # Final constraint attempt failed - send warning but continue
                                logger.error(f"Final constraint attempt failed - proceeding with warning")
                                if ws_manager:
                                    await ws_manager.broadcast(
                                        project_id,
                                        {
                                            "type": "constraint_violation",
                                            "analysis_id": analysis_id,
                                            "violations": validation_result["violations"],
                                            "warnings": validation_result["warnings"],
                                            "message": "⚠️ Analysis violates project constraints but max constraint retries reached. Manual review recommended.",
                                            "timestamp": datetime.now().isoformat()
                                        }
                                    )
                        else:
                            logger.info(f"Analysis passes constraint validation")
                            
                    except Exception as validation_error:
                        logger.error(f"Error during constraint validation: {validation_error}")
                        validation_result = {"is_valid": False, "error": str(validation_error)}
                
                # Debug logging before broadcasts
                logger.info(f"About to broadcast analysis completion for project_id: {project_id} (type: {type(project_id)})")
                logger.info(f"WebSocket manager exists: {ws_manager is not None}")
                logger.info(f"Analysis ID: {analysis_id}")
                logger.info(f"Structured analysis created: {structured_analysis is not None}")
                
                # Prepare structured data safely
                structured_data = None
                if structured_analysis:
                    try:
                        structured_data = structured_analysis.model_dump(mode='json')
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
                            "attempts": total_attempts,
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
                        
                        # If structured data is None or empty, send formatted fallback via agent_message
                        if not structured_data or len(structured_data) == 0:
                            logger.warning(f"Structured data is None/empty, sending formatted fallback message")
                            try:
                                # Create a simple formatted version of the raw output
                                formatted_output = f"""# Technical Analysis

{str(crew_result)[:2000]}

---
*Note: Analysis completed but structured parsing failed. This is the raw agent output.*"""
                                
                                formatted_message = {
                                    "type": "agent_message",
                                    "sender": "technical_agent", 
                                    "sender_name": "Technical Analysis Agent",
                                    "message": formatted_output,
                                    "analysis_id": analysis_id,
                                    "timestamp": str(datetime.now())
                                }
                                
                                await ws_manager.broadcast(project_id, formatted_message)
                                logger.info(f"Successfully sent formatted fallback message")
                                
                            except Exception as format_error:
                                logger.error(f"Failed to send formatted fallback: {format_error}")
                        
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
                                "attempts": total_attempts,
                                "completed_at": str(datetime.now())
                            }
                            
                            logger.info(f"Broadcasting fallback analysis_complete message")
                            await ws_manager.broadcast(project_id, fallback_message)
                            logger.info(f"Successfully broadcasted fallback analysis_complete")
                            
                        except Exception as fallback_error:
                            logger.error(f"Failed to broadcast fallback message: {fallback_error}")
                else:
                    logger.error(f"WebSocket manager is None - cannot broadcast messages!")
                
                logger.info(f"Analysis {analysis_id} completed successfully after {total_attempts} total attempts (API: {api_attempt}, Constraint: {constraint_attempt})")
                return {
                    "status": "completed",
                    "analysis_id": analysis_id,
                    "raw_output": str(crew_result),
                    "structured_analysis": structured_analysis,
                    "attempts": total_attempts
                }
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                logger.error(f"Analysis execution attempt {total_attempts} failed: {error_msg}")
                
                # Classify error type and determine retry strategy
                error_type = self._classify_error(e)
                should_retry_api, retry_delay = await self._should_retry_api_error(e, api_attempt + 1)
                
                if should_retry_api:
                    api_attempt += 1
                    logger.warning(f"API error detected ({error_type}). Retrying in {retry_delay} seconds... (API attempt {api_attempt}/{self.max_api_retries})")
                    
                    if ws_manager:
                        await ws_manager.broadcast(
                            project_id,
                            {
                                "type": "api_retry",
                                "status": "api_retrying", 
                                "analysis_id": analysis_id,
                                "error_type": error_type,
                                "retry_delay": retry_delay,
                                "message": f"🔄 {error_type.replace('_', ' ').title()} detected. Retrying in {retry_delay} seconds... (API attempt {api_attempt}/{self.max_api_retries})",
                                "timestamp": datetime.now().isoformat(),
                                "attempt": api_attempt
                            }
                        )
                    
                    # Wait before retrying
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    # No more API retries or non-retryable error
                    logger.error(f"Analysis {analysis_id} failed after {total_attempts} total attempts (API: {api_attempt}, Constraint: {constraint_attempt})")
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
            
            # Parse results using Pydantic validation
            is_valid, structured_analysis, validation_error = self._validate_analysis_with_pydantic(
                crew_output, analysis_id, project_id
            )
            
            if not is_valid:
                logger.error(f"Regeneration analysis validation failed: {validation_error}")
                raise ValueError(f"Regeneration analysis validation failed: {validation_error}")
            
            if not structured_analysis:
                raise ValueError("Regeneration analysis validation returned no structured data")
            
            # Debug logging before broadcasts
            logger.info(f"About to broadcast regeneration completion for project_id: {project_id} (type: {type(project_id)})")
            logger.info(f"WebSocket manager exists: {ws_manager is not None}")
            logger.info(f"Analysis ID: {analysis_id}")
            logger.info(f"Structured analysis created: {structured_analysis is not None}")
            
            # Prepare structured data safely
            structured_data = None
            if structured_analysis:
                try:
                    structured_data = structured_analysis.model_dump(mode='json')
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
    
    async def _get_existing_analysis_context(self, db: AsyncSession, project_id: str) -> Optional[Dict[str, Any]]:
        """Get existing analysis data for update context"""
        try:
            from app.db.models import Analysis
            from sqlalchemy import select
            
            # Use async query syntax
            query = select(Analysis).where(
                Analysis.project_id == project_id
            ).order_by(Analysis.created_at.desc()).limit(1)
            
            result = await db.execute(query)
            existing_analysis = result.scalars().first()
            
            if existing_analysis:
                import json
                analysis_result = json.loads(existing_analysis.result) if isinstance(existing_analysis.result, str) else existing_analysis.result
                return analysis_result
            return None
        except Exception as e:
            logger.warning(f"Could not retrieve existing analysis for context: {e}")
            return None

    def _build_task_description(self, project: Project, user_context: str = "", document_status: Dict[str, Any] = None, document_preview: str = "", forced_search_results: str = "", constraint_violation_feedback: str = "", existing_analysis: Optional[Dict[str, Any]] = None) -> str:
        """Build unified task description for analysis with optional user context"""
        
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
        
        # Determine analysis mode and build context sections
        analysis_mode = "update" if existing_analysis else "initial"
        
        # Build project brief section
        project_brief_section = ""
        if hasattr(project, 'brief_sections') and project.brief_sections:
            project_brief_section = f"""
        
        📋 PROJECT BRIEF (Generated by Project Planner):
        {self._format_project_brief_for_analysis(project.brief_sections)}
        
        ✅ IMPORTANT: This comprehensive project brief provides detailed context about the project. 
        Use this information to inform your technical analysis and recommendations.
        """
        
        # Build constraint preservation section with extra emphasis on team size
        team_size = getattr(project, 'team_size', None)
        team_size_constraint = ""
        if team_size is not None:
            team_size_constraint = f"""
        
        🚨🚨🚨 CRITICAL TEAM SIZE CONSTRAINT 🚨🚨🚨
        - MAXIMUM TEAM SIZE: {team_size} people total
        - This includes ALL roles: developers, designers, QA, DevOps, PM, and any other roles
        - You MUST NOT exceed this limit under any circumstances
        - If {team_size} = 1, then ALL work must be done by 1 person (full-stack developer)
        - If {team_size} = 2, then distribute work among 2 people maximum
        - Resource allocation MUST sum to exactly {team_size} or less
        
        RESOURCE ALLOCATION RULES:
        - For team_size = 1: {{"developers": 1, "designers": 0, "qa": 0, "devops": 0, "pm": 0, "other": {{}}}}
        - For team_size = 2: Example: {{"developers": 1, "designers": 1, "qa": 0, "devops": 0, "pm": 0, "other": {{}}}}
        - The sum of all resource values MUST NOT exceed {team_size}
        """
        
        constraint_section = f"""
        
        🔒 PROJECT CONSTRAINTS (MUST BE PRESERVED):
        - Project Deadline: {getattr(project, 'deadline', 'Not specified')}
        - Budget Constraint: {getattr(project, 'budget', 'Not specified')}
        - Team Size Limit: {team_size} people maximum
        - Project Goal: {getattr(project, 'goal', 'Not specified')}
        {team_size_constraint}
        
        ⚠️ CRITICAL: These constraints MUST be respected in your analysis. Do not violate these limits.
        🚨 TEAM SIZE CONSTRAINT: You MUST NOT recommend more than {team_size} team members total.
        """
        
        # Debug logging for constraint verification
        logger.info(f"🔍 PROJECT CONSTRAINTS DEBUG:")
        logger.info(f"   - Project ID: {project.id}")
        logger.info(f"   - Team Size: {getattr(project, 'team_size', 'Not specified')}")
        logger.info(f"   - Budget: {getattr(project, 'budget', 'Not specified')}")
        logger.info(f"   - Deadline: {getattr(project, 'deadline', 'Not specified')}")
        logger.info(f"   - Goal: {getattr(project, 'goal', 'Not specified')}")
        
        # Build analysis mode section - unified approach for all analysis requests
        analysis_mode_section = """
        
        📋 ANALYSIS MODE: UNIFIED STRUCTURED FORMAT
        - Always create fresh, comprehensive analysis based on project data
        - Respect all project constraints listed above
        - CRITICAL: Follow EXACT JSON structure as specified in agents.yaml
        - Use clear, concise format matching the required template
        - Structure: Technical Analysis → Risk Assessment → Project Plan → Recommendations
        - Ensure proper phase naming with durations in weeks
        - Timeline format: "Month Day, Year - Month Day, Year"
        """
        
        # Build user context section
        user_context_section = ""
        if user_context:
            user_context_section = f"""
        
        🔥 USER CONTEXT - INCORPORATE INTO ANALYSIS:
        {user_context}
        
        ⚠️ IMPORTANT: The above context should be integrated into your comprehensive analysis.
        Consider this context when making recommendations and planning decisions.
        """
        
        base_description = f"""
        Analyze the project '{project.name}' and provide a comprehensive technical analysis based on the uploaded project documents.{project_brief_section}{constraint_section}{constraint_violation_feedback}{analysis_mode_section}{user_context_section}
        
        Project Details:
        - Name: {project.name}
        - Description: {project.description or 'No description provided'}
        - Industry: {getattr(project, 'industry', 'Not specified')}
        - Team Size: {getattr(project, 'team_size', 'Not specified')}
        - Budget: {getattr(project, 'budget', 'Not specified')}
        - Deadline: {getattr(project, 'deadline', 'Not specified')}
        - Analysis Mode: {analysis_mode.upper()}{doc_info}
        
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
        🚨🚨🚨 CRITICAL: YOU MUST RETURN EXACTLY THIS JSON FORMAT - NO DEVIATIONS ALLOWED 🚨🚨🚨
        
        ABSOLUTE REQUIREMENTS:
        1. RETURN ONLY VALID JSON - NO TEXT, NO MARKDOWN, NO EXPLANATIONS
        2. DO NOT create "Technical Analysis Update" format
        3. DO NOT use Start Date/End Date fields
        4. DO NOT create "Architecture Overview" sections
        5. MUST match the original analysis structure EXACTLY
        6. Your response must start with {{ and end with }}
        7. NO explanatory text before or after the JSON
        
        REQUIRED JSON STRUCTURE (copy this structure exactly):
        {{
          "analysis_mode": "initial|update",
          "technical_analysis": {{
            "architecture": "Specific architectural pattern based on documents",
            "tech_stack": {{
              "frontend": ["Technologies found in documents"],
              "backend": ["Technologies found in documents"], 
              "infrastructure": ["Infrastructure mentioned in documents"],
              "tools": ["Tools and frameworks from documents"]
            }},
            "complexity_score": [1-10 based on document analysis],
            "maintainability_score": [1-10 based on document findings],
            "scalability_score": [1-10 based on requirements],
            "performance_score": [1-10 based on requirements],
            "security_score": [1-10 based on requirements]
          }},
          "risk_assessment": {{
            "overall_risk_score": [1-10 based on project complexity],
            "key_risks": [
              {{
                "name": "Risk name from analysis",
                "level": "Low/Medium/High",
                "impact": [1-10],
                "probability": [1-10], 
                "description": "Description based on document findings"
              }}
            ],
            "mitigation_strategies": ["Strategies based on identified risks"]
          }},
          "project_plan": {{
            "timeline": "Timeline preserving original deadline constraints",
            "estimated_cost": [Cost respecting original budget constraints],
            "phases": [
              {{
                "name": "Phase name",
                "duration": [weeks],
                "description": "Phase description"
              }}
            ],
            "milestones": [
              {{
                "name": "Milestone name",
                "date": "Target date within original timeline",
                "status": "upcoming",
                "description": "Milestone description"
              }}
            ],
            "resource_requirements": {{
              "developers": [whole number - integer only, no decimals],
              "designers": [whole number - integer only, no decimals],
              "qa": [whole number - integer only, no decimals],
              "devops": [whole number - integer only, no decimals],
              "pm": 1,
              "other": {{}}
            }}
          }},
          "recommendations": ["Recommendations based on document analysis"],
          "explanations": {{
            "complexity_reasoning": "Cite specific documents and findings",
            "risk_analysis_details": "Cite specific documents and findings",
            "technology_rationale": "Cite specific documents and findings"
          }}
        }}
        
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
        
        # Additional context is already included prominently at the top
        
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
    
    def _format_project_brief_for_analysis(self, brief_sections: Dict[str, Any]) -> str:
        """Format project brief data for inclusion in technical analysis context"""
        if not brief_sections or not isinstance(brief_sections, dict):
            return "No project brief available"
        
        formatted_sections = []
        
        # Define the preferred order of sections
        section_order = [
            'project_overview', 'project_background', 'business_case', 
            'goals_success_criteria', 'target_audience', 'high_level_scope',
            'high_level_requirements', 'preliminary_timeline', 'preliminary_budget',
            'key_stakeholders', 'initial_resources', 'next_steps'
        ]
        
        # Format sections in order
        for section_id in section_order:
            if section_id in brief_sections:
                section_data = brief_sections[section_id]
                if isinstance(section_data, dict) and 'content' in section_data:
                    title = section_data.get('title', section_id.replace('_', ' ').title())
                    content = section_data['content']
                    formatted_sections.append(f"**{title}:**\n{content}")
        
        # Add any remaining sections not in the predefined order
        for section_id, section_data in brief_sections.items():
            if section_id not in section_order and isinstance(section_data, dict):
                title = section_data.get('title', section_id.replace('_', ' ').title())
                content = section_data.get('content', str(section_data))
                formatted_sections.append(f"**{title}:**\n{content}")
        
        return "\n\n".join(formatted_sections) if formatted_sections else "Project brief sections found but content not available"
