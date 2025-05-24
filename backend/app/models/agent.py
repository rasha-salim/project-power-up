from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Agent(Base):
    """SQLAlchemy Agent model"""
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="idle")  # idle, busy, error
    last_active = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentTask(Base):
    """SQLAlchemy AgentTask model"""
    __tablename__ = "agent_tasks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False)
    project_id = Column(String, nullable=True)
    task_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending, processing, completed, error
    input_data = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentBase(BaseModel):
    """Base Pydantic model for Agent"""
    name: str
    role: str
    description: Optional[str] = None


class AgentCreate(AgentBase):
    """Pydantic model for creating an Agent"""
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "idle"


class AgentUpdate(BaseModel):
    """Pydantic model for updating an Agent"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    last_active: Optional[datetime] = None


class AgentResponse(BaseModel):
    """Pydantic model for Agent response"""
    id: str
    name: str
    role: str
    status: str
    last_active: Optional[datetime] = None
    message: str
    
    class Config:
        orm_mode = True


class AgentTask(BaseModel):
    """Pydantic model for creating an Agent Task"""
    agent_id: str
    project_id: Optional[str] = None
    task_type: str
    input_data: Optional[Dict[str, Any]] = None
    
    class Config:
        orm_mode = True


class AgentTaskResponse(BaseModel):
    """Pydantic model for Agent Task response"""
    id: str
    agent_id: str
    project_id: Optional[str] = None
    task_type: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True
