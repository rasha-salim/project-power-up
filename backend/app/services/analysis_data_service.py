"""
Analysis data service for parsing and structuring agent outputs
"""
import json
import logging
import re
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from app.models.analysis import (
    ProjectAnalysis, TechnicalAnalysis, RiskAssessment, ProjectPlan,
    TechStackCategory, Risk, ResourceRequirements, ProjectPhase, 
    Milestone, EffortDistribution, RiskLevel
)
from app.services.analysis_helper import AnalysisDataHelper

logger = logging.getLogger(__name__)


class AnalysisDataService:
    """Service for parsing and structuring analysis data"""
    
    def __init__(self):
        """Initialize the analysis data service"""
        self.analysis_helper = AnalysisDataHelper()
    
    def parse_agent_output_to_pydantic(
        self, 
        raw_output: str, 
        analysis_id: str, 
        project_id: str
    ) -> ProjectAnalysis:
        """
        Parse raw agent output into structured Pydantic model
        
        Args:
            raw_output: Raw text output from agent
            analysis_id: ID of the analysis
            project_id: ID of the project
            
        Returns:
            ProjectAnalysis: Structured analysis data
        """
        try:
            logger.info(f"Parsing agent output for analysis {analysis_id}")
            
            # Try to parse as JSON first
            data = self._parse_json_output(raw_output)
            
            # Extract and create technical analysis
            technical_analysis = self._create_technical_analysis(data)
            
            # Extract and create risk assessment
            risk_assessment = self._create_risk_assessment(data)
            
            # Extract and create project plan
            project_plan = self._create_project_plan(data)
            
            # Extract recommendations
            recommendations = data.get('recommendations', []) if isinstance(data, dict) else []
            
            # Create the complete ProjectAnalysis
            project_analysis = ProjectAnalysis(
                analysis_id=analysis_id,
                project_id=project_id,
                version=1,
                technical_analysis=technical_analysis,
                risk_assessment=risk_assessment,
                project_plan=project_plan,
                recommendations=recommendations,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            logger.info(f"Successfully parsed agent output into Pydantic model for analysis {analysis_id}")
            return project_analysis
            
        except Exception as e:
            logger.error(f"Error parsing agent output: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def _parse_json_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse JSON output with fallback to text extraction"""
        try:
            # Try direct JSON parsing
            if isinstance(raw_output, dict):
                data = raw_output
            else:
                data = json.loads(raw_output)
                
            logger.info(f"Successfully parsed JSON, keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            
            # Check if the data has a nested 'technical_analysis' structure
            if isinstance(data, dict) and 'technical_analysis' in data:
                # The agent output has everything nested under 'technical_analysis'
                nested_data = data['technical_analysis']
                if isinstance(nested_data, dict):
                    # Use the nested data as the main data source
                    data = nested_data
                    logger.info(f"Using nested technical_analysis data, keys: {list(data.keys())}")
            
            return data
            
        except json.JSONDecodeError:
            # If not valid JSON, use regex to extract structured data
            logger.warning(f"Agent output is not valid JSON, using fallback parsing")
            return self._extract_structured_data_from_text(raw_output)
    
    def _create_technical_analysis(self, data: Dict[str, Any]) -> TechnicalAnalysis:
        """Create TechnicalAnalysis from parsed data"""
        # Extract technical analysis data
        tech_data = data.get('technical_analysis', {}) if isinstance(data, dict) else {}
        
        # If tech_data is still empty, check if the data itself contains the technical fields
        if not tech_data and isinstance(data, dict):
            # Check if data itself contains technical analysis fields
            if any(key in data for key in ['architecture', 'tech_stack', 'complexity_score']):
                tech_data = data
                logger.info("Using root data as technical analysis data")
        
        # Create TechStackCategory
        tech_stack = TechStackCategory(
            frontend=tech_data.get('tech_stack', {}).get('frontend', []),
            backend=tech_data.get('tech_stack', {}).get('backend', []),
            infrastructure=tech_data.get('tech_stack', {}).get('infrastructure', []),
            tools=tech_data.get('tech_stack', {}).get('tools', [])
        )
        
        # Create TechnicalAnalysis
        return TechnicalAnalysis(
            architecture=tech_data.get('architecture', 'Not specified'),
            tech_stack=tech_stack,
            complexity_score=tech_data.get('complexity_score', 5.0),
            maintainability_score=tech_data.get('maintainability_score', 5.0),
            scalability_score=tech_data.get('scalability_score', 5.0),
            performance_score=tech_data.get('performance_score', 5.0),
            security_score=tech_data.get('security_score', 5.0)
        )
    
    def _create_risk_assessment(self, data: Dict[str, Any]) -> RiskAssessment:
        """Create RiskAssessment from parsed data"""
        # Extract risk assessment data
        risk_data = data.get('risk_assessment', {}) if isinstance(data, dict) else {}
        
        # Create Risk objects
        risks = []
        for risk_item in risk_data.get('key_risks', []):
            if isinstance(risk_item, dict):
                # Try to parse risk level
                try:
                    risk_level = RiskLevel(risk_item.get('level', 'Medium'))
                except ValueError:
                    risk_level = RiskLevel.MEDIUM
                
                risks.append(Risk(
                    name=risk_item.get('name', 'Unknown Risk'),
                    level=risk_level,
                    impact=risk_item.get('impact', 5),
                    probability=risk_item.get('probability', 5),
                    description=risk_item.get('description')
                ))
        
        # Create RiskAssessment
        return RiskAssessment(
            key_risks=risks,
            overall_risk_score=risk_data.get('overall_risk_score', 5.0),
            mitigation_strategies=risk_data.get('mitigation_strategies', [])
        )
    
    def _create_project_plan(self, data: Dict[str, Any]) -> ProjectPlan:
        """Create ProjectPlan from parsed data"""
        # Extract project plan data
        plan_data = data.get('project_plan', {}) if isinstance(data, dict) else {}
        
        # Create ProjectPhase objects
        phases = []
        for phase_item in plan_data.get('phases', []):
            if isinstance(phase_item, dict):
                phases.append(ProjectPhase(
                    name=phase_item.get('name', 'Unnamed Phase'),
                    duration=phase_item.get('duration', 4),
                    progress=phase_item.get('progress', 0),
                    description=phase_item.get('description')
                ))
        
        # Create Milestone objects
        milestones = []
        for milestone_item in plan_data.get('milestones', []):
            if isinstance(milestone_item, dict):
                milestones.append(Milestone(
                    name=milestone_item.get('name', 'Unnamed Milestone'),
                    date=milestone_item.get('date', datetime.now().isoformat()),
                    status=milestone_item.get('status', 'upcoming'),
                    description=milestone_item.get('description')
                ))
        
        # Create ResourceRequirements
        resource_data = plan_data.get('resource_requirements', {})
        resources = ResourceRequirements(
            developers=resource_data.get('developers', 0),
            designers=resource_data.get('designers', 0),
            qa=resource_data.get('qa', 0),
            devops=resource_data.get('devops', 0),
            pm=resource_data.get('pm', 0),
            other=resource_data.get('other', {})
        )
        
        # Create EffortDistribution objects
        effort_distribution = []
        for effort_item in plan_data.get('effort_distribution', []):
            if isinstance(effort_item, dict):
                effort_distribution.append(EffortDistribution(
                    component=effort_item.get('component', 'Unknown'),
                    effort=effort_item.get('effort', 0)
                ))
        
        # Create ProjectPlan
        return ProjectPlan(
            timeline=plan_data.get('timeline', 'Not specified'),
            phases=phases,
            milestones=milestones,
            resource_requirements=resources,
            estimated_cost=plan_data.get('estimated_cost', 0.0),
            effort_distribution=effort_distribution
        )
    
    def _extract_structured_data_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract structured data from unstructured text using regex patterns
        This is a fallback method when JSON parsing fails
        
        Args:
            text: Raw text from agent output
            
        Returns:
            Dict[str, Any]: Structured data extracted from text
        """
        # Initialize the structure
        data = {
            'technical_analysis': {
                'architecture': '',
                'tech_stack': {
                    'frontend': [],
                    'backend': [],
                    'infrastructure': [],
                    'tools': []
                },
                'complexity_score': 5.0,
                'maintainability_score': 5.0,
                'scalability_score': 5.0,
                'performance_score': 5.0,
                'security_score': 5.0
            },
            'risk_assessment': {
                'key_risks': [],
                'overall_risk_score': 5.0,
                'mitigation_strategies': []
            },
            'project_plan': {
                'timeline': 'Not specified',
                'phases': [],
                'milestones': [],
                'resource_requirements': {
                    'developers': 0,
                    'designers': 0,
                    'qa': 0,
                    'devops': 0,
                    'pm': 0
                },
                'estimated_cost': 0.0,
                'effort_distribution': []
            },
            'recommendations': []
        }
        
        # Extract architecture
        arch_match = re.search(r'Architecture[:\s]+(.*?)(?:\n|$)', text, re.IGNORECASE)
        if arch_match:
            data['technical_analysis']['architecture'] = arch_match.group(1).strip()
        
        # Extract frontend technologies
        frontend_match = re.search(r'Frontend[:\s]+(.*?)(?:\n|$)', text, re.IGNORECASE)
        if frontend_match:
            frontend_techs = re.findall(r'\b([\w\+\#\.]+)\b', frontend_match.group(1))
            data['technical_analysis']['tech_stack']['frontend'] = frontend_techs
        
        # Backend
        backend_match = re.search(r'Backend[:\s]+(.*?)(?:\n|$)', text, re.IGNORECASE)
        if backend_match:
            backend_techs = re.findall(r'\b([\w\+\#\.]+)\b', backend_match.group(1))
            data['technical_analysis']['tech_stack']['backend'] = backend_techs
        
        # Extract recommendations
        recommendations = re.findall(r'(?:Recommendation|Recommend)[:\s]+(.*?)(?:\n|$)', text, re.IGNORECASE)
        if recommendations:
            data['recommendations'] = [rec.strip() for rec in recommendations]
        
        return data
    
    def format_analysis_summary(self, analysis: ProjectAnalysis) -> str:
        """Format analysis into a readable summary string"""
        return self.analysis_helper.format_analysis_summary(analysis)
    
    def validate_analysis_completeness(self, analysis: ProjectAnalysis) -> Dict[str, bool]:
        """Validate that analysis has all required components"""
        return self.analysis_helper.validate_analysis_completeness(analysis)
