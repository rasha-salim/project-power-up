"""
Conversation Memory Service - Manages conversation context for agents
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class ConversationMemoryService:
    """Service for managing conversation memory and context"""
    
    def __init__(self):
        """Initialize the conversation memory service"""
        self._conversations: Dict[str, Dict[str, Any]] = {}
        self._memory_ttl = timedelta(hours=2)  # Memory expires after 2 hours
    
    def _get_conversation_key(self, project_id: str, agent_id: str) -> str:
        """Generate a unique key for the conversation"""
        return f"{project_id}:{agent_id}"
    
    def _cleanup_expired_conversations(self) -> None:
        """Clean up expired conversations"""
        current_time = datetime.now()
        expired_keys = []
        
        for key, conversation in self._conversations.items():
            if current_time - conversation['last_updated'] > self._memory_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._conversations[key]
            logger.info(f"Cleaned up expired conversation: {key}")
    
    def get_conversation_context(self, project_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get conversation context for a specific project and agent
        
        Args:
            project_id: ID of the project
            agent_id: ID of the agent
            
        Returns:
            Dict containing conversation context or None if not found
        """
        self._cleanup_expired_conversations()
        
        key = self._get_conversation_key(project_id, agent_id)
        conversation = self._conversations.get(key)
        
        if conversation:
            logger.info(f"Retrieved conversation context for {key}")
            return conversation.get('context', {})
        
        return None
    
    def update_conversation_context(self, project_id: str, agent_id: str, context: Dict[str, Any]) -> None:
        """
        Update conversation context for a specific project and agent
        
        Args:
            project_id: ID of the project
            agent_id: ID of the agent
            context: Context data to store
        """
        key = self._get_conversation_key(project_id, agent_id)
        
        if key not in self._conversations:
            self._conversations[key] = {
                'context': {},
                'created_at': datetime.now(),
                'last_updated': datetime.now()
            }
        
        # Merge new context with existing context
        existing_context = self._conversations[key]['context']
        merged_context = {**existing_context, **context}
        
        self._conversations[key]['context'] = merged_context
        self._conversations[key]['last_updated'] = datetime.now()
        
        logger.info(f"Updated conversation context for {key}")
    
    def add_message_to_context(self, project_id: str, agent_id: str, user_message: str, agent_response: str) -> None:
        """
        Add a message exchange to the conversation context
        
        Args:
            project_id: ID of the project
            agent_id: ID of the agent
            user_message: User's message
            agent_response: Agent's response
        """
        key = self._get_conversation_key(project_id, agent_id)
        
        if key not in self._conversations:
            self._conversations[key] = {
                'context': {'messages': []},
                'created_at': datetime.now(),
                'last_updated': datetime.now()
            }
        
        # Add message to conversation history
        if 'messages' not in self._conversations[key]['context']:
            self._conversations[key]['context']['messages'] = []
        
        message_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_message': user_message,
            'agent_response': agent_response
        }
        
        self._conversations[key]['context']['messages'].append(message_entry)
        
        # Keep only last 10 messages to prevent memory bloat
        if len(self._conversations[key]['context']['messages']) > 10:
            self._conversations[key]['context']['messages'] = self._conversations[key]['context']['messages'][-10:]
        
        self._conversations[key]['last_updated'] = datetime.now()
        
        logger.info(f"Added message to conversation context for {key}")
    
    def get_brief_building_context(self, project_id: str) -> Dict[str, Any]:
        """
        Get project brief building context specifically for Project Planner
        
        Args:
            project_id: ID of the project
            
        Returns:
            Dict containing brief building context
        """
        context = self.get_conversation_context(project_id, "project_planner")
        
        if context and 'brief_sections' in context:
            return context['brief_sections']
        
        return {}
    
    def update_brief_section(self, project_id: str, section_id: str, section_data: Dict[str, Any]) -> None:
        """
        Update a specific section of the project brief being built
        
        Args:
            project_id: ID of the project
            section_id: ID of the section to update
            section_data: Section data to store
        """
        key = self._get_conversation_key(project_id, "project_planner")
        
        if key not in self._conversations:
            self._conversations[key] = {
                'context': {'brief_sections': {}},
                'created_at': datetime.now(),
                'last_updated': datetime.now()
            }
        
        if 'brief_sections' not in self._conversations[key]['context']:
            self._conversations[key]['context']['brief_sections'] = {}
        
        self._conversations[key]['context']['brief_sections'][section_id] = section_data
        self._conversations[key]['last_updated'] = datetime.now()
        
        logger.info(f"Updated brief section {section_id} for project {project_id}")
    
    def merge_user_information(self, project_id: str, user_info: Dict[str, Any]) -> None:
        """
        Merge user-provided information into the conversation context
        
        Args:
            project_id: ID of the project
            user_info: User information to merge
        """
        key = self._get_conversation_key(project_id, "project_planner")
        
        if key not in self._conversations:
            self._conversations[key] = {
                'context': {'user_information': {}},
                'created_at': datetime.now(),
                'last_updated': datetime.now()
            }
        
        if 'user_information' not in self._conversations[key]['context']:
            self._conversations[key]['context']['user_information'] = {}
        
        # Merge user information
        existing_info = self._conversations[key]['context']['user_information']
        merged_info = {**existing_info, **user_info}
        
        self._conversations[key]['context']['user_information'] = merged_info
        self._conversations[key]['last_updated'] = datetime.now()
        
        logger.info(f"Merged user information for project {project_id}")
    
    def clear_conversation_context(self, project_id: str, agent_id: str) -> bool:
        """
        Clear conversation context for a specific project and agent
        
        Args:
            project_id: ID of the project
            agent_id: ID of the agent
            
        Returns:
            True if context was cleared, False if no context existed
        """
        key = self._get_conversation_key(project_id, agent_id)
        
        if key in self._conversations:
            del self._conversations[key]
            logger.info(f"Cleared conversation context for {key}")
            return True
        
        return False
    
    def get_conversation_summary(self, project_id: str, agent_id: str) -> str:
        """
        Get a summary of the conversation context
        
        Args:
            project_id: ID of the project
            agent_id: ID of the agent
            
        Returns:
            String summary of conversation context
        """
        context = self.get_conversation_context(project_id, agent_id)
        
        if not context:
            return "No conversation context available"
        
        summary_parts = []
        
        # Add brief sections summary
        if 'brief_sections' in context:
            brief_sections = context['brief_sections']
            completed_sections = len(brief_sections)
            summary_parts.append(f"Brief sections completed: {completed_sections}")
        
        # Add user information summary
        if 'user_information' in context:
            user_info = context['user_information']
            info_items = len(user_info)
            summary_parts.append(f"User information items: {info_items}")
        
        # Add message history summary
        if 'messages' in context:
            messages = context['messages']
            message_count = len(messages)
            summary_parts.append(f"Message exchanges: {message_count}")
        
        return ", ".join(summary_parts) if summary_parts else "Empty context"


# Global instance
conversation_memory = ConversationMemoryService()