import asyncio
import logging
from app.db.init_db_simple import init_db
from app.db.connection_pool import initialize_pool, close_pool

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_startup():
    try:
        logger.info("Testing database initialization...")
        await init_db()
        logger.info("Database initialization completed")
        
        logger.info("Testing connection pool...")
        pool_initialized = await initialize_pool()
        if pool_initialized:
            logger.info("Connection pool initialized successfully")
        else:
            logger.error("Failed to initialize connection pool")
            
        logger.info("Testing migration...")
        try:
            from app.db.migrations.add_progress_column import run_migration
            migration_success = await run_migration()
            if migration_success:
                logger.info("Migration completed successfully")
            else:
                logger.error("Migration failed")
        except Exception as e:
            logger.error(f"Migration error: {str(e)}")
            
        await close_pool()
        logger.info("Test completed successfully")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_startup())
