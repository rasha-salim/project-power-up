"""
Incremental Brief Service - Handles saving partial brief sections to database
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.project_service import ProjectService
from app.services.conversation_memory_service import conversation_memory
from app.models.project import ProjectUpdate

logger = logging.getLogger(__name__)


class IncrementalBriefService:
    """Service for managing incremental brief building and saving partial sections"""
    
    def __init__(self):
        """Initialize the incremental brief service"""
        self.project_service = ProjectService()
    
    async def save_partial_brief_sections(
        self, 
        db: AsyncSession, 
        project_id: str, 
        sections_to_save: Dict[str, Any] = None
    ) -> bool:
        """
        Save partial brief sections to database, preserving existing data
        
        Args:
            db: Database session
            project_id: ID of the project
            sections_to_save: Specific sections to save (if None, gets from memory)
            
        Returns:
            bool: True if saved successfully
        """
        try:
            logger.info(f"Saving partial brief sections for project {project_id}")
            
            # Get project
            project = await self.project_service.get_project(db, project_id)
            if not project:
                logger.error(f"Project {project_id} not found")
                return False
            
            # Get sections to save (from parameter or memory)
            if sections_to_save is None:
                sections_to_save = conversation_memory.get_brief_building_context(project_id)
            
            if not sections_to_save:
                logger.warning(f"No brief sections to save for project {project_id}")
                return False
            
            # Get existing brief sections from database
            existing_sections = getattr(project, 'brief_sections', {}) or {}
            
            # Merge new sections with existing ones (new sections take precedence)
            merged_sections = {**existing_sections, **sections_to_save}
            
            # Update project with merged sections
            planning_status = self._determine_planning_status(merged_sections)
            
            # Create ProjectUpdate model
            project_update = ProjectUpdate(
                brief_sections=merged_sections,
                planning_status=planning_status
            )
            
            logger.info(f"Update data for project {project_id}: planning_status={planning_status}, sections_count={len(merged_sections)}")
            logger.debug(f"Merged sections keys: {list(merged_sections.keys())}")
            
            # Save to database
            await self.project_service.update_project(db, project_id, project_update)
            logger.info(f"Database update completed successfully for project {project_id}")
            
            logger.info(f"Successfully saved {len(sections_to_save)} brief sections for project {project_id}")
            return True
            
        except Exception as e:
            import traceback
            logger.error(f"Error saving partial brief sections for project {project_id}: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False
    
    async def get_merged_brief_sections(self, db: AsyncSession, project_id: str) -> Dict[str, Any]:
        """
        Get merged brief sections from database and memory
        
        Args:
            db: Database session
            project_id: ID of the project
            
        Returns:
            Dict containing merged brief sections
        """
        try:
            # Get project from database
            project = await self.project_service.get_project(db, project_id)
            database_sections = getattr(project, 'brief_sections', {}) or {} if project else {}
            
            # Get sections from memory
            memory_sections = conversation_memory.get_brief_building_context(project_id)
            
            # Merge (memory takes precedence for active work)
            merged_sections = {**database_sections, **memory_sections}
            
            return merged_sections
            
        except Exception as e:
            logger.error(f"Error getting merged brief sections: {str(e)}")
            return {}
    
    async def auto_save_progress(self, db: AsyncSession, project_id: str) -> bool:
        """
        Automatically save conversation progress to database periodically
        
        Args:
            db: Database session
            project_id: ID of the project
            
        Returns:
            bool: True if saved successfully
        """
        try:
            # Get conversation context
            conversation_context = conversation_memory.get_conversation_context(project_id, "project_planner")
            
            if not conversation_context:
                return False
            
            # Check if we have enough content to warrant saving
            memory_sections = conversation_memory.get_brief_building_context(project_id)
            
            if len(memory_sections) >= 2:  # Save if we have at least 2 sections
                return await self.save_partial_brief_sections(db, project_id, memory_sections)
            
            return False
            
        except Exception as e:
            logger.error(f"Error in auto-save progress: {str(e)}")
            return False
    
    def _determine_planning_status(self, brief_sections: Dict[str, Any]) -> str:
        """
        Determine planning status based on completed sections
        
        Args:
            brief_sections: Dictionary of brief sections
            
        Returns:
            str: Planning status (not_started, in_progress, completed)
        """
        if not brief_sections:
            return 'not_started'
        
        # Count completed sections (sections with substantial content)
        completed_count = 0
        total_sections = 12  # We have 12 total sections
        
        for section_data in brief_sections.values():
            if isinstance(section_data, dict) and 'content' in section_data:
                content = section_data['content']
                if content and len(str(content).strip()) >= 20:  # At least 20 characters
                    completed_count += 1
            elif section_data and len(str(section_data).strip()) >= 20:
                completed_count += 1
        
        # Determine status based on completion percentage
        completion_percentage = (completed_count / total_sections) * 100
        
        if completion_percentage >= 80:
            return 'completed'
        elif completion_percentage > 0:
            return 'in_progress'
        else:
            return 'not_started'
    
    async def clear_memory_after_save(self, project_id: str) -> None:
        """
        Clear conversation memory after successful save to database
        
        Args:
            project_id: ID of the project
        """
        try:
            conversation_memory.clear_conversation_context(project_id, "project_planner")
            logger.info(f"Cleared conversation memory for project {project_id} after save")
        except Exception as e:
            logger.error(f"Error clearing memory after save: {str(e)}")
    
    async def sync_memory_with_database(self, db: AsyncSession, project_id: str) -> bool:
        """
        Sync conversation memory with database (useful for resuming conversations)
        
        Args:
            db: Database session
            project_id: ID of the project
            
        Returns:
            bool: True if synced successfully
        """
        try:
            # Get project from database
            project = await self.project_service.get_project(db, project_id)
            if not project:
                return False
            
            # Get existing brief sections
            database_sections = getattr(project, 'brief_sections', {}) or {}
            
            if database_sections:
                # Load database sections into memory for continuation
                for section_id, section_data in database_sections.items():
                    conversation_memory.update_brief_section(project_id, section_id, section_data)
                
                logger.info(f"Synced {len(database_sections)} sections from database to memory for project {project_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error syncing memory with database: {str(e)}")
            return False


# Global instance
incremental_brief_service = IncrementalBriefService()