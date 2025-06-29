"""
Migration script to add progress column to documents table

TODO: MIGRATION PRIORITY 2 - Migrate to SQLAlchemy AsyncSession for consistency
Currently uses asyncpg connection pool - target for Phase 2 migration
See docs/database-migration-plan.md for details
"""
import asyncio
import logging
from app.db.connection_pool import get_pool  # TODO: Replace with SQLAlchemy AsyncSession

logger = logging.getLogger(__name__)

async def run_migration():
    """Add progress column to documents table"""
    logger.info("Running migration: Adding progress column to documents table")
    
    # Get connection pool - properly await the async function
    pg_pool = await get_pool()
    if not pg_pool:
        logger.error("Database connection pool not available")
        return False
    
    try:
        async with pg_pool.acquire() as conn:
            # Check if the column already exists
            column_exists = await conn.fetchval(
                """SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'documents' AND column_name = 'progress'
                )"""
            )
            
            if not column_exists:
                # Add progress column
                await conn.execute(
                    """ALTER TABLE documents 
                    ADD COLUMN IF NOT EXISTS progress TEXT DEFAULT '0'"""
                )
                logger.info("Added progress column to documents table")
            else:
                logger.info("Progress column already exists in documents table")
                
        return True
    except Exception as e:
        logger.error(f"Error adding progress column: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(run_migration())
