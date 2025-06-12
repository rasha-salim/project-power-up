#!/usr/bin/env python
"""
Migration script to add missing columns to the documents table
"""

import asyncio
import sys
import logging
from sqlalchemy import text
from app.db.init_db_simple import AsyncSessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    """Add missing columns to documents table"""
    logger.info("Starting migration to add missing columns to documents table")
    
    # Create a database session
    db = AsyncSessionLocal()
    try:
        # Check if the column exists first
        logger.info("Checking if columns already exist")
        
        # Add progress column if it doesn't exist
        await db.execute(text("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'documents' AND column_name = 'progress'
                ) THEN 
                    ALTER TABLE documents ADD COLUMN progress TEXT DEFAULT '0';
                    RAISE NOTICE 'Added progress column to documents table';
                END IF;
            END $$;
        """))
        
        # Add doc_metadata column if it doesn't exist
        await db.execute(text("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'documents' AND column_name = 'doc_metadata'
                ) THEN 
                    ALTER TABLE documents ADD COLUMN doc_metadata JSONB;
                    RAISE NOTICE 'Added doc_metadata column to documents table';
                END IF;
            END $$;
        """))
        
        # Commit the changes
        await db.commit()
        logger.info("Migration completed successfully")
    
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        await db.rollback()
        raise
    
    finally:
        # Close the database session
        await db.close()
        logger.info("Database session closed")

if __name__ == "__main__":
    logger.info("Running migration script")
    asyncio.run(migrate())
    logger.info("Migration script completed")
