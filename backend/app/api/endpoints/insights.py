from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any
import json
import logging

from app.db.database import get_db
from app.db.models import Analysis
from app.models.analysis import ProjectAnalysis
from app.services.analysis_helper import AnalysisDataHelper

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/insights/{project_id}")
async def get_project_insights(
    project_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get the latest insights for a project
    """
    try:
        # Get the latest analysis for the project
        analysis = db.query(Analysis).filter(
            Analysis.project_id == project_id
        ).order_by(Analysis.created_at.desc()).first()
        
        if not analysis:
            raise HTTPException(
                status_code=404,
                detail="No insights found for this project"
            )
        
        # Parse the result JSON and try to create ProjectAnalysis model
        result = json.loads(analysis.result) if isinstance(analysis.result, str) else analysis.result
        
        try:
            # Try to parse as ProjectAnalysis for standardized access
            project_analysis = ProjectAnalysis.parse_obj(result)
            
            # Use AnalysisDataHelper for consistent formatting
            tech_summary = AnalysisDataHelper.get_tech_stack_summary(project_analysis)
            risk_summary = AnalysisDataHelper.get_risk_summary(project_analysis)
            timeline_summary = AnalysisDataHelper.get_project_timeline_summary(project_analysis)
            
            # Structure the response using standardized data
            response = {
                "technical_analysis": {
                    "analysis_id": str(analysis.id),
                    "project_id": str(analysis.project_id),
                    "version": analysis.version or 1,
                    "technical_analysis": {
                        "architecture": project_analysis.technical_analysis.architecture,
                        "tech_stack": tech_summary,
                        "complexity_score": project_analysis.technical_analysis.complexity_score,
                        "maintainability_score": project_analysis.technical_analysis.maintainability_score,
                        "scalability_score": project_analysis.technical_analysis.scalability_score,
                        "performance_score": project_analysis.technical_analysis.performance_score,
                        "security_score": project_analysis.technical_analysis.security_score
                    },
                    "risk_assessment": risk_summary,
                    "project_plan": timeline_summary,
                    "recommendations": project_analysis.recommendations,
                    "created_at": analysis.created_at.isoformat(),
                    "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else analysis.created_at.isoformat()
                }
            }
            
        except Exception as parse_error:
            logger.warning(f"Could not parse analysis as ProjectAnalysis: {parse_error}")
            # Fallback to dictionary access for backward compatibility
            response = {
                "technical_analysis": {
                    "analysis_id": str(analysis.id),
                    "project_id": str(analysis.project_id),
                    "version": analysis.version or 1,
                    "technical_analysis": result.get("technical_analysis", {}),
                    "risk_assessment": result.get("risk_assessment", {}),
                    "project_plan": result.get("project_plan", {}),
                    "recommendations": result.get("recommendations", []),
                    "created_at": analysis.created_at.isoformat(),
                    "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else analysis.created_at.isoformat()
                }
            }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching insights: {str(e)}"
        )

@router.get("/insights/{project_id}/history")
async def get_insights_history(
    project_id: str,
    limit: int = 10,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get the history of insights for a project
    """
    try:
        analyses = db.query(Analysis).filter(
            Analysis.project_id == project_id
        ).order_by(Analysis.created_at.desc()).limit(limit).all()
        
        if not analyses:
            return {"analyses": []}
        
        history = []
        for analysis in analyses:
            result = json.loads(analysis.result) if isinstance(analysis.result, str) else analysis.result
            
            history.append({
                "analysis_id": str(analysis.id),
                "version": analysis.version or 1,
                "created_at": analysis.created_at.isoformat(),
                "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else analysis.created_at.isoformat(),
                "summary": {
                    "architecture": result.get("technical_analysis", {}).get("architecture", ""),
                    "overall_risk_score": result.get("risk_assessment", {}).get("overall_risk_score", 0),
                    "estimated_cost": result.get("project_plan", {}).get("estimated_cost", 0)
                }
            })
        
        return {"analyses": history}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching insights history: {str(e)}"
        )
