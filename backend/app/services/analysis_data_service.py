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
            print(f"🔍 PARSING AGENT OUTPUT: Length {len(raw_output)} characters")
            print(f"🔍 RAW OUTPUT PREVIEW: {raw_output[:500]}...")
            
            # Try to parse as JSON first
            data = self._parse_json_output(raw_output)
            print(f"🔍 PARSED DATA KEYS: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Extract and create technical analysis
            technical_analysis = self._create_technical_analysis(data)
            
            # Extract and create risk assessment
            risk_assessment = self._create_risk_assessment(data)
            
            # Extract and create project plan
            project_plan = self._create_project_plan(data)
            
            # Extract recommendations
            recommendations = data.get('recommendations', []) if isinstance(data, dict) else []
            
            # Create the complete ProjectAnalysis
            print(f"🔍 CREATING PYDANTIC MODEL")
            print(f"🔍 Technical analysis type: {type(technical_analysis)}")
            print(f"🔍 Risk assessment type: {type(risk_assessment)}")
            print(f"🔍 Project plan type: {type(project_plan)}")
            
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
            
            print(f"🔍 PYDANTIC MODEL CREATED SUCCESSFULLY")
            print(f"🔍 Final architecture: {project_analysis.technical_analysis.architecture[:100] if project_analysis.technical_analysis.architecture else 'EMPTY'}...")
            print(f"🔍 Final tech stack frontend: {project_analysis.technical_analysis.tech_stack.frontend}")
            print(f"🔍 Final complexity score: {project_analysis.technical_analysis.complexity_score}")
            print(f"🔍 Final timeline: {project_analysis.project_plan.timeline[:100] if project_analysis.project_plan.timeline else 'EMPTY'}...")
            print(f"🔍 Final estimated cost: {project_analysis.project_plan.estimated_cost}")
            
            logger.info(f"Successfully parsed agent output into Pydantic model for analysis {analysis_id}")
            return project_analysis
            
        except Exception as e:
            logger.error(f"Error parsing agent output: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def _parse_json_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse JSON output with fallback to text extraction"""
        try:
            print(f"🔍 JSON PARSING: Input type: {type(raw_output)}")
            
            # Try direct JSON parsing
            if isinstance(raw_output, dict):
                data = raw_output
                print(f"🔍 JSON PARSING: Already a dict")
            else:
                print(f"🔍 JSON PARSING: Attempting json.loads()")
                
                # Clean the raw output first - remove markdown code blocks
                cleaned_output = raw_output.strip()
                if cleaned_output.startswith('```json'):
                    cleaned_output = cleaned_output[7:]  # Remove ```json
                if cleaned_output.startswith('```'):
                    cleaned_output = cleaned_output[3:]   # Remove ```
                if cleaned_output.endswith('```'):
                    cleaned_output = cleaned_output[:-3]  # Remove closing ```
                cleaned_output = cleaned_output.strip()
                
                # Fix control characters and formatting issues in JSON strings
                import re
                # Replace problematic characters that break JSON parsing
                # Simple approach: replace all control characters except necessary ones
                cleaned_output = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', ' ', cleaned_output)
                # Normalize whitespace within string values (but preserve JSON structure)
                # This will replace sequences of whitespace with single spaces
                cleaned_output = re.sub(r'[ \t\r\n]+', ' ', cleaned_output)
                
                print(f"🔍 JSON PARSING: Cleaned output preview: {cleaned_output[:200]}...")
                print(f"🔍 JSON PARSING: Cleaned output length: {len(cleaned_output)} characters")
                print(f"🔍 JSON PARSING: Cleaned output ending: ...{cleaned_output[-200:]}")
                
                data = json.loads(cleaned_output)
                print(f"🔍 JSON PARSING: Successfully parsed JSON")
                
            logger.info(f"Successfully parsed JSON, keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            print(f"🔍 JSON PARSING: Keys found: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            
            # DON'T flatten the structure - keep the full JSON structure intact
            # The data should have: technical_analysis, risk_assessment, project_plan, etc.
            if isinstance(data, dict):
                logger.info(f"JSON structure preserved with keys: {list(data.keys())}")
                print(f"🔍 JSON STRUCTURE PRESERVED: {list(data.keys())}")
                
                # Debug: Show what's in each section
                if 'project_plan' in data:
                    project_plan = data['project_plan']
                    print(f"🔍 PROJECT PLAN FOUND: {list(project_plan.keys()) if isinstance(project_plan, dict) else 'Not a dict'}")
                    if isinstance(project_plan, dict):
                        print(f"🔍 TIMELINE IN JSON: '{project_plan.get('timeline', 'NOT FOUND')}'")
                        print(f"🔍 COST IN JSON: {project_plan.get('estimated_cost', 'NOT FOUND')}")
                        print(f"🔍 PHASES COUNT: {len(project_plan.get('phases', []))}")
                        print(f"🔍 MILESTONES COUNT: {len(project_plan.get('milestones', []))}")
            
            return data
            
        except json.JSONDecodeError as e:
            # If not valid JSON, try to fix truncated JSON first
            logger.warning(f"Agent output is not valid JSON, attempting to fix truncation")
            print(f"🔍 JSON DECODE ERROR: {str(e)}")
            print(f"🔍 JSON DECODE ERROR: Position {e.pos if hasattr(e, 'pos') else 'unknown'}")
            
            # Try to fix truncated JSON by completing missing braces/quotes
            fixed_json = self._attempt_json_repair(cleaned_output)
            if fixed_json:
                try:
                    print(f"🔍 ATTEMPTING REPAIRED JSON")
                    data = json.loads(fixed_json)
                    print(f"🔍 REPAIRED JSON SUCCESS!")
                    return data
                except Exception as repair_error:
                    print(f"🔍 REPAIRED JSON FAILED: {repair_error}")
            
            # IMMEDIATE FALLBACK: Extract content directly from the rich output
            print(f"🔍 JSON FAILED - EXTRACTING RICH CONTENT DIRECTLY")
            return self._extract_rich_content_directly(raw_output)
    
    def _attempt_json_repair(self, broken_json: str) -> Optional[str]:
        """Attempt to repair truncated JSON"""
        try:
            print(f"🔍 ATTEMPTING JSON REPAIR")
            
            # Check if we have the start of JSON
            if not broken_json.strip().startswith('{'):
                return None
            
            # Count opening and closing braces to see what's missing
            open_braces = broken_json.count('{')
            close_braces = broken_json.count('}')
            open_brackets = broken_json.count('[')
            close_brackets = broken_json.count(']')
            
            print(f"🔍 REPAIR: Open braces: {open_braces}, Close braces: {close_braces}")
            print(f"🔍 REPAIR: Open brackets: {open_brackets}, Close brackets: {close_brackets}")
            
            # If JSON ends abruptly without closing quote, try to fix it
            repaired = broken_json
            
            # Check if last character suggests an unterminated string
            if not repaired.rstrip().endswith(('"', '}', ']')):
                # Add closing quote if it seems like a string was cut off
                repaired += '"'
                print(f"🔍 REPAIR: Added closing quote")
            
            # Add missing closing brackets
            missing_brackets = open_brackets - close_brackets
            for _ in range(missing_brackets):
                repaired += ']'
                print(f"🔍 REPAIR: Added closing bracket")
            
            # Add missing closing braces
            missing_braces = open_braces - close_braces
            for _ in range(missing_braces):
                repaired += '}'
                print(f"🔍 REPAIR: Added closing brace")
            
            print(f"🔍 REPAIR: Final repaired length: {len(repaired)}")
            print(f"🔍 REPAIR: Final ending: ...{repaired[-100:]}")
            
            return repaired
            
        except Exception as e:
            print(f"🔍 REPAIR ERROR: {e}")
            return None
    
    def _extract_rich_content_directly(self, raw_output: str) -> Dict[str, Any]:
        """
        Extract rich content directly from agent output when JSON parsing fails
        This method looks for the actual analysis content in the text and extracts it
        """
        print(f"🔍 EXTRACTING RICH CONTENT DIRECTLY")
        print(f"🔍 Raw output length: {len(raw_output)} characters")
        print(f"🔍 Raw output preview: {raw_output[:1000]}...")
        print(f"🔍 Raw output ending: ...{raw_output[-500:]}")
        
        # Look for patterns that indicate rich content
        # The agent typically produces detailed descriptions that we want to preserve
        
        # Initialize with enhanced defaults
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
                'timeline': '',
                'phases': [],
                'milestones': [],
                'resource_requirements': {
                    'developers': 2,
                    'designers': 1,
                    'qa': 1,
                    'devops': 1,
                    'pm': 1
                },
                'estimated_cost': 50000.0,
                'effort_distribution': []
            },
            'recommendations': []
        }
        
        # Extract detailed architecture description - try JSON first
        arch_json_match = re.search(r'"architecture":\s*"([^"]*(?:\\.[^"]*)*)"', raw_output, re.DOTALL)
        if arch_json_match:
            arch_text = arch_json_match.group(1)
            # Unescape JSON string
            arch_text = arch_text.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
            data['technical_analysis']['architecture'] = arch_text
            print(f"🔍 EXTRACTED ARCHITECTURE FROM JSON: {len(arch_text)} chars")
        else:
            # Fallback to text patterns
            arch_patterns = [
                r'(?i)architecture[:\s]*([^{}\[\]]*?)(?=\n\n|\n[A-Z]|$)',
                r'(?i)system architecture[:\s]*([^{}\[\]]*?)(?=\n\n|\n[A-Z]|$)',
                r'(?i)architectural approach[:\s]*([^{}\[\]]*?)(?=\n\n|\n[A-Z]|$)'
            ]
            
            for pattern in arch_patterns:
                match = re.search(pattern, raw_output, re.DOTALL)
                if match:
                    arch_text = match.group(1).strip()
                    if len(arch_text) > 20:  # Only use if substantial content
                        data['technical_analysis']['architecture'] = arch_text[:500]  # Limit length
                        print(f"🔍 EXTRACTED ARCHITECTURE: {len(arch_text)} chars")
                        break
        
        # Extract detailed timeline description - try JSON first
        timeline_json_match = re.search(r'"timeline":\s*"([^"]*(?:\\.[^"]*)*)"', raw_output, re.DOTALL)
        if timeline_json_match:
            timeline_text = timeline_json_match.group(1)
            # Unescape JSON string
            timeline_text = timeline_text.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
            data['project_plan']['timeline'] = timeline_text
            print(f"🔍 EXTRACTED TIMELINE FROM JSON: {len(timeline_text)} chars")
        else:
            # Fallback to text patterns
            timeline_patterns = [
                r'(?i)timeline[:\s]*([^{}\[\]]*?)(?=\n\n|\n[A-Z]|$)',
                r'(?i)project timeline[:\s]*([^{}\[\]]*?)(?=\n\n|\n[A-Z]|$)',
                r'(?i)development timeline[:\s]*([^{}\[\]]*?)(?=\n\n|\n[A-Z]|$)'
            ]
            
            for pattern in timeline_patterns:
                match = re.search(pattern, raw_output, re.DOTALL)
                if match:
                    timeline_text = match.group(1).strip()
                    if len(timeline_text) > 10:
                        data['project_plan']['timeline'] = timeline_text[:300]
                        print(f"🔍 EXTRACTED TIMELINE: {len(timeline_text)} chars")
                        break
        
        # Extract cost information - try JSON first
        cost_json_patterns = [
            r'"estimated_cost":\s*(\d+(?:\.\d+)?)',
            r'"cost":\s*(\d+(?:\.\d+)?)',
            r'"budget":\s*(\d+(?:\.\d+)?)'
        ]
        
        for pattern in cost_json_patterns:
            match = re.search(pattern, raw_output)
            if match:
                try:
                    cost = float(match.group(1))
                    if cost > 0:  # Any positive cost
                        data['project_plan']['estimated_cost'] = cost
                        print(f"🔍 EXTRACTED COST FROM JSON: ${cost}")
                        break
                except:
                    continue
        
        # Fallback to text-based cost extraction if JSON didn't work
        if data['project_plan']['estimated_cost'] == 50000.0:  # Still default
            cost_text_patterns = [
                r'(?i)cost[:\s]*\$?([\d,\.]+)',
                r'(?i)budget[:\s]*\$?([\d,\.]+)',
                r'(?i)estimated cost[:\s]*\$?([\d,\.]+)'
            ]
            
            for pattern in cost_text_patterns:
                match = re.search(pattern, raw_output)
                if match:
                    try:
                        cost_str = match.group(1).replace(',', '')
                        cost = float(cost_str)
                        if cost > 1000:  # Reasonable minimum
                            data['project_plan']['estimated_cost'] = cost
                            print(f"🔍 EXTRACTED COST FROM TEXT: ${cost}")
                            break
                    except:
                        continue
        
        # Extract technology stack with better parsing - look for JSON structure first
        tech_stack_match = re.search(r'"tech_stack":\s*\{([^}]+)\}', raw_output, re.DOTALL)
        if tech_stack_match:
            tech_stack_content = tech_stack_match.group(1)
            print(f"🔍 FOUND TECH STACK JSON: {tech_stack_content[:200]}...")
            
            # Extract arrays from the JSON structure
            frontend_match = re.search(r'"frontend":\s*\[([^\]]+)\]', tech_stack_content)
            if frontend_match:
                frontend_items = re.findall(r'"([^"]+)"', frontend_match.group(1))
                data['technical_analysis']['tech_stack']['frontend'] = frontend_items
                print(f"🔍 EXTRACTED FRONTEND FROM JSON: {frontend_items}")
            
            backend_match = re.search(r'"backend":\s*\[([^\]]+)\]', tech_stack_content)
            if backend_match:
                backend_items = re.findall(r'"([^"]+)"', backend_match.group(1))
                data['technical_analysis']['tech_stack']['backend'] = backend_items
                print(f"🔍 EXTRACTED BACKEND FROM JSON: {backend_items}")
                
            infrastructure_match = re.search(r'"infrastructure":\s*\[([^\]]+)\]', tech_stack_content)
            if infrastructure_match:
                infra_items = re.findall(r'"([^"]+)"', infrastructure_match.group(1))
                data['technical_analysis']['tech_stack']['infrastructure'] = infra_items
                print(f"🔍 EXTRACTED INFRASTRUCTURE FROM JSON: {infra_items}")
                
            tools_match = re.search(r'"tools":\s*\[([^\]]+)\]', tech_stack_content)
            if tools_match:
                tools_items = re.findall(r'"([^"]+)"', tools_match.group(1))
                data['technical_analysis']['tech_stack']['tools'] = tools_items
                print(f"🔍 EXTRACTED TOOLS FROM JSON: {tools_items}")
        else:
            # Fallback to text-based extraction
            tech_section = re.search(r'(?i)tech(?:nology)?\s*stack[:\s]*([^{}\[\]]*?)(?=\n\n|\n[A-Z]|$)', raw_output, re.DOTALL)
            if tech_section:
                tech_content = tech_section.group(1)
                
                # Look for structured lists or mentions of technologies
                frontend_techs = re.findall(r'(?i)(?:react|vue|angular|next\.js|svelte|typescript|javascript)', tech_content)
                backend_techs = re.findall(r'(?i)(?:node\.js|python|django|flask|fastapi|express|spring|java|\.net)', tech_content)
                db_techs = re.findall(r'(?i)(?:postgresql|mysql|mongodb|redis|sqlite|oracle)', tech_content)
                
                if frontend_techs:
                    data['technical_analysis']['tech_stack']['frontend'] = list(set(frontend_techs))
                    print(f"🔍 EXTRACTED FRONTEND: {frontend_techs}")
                
                if backend_techs:
                    data['technical_analysis']['tech_stack']['backend'] = list(set(backend_techs))
                    print(f"🔍 EXTRACTED BACKEND: {backend_techs}")
                    
                if db_techs:
                    data['technical_analysis']['tech_stack']['infrastructure'] = list(set(db_techs))
                    print(f"🔍 EXTRACTED DATABASES: {db_techs}")
        
        # Extract complexity and other scores - try JSON first
        score_patterns = [
            (r'"complexity_score":\s*(\d+(?:\.\d+)?)', 'complexity_score'),
            (r'"maintainability_score":\s*(\d+(?:\.\d+)?)', 'maintainability_score'),
            (r'"scalability_score":\s*(\d+(?:\.\d+)?)', 'scalability_score'),
            (r'"performance_score":\s*(\d+(?:\.\d+)?)', 'performance_score'),
            (r'"security_score":\s*(\d+(?:\.\d+)?)', 'security_score')
        ]
        
        for pattern, score_key in score_patterns:
            match = re.search(pattern, raw_output)
            if match:
                try:
                    score = float(match.group(1))
                    if 1 <= score <= 10:
                        data['technical_analysis'][score_key] = score
                        print(f"🔍 EXTRACTED {score_key}: {score}")
                except:
                    continue
        
        # Fallback to text-based score extraction
        text_score_patterns = [
            (r'(?i)complexity[:\s]*(\d+(?:\.\d+)?)', 'complexity_score'),
            (r'(?i)maintainability[:\s]*(\d+(?:\.\d+)?)', 'maintainability_score'),
            (r'(?i)scalability[:\s]*(\d+(?:\.\d+)?)', 'scalability_score')
        ]
        
        for pattern, score_key in text_score_patterns:
            if data['technical_analysis'][score_key] == 5.0:  # Only if not already extracted
                match = re.search(pattern, raw_output)
                if match:
                    try:
                        score = float(match.group(1))
                        if 1 <= score <= 10:
                            data['technical_analysis'][score_key] = score
                            print(f"🔍 EXTRACTED {score_key} FROM TEXT: {score}")
                    except:
                        continue
        
        # Set realistic defaults based on project type analysis
        if not data['technical_analysis']['architecture']:
            data['technical_analysis']['architecture'] = "Modern web application architecture with separated frontend and backend components, following industry best practices for scalability and maintainability."
        
        if not data['project_plan']['timeline']:
            data['project_plan']['timeline'] = "12-16 weeks development timeline with iterative sprints, including planning, development, testing, and deployment phases."
        
        print(f"🔍 RICH CONTENT EXTRACTION COMPLETE")
        print(f"🔍 Architecture length: {len(data['technical_analysis']['architecture'])}")
        print(f"🔍 Timeline length: {len(data['project_plan']['timeline'])}")
        print(f"🔍 Estimated cost: ${data['project_plan']['estimated_cost']}")
        
        # DEBUG: Show what we actually extracted
        print(f"🔍 EXTRACTED TIMELINE: '{data['project_plan']['timeline']}'")
        print(f"🔍 EXTRACTED COST: {data['project_plan']['estimated_cost']}")
        
        # DEBUG: Look for timeline and cost in original output
        timeline_search = re.search(r'"timeline":\s*"([^"]*)"', raw_output, re.DOTALL)
        if timeline_search:
            found_timeline = timeline_search.group(1)
            print(f"🔍 FOUND TIMELINE IN JSON: '{found_timeline[:200]}...'")
        
        cost_search = re.search(r'"estimated_cost":\s*(\d+)', raw_output)
        if cost_search:
            found_cost = cost_search.group(1)
            print(f"🔍 FOUND COST IN JSON: {found_cost}")
        
        return data
    
    def _create_technical_analysis(self, data: Dict[str, Any]) -> TechnicalAnalysis:
        """Create TechnicalAnalysis from parsed data"""
        print(f"🔍 CREATING TECHNICAL ANALYSIS")
        print(f"🔍 Input data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        # Extract technical analysis data
        tech_data = data.get('technical_analysis', {}) if isinstance(data, dict) else {}
        print(f"🔍 Tech data from 'technical_analysis' key: {bool(tech_data)}")
        
        # If tech_data is still empty, the structure might be different
        if not tech_data and isinstance(data, dict):
            print(f"🔍 No 'technical_analysis' key found in data")
            print(f"🔍 Available keys: {list(data.keys())}")
            # Don't use root data - this flattens the structure incorrectly
            tech_data = {}  # Use empty dict to trigger defaults
        
        print(f"🔍 Final tech_data keys: {list(tech_data.keys()) if isinstance(tech_data, dict) else 'Not a dict'}")
        if isinstance(tech_data, dict):
            print(f"🔍 Architecture: {tech_data.get('architecture', 'NOT FOUND')}")
            print(f"🔍 Tech stack: {tech_data.get('tech_stack', 'NOT FOUND')}")
            print(f"🔍 Complexity score: {tech_data.get('complexity_score', 'NOT FOUND')}")
        
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
        print(f"🔍 CREATING RISK ASSESSMENT")
        print(f"🔍 Input data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        # Extract risk assessment data
        risk_data = data.get('risk_assessment', {}) if isinstance(data, dict) else {}
        print(f"🔍 Risk data found: {bool(risk_data)}")
        print(f"🔍 Risk data keys: {list(risk_data.keys()) if isinstance(risk_data, dict) else 'Not a dict'}")
        
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
        print(f"🔍 CREATING PROJECT PLAN")
        print(f"🔍 Input data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        # Extract project plan data
        plan_data = data.get('project_plan', {}) if isinstance(data, dict) else {}
        print(f"🔍 Plan data found: {bool(plan_data)}")
        print(f"🔍 Plan data keys: {list(plan_data.keys()) if isinstance(plan_data, dict) else 'Not a dict'}")
        
        if isinstance(plan_data, dict):
            print(f"🔍 Plan timeline: '{plan_data.get('timeline', 'NOT FOUND')}'")
            print(f"🔍 Plan cost: {plan_data.get('estimated_cost', 'NOT FOUND')}")
            print(f"🔍 Plan phases: {len(plan_data.get('phases', []))} items")
            print(f"🔍 Plan milestones: {len(plan_data.get('milestones', []))} items")
        
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
        
        # Create ResourceRequirements - handle nested developers object
        resource_data = plan_data.get('resource_requirements', {})
        print(f"🔍 Resource data: {resource_data}")
        
        # Handle developers field - could be int or nested object
        developers_data = resource_data.get('developers', 0)
        if isinstance(developers_data, dict):
            # Sum up all developer roles
            developers_count = sum([
                developers_data.get('lead', 0),
                developers_data.get('backend', 0),
                developers_data.get('frontend', 0),
                developers_data.get('fullstack', 0)
            ])
            print(f"🔍 Developers from nested object: {developers_count}")
        else:
            developers_count = int(developers_data) if developers_data else 0
            print(f"🔍 Developers from simple int: {developers_count}")
        
        resources = ResourceRequirements(
            developers=int(developers_count),
            designers=int(resource_data.get('designers', 0)),
            qa=int(resource_data.get('qa', 0)),
            devops=int(resource_data.get('devops', 0)),
            pm=int(resource_data.get('pm', 0)),
            other=resource_data.get('other', {})
        )
        print(f"🔍 Final resource requirements: developers={resources.developers}, devops={resources.devops}, pm={resources.pm}")
        
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
        logger.info("Extracting structured data from text using regex patterns")
        
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
        arch_match = re.search(r'\*\*Architecture\*\*[:\s]*(.*?)(?:\n|\*\*)', text, re.IGNORECASE | re.DOTALL)
        if arch_match:
            data['technical_analysis']['architecture'] = arch_match.group(1).strip()
            logger.info(f"Extracted architecture: {data['technical_analysis']['architecture']}")
        
        # Extract tech stack section
        tech_stack_section = re.search(r'\*\*Tech Stack\*\*[:\s]*\n(.*?)(?:\n\*\*|\n##|\Z)', text, re.IGNORECASE | re.DOTALL)
        if tech_stack_section:
            tech_content = tech_stack_section.group(1)
            
            # Extract frontend
            frontend_match = re.search(r'[-*]\s*Frontend[:\s]*\[(.*?)\]', tech_content, re.IGNORECASE)
            if frontend_match:
                frontend_techs = [tech.strip() for tech in frontend_match.group(1).split(',')]
                data['technical_analysis']['tech_stack']['frontend'] = frontend_techs
                logger.info(f"Extracted frontend: {frontend_techs}")
            
            # Extract backend
            backend_match = re.search(r'[-*]\s*Backend[:\s]*\[(.*?)\]', tech_content, re.IGNORECASE)
            if backend_match:
                backend_techs = [tech.strip() for tech in backend_match.group(1).split(',')]
                data['technical_analysis']['tech_stack']['backend'] = backend_techs
                logger.info(f"Extracted backend: {backend_techs}")
            
            # Extract database (treat as infrastructure)
            db_match = re.search(r'[-*]\s*Database[:\s]*\[(.*?)\]', tech_content, re.IGNORECASE)
            if db_match:
                db_techs = [tech.strip() for tech in db_match.group(1).split(',')]
                data['technical_analysis']['tech_stack']['infrastructure'].extend(db_techs)
                logger.info(f"Extracted database: {db_techs}")
            
            # Extract infrastructure
            infra_match = re.search(r'[-*]\s*Infrastructure[:\s]*\[(.*?)\]', tech_content, re.IGNORECASE)
            if infra_match:
                infra_techs = [tech.strip() for tech in infra_match.group(1).split(',')]
                data['technical_analysis']['tech_stack']['infrastructure'].extend(infra_techs)
                logger.info(f"Extracted infrastructure: {infra_techs}")
            
            # Extract tools
            tools_match = re.search(r'[-*]\s*Tools[:\s]*\[(.*?)\]', tech_content, re.IGNORECASE)
            if tools_match:
                tools_techs = [tech.strip() for tech in tools_match.group(1).split(',')]
                data['technical_analysis']['tech_stack']['tools'] = tools_techs
                logger.info(f"Extracted tools: {tools_techs}")
        
        # Extract scores
        scores_section = re.search(r'\*\*Scores\*\*[:\s]*\n(.*?)(?:\n##|\n\*\*|\Z)', text, re.IGNORECASE | re.DOTALL)
        if scores_section:
            scores_content = scores_section.group(1)
            
            # Extract individual scores
            complexity_match = re.search(r'[-*]\s*Complexity[:\s]*(\d+(?:\.\d+)?)', scores_content, re.IGNORECASE)
            if complexity_match:
                data['technical_analysis']['complexity_score'] = float(complexity_match.group(1))
            
            maintainability_match = re.search(r'[-*]\s*Maintainability[:\s]*(\d+(?:\.\d+)?)', scores_content, re.IGNORECASE)
            if maintainability_match:
                data['technical_analysis']['maintainability_score'] = float(maintainability_match.group(1))
            
            scalability_match = re.search(r'[-*]\s*Scalability[:\s]*(\d+(?:\.\d+)?)', scores_content, re.IGNORECASE)
            if scalability_match:
                data['technical_analysis']['scalability_score'] = float(scalability_match.group(1))
            
            performance_match = re.search(r'[-*]\s*Performance[:\s]*(\d+(?:\.\d+)?)', scores_content, re.IGNORECASE)
            if performance_match:
                data['technical_analysis']['performance_score'] = float(performance_match.group(1))
            
            security_match = re.search(r'[-*]\s*Security[:\s]*(\d+(?:\.\d+)?)', scores_content, re.IGNORECASE)
            if security_match:
                data['technical_analysis']['security_score'] = float(security_match.group(1))
            
            logger.info(f"Extracted scores: complexity={data['technical_analysis']['complexity_score']}, maintainability={data['technical_analysis']['maintainability_score']}, scalability={data['technical_analysis']['scalability_score']}")
        
        # Extract risk assessment
        risk_section = re.search(r'##\s*Risk Assessment\s*\n(.*?)(?:\n##|\Z)', text, re.IGNORECASE | re.DOTALL)
        if risk_section:
            risk_content = risk_section.group(1)
            
            # Extract overall risk score
            overall_risk_match = re.search(r'[-*]\s*Overall Risk Score[:\s]*(\d+(?:\.\d+)?)', risk_content, re.IGNORECASE)
            if overall_risk_match:
                data['risk_assessment']['overall_risk_score'] = float(overall_risk_match.group(1))
            
            # Extract key risks
            risks_section = re.search(r'[-*]\s*Key Risks[:\s]*\n(.*?)(?:\n##|\n\*\*|\Z)', risk_content, re.IGNORECASE | re.DOTALL)
            if risks_section:
                risks_text = risks_section.group(1)
                risk_items = re.findall(r'[-*]\s*\[(.*?)\][:\s]*(\w+)[:\s]*[-–—]\s*(.*?)(?:\n|$)', risks_text)
                
                for risk_name, risk_level, risk_desc in risk_items:
                    data['risk_assessment']['key_risks'].append({
                        'name': risk_name.strip(),
                        'level': risk_level.strip().title(),
                        'impact': 5,  # Default value
                        'probability': 5,  # Default value
                        'description': risk_desc.strip()
                    })
                
                logger.info(f"Extracted {len(data['risk_assessment']['key_risks'])} risks")
        
        # Extract project plan
        project_section = re.search(r'##\s*Project Plan\s*\n(.*?)(?:\n##|\Z)', text, re.IGNORECASE | re.DOTALL)
        if project_section:
            project_content = project_section.group(1)
            
            # Extract timeline
            timeline_match = re.search(r'\*\*Timeline\*\*[:\s]*(.*?)(?:\n|\*\*)', project_content, re.IGNORECASE)
            if timeline_match:
                data['project_plan']['timeline'] = timeline_match.group(1).strip()
            
            # Extract estimated cost
            cost_match = re.search(r'\*\*Estimated Cost\*\*[:\s]*\$?([\d,\.]+)', project_content, re.IGNORECASE)
            if cost_match:
                cost_str = cost_match.group(1).replace(',', '')
                try:
                    data['project_plan']['estimated_cost'] = float(cost_str)
                except ValueError:
                    data['project_plan']['estimated_cost'] = 0.0
            
            # Extract team size (use as developers count)
            team_match = re.search(r'\*\*Team Size\*\*[:\s]*(\d+)', project_content, re.IGNORECASE)
            if team_match:
                team_size = int(team_match.group(1))
                data['project_plan']['resource_requirements']['developers'] = team_size
            
            # Extract project phases
            phases_section = re.search(r'\*\*Project Phases\*\*[:\s]*\n(.*?)(?:\n\*\*|\n##|\Z)', project_content, re.IGNORECASE | re.DOTALL)
            if phases_section:
                phases_text = phases_section.group(1)
                phase_items = re.findall(r'\d+\.\s*(.*?)\s*[-–—]\s*(.*?)\s*[-–—]\s*(.*?)(?:\n|$)', phases_text)
                
                for phase_name, duration, deliverables in phase_items:
                    # Extract duration in weeks
                    duration_weeks = 4  # Default
                    duration_match = re.search(r'(\d+)', duration)
                    if duration_match:
                        duration_weeks = int(duration_match.group(1))
                    
                    data['project_plan']['phases'].append({
                        'name': phase_name.strip(),
                        'duration': duration_weeks,
                        'progress': 0,
                        'description': deliverables.strip()
                    })
                
                logger.info(f"Extracted {len(data['project_plan']['phases'])} phases")
            
            # Extract milestones
            milestones_section = re.search(r'\*\*Milestones\*\*[:\s]*\n(.*?)(?:\n\*\*|\n##|\Z)', project_content, re.IGNORECASE | re.DOTALL)
            if milestones_section:
                milestones_text = milestones_section.group(1)
                milestone_items = re.findall(r'[-*]\s*(.*?)\s*[-–—]\s*(.*?)(?:\n|$)', milestones_text)
                
                for milestone_name, milestone_date in milestone_items:
                    data['project_plan']['milestones'].append({
                        'name': milestone_name.strip(),
                        'date': milestone_date.strip(),
                        'status': 'upcoming',
                        'description': None
                    })
                
                logger.info(f"Extracted {len(data['project_plan']['milestones'])} milestones")
        
        # Extract recommendations
        recommendations_section = re.search(r'##\s*Recommendations\s*\n(.*?)(?:\n##|\Z)', text, re.IGNORECASE | re.DOTALL)
        if recommendations_section:
            recommendations_text = recommendations_section.group(1)
            recommendation_items = re.findall(r'[-*]\s*(.*?)(?:\n|$)', recommendations_text)
            data['recommendations'] = [rec.strip() for rec in recommendation_items if rec.strip()]
            logger.info(f"Extracted {len(data['recommendations'])} recommendations")
        
        logger.info("Completed text extraction with comprehensive parsing")
        return data
    
    def format_analysis_summary(self, analysis: ProjectAnalysis) -> str:
        """Format analysis into a readable summary string"""
        return self.analysis_helper.format_analysis_summary(analysis)
    
    def validate_analysis_completeness(self, analysis: ProjectAnalysis) -> Dict[str, bool]:
        """Validate that analysis has all required components"""
        return self.analysis_helper.validate_analysis_completeness(analysis)
