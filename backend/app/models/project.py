from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, Date
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

# Import the centralized Base class
from app.db.base.base_class import Base

class Project(Base):
    """SQLAlchemy Project model"""
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="draft")  # draft, analyzing, completed
    team_size = Column(Integer, nullable=True)
    deadline = Column(Date, nullable=True)
    goal = Column(Text, nullable=True)
    industry = Column(String, nullable=True)
    budget = Column(String, nullable=True)
    insights = Column(JSON, nullable=True)  # Stores analysis results
    planning_status = Column(String, nullable=False, default="not_started")  # not_started, in_progress, completed
    brief_sections = Column(JSON, nullable=True)  # Stores project brief section data
    generated_documents = Column(JSON, nullable=True)  # Stores generated document metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProjectBase(BaseModel):
    """Base Pydantic model for Project"""
    name: str
    description: Optional[str] = None
    team_size: Optional[int] = None
    deadline: Optional[date] = None
    goal: Optional[str] = None
    industry: Optional[str] = None
    budget: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Pydantic model for creating a Project"""
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "draft"


class ProjectUpdate(BaseModel):
    """Pydantic model for updating a Project"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    team_size: Optional[int] = None
    deadline: Optional[date] = None
    goal: Optional[str] = None
    industry: Optional[str] = None
    budget: Optional[str] = None
    insights: Optional[Dict[str, Any]] = None
    planning_status: Optional[str] = None
    brief_sections: Optional[Dict[str, Any]] = None
    generated_documents: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    """Pydantic model for Project response"""
    id: str
    name: str
    description: Optional[str] = None
    status: str
    team_size: Optional[int] = None
    deadline: Optional[date] = None
    goal: Optional[str] = None
    industry: Optional[str] = None
    budget: Optional[str] = None
    insights: Optional[Dict[str, Any]] = None
    planning_status: Optional[str] = None
    brief_sections: Optional[Dict[str, Any]] = None
    generated_documents: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message: str
    
    class Config:
        orm_mode = True
