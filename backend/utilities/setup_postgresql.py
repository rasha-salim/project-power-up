#!/usr/bin/env python3
"""
PostgreSQL Database Setup Script

This script:
1. Verifies PostgreSQL connection
2. Creates the database if it doesn't exist
3. Creates all tables with the current schema
4. Verifies the schema is correct
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.db.base.base_class import Base
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_postgresql_connection():
    """Check if PostgreSQL server is running and accessible"""
    try:
        # Connect to PostgreSQL server (not to specific database)
        conn = psycopg2.connect(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database='postgres'  # Connect to default postgres database
        )
        conn.close()
        logger.info("✅ PostgreSQL server is accessible")
        return True
    except psycopg2.Error as e:
        logger.error(f"❌ Cannot connect to PostgreSQL server: {e}")
        logger.error("💡 Make sure PostgreSQL is running and credentials are correct")
        return False

def create_database_if_not_exists():
    """Create the project database if it doesn't exist"""
    try:
        # Connect to PostgreSQL server
        conn = psycopg2.connect(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (settings.POSTGRES_DB,)
        )
        exists = cursor.fetchone()
        
        if exists:
            logger.info(f"✅ Database '{settings.POSTGRES_DB}' already exists")
        else:
            logger.info(f"📝 Creating database '{settings.POSTGRES_DB}'...")
            cursor.execute(f'CREATE DATABASE "{settings.POSTGRES_DB}"')
            logger.info(f"✅ Database '{settings.POSTGRES_DB}' created successfully")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        logger.error(f"❌ Failed to create database: {e}")
        return False

def setup_database_schema():
    """Create all tables with current schema"""
    try:
        # Create engine for the project database
        engine = create_engine(settings.DATABASE_URI)
        
        logger.info("🏗️  Creating tables with current schema...")
        Base.metadata.create_all(engine)
        
        # Verify tables were created
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"✅ Created/verified tables: {', '.join(tables)}")
        
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to setup database schema: {e}")
        return False

def verify_projects_table():
    """Verify the projects table has all required columns"""
    try:
        engine = create_engine(settings.DATABASE_URI)
        
        with engine.connect() as conn:
            # Check projects table columns
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'projects'
                ORDER BY ordinal_position
            """))
            
            columns = result.fetchall()
            if not columns:
                logger.error("❌ Projects table not found")
                return False
            
            logger.info("📋 Projects table schema:")
            for col in columns:
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                default = f" DEFAULT {col[3]}" if col[3] else ""
                logger.info(f"  - {col[0]}: {col[1]} {nullable}{default}")
            
            # Check for required columns
            column_names = [col[0] for col in columns]
            required_columns = [
                'id', 'name', 'description', 'status', 'team_size', 
                'deadline', 'goal', 'industry', 'budget', 'insights', 
                'created_at', 'updated_at'
            ]
            
            missing_columns = [col for col in required_columns if col not in column_names]
            if missing_columns:
                logger.error(f"❌ Missing required columns: {missing_columns}")
                return False
            
            logger.info("✅ All required columns are present")
            
            # Check if there are any existing projects
            result = conn.execute(text("SELECT COUNT(*) FROM projects"))
            count = result.scalar()
            logger.info(f"📊 Current projects in database: {count}")
            
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to verify projects table: {e}")
        return False

def main():
    """Main function"""
    logger.info("🐘 PostgreSQL Database Setup")
    logger.info("=" * 50)
    
    # Show current configuration
    logger.info(f"Database Type: {settings.DATABASE_TYPE}")
    logger.info(f"PostgreSQL Server: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}")
    logger.info(f"Database Name: {settings.POSTGRES_DB}")
    logger.info(f"Database User: {settings.POSTGRES_USER}")
    logger.info(f"Database URI: {settings.DATABASE_URI}")
    
    if settings.DATABASE_TYPE != "postgresql":
        logger.error("❌ DATABASE_TYPE is not set to 'postgresql'")
        logger.error("💡 Please update your .env file to set DATABASE_TYPE=postgresql")
        return 1
    
    # Step 1: Check PostgreSQL connection
    logger.info("\n🔍 Step 1: Checking PostgreSQL connection...")
    if not check_postgresql_connection():
        return 1
    
    # Step 2: Create database if needed
    logger.info("\n🔍 Step 2: Creating database if needed...")
    if not create_database_if_not_exists():
        return 1
    
    # Step 3: Setup database schema
    logger.info("\n🔍 Step 3: Setting up database schema...")
    if not setup_database_schema():
        return 1
    
    # Step 4: Verify projects table
    logger.info("\n🔍 Step 4: Verifying projects table...")
    if not verify_projects_table():
        return 1
    
    logger.info("\n🎉 PostgreSQL database setup completed successfully!")
    logger.info("💡 You can now start the backend and the projects page should work")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
