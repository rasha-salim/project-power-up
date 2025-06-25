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

logger = logging.getLogger(__name__)


class AgentCommunicationService:
    """Service for basic agent communication and chat functionality"""
    
    def __init__(self):
        """Initialize the agent communication service"""
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    
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
            
            # Create chat agent
            llm = self._get_llm()
            
            chat_agent = Agent(
                role="Project Assistant",
                goal="Help users with their project questions and provide guidance",
                backstory=f"""You are a helpful project assistant for the project '{project.name}'. 
                You help users understand their project, answer questions, and provide guidance.
                
                Project Details:
                - Name: {project.name}
                - Description: {project.description or 'No description provided'}
                - Industry: {getattr(project, 'industry', 'Not specified')}
                - Team Size: {getattr(project, 'team_size', 'Not specified')}
                """,
                verbose=True,
                allow_delegation=False,
                llm=llm
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
