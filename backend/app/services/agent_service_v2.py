import logging
import json
import uuid
import asyncio
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from crewai import Agent, Task, Crew, Process
from langchain_anthropic import ChatAnthropic
from crewai.agent import Agent as CrewAgent
from crewai.task import Task as CrewTask

from app.models.agent import AgentTask as AgentTaskModel
from app.services.project_service import ProjectService
from app.config.config_loader import ConfigLoader
from app.core.config import settings
from app.tools.document_search import DocumentSearchTool
from app.services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

class AgentServiceV2:
    """Service for managing AI agents using CrewAI with Anthropic integration"""
    
    def __init__(self):
        """Initialize the agent service"""
        self.config_loader = ConfigLoader()
    
    async def start_analysis(self, db: AsyncSession, project_id: str, ws_manager: Optional[WebSocketManager] = None) -> str:
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
        logger.info(f"Starting analysis {analysis_id} for project {project_id}")
        
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
        
        # Start the analysis in a background task
        asyncio.create_task(self._execute_analysis(analysis_id, project_id, db, ws_manager))
        
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
    
    async def _execute_analysis(self, analysis_id: str, project_id: str, db: AsyncSession, ws_manager: Optional[WebSocketManager] = None) -> None:
        """
        Execute an agent analysis
        
        Args:
            analysis_id: ID of the analysis
            project_id: ID of the project to analyze
            db: Database session
            ws_manager: Optional WebSocket manager for real-time updates
        """
        try:
            logger.info(f"Executing analysis {analysis_id} for project {project_id}")
            
            # Check if all documents for this project are processed
            # Import here to avoid circular imports
            from app.services.document_processor import DocumentProcessor
            document_processor = DocumentProcessor()
            
            # Send status update via WebSocket
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_status",
                        "status": "processing_documents",
                        "analysis_id": analysis_id,
                        "message": "Processing project documents"
                    }
                )
            
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
            
            # Check if we already have analysis results for this project
            from app.services.project_service import ProjectService
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            
            if project and project.insights:
                logger.info(f"Analysis results already exist for project {project_id}")
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
                error_msg = "ANTHROPIC_API_KEY not found in environment variables"
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
            
            # Initialize the Anthropic LLM
            llm = ChatAnthropic(
                model_name=anthropic_model,
                anthropic_api_key=anthropic_api_key,
                temperature=0.2,
                max_tokens=4000
            )
            
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
            logger.info("Starting crew execution")
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_status",
                        "status": "executing_analysis",
                        "analysis_id": analysis_id,
                        "message": "AI agent is analyzing the project"
                    }
                )
            
            # Create a callback handler for real-time updates
            class WebSocketCallback:
                @staticmethod
                async def on_agent_start(agent: CrewAgent):
                    if ws_manager:
                        await ws_manager.broadcast(
                            project_id,
                            {
                                "type": "agent_message",
                                "sender": "technical_agent",
                                "sender_name": "Technical Analysis Agent",
                                "message": f"Starting analysis as {agent.role}",
                                "analysis_id": analysis_id
                            }
                        )
                
                @staticmethod
                async def on_agent_task(agent: CrewAgent, task: CrewTask):
                    if ws_manager:
                        await ws_manager.broadcast(
                            project_id,
                            {
                                "type": "agent_message",
                                "sender": "technical_agent",
                                "sender_name": "Technical Analysis Agent",
                                "message": f"Working on task: {task.description[:100]}...",
                                "analysis_id": analysis_id
                            }
                        )
                
                @staticmethod
                async def on_agent_thinking(agent: CrewAgent, thought: str):
                    if ws_manager and thought:
                        await ws_manager.broadcast(
                            project_id,
                            {
                                "type": "agent_thought",
                                "sender": "technical_agent",
                                "sender_name": "Technical Analysis Agent",
                                "message": thought[:500] + ("..." if len(thought) > 500 else ""),
                                "analysis_id": analysis_id
                            }
                        )
            
            # Register callbacks if we have a WebSocket manager
            if ws_manager:
                # Note: In a real implementation, we would register these callbacks with CrewAI
                # For now, we'll simulate some updates during execution
                await WebSocketCallback.on_agent_start(technical_agent)
            
            try:
                result = crew.kickoff()
                logger.info("Crew execution completed")
                
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_status",
                            "status": "analysis_completed",
                            "analysis_id": analysis_id,
                            "message": "AI analysis completed successfully"
                        }
                    )
            except Exception as crew_error:
                error_msg = f"Error during crew execution: {str(crew_error)}"
                logger.error(error_msg)
                import traceback
                trace = traceback.format_exc()
                logger.error(f"Traceback: {trace}")
                
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "analysis_id": analysis_id,
                            "message": error_msg
                        }
                    )
                raise
            
            # Format the results
            analysis_result = {
                "technical_analysis": {
                    "raw_output": result,
                    "completed_at": str(datetime.now())
                },
                "analysis_id": analysis_id
            }
            
            # Store the results
            logger.info("Storing analysis results")
            if ws_manager:
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "analysis_status",
                        "status": "storing_results",
                        "analysis_id": analysis_id,
                        "message": "Storing analysis results"
                    }
                )
            
            project_service = ProjectService()
            
            try:
                await project_service.store_project_insights(db, project_id, analysis_result)
                logger.info("Successfully stored project insights")
                
                # Send the final results via WebSocket
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "analysis_result",
                            "analysis_id": analysis_id,
                            "result": {
                                "technical_analysis": result[:1000] + ("..." if len(result) > 1000 else ""),
                                "completed_at": str(datetime.now())
                            },
                            "message": "Analysis results are ready"
                        }
                    )
            except Exception as store_error:
                error_msg = f"Error storing project insights: {str(store_error)}"
                logger.error(error_msg)
                import traceback
                trace = traceback.format_exc()
                logger.error(f"Traceback: {trace}")
                
                if ws_manager:
                    await ws_manager.broadcast(
                        project_id,
                        {
                            "type": "error",
                            "analysis_id": analysis_id,
                            "message": error_msg
                        }
                    )
                raise
            
            logger.info(f"Completed analysis {analysis_id} for project {project_id}")
            
        except Exception as e:
            logger.error(f"Error executing analysis {analysis_id}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # In a real implementation, this would update the analysis status to error
