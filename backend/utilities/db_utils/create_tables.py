"""
Script to initialize the database and create tables
"""
import asyncio
import logging
import sys
import os
from sqlalchemy import create_engine, Column, String, Text, DateTime, JSON, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import CreateTable
from datetime import datetime
import uuid

# Add the parent directory to the path so we can import the app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a base class for SQLAlchemy models
Base = declarative_base()

# Define the Project model
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

# Use the same database configuration as the main application
DATABASE_URL = str(settings.DATABASE_URI)

def create_tables():
    """Create all database tables"""
    try:
        # Create engine
        logger.info(f"Creating engine with URL: {DATABASE_URL}")
        engine = create_engine(DATABASE_URL)
        
        # Create tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(engine)
        
        # Print the SQL for creating the tables (for debugging)
        for table in Base.metadata.sorted_tables:
            logger.info(f"Created table: {table.name}")
            logger.info(CreateTable(table).compile(engine))
        
        logger.info("Database tables created successfully")
        
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    create_tables()
