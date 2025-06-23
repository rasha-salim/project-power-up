import logging
import json
from typing import List, Dict, Any, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.project import Project, ProjectCreate, ProjectUpdate
from app.models.analysis import ProjectAnalysis
from app.db.init_db_simple import get_chroma_client

logger = logging.getLogger(__name__)

class ProjectService:
    """Service for managing projects"""
    
    async def create_project(self, db: AsyncSession, project_create: ProjectCreate) -> Project:
        """
        Create a new project
        
        Args:
            db: Database session
            project_create: Project creation data
            
        Returns:
            Project: Created project
        """
        logger.info(f"Creating project with name: {project_create.name}")
        
        try:
            # Create the project object
            project = Project(
                id=project_create.id,
                name=project_create.name,
                description=project_create.description,
                status=project_create.status
            )
            
            # Add to session and commit
            logger.info(f"Project object created, adding to database")
            async with db.begin():
                db.add(project)
                logger.info(f"Project added to session, committing")
            
            # Refresh to get updated values from database
            logger.info(f"Refreshing project object")
            await db.refresh(project)
            
            logger.info(f"Project created successfully with ID: {project.id}")
            return project
            
        except Exception as e:
            logger.error(f"Error in create_project: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # No need to explicitly rollback as the context manager will do it
            raise
    
    async def get_project(self, db: AsyncSession, project_id: str) -> Optional[Project]:
        """
        Get a project by ID
        
        Args:
            db: Database session
            project_id: ID of the project to retrieve
            
        Returns:
            Optional[Project]: Project if found, None otherwise
        """
        result = await db.execute(select(Project).where(Project.id == project_id))
        return result.scalars().first()
        
    async def get_project_with_structured_insights(self, db: AsyncSession, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a project by ID with insights deserialized into Pydantic models
        
        Args:
            db: Database session
            project_id: ID of the project to retrieve
            
        Returns:
            Optional[Dict]: Project with structured insights if found, None otherwise
        """
        project = await self.get_project(db, project_id)
        
        if not project:
            return None
            
        # Convert SQLAlchemy model to dict
        project_dict = {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "created_at": project.created_at,
            "updated_at": project.updated_at
        }
        
        # If insights exist, deserialize them
        if project.insights:
            try:
                # Parse insights into Pydantic model
                structured_insights = self.deserialize_project_insights(project.insights)
                project_dict["insights"] = structured_insights
            except Exception as e:
                logger.error(f"Error deserializing insights for project {project_id}: {str(e)}")
                # Fall back to raw insights
                project_dict["insights"] = project.insights
                
        return project_dict
    
    async def list_projects(self, db: AsyncSession) -> List[Project]:
        """
        List all projects
        
        Args:
            db: Database session
            
        Returns:
            List[Project]: List of projects
        """
        result = await db.execute(select(Project))
        return result.scalars().all()
        
    async def list_projects_with_structured_insights(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        List all projects with insights deserialized into Pydantic models
        
        Args:
            db: Database session
            
        Returns:
            List[Dict]: List of projects with structured insights
        """
        projects = await self.list_projects(db)
        structured_projects = []
        
        for project in projects:
            # Convert SQLAlchemy model to dict
            project_dict = {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "status": project.status,
                "created_at": project.created_at,
                "updated_at": project.updated_at
            }
            
            # If insights exist, deserialize them
            if project.insights:
                try:
                    # Parse insights into Pydantic model
                    structured_insights = self.deserialize_project_insights(project.insights)
                    project_dict["insights"] = structured_insights
                except Exception as e:
                    logger.error(f"Error deserializing insights for project {project.id}: {str(e)}")
                    # Fall back to raw insights
                    project_dict["insights"] = project.insights
            
            structured_projects.append(project_dict)
                
        return structured_projects
    
    async def update_project(self, db: AsyncSession, project_id: str, project_update: ProjectUpdate) -> Optional[Project]:
        """
        Update a project
        
        Args:
            db: Database session
            project_id: ID of the project to update
            project_update: Project update data
            
        Returns:
            Optional[Project]: Updated project if found, None otherwise
        """
        project = await self.get_project(db, project_id)
        
        if not project:
            return None
            
        # Update project fields
        if project_update.name is not None:
            project.name = project_update.name
            
        if project_update.description is not None:
            project.description = project_update.description
            
        if project_update.status is not None:
            project.status = project_update.status
            
        if project_update.insights is not None:
            project.insights = project_update.insights
            
        await db.commit()
        await db.refresh(project)
        
        return project
    
    async def delete_project(self, db: AsyncSession, project_id: str) -> bool:
        """
        Delete a project
        
        Args:
            db: Database session
            project_id: ID of the project to delete
            
        Returns:
            bool: True if project was deleted, False otherwise
        """
        project = await self.get_project(db, project_id)
        
        if not project:
            return False
            
        # Delete project insights from vector store
        client = get_chroma_client()
        collection = client.get_collection("project_insights")
        
        # Query for insights with this project_id in metadata
        results = collection.get(
            where={"project_id": project_id}
        )
        
        if results and results["ids"]:
            # Delete insights from collection
            collection.delete(ids=results["ids"])
            
        # Delete project from database
        await db.delete(project)
        await db.commit()
        
        return True
    
    async def trigger_agent_analysis(self, db: AsyncSession, project_id: str) -> None:
        """
        Trigger AI agent analysis for a project
        
        Args:
            db: Database session
            project_id: ID of the project to analyze
        """
        # This method would integrate with the AgentService to start the analysis
        # For now, it's a placeholder
        logger.info(f"Triggered agent analysis for project {project_id}")
        
        # In a real implementation, this would:
        # 1. Get all documents for the project
        # 2. Prepare the data for the agents
        # 3. Start the agent analysis process
        # 4. Update the project status
        
        # For now, we'll just update the project status
        await self.update_project(
            db, 
            project_id, 
            ProjectUpdate(status="analyzing")
        )
    
    def deserialize_project_insights(self, insights_data: Dict[str, Any]) -> Union[ProjectAnalysis, Dict[str, Any]]:
        """
        Deserialize project insights from JSON to Pydantic model
        
        Args:
            insights_data: Raw insights data from database
            
        Returns:
            Union[ProjectAnalysis, Dict[str, Any]]: Structured insights as Pydantic model or raw dict if parsing fails
        """
        try:
            # Try to parse as ProjectAnalysis
            return ProjectAnalysis.parse_obj(insights_data)
        except Exception as e:
            logger.warning(f"Could not parse insights as ProjectAnalysis: {str(e)}")
            # Return the raw dict if parsing fails
            return insights_data
    
    async def store_project_insights(self, db: AsyncSession, project_id: str, insights: Dict[str, Any]) -> None:
        """
        Store project insights from agent analysis
        
        Args:
            db: Database session
            project_id: ID of the project
            insights: Insights from agent analysis
        """
        try:
            # Update project with insights in the database only
            # Skip the vector store operations for now to avoid ChromaDB issues
            await self.update_project(
                db, 
                project_id, 
                ProjectUpdate(
                    status="completed",
                    insights=insights
                )
            )
            
            logger.info(f"Successfully stored insights for project {project_id} in database")
            
            # Note: We're skipping the ChromaDB vector storage for now
            # This will make the project creation work, but semantic search won't be available
            # TODO: Fix ChromaDB integration in a future update
            
        except Exception as e:
            logger.error(f"Error storing project insights: {str(e)}")
            raise
    
    async def search_project_insights(self, db: AsyncSession, project_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search project insights using basic keyword matching (temporary solution)
        
        Args:
            db: Database session
            project_id: ID of the project
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: List of matching insights
        """
        try:
            # Get the project to access its insights
            project = await self.get_project(db, project_id)
            
            if not project or not project.insights:
                return []
            
            # Simple keyword-based search as a fallback
            # This is not as powerful as semantic search but will work without ChromaDB
            query = query.lower()
            insights = []
            
            # Helper function to check if a string contains the query
            def matches_query(text):
                return isinstance(text, str) and query in text.lower()
            
            # Process insights from the project
            for category, items in project.insights.items():
                if isinstance(items, list):
                    for i, item in enumerate(items):
                        if matches_query(item):
                            insights.append({
                                "text": item,
                                "metadata": {
                                    "project_id": project_id,
                                    "category": category,
                                    "index": i
                                },
                                "score": 1.0  # Simple match score
                            })
                elif isinstance(items, dict):
                    for key, value in items.items():
                        if matches_query(value):
                            insights.append({
                                "text": value,
                                "metadata": {
                                    "project_id": project_id,
                                    "category": category,
                                    "key": key
                                },
                                "score": 1.0  # Simple match score
                            })
            
            # Sort by relevance (all have same score in this simple implementation)
            # and limit results
            return insights[:limit]
            
        except Exception as e:
            logger.error(f"Error searching project insights: {str(e)}")
            return []
