"""
Script to initialize the database and create tables
Run this script directly to create all required tables
"""
import asyncio
import logging
import sys
import os

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.db.base import Base
from app.models.project import Project
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_tables():
    """Create all database tables"""
    try:
        # Get database URL from settings
        db_url = str(settings.DATABASE_URI)
        
        # For PostgreSQL, use async engine
        async_db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')
        
        # Create engine
        logger.info(f"Creating async engine with URL: {async_db_url}")
        engine = create_async_engine(async_db_url, echo=True)
        
        # Create tables
        logger.info("Creating database tables...")
        async with engine.begin() as conn:
            # Drop tables first to ensure clean state
            logger.info("Dropping existing tables...")
            await conn.run_sync(Base.metadata.drop_all)
            
            # Create tables
            logger.info("Creating tables...")
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created successfully")
        
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(create_tables())
