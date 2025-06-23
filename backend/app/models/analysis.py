from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class TechStackCategory(BaseModel):
    frontend: List[str] = Field(default_factory=list)
    backend: List[str] = Field(default_factory=list)
    infrastructure: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)


class TechnicalAnalysis(BaseModel):
    architecture: str
    tech_stack: TechStackCategory
    complexity_score: float = Field(ge=0, le=10)
    maintainability_score: float = Field(ge=0, le=10)
    scalability_score: float = Field(ge=0, le=10)
    performance_score: float = Field(ge=0, le=10)
    security_score: float = Field(ge=0, le=10)


class Risk(BaseModel):
    name: str
    level: RiskLevel
    impact: int = Field(ge=1, le=10)
    probability: int = Field(ge=1, le=10)
    description: Optional[str] = None


class RiskAssessment(BaseModel):
    key_risks: List[Risk]
    overall_risk_score: float = Field(ge=0, le=10)
    mitigation_strategies: List[str]


class ProjectPhase(BaseModel):
    name: str
    duration: int  # in weeks
    progress: int = Field(ge=0, le=100)
    description: Optional[str] = None


class Milestone(BaseModel):
    name: str
    date: str  # ISO date string
    status: str  # completed, in-progress, upcoming
    description: Optional[str] = None


class ResourceRequirements(BaseModel):
    developers: int = 0
    designers: int = 0
    qa: int = 0
    devops: int = 0
    pm: int = 0
    other: Dict[str, int] = Field(default_factory=dict)


class EffortDistribution(BaseModel):
    component: str
    effort: int  # percentage


class ProjectPlan(BaseModel):
    timeline: str
    phases: List[ProjectPhase]
    milestones: List[Milestone]
    resource_requirements: ResourceRequirements
    estimated_cost: float
    effort_distribution: List[EffortDistribution]


class ProjectAnalysis(BaseModel):
    """Complete project analysis structure"""
    analysis_id: str
    project_id: str
    version: int = 1
    technical_analysis: TechnicalAnalysis
    risk_assessment: RiskAssessment
    project_plan: ProjectPlan
    recommendations: List[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AnalysisResponse(BaseModel):
    """Response model for analysis endpoints"""
    analysis: ProjectAnalysis
    message: str = "Analysis retrieved successfully"
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
