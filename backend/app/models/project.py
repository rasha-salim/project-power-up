from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Project(Base):
    """SQLAlchemy Project model"""
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="draft")  # draft, analyzing, completed
    insights = Column(JSON, nullable=True)  # Stores analysis results
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProjectBase(BaseModel):
    """Base Pydantic model for Project"""
    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Pydantic model for creating a Project"""
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "draft"


class ProjectUpdate(BaseModel):
    """Pydantic model for updating a Project"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    insights: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    """Pydantic model for Project response"""
    id: str
    name: str
    description: Optional[str] = None
    status: str
    insights: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message: str
    
    class Config:
        orm_mode = True
