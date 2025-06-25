#!/usr/bin/env python3
"""
Add Status Column to Projects Table

This script adds the missing 'status' column to the projects table in SQLite.
This is a safer approach than recreating the entire database.
"""

import os
import sys
import logging
import sqlite3
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_status_column():
    """Add status column to projects table if it doesn't exist"""
    
    # For SQLite, we need to use the actual file path
    if settings.DATABASE_TYPE == "sqlite":
        db_path = settings.SQLITE_PATH
        logger.info(f"Using SQLite database: {db_path}")
    else:
        logger.error("This script is only for SQLite databases")
        return False
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if status column already exists
        cursor.execute("PRAGMA table_info(projects)")
        columns = [row[1] for row in cursor.fetchall()]  # Get column names
        
        if 'status' in columns:
            logger.info("✅ Status column already exists")
            conn.close()
            return True
        
        logger.info("📝 Adding status column to projects table...")
        
        # Add the status column with default value
        cursor.execute("""
            ALTER TABLE projects 
            ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'
        """)
        
        # Update any existing projects to have 'draft' status
        cursor.execute("""
            UPDATE projects 
            SET status = 'draft' 
            WHERE status IS NULL OR status = ''
        """)
        
        conn.commit()
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(projects)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'status' in columns:
            logger.info("✅ Status column added successfully")
            logger.info(f"Current columns: {', '.join(columns)}")
            
            # Show current projects
            cursor.execute("SELECT id, name, status FROM projects")
            projects = cursor.fetchall()
            if projects:
                logger.info(f"📊 Updated {len(projects)} existing projects with 'draft' status")
                for project in projects:
                    logger.info(f"  - {project[1]} (ID: {project[0][:8]}...) -> {project[2]}")
            else:
                logger.info("📊 No existing projects found")
            
            conn.close()
            return True
        else:
            logger.error("❌ Failed to add status column")
            conn.close()
            return False
            
    except Exception as e:
        logger.error(f"❌ Error adding status column: {e}")
        return False

def main():
    """Main function"""
    logger.info("🔧 Adding Status Column to Projects Table")
    logger.info("=" * 50)
    
    # Show current configuration
    logger.info(f"Database Type: {settings.DATABASE_TYPE}")
    
    if settings.DATABASE_TYPE != "sqlite":
        logger.error("This script only works with SQLite databases")
        logger.info("If you're using PostgreSQL, you need to run a proper migration")
        return 1
    
    logger.info(f"SQLite Path: {settings.SQLITE_PATH}")
    
    # Add the column
    if add_status_column():
        logger.info("🎉 Status column added successfully!")
        logger.info("💡 You can now start the backend and the projects page should work")
        return 0
    else:
        logger.error("❌ Failed to add status column")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
