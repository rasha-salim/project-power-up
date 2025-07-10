import os
import logging
import re
import uuid
import asyncio
import json
from datetime import datetime
from decimal import Decimal
import traceback
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from crewai import Agent, Task, Crew, Process
from langchain_anthropic import ChatAnthropic
from app.models.analysis import ProjectAnalysis, TechnicalAnalysis, RiskAssessment, ProjectPlan
from app.models.analysis import TechStackCategory, Risk, ResourceRequirements, ProjectPhase, Milestone, EffortDistribution, RiskLevel
from app.models.project import Project
from app.services.project_service import ProjectService
from app.services.websocket_manager import WebSocketManager
from app.services.analysis_helper import AnalysisDataHelper
from app.tools.document_search import DocumentSearchTool
from app.core.agent_registry import agent_registry
from app.config.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

class AgentService:
    """Service for managing AI agents using CrewAI with Anthropic integration"""
    
    def __init__(self):
        """Initialize the agent service"""
        self.config_loader = ConfigLoader()
        self.running_tasks = {}
        self.pending_analyses = {}
    
    def _safe_json_dumps(self, obj, **kwargs):
        """
        Safely serialize an object to JSON, handling datetime and other non-serializable types
        """
        def json_serial(obj):
            """JSON serializer for objects not serializable by default json code"""
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                return float(obj)
            elif hasattr(obj, '__dict__'):
                return obj.__dict__
            else:
                return str(obj)
        
        return json.dumps(obj, default=json_serial, **kwargs)
    
    async def start_analysis(self, db: AsyncSession, project_id: str, ws_manager: Optional[WebSocketManager] = None, force: bool = False) -> str:
        """
        Start an agent analysis for a project
        
        Args:
            db: Database session
            project_id: ID of the project to analyze
            ws_manager: Optional WebSocket manager for real-time updates
            
        Returns:
            str: ID of the analysis
        """
        # Generate a unique analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Log the start of the analysis
        logger.info(f"Starting agent analysis for project {project_id} (force={force})")
        
        # Notify clients if WebSocket manager is provided
        if ws_manager:
            await ws_manager.broadcast(
                project_id,
                {
                    "type": "analysis_status",
                    "status": "starting",
                    "analysis_id": analysis_id,
                    "message": "Starting agent analysis"
                }
            )
        
        # Start the analysis in the background
        task = asyncio.create_task(
            self._execute_analysis(analysis_id, project_id, db, ws_manager, force)
        )
        
        # Track the running task
        self.running_tasks[analysis_id] = task
        
        # Clean up completed tasks
        def cleanup_task(task):
            if analysis_id in self.running_tasks:
                del self.running_tasks[analysis_id]
        
        task.add_done_callback(cleanup_task)
        
        return analysis_id
    
    async def _execute_analysis_with_context(
        self, 
        analysis_id: str, 
        project_id: str,
        db: AsyncSession,
        ws_manager: Optional[WebSocketManager] = None,
        additional_context: str = ""
    ):
        """
        Execute analysis with additional context provided by the user
        
        Args:
            analysis_id: ID of the analysis
            project_id: ID of the project
            db: Database session
            ws_manager: WebSocket manager for real-time updates
            additional_context: Additional context from user message
        """
        try:
            logger.info(f"Starting analysis {analysis_id} with context: {additional_context}")
            
            # Update status
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_status",
                        "status": "loading_documents",
                        "analysis_id": analysis_id,
                        "message": "Loading project documents..."
                    }
                )
            
            # Import document processor
            from app.services.document_processor import DocumentProcessor
            document_processor = DocumentProcessor()
            
            # Get all documents for this project
            documents = await document_processor.list_documents(db, project_id)
            
            # Check if any documents are still processing
            processing_docs = [doc for doc in documents if doc.status == "processing"]
            if processing_docs:
                logger.warning(f"Cannot start analysis - {len(processing_docs)} documents still processing")
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "analysis_id": analysis_id,
                            "message": f"Cannot start analysis - {len(processing_docs)} documents still processing"
                        }
                    )
                return
            
            # Set up Anthropic LLM
            anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
            anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
            
            if not anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not found")
            
            # Initialize LLM
            llm = ChatAnthropic(
                model_name=anthropic_model,
                anthropic_api_key=anthropic_api_key,
                temperature=0.3,
                max_tokens=4000
            )
            
            # Pre-fetch all relevant document content using batch search
            # This reduces API calls by getting all content upfront
            document_search_tool = DocumentSearchTool(project_id)
            
            # Define key search terms for comprehensive document analysis
            search_queries = [
                "requirements specifications functional non-functional",
                "architecture design system structure patterns",
                "technology stack frameworks tools libraries",
                "timeline schedule milestones deadlines budget cost",
                "security privacy authentication authorization",
                "performance scalability database API integration"
            ]
            
            logger.info(f"Pre-fetching document content with batch search for project {project_id}")
            
            # Get all relevant document content in one operation
            try:
                comprehensive_document_content = document_search_tool.batch_search(search_queries, limit_per_query=3)
                logger.info(f"Batch search completed, content length: {len(comprehensive_document_content)}")
            except Exception as e:
                logger.error(f"Batch search failed, falling back to basic search: {e}")
                # Fallback to basic search if batch fails
                comprehensive_document_content = document_search_tool._run("project requirements architecture technology", limit=10)
            
            # Load agent configuration
            agent_config = self.config_loader.get_agent_config("technical_analyst")
            if not agent_config:
                raise ValueError("Technical analyst agent configuration not found")
            
            # Create the technical agent WITHOUT document search tool
            # Since we've already fetched all document content
            technical_agent = Agent(
                role=agent_config["role"],
                goal=agent_config["goal"],
                backstory=agent_config["backstory"],
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=[]  # No tools needed - we provide document content directly
            )
            
            # Get document previews for fallback
            document_previews = []
            for doc in documents[:5]:  # Limit to first 5 documents
                preview = f"- {doc.filename}: {doc.content[:200]}..." if hasattr(doc, 'content') and doc.content else f"- {doc.filename}: [No content available]"
                document_previews.append(preview)
            
            # Build task description with pre-fetched document content
            task_description = f"""
            Analyze the technical aspects of project {project_id}.
            
            Additional Context from User:
            {additional_context}
            
            COMPREHENSIVE DOCUMENT CONTENT:
            All relevant project documents have been pre-analyzed and compiled below.
            Use this information as the foundation for your technical analysis.
            
            {comprehensive_document_content}
            
            ANALYSIS REQUIREMENTS:
            Based on the document content above, provide your analysis in the structured JSON format
            specified in your configuration. Include:
            1. Architecture recommendations based on documented requirements
            2. Technology stack suggestions from identified technologies
            3. Technical challenges and risks from project complexity
            4. Implementation timeline respecting documented constraints
            5. Resource requirements based on project scope
            
            Make sure to reference specific document content in your explanations and
            incorporate the user's additional context in all aspects of your analysis.
            """
            
            # Create task
            task = Task(
                description=task_description,
                expected_output=agent_config["expected_output"],
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
                        "message": "Analyzing project with your additional context..."
                    }
                )
            
            # Execute the analysis
            result = crew.kickoff()
            
            # Convert result to string
            if hasattr(result, 'raw'):
                crew_result = result.raw
            else:
                crew_result = str(result)
            
            logger.info(f"Analysis completed for {analysis_id}")
            
            # Try to parse the result as structured JSON data
            analysis_result = crew_result
            try:
                import json
                if crew_result.strip().startswith('{') and crew_result.strip().endswith('}'):
                    # Parse as JSON to preserve structure
                    parsed_result = json.loads(crew_result)
                    if any(key in parsed_result for key in ['technical_analysis', 'risk_assessment', 'project_plan']):
                        analysis_result = parsed_result
                    else:
                        analysis_result = crew_result
            except (json.JSONDecodeError, ValueError):
                # Keep as string if not valid JSON
                analysis_result = crew_result
            
            # Update pending analysis with result
            self.pending_analyses[analysis_id] = {
                "project_id": project_id,
                "status": "completed",
                "result": analysis_result if isinstance(analysis_result, dict) else {
                    "raw_analysis": crew_result,
                    "additional_context": additional_context,
                    "analysis_id": analysis_id,
                    "project_id": project_id,
                    "version": 1,
                    "created_at": datetime.utcnow().isoformat()
                },
                "crew": crew,
                "technical_agent": technical_agent,
                "document_search_tool": document_search_tool
            }
            
            # Send completion message
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_complete",
                        "analysis_id": analysis_id,
                        "result": self.pending_analyses[analysis_id]["result"],
                        "message": "Analysis complete!",
                        "show_save_button": True
                    }
                )
                
                # Send formatted agent message with analysis content
                # Format the analysis result for display
                if isinstance(analysis_result, dict):
                    # If it's structured data, format it properly
                    from app.utils.message_formatter import MessageFormatter
                    formatted_message = MessageFormatter.format_technical_analysis(analysis_result)
                    if additional_context:
                        formatted_message = f"Here is the previous analysis for this project:\n\n{formatted_message}"
                    else:
                        formatted_message = f"Here is the updated analysis for this project:\n\n{formatted_message}"
                else:
                    # If it's raw text, format it as a regular response
                    from app.utils.message_formatter import MessageFormatter
                    formatted_message = MessageFormatter.format_agent_response(analysis_result)
                
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical_analyst",
                        "sender_name": "Technical Analysis Agent",
                        "message": formatted_message,
                        "analysis_id": analysis_id,
                        "structured_data": analysis_result if isinstance(analysis_result, dict) else None
                    }
                )
            
        except Exception as e:
            logger.error(f"Error in analysis execution: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Update status
            self.pending_analyses[analysis_id] = {
                "project_id": project_id,
                "status": "error",
                "error": str(e)
            }
            
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "error",
                        "analysis_id": analysis_id,
                        "message": f"Analysis failed: {str(e)}"
                    }
                )
    
    async def get_analysis_status(self, db: AsyncSession, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status and results of an analysis
        
        Args:
            db: Database session
            analysis_id: ID of the analysis to retrieve
            
        Returns:
            Optional[Dict[str, Any]]: Analysis status and results if found, None otherwise
        """
        # In a real implementation, this would query the database
        # For now, we'll return a simulated result
        from app.services.project_service import ProjectService
        project_service = ProjectService()
        
        # Get all projects (in a real implementation, we would filter by analysis_id)
        projects = await project_service.list_projects(db)
        
        # Find the project with this analysis
        for project in projects:
            if project.get("insights") and project["insights"].get("analysis_id") == analysis_id:
                return {
                    "analysis_id": analysis_id,
                    "status": "completed",
                    "results": project["insights"]
                }
        
        # If not found, return a pending status
        return {
            "analysis_id": analysis_id,
            "status": "pending",
            "results": None
        }
    
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
                del self.running_tasks[analysis_id]
                
                logger.info(f"Successfully cancelled analysis {analysis_id}")
                return True
            else:
                logger.warning(f"Analysis {analysis_id} not found in running tasks")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling analysis {analysis_id}: {e}")
            return False
    
    async def handle_user_question(self, db: AsyncSession, analysis_id: str, question: str, ws_manager: Optional[WebSocketManager] = None) -> str:
        """
        Handle a user question about the analysis
        
        Args:
            db: Database session
            analysis_id: ID of the analysis
            question: User's question
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            str: Agent's response
        """
        try:
            logger.info(f"Handling user question for analysis {analysis_id}")
            logger.info(f"Question content: {question}")
            logger.info(f"Current pending analyses: {list(self.pending_analyses.keys())}")
            
            # Check if we have the analysis in memory
            if analysis_id not in self.pending_analyses:
                logger.error(f"Analysis {analysis_id} not found in pending analyses")
                # Try to use general chat instead
                if ws_manager:
                    await ws_manager.broadcast(
                        analysis_id,  # This might be wrong, but we don't have project_id
                        {
                            "type": "agent_message",
                            "sender": "assistant",
                            "sender_name": "Project Assistant",
                            "message": "I notice the analysis context has been lost. Let me help you with your question using the general chat feature instead.",
                            "analysis_id": analysis_id
                        }
                    )
                return "Analysis context not found. Please try asking your question as a general chat message instead."
            
            pending = self.pending_analyses[analysis_id]
            project_id = pending["project_id"]
            technical_agent = pending["technical_agent"]
            document_search_tool = pending["document_search_tool"]
            
            # Check if this is a feedback request rather than a question
            feedback_patterns = [
                r'(?i)update.*analysis',
                r'(?i)focus.*on',
                r'(?i)regenerate',
                r'(?i)focus.*more',
                r'(?i)please.*update',
                r'(?i)modify.*analysis',
                r'(?i)change.*analysis',
                r'(?i)redo.*analysis',
                r'(?i)improve.*analysis',
                r'(?i)revise.*analysis',
                r'(?i)demo',
                r'(?i)technical.*aspects'
            ]
            
            is_feedback_request = any(re.search(pattern, question.lower()) for pattern in feedback_patterns)
            logger.info(f"Is feedback request detected in handle_user_question: {is_feedback_request}")
            
            if is_feedback_request:
                logger.info(f"Routing feedback request to regenerate_analysis_with_feedback: {question}")
                # Handle as a feedback request instead of a question
                result = await self.regenerate_analysis_with_feedback(db, analysis_id, question, ws_manager)
                return "Processing your feedback to update the analysis."
                
            logger.info(f"Handling as standard question for analysis {analysis_id}: {question}")
            
            # Send status update
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical_agent",
                        "sender_name": "Technical Analysis Agent",
                        "message": "Let me analyze your question...",
                        "is_thinking": True
                    }
                )
            
            # Create a follow-up task for the agent
            follow_up_task = Task(
                description=f"""
                Based on the previous analysis and the project documents, answer this user question:
                
                {question}
                
                Provide a detailed and helpful response that directly addresses their question.
                Reference specific parts of the project documentation if relevant.
                """, 
                agent=technical_agent,
                tools=[document_search_tool],
                expected_output="A clear and detailed answer to the user's question"
            )
            
            # Execute the task
            response = technical_agent.execute_task(follow_up_task)
            
            # Convert response to string
            if hasattr(response, 'raw'):
                response_text = response.raw
            else:
                response_text = str(response)
            
            # Send the response
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical_agent",
                        "sender_name": "Technical Analysis Agent",
                        "message": response_text,
                        "analysis_id": analysis_id
                    }
                )
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error handling user question for analysis {analysis_id}: {e}")
            error_msg = "I apologize, but I encountered an error while processing your question. Please try again."
            
            if ws_manager and analysis_id in self.pending_analyses:
                await ws_manager.broadcast(
                    self.pending_analyses[analysis_id]["project_id"],
                    {
                        "type": "error",
                        "analysis_id": analysis_id,
                        "message": error_msg
                    }
                )
            
            return error_msg
    
    async def regenerate_analysis_with_feedback(self, db: AsyncSession, analysis_id: str, user_feedback: str, ws_manager: Optional[WebSocketManager] = None) -> bool:
        """
        Regenerate the analysis incorporating user feedback and suggestions
        
        Args:
            db: Database session
            analysis_id: ID of the current analysis
            user_feedback: User's notes and suggestions
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            bool: True if regeneration was successful, False otherwise
        """
        try:
            # Check if we have the analysis in memory
            if analysis_id not in self.pending_analyses:
                logger.error(f"Analysis {analysis_id} not found in pending analyses")
                return False
            
            pending = self.pending_analyses[analysis_id]
            project_id = pending["project_id"]
            previous_result = pending["result"]
            
            # Get project details from DB
            from app.models.project import Project
            project = await db.get(Project, project_id)
            if not project:
                logger.error(f"Project {project_id} not found")
                return False
            
            logger.info(f"Regenerating analysis {analysis_id} with user feedback for project {project_id}")
            
            # Send status update
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical_agent",
                        "sender_name": "Technical Analysis Agent",
                        "message": "I'm incorporating your feedback and regenerating the analysis...",
                        "is_thinking": True
                    }
                )
            
            # Set up Anthropic LLM
            anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
            anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
            
            if not anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            
            # Initialize LLM
            llm = ChatAnthropic(
                model_name=anthropic_model,
                anthropic_api_key=anthropic_api_key,
                temperature=0.2,
                max_tokens=4000
            )
            
            # Create document search tool
            document_search_tool = DocumentSearchTool(project_id)
            
            # Load agent configuration
            agent_config = self.config_loader.get_agent_config("technical_analyst")
            if not agent_config:
                raise ValueError("Technical analyst agent configuration not found")
            
            # Create the agent with all required parameters
            technical_agent = Agent(
                role=agent_config["role"],
                goal=f"Answer specific questions about the technical analysis for project {project_id}",
                backstory=agent_config["backstory"],
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=[document_search_tool]
            )
            
            # Prepare document content for context
            document_content = []
            for doc in documents:
                document_content.append({
                    "id": doc.id,
                    "filename": doc.filename,
                    "description": doc.description or "",
                    "content_preview": doc.content[:500] if hasattr(doc, "content") and doc.content else "Content not available"
                })
            
            # Create context for the agent including previous analysis and user feedback
            context_str = f"""
            Project ID: {project_id}\n\nDocuments:\n"""
            for doc in document_content:
                context_str += f"\n--- Document: {doc['filename']} ---\n"
                context_str += f"Description: {doc['description']}\n\n"
                context_str += f"Preview: {doc['content_preview']}\n"
            
            # Add user feedback to context
            feedback_context = f"\n\nPrevious Analysis Summary:\n{self._safe_json_dumps(previous_result.get('technical_analysis', 'No previous analysis'), indent=2)[:500]}\n\n"
            feedback_context += f"User Feedback: {user_feedback}\n\n"
            
            # Create task exactly like in start_analysis
            regeneration_task = Task(
                description=f"""
                Previous Analysis:
                {self._safe_json_dumps(previous_result.get("result", {}), indent=2)}
                
                User Feedback:
                {feedback}
                
                Project Details:
                - Name: {project.get("name", "Unknown")}
                - Description: {project.get("description", "No description")}
                
                Please regenerate the technical analysis incorporating the user's feedback.
                You MUST maintain the exact same structure and format as the previous analysis.
                Return your response as a detailed technical analysis in the same format as before.
                
                IMPORTANT: Your output MUST be in the exact same format as the original technical analysis.
                Do not use a simplified format with just a summary field.
                """,
                expected_output="Updated technical analysis incorporating user feedback",
                agent=technical_agent
            )
            
            # Create crew exactly like in start_analysis
            crew = Crew(
                agents=[technical_agent],
                tasks=[regeneration_task],
                process=Process.sequential,
                verbose=True
            )
            
            logger.info("Successfully created regeneration task and crew")
            
            # Execute the crew to get the regenerated analysis
            result = crew.kickoff()
            
            # Update the analysis result with the new version
            if analysis_id in self.pending_analyses:
                # Increment version number
                current_version = self.pending_analyses[analysis_id].get("version", 1)
                new_version = current_version + 1
                
                # Create a complete result structure
                analysis_result = {
                    "technical_analysis": str(result),
                    "version": new_version,
                    "feedback_incorporated": user_feedback,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Update the pending analysis with the complete result
                self.pending_analyses[analysis_id] = {
                    "project_id": project_id,
                    "result": analysis_result,
                    "version": new_version,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                logger.info(f"Successfully updated analysis {analysis_id} with new version {new_version}")
                
                # Send the updated analysis via WebSocket - using the same message type as the New Analysis flow
                if ws_manager:
                    # First, send the analysis_complete message with is_regeneration flag
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_complete",
                            "analysis_id": analysis_id,
                            "result": analysis_result,
                            "version": new_version,
                            "is_regeneration": True,
                            "message": f"Analysis regenerated successfully (version {new_version})"
                        }
                    )
                    
                    # Send a follow-up message
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "agent_message",
                            "sender": "technical",
                            "sender_name": "Technical Analysis Agent",
                            "message": "I've updated the analysis based on your feedback. The changes have been incorporated into the recommendations. You can now save this updated version or provide additional feedback.",
                            "analysis_id": analysis_id
                        }
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"Error regenerating analysis {analysis_id} with feedback: {e}")
            
            if ws_manager and analysis_id in self.pending_analyses:
                await ws_manager.broadcast(
                    self.pending_analyses[analysis_id]["project_id"],
                    {
                        "type": "error",
                        "analysis_id": analysis_id,
                        "message": f"Failed to regenerate analysis: {str(e)}"
                    }
                )
            
            return False
    
    async def chat_with_agent(self, db: AsyncSession, project_id: str, message: str, ws_manager: Optional[WebSocketManager] = None) -> str:
        """
        Handle a general chat message with the agent for a project
        
        Args:
            db: Database session
            project_id: ID of the project
            message: User's message
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            str: Agent's response
        """
        try:
            logger.info(f"Handling chat message for project {project_id}: {message}")
            
            # Send status update
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "assistant",
                        "sender_name": "Project Assistant",
                        "message": "Let me help you with that...",
                        "is_thinking": True
                    }
                )
            
            # Set up Anthropic LLM
            anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
            anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
            
            if not anthropic_api_key:
                error_msg = "AI service not configured properly"
                logger.error("ANTHROPIC_API_KEY not found")
                return error_msg
            
            # Initialize the LLM
            llm = ChatAnthropic(
                model_name=anthropic_model,
                anthropic_api_key=anthropic_api_key,
                temperature=0.3,
                max_tokens=2000
            )
            
            # Create the document search tool for this project
            document_search_tool = DocumentSearchTool(project_id)
            
            # Get project details for context
            from app.services.project_service import ProjectService
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            
            # Create a conversational agent with a more flexible role
            chat_agent = Agent(
                role="Project Assistant",
                goal="Help users understand their project, answer questions about documents, provide technical guidance, and assist with project-related queries",
                backstory="""You are a knowledgeable project assistant with expertise in:
                - Technical analysis and software architecture
                - Project management and planning
                - Risk assessment and mitigation
                - Understanding and explaining project documentation
                
                You have access to all project documents and can search through them to provide accurate information.
                You should be helpful, conversational, and provide clear explanations tailored to the user's needs.
                When referencing project documents, cite specific sections or files when possible.""",
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=[document_search_tool]
            )
            
            # Build context about the project
            context = f"""
            Project: {project.get("name") if project else 'Unknown'}
            Description: {project.get("description") if project else 'No description available'}
            
            User Message: {message}
            """
            
            # Check if the message is asking about project insights
            if project and project.get("insights") and any(keyword in message.lower() for keyword in ['analysis', 'insights', 'recommendations', 'technical', 'risks', 'plan']):
                context += f"\n\nPrevious Analysis Results:\n{json.dumps(project['insights'], indent=2)}"
            
            # Create a task for the chat
            chat_task = Task(
                description=f"""
                User message: {message}
                
                Project context:
                - Name: {project.name}
                - Description: {project.description}
                
                Please provide a helpful response to the user's message.
                If they're asking about project documents, use the search tool.
                If they're asking about analysis results and insights are available, reference them.
                """,
                agent=chat_agent,
                tools=[document_search_tool],
                expected_output="A helpful and relevant response to the user's message"
            )
            
            # Create crew
            crew = Crew(
                agents=[chat_agent],
                tasks=[chat_task],
                process=Process.sequential,
                verbose=True
            )
            
            logger.info("Executing crew for chat")
            
            # Send initial thinking message
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "assistant",
                        "sender_name": "Project Assistant",
                        "message": "Let me help you with that...",
                        "is_thinking": True
                    }
                )
            
            # Execute the crew
            result = crew.kickoff()
            
            # Send the response
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "assistant",
                        "sender_name": "Project Assistant",
                        "message": str(result)
                    }
                )
            
            return str(result)
            
        except Exception as e:
            logger.error(f"Error in chat_with_agent for project {project_id}: {e}")
            error_msg = "I apologize, but I encountered an error. Please try again."
            
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "error",
                        "message": error_msg
                    }
                )
            
            return error_msg
    
    async def answer_analysis_question(
        self, 
        db: AsyncSession, 
        project_id: str,
        analysis_id: str,
        question: str,
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Answer specific questions about the analysis using the technical agent
        
        Args:
            db: Database session
            project_id: ID of the project
            analysis_id: ID of the analysis
            question: User's question about the analysis
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            Dict with status and response
        """
        try:
            logger.info(f"Answering question about analysis {analysis_id}: {question}")
            
            # Check if we have the analysis in memory
            if analysis_id not in self.pending_analyses:
                logger.error(f"Analysis {analysis_id} not found in pending analyses")
                
                # Try to load from database
                structured_analysis = await self.load_structured_analysis(db, project_id)
                if not structured_analysis:
                    return {
                        "status": "error",
                        "message": "Analysis not found. Please run a new analysis first."
                    }
                
                # Store in pending analyses for reference
                self.pending_analyses[analysis_id] = {
                    "project_id": project_id,
                    "result": {
                        "technical_analysis": structured_analysis.dict() if hasattr(structured_analysis, 'dict') else structured_analysis
                    }
                }
            
            pending = self.pending_analyses[analysis_id]
            analysis_result = pending.get("result", {})
            
            # Send thinking message
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical",
                        "sender_name": "Technical Analysis Agent",
                        "message": "Let me analyze your question...",
                        "is_thinking": True,
                        "analysis_id": analysis_id
                    }
                )
            
            # Set up Anthropic LLM
            anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
            anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
            
            if not anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            
            # Initialize LLM
            llm = ChatAnthropic(
                model_name=anthropic_model,
                anthropic_api_key=anthropic_api_key,
                temperature=0.2,
                max_tokens=2000
            )
            
            # Create document search tool
            document_search_tool = DocumentSearchTool(project_id)
            
            # Load agent configuration
            agent_config = self.config_loader.get_agent_config("technical_analyst")
            if not agent_config:
                raise ValueError("Technical analyst agent configuration not found")
            
            # Create the agent with question-answering focus
            technical_agent = Agent(
                role=agent_config["role"],
                goal=f"Answer specific questions about the technical analysis for project {project_id}",
                backstory=agent_config["backstory"],
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=[document_search_tool]
            )
            
            # Prepare context from the analysis
            # Extract the actual analysis content
            if isinstance(analysis_result, dict):
                # If we have technical_analysis key, use that
                if "technical_analysis" in analysis_result:
                    analysis_content = analysis_result["technical_analysis"]
                else:
                    analysis_content = analysis_result
            else:
                analysis_content = str(analysis_result)
            
            # If analysis_content is still a complex object, try to extract meaningful data
            if isinstance(analysis_content, dict):
                # Look for common analysis fields
                relevant_fields = ["architecture", "tech_stack", "risks", "recommendations", 
                                 "timeline", "challenges", "complexity_score", "risk_assessment",
                                 "project_plan", "technical_analysis"]
                extracted_content = {}
                for field in relevant_fields:
                    if field in analysis_content:
                        extracted_content[field] = analysis_content[field]
                if extracted_content:
                    analysis_content = extracted_content
            
            analysis_context = f"""
            Based on the following technical analysis:
            
            {self._safe_json_dumps(analysis_content, indent=2) if isinstance(analysis_content, dict) else analysis_content}
            
            Please answer this specific question: {question}
            
            Provide a focused, detailed answer based on the analysis results and project documents.
            If the question asks about technical challenges, focus on complexity, risks, and implementation difficulties.
            If the question asks about recommendations, provide specific actionable advice.
            """
            
            # Create task for answering the question
            answer_task = Task(
                description=analysis_context,
                expected_output="A detailed, specific answer to the user's question based on the analysis",
                agent=technical_agent
            )
            
            # Create crew
            crew = Crew(
                agents=[technical_agent],
                tasks=[answer_task],
                verbose=True,
                process=Process.sequential
            )
            
            # Execute the task
            result = crew.kickoff()
            
            # Convert result to string
            if hasattr(result, 'raw'):
                answer = result.raw
            else:
                answer = str(result)
            
            logger.info(f"Successfully answered question for analysis {analysis_id}")
            
            # Send the answer via WebSocket
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical",
                        "sender_name": "Technical Analysis Agent",
                        "message": answer,
                        "analysis_id": analysis_id,
                        "is_answer": True
                    }
                )
            
            return {
                "status": "success",
                "answer": answer
            }
            
        except Exception as e:
            logger.error(f"Error answering question: {str(e)}")
            logger.error(traceback.format_exc())
            
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "error",
                        "message": f"Failed to answer question: {str(e)}"
                    }
                )
            
            return {
                "status": "error",
                "message": str(e)
            }

    async def regenerate_analysis_with_feedback(self, db: AsyncSession, analysis_id: str, feedback: str, ws_manager: Optional[WebSocketManager] = None) -> Dict[str, Any]:
        """
        Regenerate analysis with user feedback
        """
        try:
            # Check if analysis exists in pending analyses
            if analysis_id not in self.pending_analyses:
                raise ValueError(f"Analysis {analysis_id} not found")
            
            previous_analysis = self.pending_analyses[analysis_id]
            project_id = previous_analysis.get('project_id')
            
            # Get project details
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Increment version
            version = previous_analysis.get("version", 1) + 1
            
            # Create LLM
            llm = ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=0.2,
                api_key=os.environ.get("ANTHROPIC_API_KEY")
            )
            
            # Create document search tool
            doc_search_tool = DocumentSearchTool(project_id=project_id)
            
            # Create technical analyst agent
            technical_agent = Agent(
                role="Technical Analyst",
                goal="Regenerate the technical analysis incorporating user feedback",
                backstory="""You are an expert technical analyst. You previously analyzed this project
                and now need to update your analysis based on user feedback. Consider the previous
                analysis and incorporate the user's suggestions to provide an improved analysis.""",
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=[doc_search_tool]
            )
            
            # Create regeneration task
            regeneration_task = Task(
                description=f"""
                Previous Analysis:
                {self._safe_json_dumps(previous_analysis.get("result", {}), indent=2)}
                
                User Feedback:
                {feedback}
                
                Project Details:
                - Name: {project.get("name", "Unknown")}
                - Description: {project.get("description", "No description")}
                
                Please regenerate the technical analysis incorporating the user's feedback.
                You MUST maintain the exact same structure and format as the previous analysis.
                Return your response as a detailed technical analysis in the same format as before.
                
                IMPORTANT: Your output MUST be in the exact same format as the original technical analysis.
                Do not use a simplified format with just a summary field.
                """,
                expected_output="Updated technical analysis incorporating user feedback",
                agent=technical_agent
            )
            
            # Create crew
            crew = Crew(
                agents=[technical_agent],
                tasks=[regeneration_task],
                process=Process.sequential,
                verbose=True
            )
            
            logger.info("Successfully created regeneration task and crew")
            
            # Execute the crew
            result = crew.kickoff()
            
            # Parse the result
            try:
                # Try to parse as JSON first
                if isinstance(result, str):
                    data = json.loads(result)
                else:
                    data = result
            except:
                # If not JSON, try to extract structured content from the text
                result_str = str(result)
                
                # Create a more structured response that matches the original format
                data = {
                    "technical_analysis": result_str,
                    "version": version,
                    "feedback_incorporated": feedback,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Update the analysis result with the new version
            if analysis_id in self.pending_analyses:
                # Create a complete result structure
                analysis_result = {
                    "technical_analysis": str(result),
                    "version": version,
                    "feedback_incorporated": feedback,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Update the pending analysis with the complete result
                self.pending_analyses[analysis_id] = {
                    "project_id": project_id,
                    "result": analysis_result,
                    "version": version,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                logger.info(f"Successfully updated analysis {analysis_id} with new version {version}")
                
                # Send the updated analysis via WebSocket - using the same message type as the New Analysis flow
                if ws_manager:
                    # First, send the analysis_complete message with is_regeneration flag
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_complete",
                            "analysis_id": analysis_id,
                            "result": analysis_result,
                            "version": version,
                            "is_regeneration": True,
                            "message": f"Analysis regenerated successfully (version {version})"
                        }
                    )
                    
                    # Send a follow-up message
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "agent_message",
                            "sender": "technical",
                            "sender_name": "Technical Analysis Agent",
                            "message": "I've updated the analysis based on your feedback. The changes have been incorporated into the recommendations. You can now save this updated version or provide additional feedback.",
                            "analysis_id": analysis_id
                        }
                    )
            
            return data
            
        except Exception as e:
            logger.error(f"Error regenerating analysis: {str(e)}")
            
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "error",
                        "message": f"Failed to regenerate analysis: {str(e)}"
                    }
                )
            raise
    
    async def handle_user_message(
        self, 
        db: AsyncSession, 
        project_id: str,
        message: str,
        analysis_id: Optional[str] = None,
        ws_manager: Optional[WebSocketManager] = None
    ) -> str:
        """
        Handle user message with @mention support and feedback detection
        """
        logger.info(f"=== handle_user_message called ===")
        logger.info(f"Project ID: {project_id}")
        logger.info(f"Message: {message}")
        logger.info(f"Analysis ID: {analysis_id}")
        logger.info(f"Pending analyses: {list(self.pending_analyses.keys())}")
        
        # Parse for @mentions
        mention_pattern = r'@(\w+)'
        mentions = re.findall(mention_pattern, message)
        
        # If no analysis_id provided, try to find the most recent one for this project
        if not analysis_id:
            for aid, analysis in self.pending_analyses.items():
                if analysis.get("project_id") == project_id:
                    analysis_id = aid
                    logger.info(f"Found pending analysis {analysis_id} for project {project_id}")
                    break
        
        # Check if this is a feedback/regeneration request
        feedback_patterns = [
            r'(?i)update.*analysis',
            r'(?i)focus.*on',
            r'(?i)regenerate',
            r'(?i)focus.*more',
            r'(?i)please.*update',
            r'(?i)modify.*analysis',
            r'(?i)change.*analysis',
            r'(?i)redo.*analysis',
            r'(?i)improve.*analysis',
            r'(?i)revise.*analysis',
            r'(?i)demo',
            r'(?i)knowing that',
            r'(?i)considering',
            r'(?i)taking into account',
            r'(?i)technical.*aspects',
            r'(?i)run.*new.*analysis.*(?:knowing|considering|with)',
            r'(?i)please.*run.*analysis',
            r'(?i)new.*analysis.*(?:knowing|considering|with)'
        ]
        
        is_feedback_request = any(re.search(pattern, message.lower()) for pattern in feedback_patterns)
        logger.info(f"Is feedback request: {is_feedback_request}")
        
        # Check if this is an analysis request
        analysis_patterns = [
            r'(?i)analyze.*project',
            r'(?i)start.*analysis',
            r'(?i)perform.*analysis',
            r'(?i)technical.*analysis',
            r'(?i)@technical'
        ]
        
        is_analysis_request = any(re.search(pattern, message.lower()) for pattern in analysis_patterns)
        logger.info(f"Is analysis request: {is_analysis_request}")
        logger.info(f"Checking routing: feedback={is_feedback_request}, analysis={is_analysis_request}, has_analysis_id={bool(analysis_id)}")
        
        # Check if this is a question about the existing analysis
        question_patterns = [
            r'(?i)what.*(?:are|is).*(?:challenge|risk|issue|problem|difficulty)',
            r'(?i)(?:tell|explain|describe).*(?:about|regarding)',
            r'(?i)(?:how|why|when|where|what).*\?',
            r'(?i)(?:can you|could you|please).*(?:explain|tell|describe|clarify)',
            r'(?i)what.*technical.*challenge',
            r'(?i)what.*recommendation',
            r'(?i)what.*architecture',
            r'(?i)what.*tech.*stack',
            r'(?i)what.*timeline',
            r'(?i)what.*resource',
            r'(?i)what.*risk'
        ]
        
        is_question = any(re.search(pattern, message.lower()) for pattern in question_patterns)
        has_technical_mention = 'technical' in mentions or '@technical' in message.lower()
        
        logger.info(f"Is question: {is_question}")
        logger.info(f"Has technical mention: {has_technical_mention}")
        logger.info(f"Checking routing: feedback={is_feedback_request}, analysis={is_analysis_request}, question={is_question}, has_analysis_id={bool(analysis_id)}")
        
        # Check if we have an existing analysis (in memory or database)
        has_existing_analysis = False
        if analysis_id and analysis_id in self.pending_analyses:
            has_existing_analysis = True
            logger.info(f"Found analysis {analysis_id} in pending_analyses")
        elif not analysis_id or analysis_id not in self.pending_analyses:
            # Try to load from database
            structured_analysis = await self.load_structured_analysis(db, project_id)
            if structured_analysis:
                has_existing_analysis = True
                logger.info(f"Found existing analysis in database for project {project_id}")
                # Create a temporary analysis_id if we don't have one
                if not analysis_id:
                    analysis_id = str(uuid.uuid4())
                # Store in pending analyses for reference
                self.pending_analyses[analysis_id] = {
                    "project_id": project_id,
                    "result": {
                        "technical_analysis": structured_analysis.dict() if hasattr(structured_analysis, 'dict') else structured_analysis
                    }
                }
        
        logger.info(f"Has existing analysis: {has_existing_analysis}")
        
        if is_question and (has_technical_mention or analysis_id) and has_existing_analysis:
            # This is a specific question about the existing analysis
            logger.info(f"Routing to answer_analysis_question for analysis {analysis_id}")
            return await self.answer_analysis_question(db, project_id, analysis_id, message, ws_manager)
        
        elif is_feedback_request and analysis_id and analysis_id in self.pending_analyses:
            # Handle feedback request
            logger.info(f"Processing feedback request for analysis {analysis_id}")
            
            await ws_manager.broadcast(
                project_id,
                {
                    "type": "agent_message",
                    "sender": "technical",
                    "sender_name": "Technical Analysis Agent",
                    "message": "I'll help you update the analysis with your feedback...",
                    "is_thinking": True
                }
            )
            
            # Extract feedback from message
            feedback = message
            logger.info(f"Extracted feedback: {feedback}")
            
            try:
                # Regenerate analysis with feedback
                result = await self.regenerate_analysis_with_feedback(
                    db, analysis_id, feedback, ws_manager
                )
                
                logger.info(f"Regeneration result: {result}")
                return {"status": "success", "result": result}
            except Exception as e:
                logger.error(f"Error in regeneration: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Send error message
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "message": f"Failed to update analysis: {str(e)}"
                        }
                    )
                
                return {"status": "error", "message": str(e)}
            
        elif is_feedback_request or is_analysis_request or 'technical' in mentions:
            # If it's a feedback request but no analysis exists, start a new one
            # If it's an analysis request, start a new one
            if is_feedback_request and not (analysis_id and analysis_id in self.pending_analyses):
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical",
                        "sender_name": "Technical Analysis Agent",
                        "message": "I don't see an existing analysis to update. Let me start a new analysis for you...",
                        "is_thinking": True
                    }
                )
            else:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical",
                        "sender_name": "Technical Analysis Agent",
                        "message": "I'll analyze your project now...",
                        "is_thinking": True
                    }
                )
            
            # Extract any additional context from the message
            # Remove the @mention and analysis request patterns to get the additional context
            additional_context = message
            for pattern in ['@technical', '@analyze']:
                additional_context = additional_context.replace(pattern, '')
            
            # Remove common analysis request phrases
            context_cleaning_patterns = [
                r'(?i)please\s+analyze.*project',
                r'(?i)analyze.*project',
                r'(?i)start.*analysis',
                r'(?i)perform.*analysis',
                r'(?i)technical.*analysis',
                r'(?i)please.*update.*analysis',
                r'(?i)update.*analysis',
                r'(?i)regenerate.*analysis',
                r'(?i)modify.*analysis'
            ]
            
            for pattern in context_cleaning_patterns:
                additional_context = re.sub(pattern, '', additional_context)
            
            additional_context = additional_context.strip()
            
            # Start analysis with additional context
            new_analysis_id = str(uuid.uuid4())
            
            # Store the pending analysis with context
            self.pending_analyses[new_analysis_id] = {
                "project_id": project_id,
                "status": "running",
                "additional_context": additional_context,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send analysis started message
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_started",
                        "analysis_id": new_analysis_id,
                        "message": "Starting technical analysis..."
                    }
                )
            
            try:
                logger.info(f"Creating async task for analysis {new_analysis_id} with context: {additional_context[:100]}...")
                task = asyncio.create_task(
                    self._execute_analysis_with_context(
                        new_analysis_id, project_id, db, ws_manager, additional_context
                    )
                )
                # Store the task reference
                if not hasattr(self, 'analysis_tasks'):
                    self.analysis_tasks = {}
                self.analysis_tasks[new_analysis_id] = task
                logger.info(f"Successfully created async task for analysis {new_analysis_id}")
            except Exception as e:
                logger.error(f"Failed to create async task for analysis: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "message": f"Failed to start analysis: {str(e)}"
                        }
                    )
                return {"status": "error", "message": str(e)}
            
            return {"status": "success", "analysis_id": new_analysis_id}
            
        else:
            # General chat - use chat agent
            return await self.chat_with_agent(db, project_id, message, ws_manager)
            
    async def chat_with_agent(self, db: AsyncSession, project_id: str, message: str, ws_manager: Optional[WebSocketManager] = None) -> Dict[str, Any]:
        """
        Handle general chat with the project assistant agent
        """
        try:
            # Get project details
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Create chat agent
            llm = ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=0.3,
                api_key=os.environ.get("ANTHROPIC_API_KEY")
            )
            
            # Create document search tool
            doc_search_tool = DocumentSearchTool(project_id=project_id)
            
            chat_agent = Agent(
                role="Project Assistant",
                goal="Help users understand their project, answer questions about documents, provide guidance, and assist with project-related queries",
                backstory="""You are a helpful project assistant with broad expertise. You can:
                - Answer questions about the project and its documents
                - Provide technical guidance and suggestions
                - Help users understand analysis results
                - Offer general project advice
                
                Be conversational, helpful, and concise in your responses.""",
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=[doc_search_tool]
            )
            
            # Create task for the chat
            chat_task = Task(
                description=f"""
                User message: {message}
                
                Project context:
                - Name: {project.name}
                - Description: {project.description}
                
                Please provide a helpful response to the user's message.
                If they're asking about project documents, use the search tool.
                If they're asking about analysis results and insights are available, reference them.
                """,
                agent=chat_agent,
                tools=[doc_search_tool],
                expected_output="A helpful, conversational response to the user's message"
            )
            
            # Create crew
            crew = Crew(
                agents=[chat_agent],
                tasks=[chat_task],
                process=Process.sequential,
                verbose=True
            )
            
            # Send initial thinking message
            if ws_manager:
                await ws_manager.send_personal_message(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "assistant",
                        "sender_name": "Project Assistant",
                        "message": "Let me help you with that...",
                        "is_thinking": True
                    }
                )
            
            # Execute the crew
            result = crew.kickoff()
            
            # Send the response
            if ws_manager:
                await ws_manager.send_personal_message(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "assistant",
                        "sender_name": "Project Assistant",
                        "message": str(result)
                    }
                )
            
            return {"status": "success", "response": str(result)}
            
        except Exception as e:
            logger.error(f"Error in chat_with_agent: {str(e)}")
            if ws_manager:
                await ws_manager.send_personal_message(
                    project_id,
                    {
                        "type": "error",
                        "message": "I apologize, but I encountered an error. Please try again."
                    }
                )
            raise

    async def load_structured_analysis(self, db: AsyncSession, project_id: str) -> Optional[ProjectAnalysis]:
        """
        Load structured analysis from project insights
        
        Args:
            db: Database session
            project_id: ID of the project
            
        Returns:
            Optional[ProjectAnalysis]: Structured analysis if available, None otherwise
        """
        try:
            # Import ProjectService
            from app.services.project_service import ProjectService
            project_service = ProjectService()
            
            # Get project with structured insights
            project_data = await project_service.get_project_with_structured_insights(db, project_id)
            
            if not project_data or "insights" not in project_data:
                logger.info(f"No insights found for project {project_id}")
                return None
                
            insights = project_data["insights"]
            
            # If insights is already a Pydantic model, return it
            if isinstance(insights, ProjectAnalysis):
                return insights
                
            # Otherwise, try to parse it
            return project_service.deserialize_project_insights(insights)
            
        except Exception as e:
            logger.error(f"Error loading structured analysis for project {project_id}: {str(e)}")
            return None
    
    async def confirm_and_save_analysis(self, db: AsyncSession, analysis_id: str, ws_manager: Optional[WebSocketManager] = None) -> bool:
        """
        Confirm and save the analysis to project insights
        
        Args:
            db: Database session
            analysis_id: ID of the analysis to save
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        logger.info(f"Confirming and saving analysis {analysis_id}")
        
        try:
            # Check if analysis exists in pending analyses
            if analysis_id not in self.pending_analyses:
                logger.error(f"Analysis {analysis_id} not found in pending analyses")
                return False
            
            analysis_data = self.pending_analyses[analysis_id]
            project_id = analysis_data.get('project_id')
            
            if not project_id:
                logger.error(f"No project_id found for analysis {analysis_id}")
                return False
            
            # Get the project
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            
            if not project:
                logger.error(f"Project {project_id} not found")
                return False
            
            # Get the analysis result from memory
            result = analysis_data.get('result')
            if not result:
                logger.error(f"No result found for analysis {analysis_id}")
                return False
            
            # Extract the technical analysis from the result
            if isinstance(result, dict):
                technical_analysis = result.get('technical_analysis', '')
                logger.info(f"Result is dict, technical_analysis type: {type(technical_analysis)}")
                logger.info(f"Technical analysis preview: {str(technical_analysis)[:500]}")
            else:
                technical_analysis = result
                logger.info(f"Result is not dict, type: {type(result)}")
            
            if not technical_analysis:
                logger.error(f"No technical analysis found for analysis {analysis_id}")
                return False
            
            # Parse the result into Pydantic model
            if isinstance(technical_analysis, str):
                try:
                    # Try to parse as JSON first
                    result_dict = json.loads(technical_analysis)
                    project_analysis = self._parse_agent_output_to_pydantic(
                        json.dumps(result_dict), 
                        analysis_id, 
                        project_id
                    )
                except json.JSONDecodeError:
                    # If not JSON, parse as text
                    project_analysis = self._parse_agent_output_to_pydantic(
                        technical_analysis, 
                        analysis_id, 
                        project_id
                    )
            else:
                # Already structured data
                project_analysis = self._parse_agent_output_to_pydantic(
                    json.dumps(technical_analysis), 
                    analysis_id, 
                    project_id
                )
            
            # Convert Pydantic model to dict for storage
            insights_data = project_analysis.model_dump(mode='json')
            
            # Update project insights
            project.insights = insights_data
            await db.commit()
            
            logger.info(f"Successfully saved analysis {analysis_id} to project {project_id} insights")
            
            # Send success message via WebSocket
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_saved",
                        "analysis_id": analysis_id,
                        "message": "Analysis saved to project insights successfully!"
                    }
                )
            
            # Remove from pending analyses
            del self.pending_analyses[analysis_id]
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving analysis {analysis_id}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Send error message via WebSocket
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "error",
                        "message": f"Failed to save analysis: {str(e)}"
                    }
                )
            
            return False
    
    async def _execute_analysis(self, analysis_id: str, project_id: str, db: AsyncSession, ws_manager: Optional[WebSocketManager] = None, force: bool = False) -> None:
        try:
            logger.info(f"Starting agent analysis execution for project {project_id} (analysis_id: {analysis_id}, force: {force})")
            
            # Send initial status
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "system",
                        "sender_name": "System",
                        "message": "Initializing agent analysis...",
                        "analysis_id": analysis_id
                    }
                )
            
            # Check for cancellation
            if asyncio.current_task().cancelled():
                logger.info(f"Analysis {analysis_id} was cancelled before starting")
                return
            
            # Import document processor
            from app.services.document_processor import DocumentProcessor
            document_processor = DocumentProcessor()
            
            # Get all documents for this project
            documents = await document_processor.list_documents(db, project_id)
            
            # Check if any documents are still processing
            processing_docs = [doc for doc in documents if doc.status == "processing"]
            if processing_docs:
                logger.warning(f"Cannot start analysis - {len(processing_docs)} documents still processing for project {project_id}")
                # Send error via WebSocket
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "analysis_id": analysis_id,
                            "message": f"Cannot start analysis - {len(processing_docs)} documents still processing"
                        }
                    )
                # We'll try again later - in a real implementation, this would be handled by a background job
                return
            
            # Ensure all processed documents are indexed in ChromaDB
            if documents:
                logger.info(f"Ensuring {len(documents)} documents are indexed in ChromaDB for project {project_id}")
                indexed = await document_processor.ensure_documents_indexed(db, project_id)
                if not indexed:
                    logger.warning(f"Failed to ensure all documents are indexed for project {project_id}")
                else:
                    logger.info(f"All documents are indexed in ChromaDB for project {project_id}")
            
            # Check for cancellation
            if asyncio.current_task().cancelled():
                logger.info(f"Analysis {analysis_id} was cancelled during document indexing")
                return
            
            # Check if we already have analysis results for this project
            from app.services.project_service import ProjectService
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            
            # Only skip if we have insights AND we're not forcing a new analysis
            if project and project.insights and not force:
                logger.info(f"Analysis results already exist for project {project_id} (not forced)")
                
                # Send existing results to client via WebSocket
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_result",
                            "analysis_id": analysis_id,
                            "result": project.insights,
                            "message": "Analysis results are ready (previously generated)"
                        }
                    )
                return
            elif force and project and project.insights:
                logger.info(f"Force flag set - running new analysis for project {project_id} despite existing results")
            
            # Set up Anthropic LLM
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_status",
                        "status": "initializing_llm",
                        "analysis_id": analysis_id,
                        "message": "Initializing AI language model"
                    }
                )
                
            anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
            anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
            
            if not anthropic_api_key:
                error_msg = "AI service not configured properly"
                logger.error("ANTHROPIC_API_KEY not found")
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "analysis_id": analysis_id,
                            "message": error_msg
                        }
                    )
                raise ValueError(error_msg)
            
            # Initialize the Anthropic LLM
            logger.info(f"Initializing Anthropic LLM with model {anthropic_model}")
            try:
                llm = ChatAnthropic(
                    model_name=anthropic_model,
                    anthropic_api_key=anthropic_api_key,
                    temperature=0.2,
                    max_tokens=4000
                )
                logger.info("Anthropic LLM initialized successfully")
            except Exception as llm_error:
                logger.error(f"Error initializing Anthropic LLM: {str(llm_error)}")
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "analysis_id": analysis_id,
                            "message": f"Failed to initialize LLM: {str(llm_error)}"
                        }
                    )
                raise
            
            # Create the document search tool
            document_search_tool = DocumentSearchTool(project_id)
            
            # Load agent configuration
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_status",
                        "status": "creating_agents",
                        "analysis_id": analysis_id,
                        "message": "Creating AI agents for analysis"
                    }
                )
                
            agent_config = self.config_loader.get_agent_config("technical_analyst")
            if not agent_config:
                error_msg = "Technical analyst agent configuration not found"
                logger.error(error_msg)
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "analysis_id": analysis_id,
                            "message": error_msg
                        }
                    )
                raise ValueError(error_msg)
            
            # Create the technical analysis agent
            technical_agent = Agent(
                role=agent_config["role"],
                goal=agent_config["goal"],
                backstory=agent_config["backstory"],
                verbose=agent_config["verbose"],
                allow_delegation=agent_config["allow_delegation"],
                llm=llm,
                tools=[document_search_tool]
            )
            
            # Prepare document content for the agent
            document_content = []
            for doc in documents:
                document_content.append({
                    "id": doc.id,
                    "filename": doc.filename,
                    "description": doc.description or "",
                    "content_preview": doc.content[:500] if hasattr(doc, "content") and doc.content else "Content not available"
                })
            
            # Create context for the agent
            context_str = f"Project ID: {project_id}\n\nDocuments:\n"
            for doc in document_content:
                context_str += f"\n--- Document: {doc['filename']} ---\n"
                context_str += f"Description: {doc['description']}\n\n"
                context_str += f"Preview: {doc['content_preview']}\n"
            
            # Create the technical analysis task
            task = Task(
                description=f"""
                Analyze the project with ID {project_id} and provide technical recommendations.
                
                Use the document_search tool to find relevant information in the project documents.
                
                Your analysis should include:
                1. Architecture recommendations
                2. Technology stack suggestions
                3. Feasibility assessment
                4. Implementation approach
                
                Project context:
                {context_str}
                """,
                expected_output="Technical analysis report with architecture recommendations and technology stack",
                agent=technical_agent
            )
            
            # Create the crew with just the technical agent
            crew = Crew(
                agents=[technical_agent],
                tasks=[task],
                verbose=True,
                process=Process.sequential
            )
            
            # Run the crew
            logger.info(f"Starting CrewAI execution for project {project_id}")
            
            # Check for cancellation before running crew
            if asyncio.current_task().cancelled():
                logger.info(f"Analysis {analysis_id} was cancelled before crew execution")
                return
            
            result = crew.kickoff()
            
            # Check for cancellation after crew execution
            if asyncio.current_task().cancelled():
                logger.info(f"Analysis {analysis_id} was cancelled after crew execution")
                return
            
            logger.info(f"CrewAI execution completed for project {project_id}")
            
            # Convert CrewOutput to serializable format
            if hasattr(result, 'raw'):
                crew_result = result.raw
            elif hasattr(result, '__str__'):
                crew_result = str(result)
            else:
                # Convert object to dict and then to string as fallback
                try:
                    crew_result = json.dumps(result.__dict__)
                except:
                    crew_result = f"Unserializable result type: {type(result).__name__}"
            
            # Format the results
            analysis_result = {
                "project_id": project_id,
                "analysis_id": analysis_id,
                "timestamp": datetime.utcnow().isoformat(),
                "technical_analysis": crew_result,
            }
            
            # Store the analysis results in memory (not in database yet)
            if not hasattr(self, 'pending_analyses'):
                self.pending_analyses = {}
            
            self.pending_analyses[analysis_id] = {
                "project_id": project_id,
                "result": analysis_result,
                "crew": crew,  # Keep the crew instance for follow-up questions
                "technical_agent": technical_agent,
                "document_search_tool": document_search_tool
            }
            
            logger.info(f"Analysis {analysis_id} completed and stored in memory for project {project_id}")
            logger.info(f"Current pending analyses: {list(self.pending_analyses.keys())}")
            
            # Send the analysis results via WebSocket for user review
            if ws_manager:
                logger.info(f"WebSocket manager available, preparing to send messages for analysis {analysis_id}")
                logger.info(f"Active connections for project {project_id}: {len(ws_manager.active_connections.get(project_id, []))}")
                
                logger.info(f"Sending analysis_complete message for analysis {analysis_id}")
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_complete",
                        "analysis_id": analysis_id,
                        "result": {
                            "technical_analysis": crew_result,
                            "completed_at": str(datetime.now())
                        },
                        "message": "Initial analysis complete. Please review and ask any follow-up questions.",
                        "message_id": str(uuid.uuid4())
                    }
                )
                logger.info(f"Successfully sent analysis_complete message")
                
                # Send the actual analysis content as an agent message
                logger.info(f"Sending agent_message with analysis content for {analysis_id}")
                logger.info(f"Analysis content length: {len(crew_result)} characters")
                
                # Try to parse the crew_result if it's a JSON string
                try:
                    parsed_result = json.loads(crew_result) if isinstance(crew_result, str) else crew_result
                    
                    # Try to create a ProjectAnalysis object and use the helper for formatting
                    try:
                        project_analysis = self._parse_agent_output_to_pydantic(crew_result, analysis_id, project_id)
                        formatted_message = AnalysisDataHelper.format_analysis_summary(project_analysis)
                        logger.info("Successfully formatted analysis using AnalysisDataHelper")
                    except Exception as parse_error:
                        logger.warning(f"Could not parse to ProjectAnalysis, using fallback formatting: {parse_error}")
                        # Fallback to original formatting if parsing fails
                        if isinstance(parsed_result, dict) and 'technical_analysis' in parsed_result:
                            analysis_data = parsed_result['technical_analysis']
                            formatted_message = f"""## Technical Analysis Results

