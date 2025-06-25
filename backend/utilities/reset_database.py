#!/usr/bin/env python3
"""
Database Reset Script

This script safely resets the database by:
1. Backing up existing data (if any)
2. Dropping and recreating all tables
3. Initializing the database with the current schema

Use this when the database schema has changed and you need to update the structure.
"""

import os
import sys
import logging
import shutil
from pathlib import Path
from datetime import datetime

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.db.base.base_class import Base
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backup_sqlite_database():
    """Create a backup of the existing SQLite database"""
    if not settings.is_sqlite:
        logger.info("Not using SQLite, skipping backup")
        return None
    
    db_path = Path(settings.SQLITE_PATH)
    if not db_path.exists():
        logger.info(f"Database file {db_path} doesn't exist, no backup needed")
        return None
    
    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_suffix(f".backup_{timestamp}.db")
    
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"✅ Database backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"❌ Failed to backup database: {e}")
        return None

def reset_database():
    """Reset the database with current schema"""
    logger.info("🔄 Starting database reset...")
    
    # Create backup if using SQLite
    backup_path = backup_sqlite_database()
    
    try:
        # Create engine
        engine = create_engine(settings.DATABASE_URI)
        
        # Drop all tables
        logger.info("🗑️  Dropping all existing tables...")
        Base.metadata.drop_all(engine)
        
        # Create all tables with current schema
        logger.info("🏗️  Creating tables with current schema...")
        Base.metadata.create_all(engine)
        
        # Verify tables were created
        with engine.connect() as conn:
            if settings.is_postgresql:
                result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """))
            else:  # SQLite
                result = conn.execute(text("""
                    SELECT name 
                    FROM sqlite_master 
                    WHERE type='table'
                """))
            
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"✅ Created tables: {', '.join(tables)}")
        
        engine.dispose()
        logger.info("🎉 Database reset completed successfully!")
        
        if backup_path:
            logger.info(f"💡 Your old data was backed up to: {backup_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database reset failed: {e}")
        return False

def verify_schema():
    """Verify the database schema matches the models"""
    logger.info("🔍 Verifying database schema...")
    
    try:
        engine = create_engine(settings.DATABASE_URI)
        
        with engine.connect() as conn:
            # Check if projects table has the expected columns
            if settings.is_postgresql:
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'projects'
                    ORDER BY ordinal_position
                """))
            else:  # SQLite
                result = conn.execute(text("PRAGMA table_info(projects)"))
                # SQLite PRAGMA returns: cid, name, type, notnull, dflt_value, pk
                # We want the 'name' column (index 1)
            
            if settings.is_postgresql:
                columns = [row[0] for row in result.fetchall()]
            else:
                columns = [row[1] for row in result.fetchall()]  # Get column names from PRAGMA
            
            expected_columns = [
                'id', 'name', 'description', 'status', 'team_size', 
                'deadline', 'goal', 'industry', 'budget', 'insights', 
                'created_at', 'updated_at'
            ]
            
            missing_columns = [col for col in expected_columns if col not in columns]
            extra_columns = [col for col in columns if col not in expected_columns]
            
            if missing_columns:
                logger.error(f"❌ Missing columns: {missing_columns}")
                return False
            
            if extra_columns:
                logger.warning(f"⚠️  Extra columns: {extra_columns}")
            
            logger.info(f"✅ Schema verification passed. Columns: {', '.join(columns)}")
            return True
        
    except Exception as e:
        logger.error(f"❌ Schema verification failed: {e}")
        return False

def main():
    """Main function"""
    logger.info("🚀 Database Reset Utility")
    logger.info("=" * 50)
    
    # Show current configuration
    logger.info(f"Database Type: {settings.DATABASE_TYPE}")
    logger.info(f"Database URI: {settings.DATABASE_URI}")
    
    # Ask for confirmation
    print("\n⚠️  WARNING: This will delete all existing data in the database!")
    if input("Do you want to continue? (yes/no): ").lower() != 'yes':
        logger.info("Operation cancelled by user")
        return 0
    
    # Reset database
    if not reset_database():
        logger.error("Database reset failed")
        return 1
    
    # Verify schema
    if not verify_schema():
        logger.error("Schema verification failed")
        return 1
    
    logger.info("🎉 Database reset completed successfully!")
    logger.info("💡 You can now start the backend and create new projects")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
