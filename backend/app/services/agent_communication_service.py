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

            PRIORITY INSTRUCTIONS - ANSWER DIRECTLY FROM ANALYSIS DATA:
            1. **FIRST**: Check the Current Context below for specific information
            2. **SECOND**: If not in context, search project documents using document_search tool
            3. **LAST**: Only provide general guidance if specific data is unavailable
            
            RESPONSE STYLE:
            - Give DIRECT, SPECIFIC answers when data is available
            - For timeline questions: State the timeline directly from analysis
            - For cost questions: Give exact figures from analysis  
            - For technical questions: Provide specific architecture/tech stack details
            - For risk questions: List specific risks and scores
            - Keep answers concise and factual
            
            CURRENT ANALYSIS DATA:
            {context}
            
            CAPABILITIES:
            1. Answer questions about timeline, costs, risks, recommendations from analysis
            2. Provide project status and technical details from analysis results
            3. Search project documents for additional information when needed
            4. Route complex technical questions to @technical agent
            
            Remember: Use the analysis data above to give precise, direct answers. Don't be vague when specific information is available."""
            
            agent = Agent(
                role="Project Assistant", 
                goal="Provide direct, specific answers about project timeline, costs, risks, and recommendations using available analysis data",
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
        """Get a comprehensive summary of analysis for context"""
        try:
            summary_parts = []
            
            # Technical Analysis
            if "technical_analysis" in insights:
                tech = insights["technical_analysis"]
                summary_parts.append("=== TECHNICAL ANALYSIS ===")
                summary_parts.append(f"Architecture: {tech.get('architecture', 'Not specified')}")
                
                if "tech_stack" in tech and tech["tech_stack"]:
                    stack = tech["tech_stack"]
                    summary_parts.append("Tech Stack:")
                    if stack.get('frontend'):
                        summary_parts.append(f"  - Frontend: {', '.join(stack['frontend'])}")
                    if stack.get('backend'):
                        summary_parts.append(f"  - Backend: {', '.join(stack['backend'])}")
                    if stack.get('infrastructure'):
                        summary_parts.append(f"  - Infrastructure: {', '.join(stack['infrastructure'])}")
                
                summary_parts.append(f"Complexity Score: {tech.get('complexity_score', 'N/A')}/10")
                summary_parts.append(f"Maintainability Score: {tech.get('maintainability_score', 'N/A')}/10")
                summary_parts.append(f"Scalability Score: {tech.get('scalability_score', 'N/A')}/10")
            
            # Project Plan & Timeline
            if "project_plan" in insights:
                plan = insights["project_plan"]
                summary_parts.append("\n=== PROJECT TIMELINE & PLAN ===")
                timeline = plan.get('timeline', 'Not specified')
                summary_parts.append(f"Overall Timeline: {timeline}")
                
                if "phases" in plan and plan["phases"]:
                    summary_parts.append("Implementation Phases:")
                    for i, phase in enumerate(plan["phases"], 1):
                        if isinstance(phase, dict):
                            phase_name = phase.get('name', f'Phase {i}')
                            phase_duration = phase.get('duration', 'TBD')
                            summary_parts.append(f"  {i}. {phase_name}: {phase_duration}")
                        else:
                            summary_parts.append(f"  {i}. {phase}")
                
                if "milestones" in plan and plan["milestones"]:
                    summary_parts.append("Key Milestones:")
                    for milestone in plan["milestones"][:5]:  # Top 5 milestones
                        if isinstance(milestone, dict):
                            summary_parts.append(f"  - {milestone.get('name', 'Milestone')}: {milestone.get('date', 'TBD')}")
                        else:
                            summary_parts.append(f"  - {milestone}")
                
                summary_parts.append(f"Estimated Cost: ${plan.get('estimated_cost', 0):,}")
                
                if "resource_requirements" in plan:
                    resources = plan["resource_requirements"]
                    if isinstance(resources, dict):
                        summary_parts.append("Resource Requirements:")
                        if "developers" in resources:
                            dev_count = resources["developers"]
                            if isinstance(dev_count, dict):
                                total_devs = sum(dev_count.values()) if dev_count.values() else dev_count.get('total', 'TBD')
                            else:
                                total_devs = dev_count
                            summary_parts.append(f"  - Developers: {total_devs}")
                        if "duration" in resources:
                            summary_parts.append(f"  - Duration: {resources['duration']}")
            
            # Risk Assessment
            if "risk_assessment" in insights:
                risks = insights["risk_assessment"]
                summary_parts.append("\n=== RISK ASSESSMENT ===")
                summary_parts.append(f"Overall Risk Score: {risks.get('overall_risk_score', 'N/A')}/10")
                
                if "key_risks" in risks and risks["key_risks"]:
                    summary_parts.append("Top Risks:")
                    for risk in risks["key_risks"][:3]:  # Top 3 risks
                        if isinstance(risk, dict):
                            risk_name = risk.get('name', 'Unknown Risk')
                            risk_level = risk.get('severity', risk.get('level', 'Unknown'))
                            summary_parts.append(f"  - {risk_name} ({risk_level})")
                        else:
                            summary_parts.append(f"  - {risk}")
            
            # Recommendations
            if "recommendations" in insights and insights["recommendations"]:
                summary_parts.append("\n=== KEY RECOMMENDATIONS ===")
                for i, rec in enumerate(insights["recommendations"][:3], 1):  # Top 3 recommendations
                    summary_parts.append(f"{i}. {rec}")
            
            return "\n".join(summary_parts) if summary_parts else "Analysis data available but no summary could be generated"
        except Exception as e:
            return f"Analysis summary not available (error: {str(e)})"
    
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
