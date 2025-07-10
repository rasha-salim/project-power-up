"""
Core agent communication service for handling basic agent interactions
"""
import os
import re
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
from app.utils.message_formatter import MessageFormatter
from app.services.project_brief_service import ProjectBriefService
from app.services.conversation_memory_service import conversation_memory
from app.services.incremental_brief_service import incremental_brief_service

logger = logging.getLogger(__name__)


class AgentCommunicationService:
    """Service for basic agent communication and chat functionality"""
    
    def __init__(self):
        """Initialize the agent communication service"""
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.brief_service = ProjectBriefService()
    
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
            try:
                result = crew.kickoff()
                response_text = str(result).strip()
                logger.info(f"Chat agent execution successful, response length: {len(response_text)}")
                logger.debug(f"Raw response preview: {response_text[:200]}...")
                
                # Format the response for better readability
                try:
                    formatted_response = MessageFormatter.format_agent_response(response_text)
                    logger.debug(f"Formatted response preview: {formatted_response[:200]}...")
                except Exception as format_error:
                    logger.error(f"Error formatting response: {str(format_error)}")
                    # Use raw response if formatting fails
                    formatted_response = response_text
                    
            except Exception as crew_error:
                logger.error(f"Chat crew execution failed: {str(crew_error)}")
                logger.error(f"Chat crew error type: {type(crew_error).__name__}")
                import traceback
                logger.error(f"Chat full traceback: {traceback.format_exc()}")
                raise crew_error
            
            # Send response
            if ws_manager:
                try:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "agent_message",
                            "sender": "assistant",
                            "sender_name": "Project Assistant",
                            "message": formatted_response
                        }
                    )
                    logger.info(f"Successfully sent chat agent response via WebSocket")
                except Exception as ws_error:
                    logger.error(f"Error broadcasting chat agent response: {str(ws_error)}")
                    # Don't raise here, as the response was successful - just log the WebSocket error
            
            return {"status": "success", "response": formatted_response}
            
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
            
            try:
                response = crew.kickoff()
                response_text = str(response).strip()
                logger.info(f"Project assistant execution successful, response length: {len(response_text)}")
                logger.debug(f"Raw response preview: {response_text[:200]}...")
                
                # Format the response for better readability
                try:
                    formatted_response = MessageFormatter.format_agent_response(response_text)
                    logger.debug(f"Formatted response preview: {formatted_response[:200]}...")
                except Exception as format_error:
                    logger.error(f"Error formatting response: {str(format_error)}")
                    # Use raw response if formatting fails
                    formatted_response = response_text
                
            except Exception as crew_error:
                logger.error(f"Project assistant crew execution failed: {str(crew_error)}")
                logger.error(f"Project assistant crew error type: {type(crew_error).__name__}")
                import traceback
                logger.error(f"Project assistant full traceback: {traceback.format_exc()}")
                raise crew_error
            
            # Send final response
            if ws_manager:
                try:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "agent_message",
                            "sender": "project_assistant",
                            "sender_name": "Project Assistant",
                            "message": formatted_response,
                            "is_thinking": False
                        }
                    )
                    logger.info(f"Successfully sent project assistant response via WebSocket")
                except Exception as ws_error:
                    logger.error(f"Error broadcasting project assistant response: {str(ws_error)}")
                    # Don't raise here, as the response was successful - just log the WebSocket error
            
            return {
                "status": "success",
                "message": formatted_response,
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
            
            try:
                response = crew.kickoff()
                response_text = str(response).strip()
                logger.info(f"Technical agent execution successful, response length: {len(response_text)}")
                logger.debug(f"Raw response preview: {response_text[:200]}...")
                
                # Format the response for better readability
                try:
                    # Check if response contains structured analysis data (JSON format)
                    if response_text.strip().startswith('{') and response_text.strip().endswith('}'):
                        try:
                            # Try to parse as JSON and format as technical analysis
                            import json
                            analysis_data = json.loads(response_text)
                            if any(key in analysis_data for key in ['technical_analysis', 'risk_assessment', 'project_plan']):
                                formatted_response = MessageFormatter.format_technical_analysis(analysis_data)
                                logger.debug(f"Formatted as technical analysis: {formatted_response[:200]}...")
                            else:
                                formatted_response = MessageFormatter.format_agent_response(response_text)
                        except json.JSONDecodeError:
                            # Not valid JSON, use regular formatting
                            formatted_response = MessageFormatter.format_agent_response(response_text)
                    else:
                        # Regular response, use standard formatting
                        formatted_response = MessageFormatter.format_agent_response(response_text)
                        
                    logger.debug(f"Formatted response preview: {formatted_response[:200]}...")
                except Exception as format_error:
                    logger.error(f"Error formatting response: {str(format_error)}")
                    # Use raw response if formatting fails
                    formatted_response = response_text
                
            except Exception as crew_error:
                logger.error(f"Technical crew execution failed: {str(crew_error)}")
                logger.error(f"Technical crew error type: {type(crew_error).__name__}")
                import traceback
                logger.error(f"Technical full traceback: {traceback.format_exc()}")
                raise crew_error
            
            # Send final response
            if ws_manager:
                try:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "agent_message",
                            "sender": "technical_analyst",
                            "sender_name": "Technical Analyst",
                            "message": formatted_response,
                            "is_thinking": False
                        }
                    )
                    logger.info(f"Successfully sent technical agent response via WebSocket")
                except Exception as ws_error:
                    logger.error(f"Error broadcasting technical agent response: {str(ws_error)}")
                    # Don't raise here, as the response was successful - just log the WebSocket error
            
            return {
                "status": "success",
                "message": formatted_response,
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
    
    async def chat_with_security_agent(
        self,
        db: AsyncSession,
        project_id: str,
        message: str,
        existing_analysis_id: Optional[str] = None,
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Handle security questions directed to the security agent
        
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
            logger.info(f"Security agent question for project {project_id}: {message}")
            
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
                        "sender": "security_analyst",
                        "sender_name": "Security Analyst",
                        "message": "Analyzing security aspects of your question...",
                        "is_thinking": True
                    }
                )
            
            # Create security-focused context
            context_parts = [f"Project: {project.name}"]
            if project.description:
                context_parts.append(f"Description: {project.description}")
            if project.industry:
                context_parts.append(f"Industry: {project.industry}")
            if project.goal:
                context_parts.append(f"Project Goal: {project.goal}")
            
            # Add comprehensive analysis context for security assessment
            if existing_analysis_id and project.insights:
                context_parts.append("Current Analysis Data for Security Review:")
                context_parts.append(self._get_security_context_summary(project.insights))
            
            context = "\n".join(context_parts)
            
            # Create security agent with document search
            llm = self._get_llm()
            tools = [DocumentSearchTool(project_id)]
            
            backstory = f"""You are a Senior Security Analyst with expertise in cybersecurity and application security. 
            
            Current Project Context:
            {context}
            
            Provide specific security recommendations based on the project's architecture and technology stack."""
            
            agent = Agent(
                role="Security Analyst",
                goal=f"Provide comprehensive security analysis and recommendations for the project based on the user's question: '{message}'",
                backstory=backstory,
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=tools
            )
            
            # Create security analysis task
            task = Task(
                description=f"Analyze the security aspects of the project and provide recommendations for the user's question: {message}",
                expected_output="Security analysis with specific recommendations and risk assessment",
                agent=agent
            )
            
            # Execute the crew
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=True,
                process=Process.sequential
            )
            
            try:
                result = crew.kickoff()
                response_text = str(result)
                logger.info(f"Security agent execution successful, response length: {len(response_text)}")
                logger.debug(f"Raw response preview: {response_text[:200]}...")
                
                # Format the response for better readability
                try:
                    formatted_response = MessageFormatter.format_agent_response(response_text)
                    logger.debug(f"Formatted response preview: {formatted_response[:200]}...")
                except Exception as format_error:
                    logger.error(f"Error formatting response: {str(format_error)}")
                    # Use raw response if formatting fails
                    formatted_response = response_text
                
            except Exception as crew_error:
                logger.error(f"Security crew execution failed: {str(crew_error)}")
                logger.error(f"Security crew error type: {type(crew_error).__name__}")
                import traceback
                logger.error(f"Security full traceback: {traceback.format_exc()}")
                raise crew_error
            
            # Send the response
            if ws_manager:
                try:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "agent_message",
                            "sender": "security_analyst",
                            "sender_name": "Security Analyst",
                            "message": formatted_response,
                            "is_thinking": False
                        }
                    )
                    logger.info(f"Successfully sent security agent response via WebSocket")
                except Exception as ws_error:
                    logger.error(f"Error broadcasting security agent response: {str(ws_error)}")
                    # Don't raise here, as the response was successful - just log the WebSocket error
            
            return {
                "status": "success",
                "message": formatted_response,
                "agent_id": "security_analyst"
            }
            
        except Exception as e:
            logger.error(f"Error in security agent chat: {str(e)}")
            error_message = "I encountered an error while analyzing your security question. Please try again."
            
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "security_analyst",
                        "sender_name": "Security Analyst",
                        "message": error_message,
                        "is_thinking": False,
                        "is_error": True
                    }
                )
            
            return {
                "status": "error",
                "message": error_message,
                "agent_id": "security_analyst"
            }
    
    def _get_security_context_summary(self, insights: Dict[str, Any]) -> str:
        """Get security-focused summary of analysis data for context"""
        try:
            summary_parts = []
            
            # Technical Analysis - Security Relevant
            if "technical_analysis" in insights:
                tech = insights["technical_analysis"]
                summary_parts.append("=== TECHNICAL ARCHITECTURE (Security Review) ===")
                summary_parts.append(f"Architecture: {tech.get('architecture', 'Not specified')}")
                
                # Technology Stack - Focus on security implications
                if "tech_stack" in tech:
                    stack = tech["tech_stack"]
                    summary_parts.append("Technology Stack:")
                    summary_parts.append(f"  Frontend: {', '.join(stack.get('frontend', []))}")
                    summary_parts.append(f"  Backend: {', '.join(stack.get('backend', []))}")
                    summary_parts.append(f"  Infrastructure: {', '.join(stack.get('infrastructure', []))}")
                    summary_parts.append(f"  Tools: {', '.join(stack.get('tools', []))}")
                
                # Security-relevant scores
                summary_parts.append(f"Security Score: {tech.get('security_score', 'Not assessed')}/10")
                summary_parts.append(f"Complexity Score: {tech.get('complexity_score', 'Not assessed')}/10")
            
            # Risk Assessment - Security Focus
            if "risk_assessment" in insights:
                risks = insights["risk_assessment"]
                summary_parts.append("\n=== IDENTIFIED RISKS (Security Perspective) ===")
                summary_parts.append(f"Overall Risk Score: {risks.get('overall_risk_score', 'Not assessed')}/10")
                
                if "key_risks" in risks:
                    summary_parts.append("Key Risks:")
                    for risk in risks["key_risks"][:5]:  # Top 5 risks
                        risk_name = risk.get("name", "Unknown Risk")
                        risk_level = risk.get("level", "Unknown")
                        impact = risk.get("impact", "Unknown")
                        summary_parts.append(f"  - {risk_name} (Level: {risk_level}, Impact: {impact})")
            
            # Project Plan - Security Considerations
            if "project_plan" in insights:
                plan = insights["project_plan"]
                summary_parts.append("\n=== PROJECT CONSTRAINTS (Security Implementation) ===")
                summary_parts.append(f"Timeline: {plan.get('timeline', 'Not specified')}")
                summary_parts.append(f"Estimated Cost: {plan.get('estimated_cost', 'Not specified')}")
                
                if "resource_requirements" in plan:
                    resources = plan["resource_requirements"]
                    dev_count = resources.get("developers", 0)
                    summary_parts.append(f"Development Team Size: {dev_count} developers")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error creating security context summary: {e}")
            return "Security context analysis not available due to data processing error."
    
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
    
    async def chat_with_project_planner(
        self,
        db: AsyncSession,
        project_id: str,
        message: str,
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """
        Handle project planning conversations with conversation memory to build project briefs incrementally
        
        Args:
            db: Database session
            project_id: ID of the project
            message: User's message
            ws_manager: WebSocket manager for real-time updates
            
        Returns:
            Dict with status and response
        """
        try:
            logger.info(f"Project planner conversation for project {project_id}: {message}")
            
            # Check if this is a save brief command
            if self._is_save_brief_command(message):
                return await self._handle_save_brief_command_with_memory(db, project_id, ws_manager)
            
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
                        "sender": "project_planner",
                        "sender_name": "Project Planner",
                        "message": "Working on your project planning request...",
                        "is_thinking": True
                    }
                )
            
            # Get conversation context from memory (sync with database if needed)
            conversation_context = conversation_memory.get_conversation_context(project_id, "project_planner")
            
            # If no conversation context but database has brief sections, sync them to memory
            if not conversation_context and getattr(project, 'brief_sections', {}):
                await incremental_brief_service.sync_memory_with_database(db, project_id)
                conversation_context = conversation_memory.get_conversation_context(project_id, "project_planner")
            
            # Get merged brief sections from database AND memory
            merged_brief_sections = await incremental_brief_service.get_merged_brief_sections(db, project_id)
            memory_brief_sections = conversation_memory.get_brief_building_context(project_id)
            
            project_data = {
                'name': project.name,
                'brief_sections': merged_brief_sections,
                'description': project.description,
                'goal': project.goal,
                'deadline': str(project.deadline) if project.deadline else None,
                'team_size': project.team_size,
                'budget': project.budget,
                'industry': project.industry
            }
            
            completion_status = self.brief_service.get_completion_status(project_data)
            
            # Build conversation history context
            conversation_history = ""
            if conversation_context and 'messages' in conversation_context:
                recent_messages = conversation_context['messages'][-3:]  # Last 3 exchanges
                history_parts = []
                for msg in recent_messages:
                    history_parts.append(f"User: {msg['user_message']}")
                    history_parts.append(f"You: {msg['agent_response'][:200]}...")
                conversation_history = "\n".join(history_parts)
            
            # Build user information context
            user_info_context = ""
            if conversation_context and 'user_information' in conversation_context:
                user_info = conversation_context['user_information']
                if user_info:
                    info_parts = []
                    for key, value in user_info.items():
                        info_parts.append(f"- {key}: {value}")
                    user_info_context = f"User-provided information:\n" + "\n".join(info_parts)
            
            # Create comprehensive context for the agent
            context_parts = [f"Project: {project.name}"]
            if project.description:
                context_parts.append(f"Description: {project.description}")
            
            # Add conversation memory context
            if conversation_history:
                context_parts.append(f"\nRECENT CONVERSATION:\n{conversation_history}")
            
            if user_info_context:
                context_parts.append(f"\n{user_info_context}")
            
            # Add brief completion status
            context_parts.append(f"\nBRIEF COMPLETION STATUS:")
            context_parts.append(f"Overall Progress: {completion_status['overall_progress']:.1f}%")
            context_parts.append(f"Completed Sections: {completion_status['completed_sections']}/{completion_status['total_sections']}")
            
            # Add work-in-progress sections from memory
            if memory_brief_sections:
                context_parts.append(f"\nWORK-IN-PROGRESS SECTIONS (from conversation):")
                for section_id, section_data in memory_brief_sections.items():
                    section = self.brief_service.get_section(section_id)
                    if section:
                        if isinstance(section_data, dict) and 'content' in section_data:
                            content_preview = section_data['content'][:100] + "..." if len(section_data['content']) > 100 else section_data['content']
                            context_parts.append(f"- {section.title}: {content_preview}")
                        else:
                            context_parts.append(f"- {section.title}: {str(section_data)[:100]}...")
            
            # Add incomplete sections
            incomplete_sections = []
            for section_id, section_status in completion_status['sections'].items():
                if not section_status['is_complete']:
                    section = self.brief_service.get_section(section_id)
                    if section:
                        incomplete_sections.append(f"- {section.title} ({section_status['completion_percentage']:.0f}% complete)")
            
            if incomplete_sections:
                context_parts.append("\nINCOMPLETE SECTIONS:")
                context_parts.extend(incomplete_sections)
            
            context = "\n".join(context_parts)
            
            # Create project planner agent with memory awareness
            llm = self._get_llm(temperature=0.3)
            
            backstory = f"""You are an expert project planning specialist helping to create a comprehensive project brief.
            You maintain conversation memory and build upon previous information shared by the user.

            CURRENT PROJECT CONTEXT:
            {context}

            CRITICAL INSTRUCTIONS FOR MEMORY CONTINUITY:
            1. **ALWAYS BUILD UPON PREVIOUS INFORMATION**: Use the "Recent Conversation" and "User-provided information" sections above
            2. **NEVER START OVER**: Incorporate new information with what was already shared
            3. **INCREMENTAL BUILDING**: Add new details to existing sections rather than replacing them
            4. **ACKNOWLEDGE PROGRESS**: Reference previous information when building on it
            5. **MAINTAIN CONTEXT**: Remember what the user has already told you about their project

            PROJECT BRIEF SECTIONS (12 sections total):
            1. Project Overview - Basic identification and metadata
            2. Project Background - Context and current situation  
            3. Business Case - Problems, objectives, expected value
            4. Goals & Success Criteria - Primary goals and metrics
            5. Target Audience/Users - User types and needs
            6. High-Level Scope - What's in and out of scope
            7. High-Level Requirements - Functional, technical, constraints
            8. Preliminary Timeline - Dates and milestones
            9. Preliminary Budget - Range, breakdown, ongoing costs
            10. Key Stakeholders - Roles and responsibilities
            11. Initial Resources - Team allocation and skills
            12. Next Steps - Immediate actions needed

            CONVERSATION APPROACH:
            - Build upon information already shared in this conversation
            - Ask for NEW information to fill gaps, not information already provided
            - Show updated brief sections incorporating both old and new information
            - Guide them through missing sections while preserving completed work
            - Celebrate progress and show how new information enhances the brief

            RESPONSE STYLE:
            - Acknowledge previous information: "Based on what you told me about..."
            - Show incremental progress: "I'll add this to the [section] we were working on..."
            - Build comprehensively: Combine all information shared so far
            - Be encouraging about cumulative progress"""
            
            agent = Agent(
                role="Project Planning Specialist with Memory",
                goal="Help users incrementally build comprehensive project briefs by remembering and building upon all previous conversation context",
                backstory=backstory,
                llm=llm,
                verbose=True,
                allow_delegation=False
            )
            
            # Create and execute task
            task = Task(
                description=f"Help the user with their project planning, building upon all previous conversation context: {message}",
                expected_output="A helpful response that incorporates previous information and adds new details to build the project brief incrementally",
                agent=agent
            )
            
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=True,
                process=Process.sequential
            )
            
            try:
                response = crew.kickoff()
                response_text = str(response).strip()
                logger.info(f"Project planner execution successful, response length: {len(response_text)}")
                
                # Extract and store any brief information mentioned in the response
                await self._extract_and_store_brief_info(project_id, message, response_text)
                
                # Store conversation in memory
                conversation_memory.add_message_to_context(project_id, "project_planner", message, response_text)
                
                # Auto-save progress to database if enough content accumulated
                await incremental_brief_service.auto_save_progress(db, project_id)
                
                # Format the response for better readability
                try:
                    formatted_response = MessageFormatter.format_agent_response(response_text)
                except Exception as format_error:
                    logger.error(f"Error formatting response: {str(format_error)}")
                    formatted_response = response_text
                
            except Exception as crew_error:
                logger.error(f"Project planner crew execution failed: {str(crew_error)}")
                raise crew_error
            
            # Send final response with updated context
            if ws_manager:
                # Get updated completion status after potential changes
                updated_brief_sections = conversation_memory.get_brief_building_context(project_id)
                updated_project_data = {**project_data, 'brief_sections': {**merged_brief_sections, **updated_brief_sections}}
                updated_completion_status = self.brief_service.get_completion_status(updated_project_data)
                
                response_message = {
                    "type": "agent_message",
                    "sender": "project_planner",
                    "sender_name": "Project Planner",
                    "message": formatted_response,
                    "is_thinking": False,
                    "planning_context": {
                        "completion_status": updated_completion_status,
                        "next_sections": [section_id for section_id, status in updated_completion_status['sections'].items() 
                                        if not status['is_complete']][:3],
                        "has_memory": bool(conversation_context),
                        "memory_sections": len(updated_brief_sections)
                    }
                }
                
                await ws_manager.broadcast(project_id, response_message)
            
            return {
                "status": "success",
                "message": formatted_response,
                "agent_id": "project_planner",
                "completion_status": completion_status,
                "memory_active": bool(conversation_context)
            }
            
        except Exception as e:
            logger.error(f"Error in project planner chat: {str(e)}")
            error_message = "I encountered an error while helping with your project planning. Please try again."
            
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "project_planner",
                        "sender_name": "Project Planner",
                        "message": error_message,
                        "is_thinking": False,
                        "is_error": True
                    }
                )
            
            return {
                "status": "error",
                "message": error_message,
                "agent_id": "project_planner"
            }
    
    async def _extract_and_store_brief_info(self, project_id: str, user_message: str, agent_response: str) -> None:
        """
        Extract project brief information from agent response and store in conversation memory
        """
        try:
            import re
            
            # Parse any structured brief information from the agent response
            # Look for section headers and content
            section_patterns = {
                'project_overview': [r'project overview', r'overview'],
                'project_background': [r'project background', r'background'],
                'business_case': [r'business case', r'business problem'],
                'goals_success_criteria': [r'goals', r'success criteria'],
                'target_audience': [r'target audience', r'users'],
                'high_level_scope': [r'scope'],
                'high_level_requirements': [r'requirements'],
                'preliminary_timeline': [r'timeline', r'schedule'],
                'preliminary_budget': [r'budget', r'cost'],
                'key_stakeholders': [r'stakeholders'],
                'initial_resources': [r'resources', r'team'],
                'next_steps': [r'next steps']
            }
            
            # Extract information from user message
            user_info = {}
            if user_message:
                # Look for specific project information patterns
                project_info_patterns = {
                    'project_name': r'project.*called\s+([^.]+)|project.*named\s+([^.]+)|building\s+([^.]+)',
                    'industry': r'industry.*is\s+([^.]+)|working.*in\s+([^.]+)',
                    'budget': r'budget.*is\s+([^.]+)|cost.*around\s+([^.]+)',
                    'timeline': r'timeline.*is\s+([^.]+)|complete.*by\s+([^.]+)|deadline.*is\s+([^.]+)',
                    'team_size': r'team.*of\s+(\d+)|(\d+)\s+people',
                    'goal': r'goal.*is\s+([^.]+)|want.*to\s+([^.]+)',
                }
                
                for key, pattern in project_info_patterns.items():
                    match = re.search(pattern, user_message.lower())
                    if match:
                        value = next((group for group in match.groups() if group), None)
                        if value:
                            user_info[key] = value.strip()
            
            # Store extracted information in conversation memory
            if user_info:
                conversation_memory.merge_user_information(project_id, user_info)
                logger.info(f"Extracted and stored user information for project {project_id}: {list(user_info.keys())}")
            
            # Parse any brief sections from the agent response
            brief_sections = {}
            response_lower = agent_response.lower()
            
            # Look for structured brief content in the response
            for section_id, patterns in section_patterns.items():
                for pattern in patterns:
                    if pattern in response_lower:
                        # Try to extract content for this section
                        section_start = response_lower.find(pattern)
                        if section_start != -1:
                            # Find content after the section header
                            content_start = section_start + len(pattern)
                            content_end = response_lower.find('\n\n', content_start)
                            if content_end == -1:
                                content_end = len(response_lower)
                            
                            content = agent_response[content_start:content_end].strip()
                            if content and len(content) > 10:  # Only store substantial content
                                brief_sections[section_id] = {
                                    'content': content,
                                    'title': section_id.replace('_', ' ').title()
                                }
                                break
            
            # Store brief sections in memory
            for section_id, section_data in brief_sections.items():
                conversation_memory.update_brief_section(project_id, section_id, section_data)
                logger.info(f"Updated brief section {section_id} in memory for project {project_id}")
            
            # Also store any explicit user information
            if user_info:
                logger.info(f"Extracted user info for project {project_id}: {user_info}")
            
        except Exception as e:
            import traceback
            logger.error(f"Error extracting brief information for project {project_id}: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            # Don't raise - this is a helper function and shouldn't break the main flow
    
    async def _handle_save_brief_command_with_memory(self, db: AsyncSession, project_id: str, ws_manager: Optional[WebSocketManager]) -> Dict[str, Any]:
        """
        Handle save brief command using conversation memory
        """
        try:
            logger.info(f"Handling save brief command with memory for project {project_id}")
            
            # Get project details
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Get brief sections from conversation memory
            memory_brief_sections = conversation_memory.get_brief_building_context(project_id)
            logger.info(f"Memory brief sections for project {project_id}: {len(memory_brief_sections) if memory_brief_sections else 0} sections")
            
            # Debug: Log what's actually in memory
            if memory_brief_sections:
                logger.debug(f"Memory sections content: {list(memory_brief_sections.keys())}")
                for section_id, content in memory_brief_sections.items():
                    logger.debug(f"Section {section_id}: {str(content)[:100]}...")
            else:
                # Check if there's any conversation context at all
                conversation_context = conversation_memory.get_conversation_context(project_id, "project_planner")
                logger.debug(f"Full conversation context exists: {bool(conversation_context)}")
                if conversation_context:
                    logger.debug(f"Context keys: {list(conversation_context.keys())}")
            
            if not memory_brief_sections:
                # No brief data in memory, try to create sample data for testing
                logger.warning(f"No brief data in memory for project {project_id}, trying fallback save method")
                
                # Temporary: Add sample data for testing if in development mode
                if os.getenv("DEBUG", "").lower() in ["true", "1"]:
                    logger.info("Debug mode: Creating sample brief data for testing")
                    sample_sections = {
                        "project_overview": {
                            "content": f"Project brief for {project.name}",
                            "title": "Project Overview"
                        }
                    }
                    # Save sample data and retry
                    for section_id, section_data in sample_sections.items():
                        conversation_memory.update_brief_section(project_id, section_id, section_data)
                    memory_brief_sections = conversation_memory.get_brief_building_context(project_id)
                    logger.info(f"Added sample data, now have {len(memory_brief_sections)} sections in memory")
                
                # Check again after potential sample data addition
                if not memory_brief_sections:
                    # Check if there's existing brief data in the database that we can reference
                    existing_brief_sections = getattr(project, 'brief_sections', {}) or {}
                    if existing_brief_sections:
                        # There's existing data, just update the status
                        success = await incremental_brief_service.save_partial_brief_sections(db, project_id, existing_brief_sections)
                        if success:
                            if ws_manager:
                                await ws_manager.broadcast(
                                    project_id,
                                    {
                                        "type": "agent_message",
                                        "sender": "project_planner",
                                        "sender_name": "Project Planner",
                                        "message": f"✅ Found and confirmed {len(existing_brief_sections)} existing brief sections in the database. No new information to save from our current conversation."
                                    }
                                )
                            return {
                                "status": "success",
                                "message": "Existing brief confirmed in database",
                                "agent_id": "project_planner"
                            }
                    
                    # Truly no brief data anywhere
                    if ws_manager:
                        await ws_manager.broadcast(
                            project_id,
                            {
                                "type": "agent_message",
                                "sender": "project_planner",
                                "sender_name": "Project Planner",
                                "message": "I don't have any project brief information in our conversation memory to save. Please share some project details first, then ask me to save the brief."
                            }
                        )
                    
                    return {
                        "status": "error",
                        "message": "No brief information found in conversation memory",
                        "agent_id": "project_planner"
                    }
            
            # Merge with existing database brief sections
            existing_brief_sections = getattr(project, 'brief_sections', {}) or {}
            merged_brief_sections = {**existing_brief_sections, **memory_brief_sections}
            logger.info(f"Preparing to save {len(memory_brief_sections)} memory sections to database for project {project_id}")
            
            # Save to database using incremental service
            success = await incremental_brief_service.save_partial_brief_sections(db, project_id, memory_brief_sections)
            logger.info(f"Save operation result for project {project_id}: {success}")
            
            if success:
                # Clear memory after successful save
                await incremental_brief_service.clear_memory_after_save(project_id)
                
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "agent_message",
                            "sender": "project_planner",
                            "sender_name": "Project Planner",
                            "message": f"✅ Successfully saved your project brief to the database! Saved {len(memory_brief_sections)} sections from our conversation. The brief is now stored in your project and can be used for technical analysis."
                        }
                    )
                
                return {
                    "status": "success",
                    "message": "Project brief saved successfully from conversation memory",
                    "agent_id": "project_planner",
                    "sections_saved": len(memory_brief_sections)
                }
            else:
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "agent_message",
                            "sender": "project_planner",
                            "sender_name": "Project Planner",
                            "message": "❌ I encountered an error while trying to save the project brief. Please try again."
                        }
                    )
                
                return {
                    "status": "error",
                    "message": "Failed to save project brief",
                    "agent_id": "project_planner"
                }
                
        except Exception as e:
            import traceback
            logger.error(f"Error in save brief command with memory for project {project_id}: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            error_message = "I encountered an error while trying to save your project brief."
            
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "project_planner",
                        "sender_name": "Project Planner",
                        "message": error_message
                    }
                )
            
            return {
                "status": "error",
                "message": error_message,
                "agent_id": "project_planner"
            }
    
    def _is_save_brief_command(self, message: str) -> bool:
        """Check if message is a command to save the project brief"""
        save_patterns = [
            r'\bsave\s+brief\b',
            r'\bsave\s+project\s+brief\b',
            r'\bstore\s+brief\b',
            r'\bsave\s+this\s+brief\b',
            r'\bsave\s+to\s+database\b',
            r'\bstore\s+in\s+database\b',
            r'\bsave\s+above\s+brief\b',
            r'\bsave\s+the\s+brief\b'
        ]
        
        message_lower = message.lower().strip()
        for pattern in save_patterns:
            if re.search(pattern, message_lower):
                return True
        return False
    
    async def _handle_save_brief_command(
        self, 
        db: AsyncSession, 
        project_id: str, 
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """Handle saving the current project brief to the database"""
        try:
            from app.services.project_brief_service import ProjectBriefService
            
            # Send thinking message
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "project_planner",
                        "sender_name": "Project Planner",
                        "message": "Looking for the latest project brief to save...",
                        "is_thinking": True
                    }
                )
            
            # Get the project to check for existing brief data
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Check if there's already brief data
            if project.brief_sections and isinstance(project.brief_sections, dict):
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "agent_message",
                            "sender": "project_planner",
                            "sender_name": "Project Planner",
                            "message": "✅ Great! I found your project brief and it's already saved in the database.\n\nYour project brief contains the following sections:\n" + 
                                     "\n".join([f"• {section_data.get('title', section_id)}" for section_id, section_data in project.brief_sections.items() if isinstance(section_data, dict)]) +
                                     "\n\nThe technical analyst will now have access to this comprehensive project brief when performing analysis. You can proceed with technical analysis!",
                            "is_thinking": False
                        }
                    )
                
                return {
                    "status": "success",
                    "message": "Project brief is already saved",
                    "agent_id": "project_planner"
                }
            else:
                # Try to parse a sample brief from the user's message for manual saving
                return await self._handle_manual_brief_save(db, project_id, ws_manager)
        
        except Exception as e:
            logger.error(f"Error handling save brief command: {str(e)}")
            error_message = "I encountered an error while trying to save the project brief. Please try again."
            
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "project_planner",
                        "sender_name": "Project Planner",
                        "message": error_message,
                        "is_thinking": False,
                        "is_error": True
                    }
                )
            
            return {
                "status": "error",
                "message": error_message,
                "agent_id": "project_planner"
            }

    
    async def _handle_manual_brief_save(
        self, 
        db: AsyncSession, 
        project_id: str, 
        ws_manager: Optional[WebSocketManager] = None
    ) -> Dict[str, Any]:
        """Handle manual saving of project brief with guided process"""
        try:
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "agent_message",
                        "sender": "project_planner",
                        "sender_name": "Project Planner",
                        "message": "📝 Ready to save your project brief!\n\nI can help you save a project brief to the database in two ways:\n\n**Option 1:** Paste your complete project brief\nIf you have a formatted project brief (like the one I just provided), you can:\n1. Copy the entire brief text\n2. Type 'save this brief:' followed by your brief content\n3. I'll parse and save it to the database\n\n**Option 2:** Build it step by step\nI can guide you through building a comprehensive project brief section by section.\n\n**Example format for Option 1:**\n```\nsave this brief:\nPROJECT OVERVIEW\nProject Name: Your Project\n...\n```\n\nWhich option would you prefer?",
                        "is_thinking": False
                    }
                )
            
            return {
                "status": "info",
                "message": "Ready to help save project brief",
                "agent_id": "project_planner"
            }
        
        except Exception as e:
            logger.error(f"Error in manual brief save: {str(e)}")
            return {
                "status": "error", 
                "message": "Error preparing brief save process",
                "agent_id": "project_planner"
            }