**Architecture Recommendations:**
{analysis_data.get('technical_analysis', {}).get('architecture', 'No architecture recommendations available.')}

**Technology Stack:**
- Frontend: {', '.join(analysis_data.get('technical_analysis', {}).get('tech_stack', {}).get('frontend', []))}
- Backend: {', '.join(analysis_data.get('technical_analysis', {}).get('tech_stack', {}).get('backend', []))}
- Infrastructure: {', '.join(analysis_data.get('technical_analysis', {}).get('tech_stack', {}).get('infrastructure', []))}

**Risk Assessment:**
- Overall Risk Score: {analysis_data.get('risk_assessment', {}).get('overall_risk_score', 'N/A')}/10
- Key Risks: {', '.join(analysis_data.get('risk_assessment', {}).get('key_risks', [])[:3])}

**Project Timeline:**
{analysis_data.get('project_plan', {}).get('timeline', 'Timeline not specified')}

**Key Recommendations:**
{chr(10).join(['- ' + rec for rec in analysis_data.get('recommendations', [])[:5]])}
"""
                        else:
                            # If it's not in the expected format, just send the raw result
                            formatted_message = crew_result
                except:
                    # If parsing fails, just use the raw result
                    formatted_message = crew_result
                
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
                logger.info(f"Successfully sent agent_message with analysis content")
                
                # Send a follow-up message prompting for questions
                logger.info(f"Sending follow-up prompt message")
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical_agent",
                        "sender_name": "Technical Analysis Agent",
                        "message": "I've completed my initial analysis of your project. Feel free to ask any questions about the analysis, request clarifications, or ask for additional insights. When you're satisfied, you can confirm to save these insights.",
                        "analysis_id": analysis_id,
                        "message_id": str(uuid.uuid4())
                    }
                )
                logger.info(f"Successfully sent follow-up prompt message")
            else:
                logger.warning(f"No WebSocket manager available for analysis {analysis_id}")
            
            logger.info(f"Completed initial analysis {analysis_id} for project {project_id}")
            
        except asyncio.CancelledError:
            logger.info(f"Analysis {analysis_id} was cancelled")
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_cancelled",
                        "analysis_id": analysis_id,
                        "message": "Analysis was cancelled"
                    }
                )
            raise  # Re-raise to properly handle cancellation
        except Exception as e:
            logger.error(f"Error executing analysis {analysis_id}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # In a real implementation, this would update the analysis status to error
    
    async def _execute_analysis_with_context(self, analysis_id: str, project_id: str, db: AsyncSession, ws_manager: Optional[WebSocketManager] = None, context: str = "") -> None:
        try:
            logger.info(f"Starting agent analysis execution for project {project_id} (analysis_id: {analysis_id})")
            
            # Send initial status
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "system",
                        "sender_name": "System",
                        "message": "Initializing agent analysis...",
                        "analysis_id": analysis_id
                    }
                )
            
            # Check for cancellation
            if asyncio.current_task().cancelled():
                logger.info(f"Analysis {analysis_id} was cancelled before starting")
                return
            
            # Import document processor
            from app.services.document_processor import DocumentProcessor
            document_processor = DocumentProcessor()
            
            # Get all documents for this project
            documents = await document_processor.list_documents(db, project_id)
            
            # Check if any documents are still processing
            processing_docs = [doc for doc in documents if doc.status == "processing"]
            if processing_docs:
                logger.warning(f"Cannot start analysis - {len(processing_docs)} documents still processing for project {project_id}")
                # Send error via WebSocket
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "analysis_id": analysis_id,
                            "message": f"Cannot start analysis - {len(processing_docs)} documents still processing"
                        }
                    )
                # We'll try again later - in a real implementation, this would be handled by a background job
                return
            
            # Ensure all processed documents are indexed in ChromaDB
            if documents:
                logger.info(f"Ensuring {len(documents)} documents are indexed in ChromaDB for project {project_id}")
                indexed = await document_processor.ensure_documents_indexed(db, project_id)
                if not indexed:
                    logger.warning(f"Failed to ensure all documents are indexed for project {project_id}")
                else:
                    logger.info(f"All documents are indexed in ChromaDB for project {project_id}")
            
            # Check for cancellation
            if asyncio.current_task().cancelled():
                logger.info(f"Analysis {analysis_id} was cancelled during document indexing")
                return
            
            # Check if we already have analysis results for this project
            from app.services.project_service import ProjectService
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            
            # Only skip if we have insights AND we're not forcing a new analysis
            if project and project.insights:
                logger.info(f"Analysis results already exist for project {project_id}")
                
                # Send existing results to client via WebSocket
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_result",
                            "analysis_id": analysis_id,
                            "result": project.insights,
                            "message": "Analysis results are ready (previously generated)"
                        }
                    )
                return
            
            # Set up Anthropic LLM
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_status",
                        "status": "initializing_llm",
                        "analysis_id": analysis_id,
                        "message": "Initializing AI language model"
                    }
                )
                
            anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
            anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
            
            if not anthropic_api_key:
                error_msg = "AI service not configured properly"
                logger.error("ANTHROPIC_API_KEY not found")
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "analysis_id": analysis_id,
                            "message": error_msg
                        }
                    )
                raise ValueError(error_msg)
            
            # Initialize the Anthropic LLM
            logger.info(f"Initializing Anthropic LLM with model {anthropic_model}")
            try:
                llm = ChatAnthropic(
                    model_name=anthropic_model,
                    anthropic_api_key=anthropic_api_key,
                    temperature=0.2,
                    max_tokens=4000
                )
                logger.info("Anthropic LLM initialized successfully")
            except Exception as llm_error:
                logger.error(f"Error initializing Anthropic LLM: {str(llm_error)}")
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "analysis_id": analysis_id,
                            "message": f"Failed to initialize LLM: {str(llm_error)}"
                        }
                    )
                raise
            
            # Create the document search tool
            document_search_tool = DocumentSearchTool(project_id)
            
            # Load agent configuration
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_status",
                        "status": "creating_agents",
                        "analysis_id": analysis_id,
                        "message": "Creating AI agents for analysis"
                    }
                )
                
            agent_config = self.config_loader.get_agent_config("technical_analyst")
            if not agent_config:
                error_msg = "Technical analyst agent configuration not found"
                logger.error(error_msg)
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "analysis_id": analysis_id,
                            "message": error_msg
                        }
                    )
                raise ValueError(error_msg)
            
            # Create the technical analysis agent
            technical_agent = Agent(
                role=agent_config["role"],
                goal=agent_config["goal"],
                backstory=agent_config["backstory"],
                verbose=agent_config["verbose"],
                allow_delegation=agent_config["allow_delegation"],
                llm=llm,
                tools=[document_search_tool]
            )
            
            # Prepare document content for the agent
            document_content = []
            for doc in documents:
                document_content.append({
                    "id": doc.id,
                    "filename": doc.filename,
                    "description": doc.description or "",
                    "content_preview": doc.content[:500] if hasattr(doc, "content") and doc.content else "Content not available"
                })
            
            # Create context for the agent
            context_str = f"Project ID: {project_id}\n\nDocuments:\n"
            for doc in document_content:
                context_str += f"\n--- Document: {doc['filename']} ---\n"
                context_str += f"Description: {doc['description']}\n\n"
                context_str += f"Preview: {doc['content_preview']}\n"
            
            # Add context from the user's message
            if context:
                context_str += f"\n\nUser Context:\n{context}"
            
            # Create the technical analysis task
            task = Task(
                description=f"""
                Analyze the project with ID {project_id} and provide technical recommendations.
                
                Use the document_search tool to find relevant information in the project documents.
                
                Your analysis should include:
                1. Architecture recommendations
                2. Technology stack suggestions
                3. Feasibility assessment
                4. Implementation approach
                
                Project context:
                {context_str}
                """,
                expected_output="Technical analysis report with architecture recommendations and technology stack",
                agent=technical_agent
            )
            
            # Create the crew with just the technical agent
            crew = Crew(
                agents=[technical_agent],
                tasks=[task],
                verbose=True,
                process=Process.sequential
            )
            
            # Run the crew
            logger.info(f"Starting CrewAI execution for project {project_id}")
            
            # Check for cancellation before running crew
            if asyncio.current_task().cancelled():
                logger.info(f"Analysis {analysis_id} was cancelled before crew execution")
                return
            
            result = crew.kickoff()
            
            # Check for cancellation after crew execution
            if asyncio.current_task().cancelled():
                logger.info(f"Analysis {analysis_id} was cancelled after crew execution")
                return
            
            logger.info(f"CrewAI execution completed for project {project_id}")
            
            # Convert CrewOutput to serializable format
            if hasattr(result, 'raw'):
                crew_result = result.raw
            elif hasattr(result, '__str__'):
                crew_result = str(result)
            else:
                # Convert object to dict and then to string as fallback
                try:
                    crew_result = json.dumps(result.__dict__)
                except:
                    crew_result = f"Unserializable result type: {type(result).__name__}"
            
            # Format the results
            analysis_result = {
                "project_id": project_id,
                "analysis_id": analysis_id,
                "timestamp": datetime.utcnow().isoformat(),
                "technical_analysis": crew_result,
            }
            
            # Store the analysis results in memory (not in database yet)
            if not hasattr(self, 'pending_analyses'):
                self.pending_analyses = {}
            
            self.pending_analyses[analysis_id] = {
                "project_id": project_id,
                "result": analysis_result,
                "crew": crew,  # Keep the crew instance for follow-up questions
                "technical_agent": technical_agent,
                "document_search_tool": document_search_tool
            }
            
            logger.info(f"Analysis {analysis_id} completed and stored in memory for project {project_id}")
            logger.info(f"Current pending analyses: {list(self.pending_analyses.keys())}")
            
            # Send the analysis results via WebSocket for user review
            if ws_manager:
                logger.info(f"WebSocket manager available, preparing to send messages for analysis {analysis_id}")
                logger.info(f"Active connections for project {project_id}: {len(ws_manager.active_connections.get(project_id, []))}")
                
                logger.info(f"Sending analysis_complete message for analysis {analysis_id}")
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_complete",
                        "analysis_id": analysis_id,
                        "result": {
                            "technical_analysis": crew_result,
                            "completed_at": str(datetime.now())
                        },
                        "message": "Initial analysis complete. Please review and ask any follow-up questions.",
                        "message_id": str(uuid.uuid4())
                    }
                )
                logger.info(f"Successfully sent analysis_complete message")
                
                # Send the actual analysis content as an agent message
                logger.info(f"Sending agent_message with analysis content for {analysis_id}")
                logger.info(f"Analysis content length: {len(crew_result)} characters")
                
                # Try to parse the crew_result if it's a JSON string
                try:
                    parsed_result = json.loads(crew_result) if isinstance(crew_result, str) else crew_result
                    
                    # Try to create a ProjectAnalysis object and use the helper for formatting
                    try:
                        project_analysis = self._parse_agent_output_to_pydantic(crew_result, analysis_id, project_id)
                        formatted_message = AnalysisDataHelper.format_analysis_summary(project_analysis)
                        logger.info("Successfully formatted analysis using AnalysisDataHelper")
                    except Exception as parse_error:
                        logger.warning(f"Could not parse to ProjectAnalysis, using fallback formatting: {parse_error}")
                        # Fallback to original formatting if parsing fails
                        if isinstance(parsed_result, dict) and 'technical_analysis' in parsed_result:
                            analysis_data = parsed_result['technical_analysis']
                            formatted_message = f"""## Technical Analysis Results

