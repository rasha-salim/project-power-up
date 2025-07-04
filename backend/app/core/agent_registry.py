"""
Agent Registry - Central registry for all available agents
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class AgentCapability(Enum):
    """Available agent capabilities"""
    TECHNICAL_ANALYSIS = "technical_analysis"
    CODE_REVIEW = "code_review"
    ARCHITECTURE_DESIGN = "architecture_design"
    SECURITY_ANALYSIS = "security_analysis"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    GENERAL_ASSISTANCE = "general_assistance"
    PROJECT_PLANNING = "project_planning"
    DOCUMENT_CREATION = "document_creation"

@dataclass
class AgentInfo:
    """Information about an agent"""
    id: str
    name: str
    mention_id: str  # Used for @mentions (e.g., @technical)
    role: str
    description: str
    capabilities: List[AgentCapability]
    example_prompts: List[str]
    avatar: Optional[str] = None  # URL or emoji
    color: Optional[str] = None  # For UI theming

class AgentRegistry:
    """Central registry for all available agents"""
    
    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        self._mention_map: Dict[str, str] = {}  # mention_id -> agent_id
        self._initialize_default_agents()
    
    def _initialize_default_agents(self):
        """Initialize the default set of agents"""
        
        # Technical Analyst Agent
        technical_agent = AgentInfo(
            id="technical_analyst",
            name="Technical Analyst",
            mention_id="technical",
            role="Senior Technical Analyst",
            description="Analyzes project architecture, technology stack, and provides technical insights. Expert in code structure, design patterns, and best practices.",
            capabilities=[
                AgentCapability.TECHNICAL_ANALYSIS,
                AgentCapability.CODE_REVIEW,
                AgentCapability.ARCHITECTURE_DESIGN
            ],
            example_prompts=[
                "@technical analyze the project architecture",
                "@technical what technologies are being used?",
                "@technical review the code structure",
                "@technical suggest improvements to the architecture"
            ],
            avatar="[TECH]",
            color="#3B82F6"  # Blue
        )
        self.register_agent(technical_agent)
        
        # Project Assistant Agent (General)
        assistant_agent = AgentInfo(
            id="project_assistant",
            name="Project Assistant",
            mention_id="assistant",
            role="Project Assistant",
            description="General project assistant that can help with various tasks, answer questions about the project, and route to specialized agents when needed.",
            capabilities=[
                AgentCapability.GENERAL_ASSISTANCE,
                AgentCapability.DOCUMENTATION
            ],
            example_prompts=[
                "What is this project about?",
                "Help me understand the main features",
                "@assistant summarize the project",
                "Which agent should I ask about security?"
            ],
            avatar="[ASSIST]",
            color="#10B981"  # Green
        )
        self.register_agent(assistant_agent)
        
        # Security Analyst Agent (Fully Implemented)
        security_agent = AgentInfo(
            id="security_analyst",
            name="Security Analyst",
            mention_id="security",
            role="Security Expert",
            description="Analyzes projects for security vulnerabilities, suggests security best practices, reviews authentication/authorization implementations, and provides comprehensive security assessments based on project context and analysis data.",
            capabilities=[
                AgentCapability.SECURITY_ANALYSIS
            ],
            example_prompts=[
                "@security analyze the project security architecture",
                "@security check for vulnerabilities in the tech stack",
                "@security review authentication and authorization systems",
                "@security assess data protection and privacy compliance",
                "@security evaluate API security measures"
            ],
            avatar="[LOCK]",
            color="#EF4444"  # Red
        )
        self.register_agent(security_agent)
        
        performance_agent = AgentInfo(
            id="performance_analyst",
            name="Performance Analyst",
            mention_id="performance",
            role="Performance Expert",
            description="[Coming Soon] Analyzes code performance, identifies bottlenecks, and suggests optimizations for better efficiency.",
            capabilities=[
                AgentCapability.PERFORMANCE_ANALYSIS
            ],
            example_prompts=[
                "@performance analyze bottlenecks",
                "@performance suggest optimizations",
                "@performance review database queries"
            ],
            avatar="[PERF]",
            color="#F59E0B"  # Amber
        )
        self.register_agent(performance_agent)
        
        # Project Planner Agent
        project_planner_agent = AgentInfo(
            id="project_planner",
            name="Project Planner",
            mention_id="planner",
            role="Project Planning Expert",
            description="Helps users create comprehensive project briefs and documentation when they don't have existing documents. Guides users through structured planning sessions to build proper project specifications, requirements, and planning documents.",
            capabilities=[
                AgentCapability.PROJECT_PLANNING,
                AgentCapability.DOCUMENT_CREATION,
                AgentCapability.GENERAL_ASSISTANCE
            ],
            example_prompts=[
                "@planner help me create a project brief",
                "@planner I need to plan my project requirements",
                "@planner guide me through project documentation",
                "@planner what should I include in my project scope?",
                "@planner help me define project goals and objectives"
            ],
            avatar="📋",
            color="#8B5CF6"  # Purple
        )
        self.register_agent(project_planner_agent)
    
    def register_agent(self, agent: AgentInfo):
        """Register a new agent"""
        self._agents[agent.id] = agent
        self._mention_map[agent.mention_id] = agent.id
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent by ID"""
        return self._agents.get(agent_id)
    
    def get_agent_by_mention(self, mention_id: str) -> Optional[AgentInfo]:
        """Get agent by mention ID (e.g., 'technical' for @technical)"""
        agent_id = self._mention_map.get(mention_id)
        return self._agents.get(agent_id) if agent_id else None
    
    def get_all_agents(self) -> List[AgentInfo]:
        """Get all registered agents"""
        return list(self._agents.values())
    
    def get_available_agents(self) -> List[AgentInfo]:
        """Get only implemented agents (not coming soon)"""
        return [
            agent for agent in self._agents.values()
            if "[Coming Soon]" not in agent.description
        ]
    
    def search_agents(self, query: str) -> List[AgentInfo]:
        """Search agents by name, mention_id, or capabilities"""
        query_lower = query.lower()
        results = []
        
        for agent in self._agents.values():
            if (query_lower in agent.name.lower() or
                query_lower in agent.mention_id.lower() or
                query_lower in agent.description.lower() or
                any(query_lower in cap.value for cap in agent.capabilities)):
                results.append(agent)
        
        return results
    
    def get_agent_for_capability(self, capability: AgentCapability) -> Optional[AgentInfo]:
        """Get the best agent for a specific capability"""
        for agent in self._agents.values():
            if capability in agent.capabilities and "[Coming Soon]" not in agent.description:
                return agent
        return None

# Global registry instance
agent_registry = AgentRegistry()
