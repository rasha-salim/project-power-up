import os
import yaml
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Loader for YAML configuration files"""
    
    def __init__(self, config_dir: str = None):
        """
        Initialize the configuration loader
        
        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = config_dir or os.path.dirname(os.path.abspath(__file__))
        self.configs = {}
    
    def load_config(self, config_name: str) -> Dict[str, Any]:
        """
        Load a configuration file
        
        Args:
            config_name: Name of the configuration file (without extension)
            
        Returns:
            Dict[str, Any]: Configuration data
        """
        if config_name in self.configs:
            return self.configs[config_name]
        
        config_path = os.path.join(self.config_dir, f"{config_name}.yaml")
        
        try:
            with open(config_path, 'r') as file:
                # Load the YAML content
                yaml_content = file.read()
                
                # Replace environment variables
                for key, value in os.environ.items():
                    placeholder = f"${{{key}}}"
                    if placeholder in yaml_content:
                        yaml_content = yaml_content.replace(placeholder, value)
                
                # Parse the YAML content
                config = yaml.safe_load(yaml_content)
                self.configs[config_name] = config
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {str(e)}")
            raise
    
    def get_agent_config(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific agent
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            Optional[Dict[str, Any]]: Agent configuration if found, None otherwise
        """
        agents_config = self.load_config("agents")
        return agents_config.get("agents", {}).get(agent_id)
    
    def get_task_config(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific task
        
        Args:
            task_id: ID of the task
            
        Returns:
            Optional[Dict[str, Any]]: Task configuration if found, None otherwise
        """
        agents_config = self.load_config("agents")
        return agents_config.get("tasks", {}).get(task_id)
    
    def get_crew_config(self, crew_id: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific crew
        
        Args:
            crew_id: ID of the crew
            
        Returns:
            Optional[Dict[str, Any]]: Crew configuration if found, None otherwise
        """
        agents_config = self.load_config("agents")
        return agents_config.get("crews", {}).get(crew_id)
    
    def get_all_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all agent configurations
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of agent configurations
        """
        agents_config = self.load_config("agents")
        return agents_config.get("agents", {})
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all task configurations
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of task configurations
        """
        agents_config = self.load_config("agents")
        return agents_config.get("tasks", {})
    
    def get_all_crews(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all crew configurations
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of crew configurations
        """
        agents_config = self.load_config("agents")
        return agents_config.get("crews", {})
