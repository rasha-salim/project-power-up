from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

# Import the Base class from the centralized location
from app.db.base.base_class import Base

class Document(Base):
    """SQLAlchemy Document model"""
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    status = Column(String, nullable=False, default="processing")  # pending, processing, processed, error
    progress = Column(String, nullable=True, default="0")  # Progress percentage as string (0-100)
    project_id = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    doc_metadata = Column(Text, nullable=True)  # JSON serialized metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentBase(BaseModel):
    """Base Pydantic model for Document"""
    filename: str
    project_id: Optional[str] = None
    description: Optional[str] = None


class DocumentCreate(DocumentBase):
    """Pydantic model for creating a Document"""
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str
    content_type: Optional[str] = None
    status: str = "processing"
    progress: str = "10"
    doc_metadata: Optional[Dict[str, Any]] = None


class DocumentUpdate(BaseModel):
    """Pydantic model for updating a Document"""
    filename: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[str] = None
    project_id: Optional[str] = None
    description: Optional[str] = None
    doc_metadata: Optional[Dict[str, Any]] = None


class DocumentResponse(BaseModel):
    """Pydantic model for Document response"""
    id: str
    filename: str
    status: str
    message: str
    progress: Optional[str] = "0"
    project_id: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    doc_metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        orm_mode = True