**Architecture Recommendations:**
{analysis_data.get('technical_analysis', {}).get('architecture', 'No architecture recommendations available.')}

**Technology Stack:**
- Frontend: {', '.join(analysis_data.get('technical_analysis', {}).get('tech_stack', {}).get('frontend', []))}
- Backend: {', '.join(analysis_data.get('technical_analysis', {}).get('tech_stack', {}).get('backend', []))}
- Infrastructure: {', '.join(analysis_data.get('technical_analysis', {}).get('tech_stack', {}).get('infrastructure', []))}

**Risk Assessment:**
- Overall Risk Score: {analysis_data.get('risk_assessment', {}).get('overall_risk_score', 'N/A')}/10
- Key Risks: {', '.join(analysis_data.get('risk_assessment', {}).get('key_risks', [])[:3])}

**Project Timeline:**
{analysis_data.get('project_plan', {}).get('timeline', 'Timeline not specified')}

**Key Recommendations:**
{chr(10).join(['- ' + rec for rec in analysis_data.get('recommendations', [])[:5]])}
"""
                        else:
                            # If it's not in the expected format, just send the raw result
                            formatted_message = crew_result
                except:
                    # If parsing fails, just use the raw result
                    formatted_message = crew_result
                
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
                logger.info(f"Successfully sent agent_message with analysis content")
                
                # Send a follow-up message prompting for questions
                logger.info(f"Sending follow-up prompt message")
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical_agent",
                        "sender_name": "Technical Analysis Agent",
                        "message": "I've completed my initial analysis of your project. Feel free to ask any questions about the analysis, request clarifications, or ask for additional insights. When you're satisfied, you can confirm to save these insights.",
                        "analysis_id": analysis_id,
                        "message_id": str(uuid.uuid4())
                    }
                )
                logger.info(f"Successfully sent follow-up prompt message")
            else:
                logger.warning(f"No WebSocket manager available for analysis {analysis_id}")
            
            logger.info(f"Completed initial analysis {analysis_id} for project {project_id}")
            
        except asyncio.CancelledError:
            logger.info(f"Analysis {analysis_id} was cancelled")
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_cancelled",
                        "analysis_id": analysis_id,
                        "message": "Analysis was cancelled"
                    }
                )
            raise  # Re-raise to properly handle cancellation
        except Exception as e:
            logger.error(f"Error executing analysis {analysis_id}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # In a real implementation, this would update the analysis status to error
    
    def _parse_agent_output_to_pydantic(self, raw_output: str, analysis_id: str, project_id: str) -> ProjectAnalysis:
        """
        Parse raw agent output into structured Pydantic models
        
        Args:
            raw_output: Raw output from the agent
            analysis_id: ID of the analysis
            project_id: ID of the project
            
        Returns:
            ProjectAnalysis: Structured analysis data
        """
        logger.info(f"Parsing raw agent output for analysis {analysis_id}")
        logger.info(f"Raw output type: {type(raw_output)}, length: {len(str(raw_output))}")
        
        try:
            # Try to parse as JSON first
            try:
                if isinstance(raw_output, str):
                    data = json.loads(raw_output)
                else:
                    data = raw_output
                    
                logger.info(f"Successfully parsed JSON, keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                
                # Check if the data has a nested 'technical_analysis' structure
                if isinstance(data, dict) and 'technical_analysis' in data:
                    # The agent output has everything nested under 'technical_analysis'
                    nested_data = data['technical_analysis']
                    if isinstance(nested_data, dict):
                        # Use the nested data as the main data source
                        data = nested_data
                        logger.info(f"Using nested technical_analysis data, keys: {list(data.keys())}")
                        
            except json.JSONDecodeError:
                # If not valid JSON, use regex to extract structured data
                logger.warning(f"Agent output is not valid JSON, using fallback parsing")
                data = self._extract_structured_data_from_text(raw_output)
            
            # Extract technical analysis data
            tech_data = data.get('technical_analysis', {}) if isinstance(data, dict) else {}
            
            # If tech_data is still empty, check if the data itself contains the technical fields
            if not tech_data and isinstance(data, dict):
                # Check if data itself contains technical analysis fields
                if any(key in data for key in ['architecture', 'tech_stack', 'complexity_score']):
                    tech_data = data
                    logger.info("Using root data as technical analysis data")
            
            # Create TechStackCategory
            tech_stack = TechStackCategory(
                frontend=tech_data.get('tech_stack', {}).get('frontend', []),
                backend=tech_data.get('tech_stack', {}).get('backend', []),
                infrastructure=tech_data.get('tech_stack', {}).get('infrastructure', []),
                tools=tech_data.get('tech_stack', {}).get('tools', [])
            )
            
            # Create TechnicalAnalysis
            technical_analysis = TechnicalAnalysis(
                architecture=tech_data.get('architecture', 'Not specified'),
                tech_stack=tech_stack,
                complexity_score=tech_data.get('complexity_score', 5.0),
                maintainability_score=tech_data.get('maintainability_score', 5.0),
                scalability_score=tech_data.get('scalability_score', 5.0),
                performance_score=tech_data.get('performance_score', 5.0),
                security_score=tech_data.get('security_score', 5.0)
            )
            
            # Extract risk assessment data
            risk_data = data.get('risk_assessment', {}) if isinstance(data, dict) else {}
            
            # Create Risk objects
            risks = []
            for risk_item in risk_data.get('key_risks', []):
                if isinstance(risk_item, dict):
                    # Try to parse risk level
                    try:
                        risk_level = RiskLevel(risk_item.get('level', 'Medium'))
                    except ValueError:
                        risk_level = RiskLevel.MEDIUM
                    
                    risks.append(Risk(
                        name=risk_item.get('name', 'Unknown Risk'),
                        level=risk_level,
                        impact=risk_item.get('impact', 5),
                        probability=risk_item.get('probability', 5),
                        description=risk_item.get('description')
                    ))
            
            # Create RiskAssessment
            risk_assessment = RiskAssessment(
                key_risks=risks,
                overall_risk_score=risk_data.get('overall_risk_score', 5.0),
                mitigation_strategies=risk_data.get('mitigation_strategies', [])
            )
            
            # Extract project plan data
            plan_data = data.get('project_plan', {}) if isinstance(data, dict) else {}
            
            # Create ProjectPhase objects
            phases = []
            for phase_item in plan_data.get('phases', []):
                if isinstance(phase_item, dict):
                    phases.append(ProjectPhase(
                        name=phase_item.get('name', 'Unnamed Phase'),
                        duration=phase_item.get('duration', 4),
                        progress=phase_item.get('progress', 0),
                        description=phase_item.get('description')
                    ))
            
            # Create Milestone objects
            milestones = []
            for milestone_item in plan_data.get('milestones', []):
                if isinstance(milestone_item, dict):
                    milestones.append(Milestone(
                        name=milestone_item.get('name', 'Unnamed Milestone'),
                        date=milestone_item.get('date', datetime.now().isoformat()),
                        status=milestone_item.get('status', 'upcoming'),
                        description=milestone_item.get('description')
                    ))
            
            # Create ResourceRequirements
            resource_data = plan_data.get('resource_requirements', {})
            resources = ResourceRequirements(
                developers=int(resource_data.get('developers', 0)),
                designers=int(resource_data.get('designers', 0)),
                qa=int(resource_data.get('qa', 0)),
                devops=int(resource_data.get('devops', 0)),
                pm=int(resource_data.get('pm', 0)),
                other=resource_data.get('other', {})
            )
            
            # Create EffortDistribution objects
            effort_distribution = []
            for effort_item in plan_data.get('effort_distribution', []):
                if isinstance(effort_item, dict):
                    effort_distribution.append(EffortDistribution(
                        component=effort_item.get('component', 'Unknown'),
                        effort=effort_item.get('effort', 0)
                    ))
            
            # Create ProjectPlan
            project_plan = ProjectPlan(
                timeline=plan_data.get('timeline', 'Not specified'),
                phases=phases,
                milestones=milestones,
                resource_requirements=resources,
                estimated_cost=plan_data.get('estimated_cost', 0.0),
                effort_distribution=effort_distribution
            )
            
            # Extract recommendations
            recommendations = data.get('recommendations', []) if isinstance(data, dict) else []
            
            # Create the complete ProjectAnalysis
            project_analysis = ProjectAnalysis(
                analysis_id=analysis_id,
                project_id=project_id,
                version=1,
                technical_analysis=technical_analysis,
                risk_assessment=risk_assessment,
                project_plan=project_plan,
                recommendations=recommendations,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            logger.info(f"Successfully parsed agent output into Pydantic model for analysis {analysis_id}")
            return project_analysis
            
        except Exception as e:
            logger.error(f"Error parsing agent output: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def _extract_structured_data_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract structured data from unstructured text using regex patterns
        This is a fallback method when JSON parsing fails
        
        Args:
            text: Raw text from agent output
            
        Returns:
            Dict[str, Any]: Structured data extracted from text
        """
        # Initialize the structure
        data = {
            'technical_analysis': {
                'architecture': '',
                'tech_stack': {
                    'frontend': [],
                    'backend': [],
                    'infrastructure': [],
                    'tools': []
                },
                'complexity_score': 5.0,
                'maintainability_score': 5.0,
                'scalability_score': 5.0,
                'performance_score': 5.0,
                'security_score': 5.0
            },
            'risk_assessment': {
                'key_risks': [],
                'overall_risk_score': 5.0,
                'mitigation_strategies': []
            },
            'project_plan': {
                'timeline': '',
                'phases': [],
                'milestones': [],
                'resource_requirements': {},
                'estimated_cost': 0.0,
                'effort_distribution': []
            },
            'recommendations': []
        }
        
        # Extract architecture
        arch_match = re.search(r'Architecture[:\s]+(.*?)(?:\n|$)', text, re.IGNORECASE)
        if arch_match:
            data['technical_analysis']['architecture'] = arch_match.group(1).strip()
        
        # Extract tech stack
        # Frontend
        frontend_match = re.search(r'Frontend[:\s]+(.*?)(?:\n|$)', text, re.IGNORECASE)
        if frontend_match:
            frontend_techs = re.findall(r'\b([\w\+\#\.]+)\b', frontend_match.group(1))
            data['technical_analysis']['tech_stack']['frontend'] = frontend_techs
        
        # Backend
        backend_match = re.search(r'Backend[:\s]+(.*?)(?:\n|$)', text, re.IGNORECASE)
        if backend_match:
            backend_techs = re.findall(r'\b([\w\+\#\.]+)\b', backend_match.group(1))
            data['technical_analysis']['tech_stack']['backend'] = backend_techs
        
        # Extract recommendations
        recommendations = re.findall(r'(?:Recommendation|Recommend)[:\s]+(.*?)(?:\n|$)', text, re.IGNORECASE)
        if recommendations:
            data['recommendations'] = [rec.strip() for rec in recommendations]
        
        return data
    
    def parse_agent_mention(self, message: str) -> Tuple[Optional[str], str]:
        """
        Parse @agent mentions from message
        Returns: (agent_id, cleaned_message)
        """
        # Pattern to match @mention at the beginning or with space before it
        pattern = r'(?:^|\s)@(\w+)'
        match = re.search(pattern, message)
        
        if match:
            mention_id = match.group(1).lower()
            # Try to find the agent
            agent_info = agent_registry.get_agent_by_mention(mention_id)
            
            if agent_info:
                # Remove the @mention from the message
                cleaned_message = re.sub(pattern, '', message, count=1).strip()
                return agent_info.id, cleaned_message
            
        return None, message
    
    def detect_feedback_request(self, message: str) -> bool:
        """
        Detect if the message is requesting to update/regenerate analysis with feedback
        """
        feedback_patterns = [
            r'(?i)update.*analysis.*with',
            r'(?i)regenerate.*considering',
            r'(?i)redo.*analysis.*but',
            r'(?i)please.*update.*analysis',
            r'(?i)modify.*analysis.*to',
            r'(?i)change.*analysis.*to',
            r'(?i)revise.*analysis',
            r'(?i)incorporate.*feedback',
            r'(?i)add.*to.*analysis',
            r'(?i)include.*in.*analysis'
        ]
        
        for pattern in feedback_patterns:
            if re.search(pattern, message):
                return True
        
        return False
    
    def extract_feedback_content(self, message: str) -> str:
        """
        Extract the actual feedback content from a feedback request message
        """
        # Remove common request phrases to get the actual feedback
        feedback = message
        
        # Patterns to remove
        remove_patterns = [
            r'(?i)please\s+',
            r'(?i)update\s+the\s+analysis\s+',
            r'(?i)regenerate\s+considering\s+',
            r'(?i)redo\s+the\s+analysis\s+but\s+',
            r'(?i)modify\s+the\s+analysis\s+to\s+',
            r'(?i)with\s+the\s+following\s+',
            r'(?i)to\s+include\s+',
            r'(?i)considering\s+that\s+'
        ]
        
        for pattern in remove_patterns:
            feedback = re.sub(pattern, '', feedback)
        
        return feedback.strip()
