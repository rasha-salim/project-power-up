#!/usr/bin/env python3
"""
Database Configuration Validation Script

This script validates the database configuration and tests connectivity.
Run this before starting the application to ensure proper setup.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_configuration():
    """Validate the database configuration"""
    logger.info("🔍 Validating database configuration...")
    
    try:
        # Test settings validation
        settings.validate_required_settings()
        logger.info("✅ Configuration validation passed")
    except ValueError as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        return False
    
    # Display current configuration
    logger.info(f"📊 Database Type: {settings.DATABASE_TYPE}")
    logger.info(f"📊 Database URI: {settings.DATABASE_URI}")
    
    if settings.is_postgresql:
        logger.info(f"📊 PostgreSQL Server: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}")
        logger.info(f"📊 PostgreSQL Database: {settings.POSTGRES_DB}")
        logger.info(f"📊 PostgreSQL User: {settings.POSTGRES_USER}")
        logger.info(f"📊 Async URI: {settings.async_database_uri}")
    elif settings.is_sqlite:
        logger.info(f"📊 SQLite Path: {settings.SQLITE_PATH}")
    
    return True

def test_sync_connection():
    """Test synchronous database connection"""
    logger.info("🔗 Testing synchronous database connection...")
    
    try:
        engine = create_engine(settings.DATABASE_URI)
        
        # Test connection
        with engine.connect() as conn:
            if settings.is_postgresql:
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                logger.info(f"✅ PostgreSQL connection successful: {version}")
            elif settings.is_sqlite:
                result = conn.execute(text("SELECT sqlite_version()"))
                version = result.fetchone()[0]
                logger.info(f"✅ SQLite connection successful: version {version}")
        
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"❌ Synchronous connection failed: {e}")
        return False

async def test_async_connection():
    """Test asynchronous database connection"""
    if not settings.is_postgresql:
        logger.info("⏭️  Skipping async connection test (not using PostgreSQL)")
        return True
    
    logger.info("🔗 Testing asynchronous database connection...")
    
    try:
        engine = create_async_engine(settings.async_database_uri)
        
        # Test connection
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"✅ Async PostgreSQL connection successful: {version}")
        
        await engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"❌ Asynchronous connection failed: {e}")
        return False

def test_table_creation():
    """Test table creation capability"""
    logger.info("🏗️  Testing table creation capability...")
    
    try:
        from app.db.base.base_class import Base
        from sqlalchemy import MetaData
        
        engine = create_engine(settings.DATABASE_URI)
        
        # Create a test table
        metadata = MetaData()
        test_table_sql = """
        CREATE TABLE IF NOT EXISTS db_test_table (
            id SERIAL PRIMARY KEY,
            test_column VARCHAR(50)
        )
        """ if settings.is_postgresql else """
        CREATE TABLE IF NOT EXISTS db_test_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_column VARCHAR(50)
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(test_table_sql))
            conn.execute(text("DROP TABLE IF EXISTS db_test_table"))
            conn.commit()
        
        logger.info("✅ Table creation test successful")
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"❌ Table creation test failed: {e}")
        return False

def main():
    """Main validation function"""
    logger.info("🚀 Starting database configuration validation...")
    logger.info("=" * 60)
    
    success = True
    
    # Step 1: Validate configuration
    if not validate_configuration():
        success = False
    
    logger.info("-" * 60)
    
    # Step 2: Test sync connection
    if not test_sync_connection():
        success = False
    
    logger.info("-" * 60)
    
    # Step 3: Test async connection
    if not asyncio.run(test_async_connection()):
        success = False
    
    logger.info("-" * 60)
    
    # Step 4: Test table creation
    if not test_table_creation():
        success = False
    
    logger.info("=" * 60)
    
    if success:
        logger.info("🎉 All database configuration tests passed!")
        logger.info("✅ Your database is ready for Project Power-Up")
        return 0
    else:
        logger.error("❌ Database configuration validation failed")
        logger.error("💡 Please check your .env file and database setup")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
