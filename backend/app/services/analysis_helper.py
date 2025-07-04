"""
Analysis data helper utilities for consistent data access patterns
"""
from typing import Dict, Any, Optional, List
from app.models.analysis import ProjectAnalysis, TechnicalAnalysis, RiskAssessment, ProjectPlan


class AnalysisDataHelper:
    """Helper class for consistent analysis data access and formatting"""
    
    @staticmethod
    def get_tech_stack_summary(analysis: ProjectAnalysis) -> Dict[str, List[str]]:
        """Get a clean tech stack summary from analysis"""
        tech_stack = analysis.technical_analysis.tech_stack
        return {
            'frontend': tech_stack.frontend,
            'backend': tech_stack.backend,
            'infrastructure': tech_stack.infrastructure,
            'tools': tech_stack.tools
        }
    
    @staticmethod
    def get_risk_summary(analysis: ProjectAnalysis) -> Dict[str, Any]:
        """Get a clean risk assessment summary"""
        risk_assessment = analysis.risk_assessment
        return {
            'overall_score': risk_assessment.overall_risk_score,
            'key_risks': [
                {
                    'name': risk.name,
                    'level': risk.level.value,
                    'impact': risk.impact,
                    'probability': risk.probability
                }
                for risk in risk_assessment.key_risks[:3]  # Top 3 risks
            ],
            'mitigation_strategies': risk_assessment.mitigation_strategies
        }
    
    @staticmethod
    def get_project_timeline_summary(analysis: ProjectAnalysis) -> Dict[str, Any]:
        """Get a clean project timeline summary"""
        project_plan = analysis.project_plan
        return {
            'timeline': project_plan.timeline,
            'total_phases': len(project_plan.phases),
            'estimated_cost': project_plan.estimated_cost,
            'key_milestones': [
                {
                    'name': milestone.name,
                    'date': milestone.date,
                    'status': milestone.status
                }
                for milestone in project_plan.milestones[:5]  # Top 5 milestones
            ]
        }
    
    @staticmethod
    def format_analysis_summary(analysis: ProjectAnalysis) -> str:
        """Format analysis into a readable summary string with improved spacing"""
        tech_summary = AnalysisDataHelper.get_tech_stack_summary(analysis)
        risk_summary = AnalysisDataHelper.get_risk_summary(analysis)
        timeline_summary = AnalysisDataHelper.get_project_timeline_summary(analysis)
        
        return f"""# Project Analysis Summary

## Technical Analysis

**Architecture**: {analysis.technical_analysis.architecture}

**Technology Stack**:

- **Frontend**: {', '.join(tech_summary['frontend']) if tech_summary['frontend'] else 'Not specified'}
- **Backend**: {', '.join(tech_summary['backend']) if tech_summary['backend'] else 'Not specified'}  
- **Infrastructure**: {', '.join(tech_summary['infrastructure']) if tech_summary['infrastructure'] else 'Not specified'}

**Quality Scores**:

- **Complexity**: {analysis.technical_analysis.complexity_score}/10
- **Maintainability**: {analysis.technical_analysis.maintainability_score}/10
- **Scalability**: {analysis.technical_analysis.scalability_score}/10


## Risk Assessment

**Overall Risk Score**: {risk_summary['overall_score']}/10

**Key Identified Risks**:

{chr(10).join(['- ' + risk['name'] for risk in risk_summary['key_risks']]) if risk_summary['key_risks'] else '- No major risks identified'}


## Project Plan

**Timeline**: {timeline_summary['timeline']}

**Estimated Cost**: ${timeline_summary['estimated_cost']:,.2f}


## Key Recommendations

{chr(10).join(['- ' + rec for rec in analysis.recommendations[:5]]) if analysis.recommendations else '- No specific recommendations available'}

---

*Analysis completed successfully*
        """.strip()
    
    @staticmethod
    def validate_analysis_completeness(analysis: ProjectAnalysis) -> Dict[str, bool]:
        """Validate that analysis has all required components"""
        return {
            'has_technical_analysis': bool(analysis.technical_analysis.architecture),
            'has_tech_stack': bool(
                analysis.technical_analysis.tech_stack.frontend or
                analysis.technical_analysis.tech_stack.backend or
                analysis.technical_analysis.tech_stack.infrastructure
            ),
            'has_risk_assessment': bool(analysis.risk_assessment.key_risks),
            'has_project_plan': bool(analysis.project_plan.phases),
            'has_recommendations': bool(analysis.recommendations)
        }
