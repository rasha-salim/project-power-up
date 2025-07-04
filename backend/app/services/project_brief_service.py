"""
Project Brief Service - Manages project brief templates and document generation
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class ProjectBriefSection:
    """Represents a section of the project brief"""
    
    def __init__(self, id: str, title: str, description: str, required_fields: List[str], 
                 example: str = "", questions: List[str] = None):
        self.id = id
        self.title = title
        self.description = description
        self.required_fields = required_fields
        self.example = example
        self.questions = questions or []


class ProjectBriefService:
    """Service for managing project brief templates and generation"""
    
    def __init__(self):
        """Initialize the project brief service"""
        self.sections = self._initialize_sections()
    
    def _initialize_sections(self) -> List[ProjectBriefSection]:
        """Initialize the 12-section project brief template"""
        return [
            ProjectBriefSection(
                id="overview",
                title="Project Overview",
                description="Basic project identification and metadata",
                required_fields=["project_name", "client", "project_sponsor", "project_lead", "date_created"],
                example="Project Name: SmartAssist - Internal LLM Solution\nClient: Internal (TechNova Startup)\nProject Sponsor: Sarah Chen, CEO",
                questions=[
                    "What is the name of your project?",
                    "Who is the client or intended user of this project?",
                    "Who is sponsoring this project (executive/business sponsor)?",
                    "Who will be the project lead/manager?",
                    "What is your target start date?"
                ]
            ),
            ProjectBriefSection(
                id="background",
                title="Project Background",
                description="Context, current situation, and drivers for the project",
                required_fields=["current_situation", "growth_drivers", "context"],
                example="TechNova is a growing startup focused on developing customized software solutions. As we scale from 15 to 30+ employees, we've identified inefficiencies in knowledge management...",
                questions=[
                    "What is the current situation that led to this project?",
                    "What business or technical challenges are you facing?",
                    "How has your organization/team grown or changed recently?",
                    "What external factors are driving this project need?"
                ]
            ),
            ProjectBriefSection(
                id="business_case",
                title="Business Case",
                description="Business problems, objectives, and expected value",
                required_fields=["business_problem", "business_objectives", "expected_value"],
                example="Business Problem: Knowledge silos forming, time lost searching for information\nObjectives: Reduce search time by 50%, improve employee satisfaction",
                questions=[
                    "What specific business problems does this project solve?",
                    "What are the main business objectives?",
                    "What value do you expect this project to deliver?",
                    "How will success be measured in business terms?"
                ]
            ),
            ProjectBriefSection(
                id="goals_success",
                title="Project Goals & Success Criteria", 
                description="Primary goals, specific objectives, and measurable success metrics",
                required_fields=["primary_goal", "specific_objectives", "success_metrics"],
                example="Primary Goal: Create a customized LLM solution for internal knowledge management\nMetrics: 50% reduction in search time, 80% accuracy, 90% adoption",
                questions=[
                    "What is the primary goal of this project?",
                    "What specific objectives must be achieved?",
                    "How will you measure success?",
                    "What metrics or KPIs will you track?"
                ]
            ),
            ProjectBriefSection(
                id="target_audience",
                title="Target Audience/Users",
                description="Primary and secondary users, key user needs",
                required_fields=["primary_users", "secondary_users", "user_needs"],
                example="Primary: Technical team (developers, designers, project managers)\nSecondary: Non-technical staff (sales, operations, HR)",
                questions=[
                    "Who are the primary users of this project?",
                    "Are there secondary users or stakeholders?",
                    "What are the key needs of these users?",
                    "What challenges do these users currently face?"
                ]
            ),
            ProjectBriefSection(
                id="scope",
                title="High-Level Scope",
                description="What is included and excluded from the project",
                required_fields=["in_scope", "out_of_scope"],
                example="In Scope: LLM integration, Slack/web interface, analytics dashboard\nOut of Scope: Client-facing assistant, mobile app, voice interface",
                questions=[
                    "What features and capabilities are included in this project?",
                    "What is explicitly excluded from this project scope?",
                    "Are there any future phases or features to consider later?",
                    "What are the boundaries of this project?"
                ]
            ),
            ProjectBriefSection(
                id="requirements",
                title="High-Level Requirements",
                description="Functional requirements, technical requirements, and constraints",
                required_fields=["functional_requirements", "technical_requirements", "constraints"],
                example="Functional: Natural language query, document search\nTechnical: API integrations, vector database\nConstraints: $25K budget, 3-month timeline",
                questions=[
                    "What are the main functional requirements?",
                    "What technical requirements or specifications are needed?",
                    "What constraints must be considered (budget, time, resources)?",
                    "Are there any compliance or regulatory requirements?"
                ]
            ),
            ProjectBriefSection(
                id="timeline",
                title="Preliminary Timeline",
                description="Start and end dates, key milestones",
                required_fields=["start_date", "end_date", "key_milestones"],
                example="Start: May 15, 2025\nEnd: August 15, 2025\nMilestones: Architecture selection (May 30), Alpha version (July 10)",
                questions=[
                    "When do you need to start this project?",
                    "What is your target completion date?",
                    "Are there any critical milestones or deadlines?",
                    "Are there external dependencies that affect timing?"
                ]
            ),
            ProjectBriefSection(
                id="budget",
                title="Preliminary Budget",
                description="Budget range, breakdown, and ongoing costs",
                required_fields=["budget_range", "budget_breakdown", "ongoing_costs"],
                example="Range: $20,000-$25,000\nBreakdown: Development $12K, API costs $7.5K, Training $2.5K\nOngoing: ~$650/month",
                questions=[
                    "What is your overall budget range for this project?",
                    "How would you like to break down the budget (development, tools, etc.)?",
                    "Are there ongoing operational costs to consider?",
                    "What is the source of funding for this project?"
                ]
            ),
            ProjectBriefSection(
                id="stakeholders",
                title="Key Stakeholders",
                description="Important stakeholders and their roles",
                required_fields=["stakeholders_list", "roles_responsibilities"],
                example="Sarah Chen (CEO) - Executive Sponsor\nAlex Rivera (CTO) - Technical Lead\nMaya Patel - Subject Matter Expert",
                questions=[
                    "Who are the key stakeholders for this project?",
                    "What are their roles and responsibilities?",
                    "Who has decision-making authority?",
                    "Who should be kept informed of progress?"
                ]
            ),
            ProjectBriefSection(
                id="resources",
                title="Initial Resources",
                description="Team allocation and resource requirements",
                required_fields=["team_allocation", "skills_needed", "resource_availability"],
                example="1 Lead Developer (50%), 2 Backend Engineers (25% each), 1 Frontend Developer (25%)",
                questions=[
                    "What team members will work on this project?",
                    "What percentage of their time will be dedicated?",
                    "What skills or expertise are needed?",
                    "Are there any resource constraints or availability issues?"
                ]
            ),
            ProjectBriefSection(
                id="next_steps",
                title="Next Steps",
                description="Immediate actions and next phases",
                required_fields=["immediate_actions", "next_phases"],
                example="Finalize requirements document, Complete technology selection, Schedule kickoff meeting",
                questions=[
                    "What are the immediate next steps after this brief?",
                    "What decisions need to be made before starting?",
                    "Who needs to approve this project brief?",
                    "What planning activities come next?"
                ]
            )
        ]
    
    def get_section(self, section_id: str) -> Optional[ProjectBriefSection]:
        """Get a specific section by ID"""
        for section in self.sections:
            if section.id == section_id:
                return section
        return None
    
    def get_all_sections(self) -> List[ProjectBriefSection]:
        """Get all sections"""
        return self.sections
    
    def get_section_questions(self, section_id: str) -> List[str]:
        """Get questions for a specific section"""
        section = self.get_section(section_id)
        return section.questions if section else []
    
    def get_completion_status(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get completion status for all sections"""
        brief_data = project_data.get('brief_sections', {})
        completion_status = {}
        overall_progress = 0
        
        for section in self.sections:
            section_data = brief_data.get(section.id, {})
            completed_fields = 0
            total_fields = len(section.required_fields)
            
            for field in section.required_fields:
                if section_data.get(field) and str(section_data[field]).strip():
                    completed_fields += 1
            
            completion_percentage = (completed_fields / total_fields) * 100 if total_fields > 0 else 0
            is_complete = completion_percentage >= 80  # Consider 80%+ as complete
            
            completion_status[section.id] = {
                "title": section.title,
                "completed_fields": completed_fields,
                "total_fields": total_fields,
                "completion_percentage": completion_percentage,
                "is_complete": is_complete,
                "missing_fields": [field for field in section.required_fields 
                                if not section_data.get(field) or not str(section_data[field]).strip()]
            }
            
            overall_progress += completion_percentage
        
        overall_progress = overall_progress / len(self.sections) if self.sections else 0
        
        return {
            "sections": completion_status,
            "overall_progress": overall_progress,
            "completed_sections": sum(1 for status in completion_status.values() if status["is_complete"]),
            "total_sections": len(self.sections)
        }
    
    def parse_formatted_brief(self, formatted_text: str) -> Dict[str, Any]:
        """
        Parse a formatted project brief text into structured data
        
        Args:
            formatted_text: The formatted brief text from Project Planner
            
        Returns:
            Dict containing parsed section data
        """
        import re
        
        brief_data = {}
        current_section = None
        current_content = []
        
        lines = formatted_text.split('\n')
        
        # Section mapping from headers to section IDs
        section_mapping = {
            'PROJECT OVERVIEW': 'project_overview',
            'PROJECT BACKGROUND': 'project_background', 
            'BUSINESS CASE': 'business_case',
            'GOALS & SUCCESS CRITERIA': 'goals_success_criteria',
            'TARGET AUDIENCE/USERS': 'target_audience',
            'HIGH-LEVEL SCOPE': 'high_level_scope',
            'HIGH-LEVEL REQUIREMENTS': 'high_level_requirements',
            'PRELIMINARY TIMELINE': 'preliminary_timeline',
            'PRELIMINARY BUDGET': 'preliminary_budget',
            'KEY STAKEHOLDERS': 'key_stakeholders',
            'INITIAL RESOURCES': 'initial_resources',
            'NEXT STEPS': 'next_steps'
        }
        
        for line in lines:
            line = line.strip()
            
            # Check if this is a section header
            if line in section_mapping:
                # Save previous section if any
                if current_section and current_content:
                    brief_data[current_section] = {
                        'content': '\n'.join(current_content).strip(),
                        'title': [k for k, v in section_mapping.items() if v == current_section][0]
                    }
                
                # Start new section
                current_section = section_mapping[line]
                current_content = []
            elif current_section and line:  # Add content to current section
                current_content.append(line)
        
        # Save last section
        if current_section and current_content:
            brief_data[current_section] = {
                'content': '\n'.join(current_content).strip(),
                'title': [k for k, v in section_mapping.items() if v == current_section][0]
            }
        
        return brief_data
    
    async def save_brief_to_project(self, db, project_id: str, formatted_brief: str = "", custom_brief_data: Dict[str, Any] = None) -> bool:
        """
        Save a formatted project brief to the database
        
        Args:
            db: Database session
            project_id: ID of the project
            formatted_brief: Formatted brief text to parse and save (optional)
            custom_brief_data: Pre-parsed brief data to save directly (optional)
            
        Returns:
            bool: True if saved successfully
        """
        try:
            from app.services.project_service import ProjectService
            
            # Use custom brief data if provided, otherwise parse formatted brief
            if custom_brief_data:
                brief_data = custom_brief_data
            elif formatted_brief:
                brief_data = self.parse_formatted_brief(formatted_brief)
            else:
                return False
            
            if not brief_data:
                return False
            
            # Get the project
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            
            if not project:
                return False
            
            # Update project with brief data
            update_data = {
                'brief_sections': brief_data,
                'planning_status': 'completed'
            }
            
            await project_service.update_project(db, project_id, update_data)
            return True
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving project brief: {str(e)}")
            return False
    
    def generate_markdown_brief(self, project_data: Dict[str, Any]) -> str:
        """Generate a markdown project brief from project data"""
        brief_data = project_data.get('brief_sections', {})
        project_name = project_data.get('name', 'Untitled Project')
        
        # Start with the header
        markdown = f"# Project Brief: {project_name}\n\n"
        
        # Add each section
        for i, section in enumerate(self.sections, 1):
            section_data = brief_data.get(section.id, {})
            markdown += f"## {i}. {section.title}\n\n"
            
            if section_data:
                # Add section content based on the section type
                if section.id == "overview":
                    markdown += self._format_overview_section(section_data)
                elif section.id == "background":
                    markdown += self._format_background_section(section_data)
                elif section.id == "business_case":
                    markdown += self._format_business_case_section(section_data)
                elif section.id == "goals_success":
                    markdown += self._format_goals_section(section_data)
                elif section.id == "target_audience":
                    markdown += self._format_audience_section(section_data)
                elif section.id == "scope":
                    markdown += self._format_scope_section(section_data)
                elif section.id == "requirements":
                    markdown += self._format_requirements_section(section_data)
                elif section.id == "timeline":
                    markdown += self._format_timeline_section(section_data)
                elif section.id == "budget":
                    markdown += self._format_budget_section(section_data)
                elif section.id == "stakeholders":
                    markdown += self._format_stakeholders_section(section_data)
                elif section.id == "resources":
                    markdown += self._format_resources_section(section_data)
                elif section.id == "next_steps":
                    markdown += self._format_next_steps_section(section_data)
                else:
                    # Generic formatting for any unhandled sections
                    for field, value in section_data.items():
                        if value and str(value).strip():
                            markdown += f"**{field.replace('_', ' ').title()}**: {value}\n\n"
            else:
                markdown += f"*{section.description}*\n\n"
                markdown += "*This section needs to be completed.*\n\n"
            
            markdown += "\n"
        
        # Add generation timestamp
        markdown += f"\n---\n\n*Project brief generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n"
        
        return markdown
    
    def _format_overview_section(self, data: Dict[str, Any]) -> str:
        """Format the overview section"""
        content = ""
        if data.get('project_name'):
            content += f"* **Project Name**: {data['project_name']}\n"
        if data.get('client'):
            content += f"* **Client**: {data['client']}\n"
        if data.get('project_sponsor'):
            content += f"* **Project Sponsor**: {data['project_sponsor']}\n"
        if data.get('project_lead'):
            content += f"* **Project Lead**: {data['project_lead']}\n"
        if data.get('date_created'):
            content += f"* **Date Created**: {data['date_created']}\n"
        if data.get('version'):
            content += f"* **Version**: {data['version']}\n"
        return content + "\n"
    
    def _format_background_section(self, data: Dict[str, Any]) -> str:
        """Format the background section"""
        content = ""
        if data.get('current_situation'):
            content += f"{data['current_situation']}\n\n"
        if data.get('growth_drivers'):
            content += f"**Growth Drivers**: {data['growth_drivers']}\n\n"
        if data.get('context'):
            content += f"**Additional Context**: {data['context']}\n\n"
        return content
    
    def _format_business_case_section(self, data: Dict[str, Any]) -> str:
        """Format the business case section"""
        content = ""
        if data.get('business_problem'):
            content += f"### Business Problem\n\n{data['business_problem']}\n\n"
        if data.get('business_objectives'):
            content += f"### Business Objectives\n\n{data['business_objectives']}\n\n"
        if data.get('expected_value'):
            content += f"### Expected Business Value\n\n{data['expected_value']}\n\n"
        return content
    
    def _format_goals_section(self, data: Dict[str, Any]) -> str:
        """Format the goals and success criteria section"""
        content = ""
        if data.get('primary_goal'):
            content += f"### Primary Goal\n\n{data['primary_goal']}\n\n"
        if data.get('specific_objectives'):
            content += f"### Specific Objectives\n\n{data['specific_objectives']}\n\n"
        if data.get('success_metrics'):
            content += f"### Success Metrics\n\n{data['success_metrics']}\n\n"
        return content
    
    def _format_audience_section(self, data: Dict[str, Any]) -> str:
        """Format the target audience section"""
        content = ""
        if data.get('primary_users'):
            content += f"* **Primary Users**: {data['primary_users']}\n"
        if data.get('secondary_users'):
            content += f"* **Secondary Users**: {data['secondary_users']}\n"
        if data.get('user_needs'):
            content += f"* **Key User Needs**: {data['user_needs']}\n"
        return content + "\n"
    
    def _format_scope_section(self, data: Dict[str, Any]) -> str:
        """Format the scope section"""
        content = ""
        if data.get('in_scope'):
            content += f"### In Scope\n\n{data['in_scope']}\n\n"
        if data.get('out_of_scope'):
            content += f"### Out of Scope\n\n{data['out_of_scope']}\n\n"
        return content
    
    def _format_requirements_section(self, data: Dict[str, Any]) -> str:
        """Format the requirements section"""
        content = ""
        if data.get('functional_requirements'):
            content += f"### Functional Requirements\n\n{data['functional_requirements']}\n\n"
        if data.get('technical_requirements'):
            content += f"### Technical Requirements\n\n{data['technical_requirements']}\n\n"
        if data.get('constraints'):
            content += f"### Constraints\n\n{data['constraints']}\n\n"
        return content
    
    def _format_timeline_section(self, data: Dict[str, Any]) -> str:
        """Format the timeline section"""
        content = ""
        if data.get('start_date'):
            content += f"* **Estimated Start Date**: {data['start_date']}\n"
        if data.get('end_date'):
            content += f"* **Estimated Completion Date**: {data['end_date']}\n"
        if data.get('key_milestones'):
            content += f"* **Key Milestones**: {data['key_milestones']}\n"
        return content + "\n"
    
    def _format_budget_section(self, data: Dict[str, Any]) -> str:
        """Format the budget section"""
        content = ""
        if data.get('budget_range'):
            content += f"* **Estimated Budget Range**: {data['budget_range']}\n"
        if data.get('budget_breakdown'):
            content += f"* **Budget Breakdown**: {data['budget_breakdown']}\n"
        if data.get('ongoing_costs'):
            content += f"* **Ongoing Costs**: {data['ongoing_costs']}\n"
        return content + "\n"
    
    def _format_stakeholders_section(self, data: Dict[str, Any]) -> str:
        """Format the stakeholders section"""
        content = ""
        if data.get('stakeholders_list'):
            content += f"{data['stakeholders_list']}\n\n"
        if data.get('roles_responsibilities'):
            content += f"**Roles & Responsibilities**: {data['roles_responsibilities']}\n\n"
        return content
    
    def _format_resources_section(self, data: Dict[str, Any]) -> str:
        """Format the resources section"""
        content = ""
        if data.get('team_allocation'):
            content += f"### Team Resources\n\n{data['team_allocation']}\n\n"
        if data.get('skills_needed'):
            content += f"### Skills Needed\n\n{data['skills_needed']}\n\n"
        if data.get('resource_availability'):
            content += f"### Resource Availability\n\n{data['resource_availability']}\n\n"
        return content
    
    def _format_next_steps_section(self, data: Dict[str, Any]) -> str:
        """Format the next steps section"""
        content = ""
        if data.get('immediate_actions'):
            content += f"{data['immediate_actions']}\n\n"
        if data.get('next_phases'):
            content += f"**Next Phases**: {data['next_phases']}\n\n"
        return content
    
    async def update_project_brief_data(self, db: AsyncSession, project_id: str, 
                                      section_id: str, section_data: Dict[str, Any]) -> bool:
        """Update project brief section data"""
        try:
            project_service = ProjectService()
            project = await project_service.get_project(db, project_id)
            
            if not project:
                logger.error(f"Project {project_id} not found")
                return False
            
            # Get existing brief data or initialize
            brief_sections = project.brief_sections or {}
            
            # Update the specific section
            brief_sections[section_id] = section_data
            
            # Update project planning status
            completion_status = self.get_completion_status({
                'brief_sections': brief_sections,
                'name': project.name
            })
            
            overall_progress = completion_status['overall_progress']
            if overall_progress >= 90:
                planning_status = 'completed'
            elif overall_progress > 0:
                planning_status = 'in_progress'
            else:
                planning_status = 'not_started'
            
            # Update the project
            update_data = {
                'brief_sections': brief_sections,
                'planning_status': planning_status
            }
            
            await project_service.update_project(db, project_id, update_data)
            logger.info(f"Updated project brief section {section_id} for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating project brief data: {str(e)}")
            return False