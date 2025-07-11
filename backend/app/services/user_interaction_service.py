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
    
    def detect_analysis_request(self, message: str) -> Tuple[bool, str]:
        """
        Detect if a user message is requesting analysis and classify the type
        
        Args:
            message: User's message
            
        Returns:
            Tuple[bool, str]: (is_analysis_request, request_type)
                request_type can be: 'new', 'update', 'update_with_context'
        """
        analysis_patterns = {
            'update_with_context': [
                r'\b(update|refresh|regenerate|modify|change)\b.*\b(analysis|assessment)\b.*\b(with|considering|knowing|given|since|because)\b',
                r'\b(please update|update the)\b.*\b(analysis|assessment)\b.*\b(knowing|considering|with|given)\b',
                r'\b(revise|adjust|modify)\b.*\b(analysis|assessment)\b.*\b(to include|considering|with|for)\b'
            ],
            'update': [
                r'\b(update|refresh|regenerate|redo)\b.*\b(analysis|assessment)\b',
                r'\b(please update|update the)\b.*\b(analysis|assessment)\b',
                r'\b(run.*again|re-run|rerun)\b.*\b(analysis|assessment)\b',
                r'\b(revise|adjust|modify)\b.*\b(analysis|assessment)\b'
            ],
            'new': [
                r'\b(analyze|analysis|technical analysis|project analysis)\b',
                r'\b(assess|evaluate|review)\b.*\b(project|code|architecture|technical)\b',
                r'\b(what.*risks?|risk assessment)\b',
                r'\b(estimate|timeline|cost|budget)\b.*\b(analysis|assessment)\b',
                r'\b(recommend|recommendation)s?\b.*\b(technology|tech stack|architecture)\b',
                r'\b(run|perform|do|execute)\b.*\b(analysis|assessment)\b',
                r'\b(create|generate|provide)\b.*\b(analysis|technical analysis|assessment)\b',
                r'\btell me about.*\b(risks?|technology|architecture|timeline|cost)\b'
            ]
        }
        
        message_lower = message.lower()
        
        # Check in priority order: update_with_context -> update -> new
        for request_type in ['update_with_context', 'update', 'new']:
            patterns = analysis_patterns[request_type]
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    logger.info(f"Detected {request_type} analysis request pattern: {pattern}")
                    return True, request_type
        
        return False, 'none'

    async def _get_latest_analysis_id(self, db: AsyncSession, project_id: str) -> Optional[str]:
        """
        Get the latest analysis ID for a project
        
        Args:
            db: Database session
            project_id: ID of the project
            
        Returns:
            Optional[str]: Latest analysis ID or None
        """
        try:
            # Get project with insights to check for existing analysis
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            
            if project and project.insights:
                # If project has insights, it means there's an existing analysis
                # We can use the project_id as a reference since insights are stored per project
                logger.info(f"Found existing analysis insights for project {project_id}")
                return f"project_{project_id}_latest"  # Synthetic ID for latest analysis
            
            # Check pending analyses
            pending_analyses = self.analysis_manager.get_all_pending_analyses()
            project_analyses = [
                (analysis_id, analysis_data) 
                for analysis_id, analysis_data in pending_analyses.items() 
                if analysis_data.get('project_id') == project_id
            ]
            
            if project_analyses:
                # Return the most recent pending analysis
                latest_analysis_id = max(project_analyses, key=lambda x: x[1].get('created_at', 0))[0]
                logger.info(f"Found pending analysis {latest_analysis_id} for project {project_id}")
                return latest_analysis_id
            
            logger.info(f"No existing analysis found for project {project_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting latest analysis ID for project {project_id}: {str(e)}")
            return None

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
            
            # Parse @mentions and handle agent context clearing
            agent_id, cleaned_message = self.parse_agent_mention(message)
            
            # Check for agent context clearing commands
            if self._is_agent_clear_command(message):
                if ws_manager:
                    ws_manager.clear_active_agent(project_id)
                    await ws_manager.notify_agent_context_change(project_id, None)
                return {
                    "type": "chat",
                    "message": "Agent context cleared. You're now chatting with the general project assistant.",
                    "agent_id": None,
                    "requires_chat_service": True,
                    "context_cleared": True
                }
            
            # Get active agent context if no new agent mentioned
            active_agent_id = None
            if ws_manager:
                active_agent_id = ws_manager.get_active_agent(project_id)
            
            # Use mentioned agent or fall back to active agent context
            effective_agent_id = agent_id if agent_id else active_agent_id
            
            # If new agent mentioned, update context
            if agent_id and ws_manager:
                ws_manager.set_active_agent(project_id, agent_id)
                # Get agent info for notification
                from app.core.agent_registry import agent_registry
                agent_info = agent_registry.get_agent(agent_id)
                agent_name = agent_info.name if agent_info else agent_id
                await ws_manager.notify_agent_context_change(project_id, agent_id, agent_name)
                logger.info(f"Set active agent context: {agent_id} for project {project_id}")
            
            # Detect feedback patterns
            is_feedback, feedback_type = self.detect_feedback_patterns(cleaned_message)
            
            # Detect analysis requests with type classification
            is_analysis_request, request_type = self.detect_analysis_request(cleaned_message)
            logger.info(f"Analysis request detection: is_analysis_request={is_analysis_request}, request_type={request_type}, message='{cleaned_message}'")
            
            # Get existing analysis context for project
            existing_analysis_id = await self._get_latest_analysis_id(db, project_id)
            
            # Route based on message type (prioritize analysis requests over agent mentions)
            if is_analysis_request:
                # Analysis request takes precedence - route to analysis execution
                logger.info(f"Routing {request_type} analysis request: {cleaned_message}")
                
                response = {
                    "type": "analysis_request", 
                    "message": cleaned_message,
                    "agent_id": agent_id,
                    "request_type": request_type,
                    "requires_analysis_execution": True
                }
                
                # Handle different analysis request types
                if request_type in ['update', 'update_with_context'] and existing_analysis_id:
                    # Use existing analysis for incremental updates
                    response["existing_analysis_id"] = existing_analysis_id
                    response["has_existing_context"] = True
                    logger.info(f"Using existing analysis {existing_analysis_id} for {request_type}")
                elif request_type == 'new' or not existing_analysis_id:
                    # Force new analysis
                    response["existing_analysis_id"] = None
                    response["has_existing_context"] = False
                    logger.info(f"Creating new analysis for {request_type} request")
                
                return response
            elif effective_agent_id:
                # Agent active or mentioned - route to specific agent for chat (not analysis)
                logger.info(f"Using agent context ({effective_agent_id}) - routing to agent chat")
                return await self._handle_general_chat(
                    db, project_id, cleaned_message, effective_agent_id, existing_analysis_id, ws_manager
                )
            elif is_feedback and analysis_id:
                return await self.handle_feedback_message(
                    db, project_id, analysis_id, cleaned_message, ws_manager
                )
            elif analysis_id:
                return await self.answer_analysis_question(
                    db, project_id, analysis_id, cleaned_message, ws_manager
                )
            else:
                # General chat - enhance with project context
                return await self._handle_general_chat(
                    db, project_id, cleaned_message, agent_id, existing_analysis_id, ws_manager
                )
                
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
    
    def _is_agent_clear_command(self, message: str) -> bool:
        """
        Check if message is a command to clear agent context
        
        Args:
            message: User message to check
            
        Returns:
            bool: True if this is an agent clear command
        """
        clear_patterns = [
            r'@clear\b',
            r'@none\b',
            r'@stop\b',
            r'@end\b',
            r'@general\b',
            r'clear agent',
            r'stop agent',
            r'end conversation'
        ]
        
        message_lower = message.lower().strip()
        for pattern in clear_patterns:
            if re.search(pattern, message_lower):
                return True
        return False
    
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
    
    async def _handle_general_chat(
        self,
        db: AsyncSession,
        project_id: str,
        message: str,
        agent_id: Optional[str],
        existing_analysis_id: Optional[str],
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Handle general chat with enhanced project context
        
        Args:
            db: Database session
            project_id: ID of the project
            message: User's message
            agent_id: Mentioned agent ID (if any)
            existing_analysis_id: Existing analysis ID for context
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            Dict with response information
        """
        # Determine which agent to use
        if agent_id == "technical_analyst":
            # User specifically mentioned technical agent for a question
            return {
                "type": "technical_question",
                "message": message,
                "agent_id": agent_id,
                "existing_analysis_id": existing_analysis_id,
                "requires_technical_response": True
            }
        elif agent_id == "security_analyst":
            # User specifically mentioned security agent for a question
            return {
                "type": "security_question",
                "message": message,
                "agent_id": agent_id,
                "existing_analysis_id": existing_analysis_id,
                "requires_security_response": True
            }
        elif agent_id == "project_planner":
            # User specifically mentioned project planner for help with project brief
            return {
                "type": "project_planning",
                "message": message,
                "agent_id": agent_id,
                "existing_analysis_id": existing_analysis_id,
                "requires_planning_response": True
            }
        else:
            # General chat - use project assistant with enhanced context
            return {
                "type": "chat",
                "message": message,
                "agent_id": agent_id or "project_assistant",  # Default to project assistant
                "existing_analysis_id": existing_analysis_id,
                "requires_chat_service": True,
                "has_project_context": bool(existing_analysis_id)
            }
