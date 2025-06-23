import os
import logging
import re
import uuid
import asyncio
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from crewai import Agent, Task, Crew, Process
from langchain_anthropic import ChatAnthropic
from app.models.project import Project
from app.services.project_service import ProjectService
from app.tools.document_search import DocumentSearchTool
from app.services.websocket_manager import WebSocketManager
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
            if project.insights and project.insights.get("analysis_id") == analysis_id:
                return {
                    "analysis_id": analysis_id,
                    "status": "completed",
                    "results": project.insights
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
                        "analysis_id": analysis_id
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
                        "analysis_id": analysis_id,
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
                goal=agent_config["goal"],
                backstory=agent_config["backstory"],
                verbose=agent_config["verbose"],
                allow_delegation=agent_config["allow_delegation"],
                llm=llm,
                tools=[document_search_tool]
            )
            
            # Update the technical agent in pending analyses
            self.pending_analyses[analysis_id]["technical_agent"] = technical_agent
            self.pending_analyses[analysis_id]["document_search_tool"] = document_search_tool
            
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
            context_str = f"Project ID: {project_id}\n\nDocuments:\n"
            for doc in document_content:
                context_str += f"\n--- Document: {doc['filename']} ---\n"
                context_str += f"Description: {doc['description']}\n\n"
                context_str += f"Preview: {doc['content_preview']}\n"
            
            # Add user feedback to context
            feedback_context = f"\n\nPrevious Analysis Summary:\n{previous_result.get('technical_analysis', 'No previous analysis')[:500]}\n\n"
            feedback_context += f"User Feedback: {user_feedback}\n\n"
            
            # Create task exactly like in start_analysis
            regeneration_task = Task(
                description=f"""
                Regenerate the technical analysis for project '{project.name}' incorporating this user feedback: 
                {user_feedback}
                
                Use the document_search tool to find relevant information in the project documents.
                
                Your analysis should include:
                1. Architecture recommendations
                2. Technology stack suggestions
                3. Feasibility assessment
                4. Implementation approach
                
                Project context:
                {context_str}
                {feedback_context}
                """,
                expected_output="Updated technical analysis report with architecture recommendations and technology stack",
                agent=technical_agent
            )
            
            # Create crew exactly like in start_analysis
            crew = Crew(
                agents=[technical_agent],
                tasks=[regeneration_task],
                verbose=True,
                process=Process.sequential
            )
            
            logger.info("Successfully created regeneration task and crew")
            
            # Execute the crew to get the regenerated analysis
            result = crew.kickoff()
            
            # Update the analysis result with the new version
            if analysis_id in self.pending_analyses:
                # Increment version number
                current_version = self.pending_analyses[analysis_id].get("version", 1)
                self.pending_analyses[analysis_id]["version"] = current_version + 1
                
                # Update the result with regenerated analysis
                self.pending_analyses[analysis_id]["result"]["technical_analysis"] = result
            
            # Send completion notification
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical_agent",
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
            Project: {project.name if project else 'Unknown'}
            Description: {project.description if project else 'No description available'}
            
            User Message: {message}
            """
            
            # Check if the message is asking about project insights
            if project and project.insights and any(keyword in message.lower() for keyword in ['analysis', 'insights', 'recommendations', 'technical', 'risks', 'plan']):
                context += f"\n\nPrevious Analysis Results:\n{json.dumps(project.insights, indent=2)}"
            
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
    
    async def regenerate_analysis_with_feedback(self, db: AsyncSession, analysis_id: str, feedback: str, ws_manager: Optional[WebSocketManager] = None) -> Dict[str, Any]:
        """
        Regenerate analysis with user feedback
        """
        try:
            # Check if analysis exists in pending analyses
            if analysis_id not in self.pending_analyses:
                raise ValueError(f"Analysis {analysis_id} not found")
            
            previous_analysis = self.pending_analyses[analysis_id]
            project_id = previous_analysis.get("project_id")
            
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
                {json.dumps(previous_analysis.get("result", {}), indent=2)}
                
                User Feedback:
                {feedback}
                
                Project Details:
                - Name: {project.name}
                - Description: {project.description}
                
                Please regenerate the technical analysis incorporating the user's feedback.
                Maintain the same structure as before but update the content based on the feedback.
                """,
                expected_output="Updated technical analysis incorporating user feedback"
            )
            
            # Create crew
            crew = Crew(
                agents=[technical_agent],
                tasks=[regeneration_task],
                process=Process.sequential,
                verbose=True
            )
            
            # Send status update
            if ws_manager:
                await ws_manager.send_personal_message(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical",
                        "sender_name": "Technical Analysis Agent",
                        "message": f"Regenerating analysis with your feedback (version {version})...",
                        "is_thinking": True
                    }
                )
            
            # Execute the crew
            result = crew.kickoff()
            
            # Parse the result
            try:
                analysis_result = json.loads(str(result))
            except:
                # If not JSON, create a structured response
                analysis_result = {
                    "summary": str(result),
                    "version": version,
                    "feedback_incorporated": feedback
                }
            
            # Update pending analysis
            self.pending_analyses[analysis_id] = {
                "project_id": project_id,
                "result": analysis_result,
                "version": version,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Successfully regenerated analysis {analysis_id} with user feedback")
            
            # Send the updated analysis via WebSocket
            if ws_manager:
                await ws_manager.send_personal_message(
                    project_id,
                    {
                        "type": "analysis_complete",
                        "analysis_id": analysis_id,
                        "result": analysis_result,
                        "version": version,
                        "message": f"Analysis regenerated successfully (version {version})"
                    }
                )
                
                # Send a follow-up message
                await ws_manager.send_personal_message(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical",
                        "sender_name": "Technical Analysis Agent",
                        "message": "I've updated the analysis based on your feedback. The changes have been incorporated into the recommendations. You can now save this updated version or provide additional feedback.",
                        "analysis_id": analysis_id
                    }
                )
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error regenerating analysis: {str(e)}")
            
            if ws_manager:
                await ws_manager.send_personal_message(
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
            r'(?i)technical.*aspects'
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
        
        if is_feedback_request and analysis_id and analysis_id in self.pending_analyses:
            # Handle feedback request
            await ws_manager.send_personal_message(
                project_id,
                {
                    "type": "agent_message",
                    "sender": "assistant",
                    "sender_name": "Project Assistant",
                    "message": "I'll help you update the analysis with your feedback...",
                    "is_thinking": True
                }
            )
            
            # Extract feedback from message
            feedback = message
            
            # Regenerate analysis with feedback
            result = await self.regenerate_analysis_with_feedback(
                db, analysis_id, feedback, ws_manager
            )
            
            return {"status": "success", "result": result}
            
        elif is_feedback_request or is_analysis_request or 'technical' in mentions:
            # If it's a feedback request but no analysis exists, start a new one
            # If it's an analysis request, start a new one
            if is_feedback_request and not (analysis_id and analysis_id in self.pending_analyses):
                await ws_manager.send_personal_message(
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
                await ws_manager.send_personal_message(
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
                r'(?i)please\s+update.*analysis',
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
                await ws_manager.send_personal_message(
                    project_id,
                    {
                        "type": "analysis_started",
                        "analysis_id": new_analysis_id,
                        "message": "Starting technical analysis..."
                    }
                )
            
            # Execute the analysis with context
            asyncio.create_task(
                self._execute_analysis_with_context(
                    new_analysis_id, project_id, db, ws_manager, additional_context
                )
            )
            
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
                goal="Help users understand their project, answer questions about documents, and provide guidance",
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
        try:
            # Check if we have the analysis in memory
            if analysis_id not in self.pending_analyses:
                logger.error(f"Analysis {analysis_id} not found in pending analyses")
                return False
            
            pending = self.pending_analyses[analysis_id]
            project_id = pending["project_id"]
            analysis_result = pending["result"]
            
            logger.info(f"Saving confirmed analysis {analysis_id} for project {project_id}")
            
            # Send status update
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "system_message",
                        "message": "Saving analysis to project insights...",
                        "sender": "system"
                    }
                )
            
            # Store the results in the database
            project_service = ProjectService()
            await project_service.store_project_insights(db, project_id, analysis_result)
            
            # Remove from pending analyses
            del self.pending_analyses[analysis_id]
            
            logger.info(f"Successfully saved analysis {analysis_id} to project insights")
            
            # Send confirmation
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_saved",
                        "analysis_id": analysis_id,
                        "message": "Analysis has been saved to project insights!"
                    }
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving analysis {analysis_id}: {e}")
            
            if ws_manager and analysis_id in self.pending_analyses:
                await ws_manager.broadcast(
                    self.pending_analyses[analysis_id]["project_id"],
                    {
                        "type": "error",
                        "analysis_id": analysis_id,
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
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_complete",
                        "analysis_id": analysis_id,
                        "result": {
                            "technical_analysis": crew_result,
                            "completed_at": str(datetime.now())
                        },
                        "message": "Initial analysis complete. Please review and ask any follow-up questions."
                    }
                )
                
                # Send a follow-up message prompting for questions
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical_agent",
                        "sender_name": "Technical Analysis Agent",
                        "message": "I've completed my initial analysis of your project. Feel free to ask any questions about the analysis, request clarifications, or ask for additional insights. When you're satisfied, you can confirm to save these insights.",
                        "analysis_id": analysis_id
                    }
                )
            
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
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_complete",
                        "analysis_id": analysis_id,
                        "result": {
                            "technical_analysis": crew_result,
                            "completed_at": str(datetime.now())
                        },
                        "message": "Initial analysis complete. Please review and ask any follow-up questions."
                    }
                )
                
                # Send a follow-up message prompting for questions
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical_agent",
                        "sender_name": "Technical Analysis Agent",
                        "message": "I've completed my initial analysis of your project. Feel free to ask any questions about the analysis, request clarifications, or ask for additional insights. When you're satisfied, you can confirm to save these insights.",
                        "analysis_id": analysis_id
                    }
                )
            
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
