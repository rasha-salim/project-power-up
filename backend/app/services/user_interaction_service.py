"""
User interaction service for handling questions, feedback, and user communication
"""
import os
import re
import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from crewai import Agent, Task, Crew, Process
from langchain_anthropic import ChatAnthropic
from app.models.project import Project
from app.services.project_service import ProjectService
from app.services.websocket_manager import WebSocketManager
from app.services.analysis_management_service import AnalysisManagementService
from app.tools.document_search import DocumentSearchTool
from app.core.agent_registry import agent_registry

logger = logging.getLogger(__name__)


class UserInteractionService:
    """Service for handling user interactions, questions, and feedback"""
    
    def __init__(self, analysis_manager: AnalysisManagementService):
        """Initialize the user interaction service"""
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.analysis_manager = analysis_manager
    
    def _get_llm(self, temperature: float = 0.3) -> ChatAnthropic:
        """Get configured Anthropic LLM instance"""
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        
        return ChatAnthropic(
            model=self.anthropic_model,
            temperature=temperature,
            anthropic_api_key=self.anthropic_api_key
        )
    
    def detect_analysis_request(self, message: str) -> bool:
        """
        Detect if a user message is requesting analysis
        
        Args:
            message: User's message
            
        Returns:
            bool: True if message requests analysis
        """
        analysis_patterns = [
            r'\b(analyze|analysis|technical analysis|project analysis)\b',
            r'\b(assess|evaluate|review)\b.*\b(project|code|architecture|technical)\b',
            r'\b(what.*risks?|risk assessment)\b',
            r'\b(estimate|timeline|cost|budget)\b.*\b(analysis|assessment)\b',
            r'\b(recommend|recommendation)s?\b.*\b(technology|tech stack|architecture)\b',
            r'\b(run|perform|do|execute)\b.*\b(analysis|assessment)\b',
            r'\b(create|generate|provide)\b.*\b(analysis|technical analysis|assessment)\b',
            r'\b(update|refresh|regenerate)\b.*\b(analysis|assessment)\b',
            r'\btell me about.*\b(risks?|technology|architecture|timeline|cost)\b'
        ]
        
        message_lower = message.lower()
        for pattern in analysis_patterns:
            if re.search(pattern, message_lower):
                logger.info(f"Detected analysis request pattern: {pattern}")
                return True
        
        return False

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
            Dict with response and routing information
        """
        try:
            logger.info(f"Handling user message for project {project_id}: {message}")
            
            # Parse @mentions
            agent_id, cleaned_message = self.parse_agent_mention(message)
            
            # Detect feedback patterns
            is_feedback, feedback_type = self.detect_feedback_patterns(cleaned_message)
            
            # Detect analysis requests
            is_analysis_request = self.detect_analysis_request(cleaned_message)
            
            # Route based on message type
            if is_analysis_request:
                # Route to analysis execution
                logger.info(f"Routing message to analysis execution: {cleaned_message}")
                return {
                    "type": "analysis_request", 
                    "message": cleaned_message,
                    "agent_id": agent_id,
                    "existing_analysis_id": analysis_id,
                    "requires_analysis_execution": True
                }
            elif is_feedback and analysis_id:
                return await self.handle_feedback_message(
                    db, project_id, analysis_id, cleaned_message, ws_manager
                )
            elif analysis_id:
                return await self.answer_analysis_question(
                    db, project_id, analysis_id, cleaned_message, ws_manager
                )
            else:
                # General chat - delegate to communication service
                return {
                    "type": "chat",
                    "message": cleaned_message,
                    "agent_id": agent_id,
                    "requires_chat_service": True
                }
                
        except Exception as e:
            logger.error(f"Error handling user message: {str(e)}")
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "error",
                        "message": "I encountered an error processing your message. Please try again."
                    }
                )
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
        try:
            logger.info(f"Answering analysis question for {analysis_id}: {question}")
            
            # Get analysis data
            analysis_data = self.analysis_manager.get_pending_analysis(analysis_id)
            if not analysis_data:
                # Try to get from project insights
                project_service = ProjectService()
                project_data = await project_service.get_project_with_insights(db, project_id)
                if project_data and "insights" in project_data:
                    analysis_data = {"result": project_data["insights"]}
                else:
                    raise ValueError(f"Analysis {analysis_id} not found")
            
            # Get project details
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Send thinking message
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical",
                        "sender_name": "Technical Analyst",
                        "message": "Let me analyze your question...",
                        "is_thinking": True
                    }
                )
            
            # Create question-answering agent
            llm = self._get_llm()
            
            qa_agent = Agent(
                role="Technical Analysis Expert",
                goal="Answer specific questions about project analysis results",
                backstory=f"""You are a technical analysis expert who helps users understand their project analysis.
                You have access to the complete technical analysis for the project '{project.name}' and can answer
                specific questions about the analysis results, recommendations, risks, and technical details.""",
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=[DocumentSearchTool(project_id)]
            )
            
            # Build context from analysis
            analysis_context = self._build_analysis_context(analysis_data.get("result", {}))
            
            # Create task
            task = Task(
                description=f"""
                Based on the technical analysis results below, answer this specific question: {question}
                
                Analysis Context:
                {analysis_context}
                
                Project Details:
                - Name: {project.name}
                - Description: {project.description or 'No description provided'}
                
                Provide a focused, helpful answer based on the analysis data.
                """,
                expected_output="A clear, specific answer to the user's question based on the analysis results",
                agent=qa_agent
            )
            
            # Create crew
            crew = Crew(
                agents=[qa_agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True
            )
            
            # Execute
            result = crew.kickoff()
            
            # Send response
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "technical",
                        "sender_name": "Technical Analyst",
                        "message": str(result)
                    }
                )
            
            return {"status": "success", "answer": str(result)}
            
        except Exception as e:
            logger.error(f"Error answering analysis question: {str(e)}")
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "error",
                        "message": "I couldn't answer your question. Please try rephrasing or ask about a different aspect of the analysis."
                    }
                )
            raise
    
    async def handle_feedback_message(
        self, 
        db: AsyncSession, 
        project_id: str, 
        analysis_id: str, 
        feedback: str,
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Handle feedback messages for analysis regeneration
        
        Args:
            db: Database session
            project_id: ID of the project
            analysis_id: ID of the analysis
            feedback: User feedback
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            Dict indicating regeneration was triggered
        """
        try:
            logger.info(f"Handling feedback for analysis {analysis_id}: {feedback}")
            
            # Get current analysis
            analysis_data = self.analysis_manager.get_pending_analysis(analysis_id)
            if not analysis_data:
                raise ValueError(f"Analysis {analysis_id} not found")
            
            # This service doesn't handle regeneration directly - it signals that regeneration is needed
            return {
                "type": "feedback",
                "analysis_id": analysis_id,
                "feedback": feedback,
                "requires_regeneration": True,
                "message": "Feedback received - regeneration will be triggered"
            }
            
        except Exception as e:
            logger.error(f"Error handling feedback: {str(e)}")
            raise
    
    def parse_agent_mention(self, message: str) -> Tuple[Optional[str], str]:
        """
        Parse @agent mentions from message
        
        Args:
            message: User message that may contain @mentions
            
        Returns:
            Tuple of (agent_id, cleaned_message)
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
    
    def detect_feedback_patterns(self, message: str) -> Tuple[bool, Optional[str]]:
        """
        Detect if message contains feedback patterns
        
        Args:
            message: User message to analyze
            
        Returns:
            Tuple of (is_feedback, feedback_type)
        """
        feedback_patterns = [
            (r'\b(update|change|modify|improve|enhance|revise)\b.*\b(analysis|recommendation|plan)\b', 'update'),
            (r'\b(please|can you|could you)\b.*\b(update|change|modify|improve|enhance|revise)\b', 'request'),
            (r'\b(add|include|consider)\b.*\b(to|in)\b.*\b(analysis|recommendation|plan)\b', 'addition'),
            (r'\b(remove|exclude|take out)\b.*\b(from|in)\b.*\b(analysis|recommendation|plan)\b', 'removal'),
            (r'\b(feedback|suggestion|comment)\b', 'general_feedback'),
            (r'\b(regenerate|redo|try again)\b', 'regenerate')
        ]
        
        message_lower = message.lower()
        
        for pattern, feedback_type in feedback_patterns:
            if re.search(pattern, message_lower):
                return True, feedback_type
        
        return False, None
    
    def _build_analysis_context(self, analysis_result: Dict[str, Any]) -> str:
        """Build formatted context from analysis results"""
        context_parts = []
        
        # Technical Analysis
        if "technical_analysis" in analysis_result:
            tech = analysis_result["technical_analysis"]
            context_parts.append(f"Technical Analysis:")
            context_parts.append(f"- Architecture: {tech.get('architecture', 'Not specified')}")
            
            if "tech_stack" in tech:
                stack = tech["tech_stack"]
                context_parts.append(f"- Tech Stack:")
                if stack.get("frontend"):
                    context_parts.append(f"  - Frontend: {', '.join(stack['frontend'])}")
                if stack.get("backend"):
                    context_parts.append(f"  - Backend: {', '.join(stack['backend'])}")
                if stack.get("infrastructure"):
                    context_parts.append(f"  - Infrastructure: {', '.join(stack['infrastructure'])}")
        
        # Risk Assessment
        if "risk_assessment" in analysis_result:
            risks = analysis_result["risk_assessment"]
            context_parts.append(f"\nRisk Assessment:")
            context_parts.append(f"- Overall Risk Score: {risks.get('overall_risk_score', 'Not specified')}")
            
            if "key_risks" in risks:
                context_parts.append("- Key Risks:")
                for risk in risks["key_risks"][:3]:  # Limit to top 3 risks
                    if isinstance(risk, dict):
                        context_parts.append(f"  - {risk.get('name', 'Unknown')}: {risk.get('description', '')}")
        
        # Project Plan
        if "project_plan" in analysis_result:
            plan = analysis_result["project_plan"]
            context_parts.append(f"\nProject Plan:")
            context_parts.append(f"- Timeline: {plan.get('timeline', 'Not specified')}")
            context_parts.append(f"- Estimated Cost: {plan.get('estimated_cost', 'Not specified')}")
        
        # Recommendations
        if "recommendations" in analysis_result:
            recs = analysis_result["recommendations"]
            if recs:
                context_parts.append(f"\nRecommendations:")
                for i, rec in enumerate(recs[:3], 1):  # Limit to top 3
                    context_parts.append(f"{i}. {rec}")
        
        return "\n".join(context_parts)
