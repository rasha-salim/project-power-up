"""
Core agent communication service for handling basic agent interactions
"""
import os
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from crewai import Agent, Task, Crew, Process
from langchain_anthropic import ChatAnthropic
from app.models.project import Project
from app.services.project_service import ProjectService
from app.services.websocket_manager import WebSocketManager
from app.core.agent_registry import agent_registry
from app.tools.document_search import DocumentSearchTool

logger = logging.getLogger(__name__)


class AgentCommunicationService:
    """Service for basic agent communication and chat functionality"""
    
    def __init__(self):
        """Initialize the agent communication service"""
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    
    def _is_document_related(self, message: str) -> bool:
        """Check if message is asking about project documents or content"""
        import re
        document_patterns = [
            r'\b(document|file|requirement|specification|design)\b',
            r'\b(what.*says?|what.*contains?|find.*in)\b',
            r'\b(according to|based on|mentioned in)\b',
            r'\b(search|look for|find)\b.*\b(document|file|content)\b'
        ]
        
        message_lower = message.lower()
        return any(re.search(pattern, message_lower) for pattern in document_patterns)
    
    def _get_llm(self, temperature: float = 0.3) -> ChatAnthropic:
        """Get configured Anthropic LLM instance"""
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        
        return ChatAnthropic(
            model=self.anthropic_model,
            temperature=temperature,
            anthropic_api_key=self.anthropic_api_key
        )
    
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
            Dict with status and response
        """
        try:
            logger.info(f"Handling chat message for project {project_id}: {message}")
            
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
                        "type": "agent_message",
                        "sender": "assistant",
                        "sender_name": "Project Assistant",
                        "message": "Let me help you with that...",
                        "is_thinking": True
                    }
                )
            
            # Create chat agent with optional document search
            llm = self._get_llm()
            
            # Determine if we need document search capabilities
            needs_document_search = self._is_document_related(message)
            tools = [DocumentSearchTool(project_id)] if needs_document_search else []
            
            backstory = f"""You are a helpful project assistant for the project '{project.name}'. 
            You help users understand their project, answer questions, and provide guidance.
            
            Project Details:
            - Name: {project.name}
            - Description: {project.description or 'No description provided'}
            - Industry: {getattr(project, 'industry', 'Not specified')}
            - Team Size: {getattr(project, 'team_size', 'Not specified')}
            """
            
            if needs_document_search:
                backstory += """
                
                IMPORTANT: You have access to project documents. When users ask about project content, 
                requirements, specifications, or design details, use the document_search tool to find 
                relevant information in the uploaded project documents. Always search the documents 
                before providing answers about project-specific content.
                """
            
            chat_agent = Agent(
                role="Project Assistant",
                goal="Help users with their project questions and provide guidance based on project documents when available",
                backstory=backstory,
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=tools
            )
            
            # Create task
            task = Task(
                description=f"Respond to this user message: {message}",
                expected_output="A helpful, informative response to the user's question or comment",
                agent=chat_agent
            )
            
            # Create crew
            crew = Crew(
                agents=[chat_agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True
            )
            
            logger.info("Executing crew for chat")
            
            # Execute the crew
            result = crew.kickoff()
            
            # Send response
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
            
            return {"status": "success", "response": str(result)}
            
        except Exception as e:
            logger.error(f"Error in chat_with_agent: {str(e)}")
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "error",
                        "message": "I apologize, but I encountered an error. Please try again."
                    }
                )
            raise
    
    def parse_agent_mention(self, message: str) -> tuple[Optional[str], str]:
        """
        Parse @agent mentions from message
        
        Args:
            message: User message that may contain @mentions
            
        Returns:
            Tuple of (agent_id, cleaned_message)
        """
        import re
        
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
    
    async def chat_with_project_assistant(
        self,
        db: AsyncSession,
        project_id: str,
        message: str,
        existing_analysis_id: Optional[str] = None,
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Enhanced chat with project assistant that includes analysis context
        
        Args:
            db: Database session
            project_id: ID of the project
            message: User's message
            existing_analysis_id: Existing analysis ID for context
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            Dict with status and response
        """
        try:
            logger.info(f"Project assistant chat for project {project_id}: {message}")
            
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
                        "type": "agent_message",
                        "sender": "project_assistant",
                        "sender_name": "Project Assistant",
                        "message": "Let me help you with that...",
                        "is_thinking": True
                    }
                )
            
            # Create enhanced context with project and analysis information
            context_parts = [f"Project: {project.name}"]
            if project.description:
                context_parts.append(f"Description: {project.description}")
            
            # Add analysis context if available
            if existing_analysis_id and project.insights:
                context_parts.append("Current Analysis Summary:")
                context_parts.append(self._get_analysis_summary(project.insights))
            
            context = "\n".join(context_parts)
            
            # Create enhanced project assistant
            llm = self._get_llm()
            tools = [DocumentSearchTool(project_id)] if self._is_document_related(message) else []
            
            backstory = f"""You are an intelligent project assistant for '{project.name}'. 
            You have access to project documents and analysis results. You can:
            
            1. Answer questions about the project based on available documents
            2. Provide insights from technical analysis when available
            3. Help users understand project status, risks, timelines, and recommendations
            4. Guide users to appropriate specialized agents when needed
            
            Current Context:
            {context}
            
            Be helpful, knowledgeable, and direct users to @technical for technical analysis questions."""
            
            agent = Agent(
                role="Project Assistant",
                goal="Help users understand their project and provide useful information",
                backstory=backstory,
                llm=llm,
                tools=tools,
                verbose=True,
                allow_delegation=False
            )
            
            # Create and execute task
            task = Task(
                description=f"User question: {message}",
                expected_output="A helpful response based on project context and available information",
                agent=agent
            )
            
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=True,
                process=Process.sequential
            )
            
            response = crew.kickoff()
            response_text = str(response).strip()
            
            # Send final response
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "project_assistant",
                        "sender_name": "Project Assistant",
                        "message": response_text,
                        "is_thinking": False
                    }
                )
            
            return {
                "status": "success",
                "message": response_text,
                "agent_id": "project_assistant"
            }
            
        except Exception as e:
            logger.error(f"Error in project assistant chat: {str(e)}")
            error_message = "I encountered an error while processing your request. Please try again."
            
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "project_assistant",
                        "sender_name": "Project Assistant",
                        "message": error_message,
                        "is_thinking": False,
                        "is_error": True
                    }
                )
            
            return {
                "status": "error",
                "message": error_message,
                "agent_id": "project_assistant"
            }
    
    async def chat_with_technical_agent(
        self,
        db: AsyncSession,
        project_id: str,
        message: str,
        existing_analysis_id: Optional[str] = None,
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Handle technical questions directed to the technical agent
        
        Args:
            db: Database session
            project_id: ID of the project
            message: User's message
            existing_analysis_id: Existing analysis ID for context
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            Dict with status and response
        """
        try:
            logger.info(f"Technical agent question for project {project_id}: {message}")
            
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
                        "type": "agent_message",
                        "sender": "technical_analyst",
                        "sender_name": "Technical Analyst",
                        "message": "Analyzing your technical question...",
                        "is_thinking": True
                    }
                )
            
            # Create technical context
            context_parts = [f"Project: {project.name}"]
            if existing_analysis_id and project.insights:
                context_parts.append("Current Technical Analysis:")
                context_parts.append(self._get_technical_analysis_summary(project.insights))
            
            context = "\n".join(context_parts)
            
            # Create technical agent with document search
            llm = self._get_llm()
            tools = [DocumentSearchTool(project_id)]
            
            backstory = f"""You are a Senior Technical Analyst specializing in software architecture, 
            technology stack analysis, and technical decision-making. You have access to project documents 
            and existing technical analysis.
            
            Current Technical Context:
            {context}
            
            Provide detailed technical insights, recommendations, and explanations. If the question would 
            benefit from a full technical analysis, suggest running a complete analysis."""
            
            agent = Agent(
                role="Senior Technical Analyst",
                goal="Provide expert technical insights and recommendations",
                backstory=backstory,
                llm=llm,
                tools=tools,
                verbose=True,
                allow_delegation=False
            )
            
            # Create and execute task
            task = Task(
                description=f"Technical question: {message}",
                expected_output="A detailed technical response with insights and recommendations",
                agent=agent
            )
            
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=True,
                process=Process.sequential
            )
            
            response = crew.kickoff()
            response_text = str(response).strip()
            
            # Send final response
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical_analyst",
                        "sender_name": "Technical Analyst",
                        "message": response_text,
                        "is_thinking": False
                    }
                )
            
            return {
                "status": "success",
                "message": response_text,
                "agent_id": "technical_analyst"
            }
            
        except Exception as e:
            logger.error(f"Error in technical agent chat: {str(e)}")
            error_message = "I encountered an error while analyzing your technical question. Please try again."
            
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical_analyst",
                        "sender_name": "Technical Analyst",
                        "message": error_message,
                        "is_thinking": False,
                        "is_error": True
                    }
                )
            
            return {
                "status": "error",
                "message": error_message,
                "agent_id": "technical_analyst"
            }
    
    def _get_analysis_summary(self, insights: Dict[str, Any]) -> str:
        """Get a summary of analysis for context"""
        try:
            summary_parts = []
            
            if "technical_analysis" in insights:
                tech = insights["technical_analysis"]
                summary_parts.append(f"Architecture: {tech.get('architecture', 'Not specified')[:100]}...")
                
                if "tech_stack" in tech and tech["tech_stack"]:
                    stack = tech["tech_stack"]
                    summary_parts.append(f"Tech Stack: Frontend: {stack.get('frontend', [])}, Backend: {stack.get('backend', [])}")
                
                summary_parts.append(f"Complexity Score: {tech.get('complexity_score', 'N/A')}/10")
            
            if "project_plan" in insights:
                plan = insights["project_plan"]
                summary_parts.append(f"Timeline: {plan.get('timeline', 'Not specified')}")
                summary_parts.append(f"Estimated Cost: ${plan.get('estimated_cost', 0)}")
            
            return "\n".join(summary_parts)
        except:
            return "Analysis summary not available"
    
    def _get_technical_analysis_summary(self, insights: Dict[str, Any]) -> str:
        """Get a technical-focused summary of analysis"""
        try:
            if "technical_analysis" not in insights:
                return "No technical analysis available"
            
            tech = insights["technical_analysis"]
            summary_parts = [
                f"Architecture: {tech.get('architecture', 'Not specified')}",
                f"Complexity: {tech.get('complexity_score', 'N/A')}/10",
                f"Maintainability: {tech.get('maintainability_score', 'N/A')}/10",
                f"Scalability: {tech.get('scalability_score', 'N/A')}/10"
            ]
            
            if "tech_stack" in tech and tech["tech_stack"]:
                stack = tech["tech_stack"]
                summary_parts.append(f"Frontend: {', '.join(stack.get('frontend', []))}")
                summary_parts.append(f"Backend: {', '.join(stack.get('backend', []))}")
                summary_parts.append(f"Infrastructure: {', '.join(stack.get('infrastructure', []))}")
            
            return "\n".join(summary_parts)
        except:
            return "Technical analysis summary not available"
