import logging
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.project import Project, ProjectCreate, ProjectUpdate
from app.db.init_db import get_chroma_client

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
        project = Project(
            id=project_create.id,
            name=project_create.name,
            description=project_create.description,
            status=project_create.status
        )
        
        db.add(project)
        await db.commit()
        await db.refresh(project)
        
        logger.info(f"Created project with ID {project.id}")
        return project
    
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
    
    async def store_project_insights(self, db: AsyncSession, project_id: str, insights: Dict[str, Any]) -> None:
        """
        Store project insights from agent analysis
        
        Args:
            db: Database session
            project_id: ID of the project
            insights: Insights from agent analysis
        """
        # Update project with insights
        await self.update_project(
            db, 
            project_id, 
            ProjectUpdate(
                status="completed",
                insights=insights
            )
        )
        
        # Store insights in vector store for semantic search
        client = get_chroma_client()
        collection = client.get_collection("project_insights")
        
        # Create vector entries for each insight
        for category, items in insights.items():
            if isinstance(items, list):
                for i, item in enumerate(items):
                    if isinstance(item, str):
                        # Store the insight text
                        collection.add(
                            ids=[f"{project_id}_{category}_{i}"],
                            documents=[item],
                            metadatas=[{
                                "project_id": project_id,
                                "category": category,
                                "index": i
                            }]
                        )
            elif isinstance(items, dict):
                # For nested dictionaries, store each value
                for key, value in items.items():
                    if isinstance(value, str):
                        collection.add(
                            ids=[f"{project_id}_{category}_{key}"],
                            documents=[value],
                            metadatas=[{
                                "project_id": project_id,
                                "category": category,
                                "key": key
                            }]
                        )
        
        logger.info(f"Stored insights for project {project_id}")
    
    async def search_project_insights(self, db: AsyncSession, project_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search project insights using semantic search
        
        Args:
            db: Database session
            project_id: ID of the project
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: List of matching insights
        """
        client = get_chroma_client()
        collection = client.get_collection("project_insights")
        
        # Search for insights
        results = collection.query(
            query_texts=[query],
            where={"project_id": project_id},
            n_results=limit
        )
        
        # Format results
        insights = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                insights.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if i < len(results["metadatas"][0]) else {},
                    "score": results["distances"][0][i] if i < len(results["distances"][0]) else 0
                })
        
        return insights
