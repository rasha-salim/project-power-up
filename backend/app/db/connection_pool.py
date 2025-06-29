"""
PostgreSQL Connection Pool
Provides a global connection pool for PostgreSQL database access
"""
import logging
import asyncpg
from typing import Optional
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Global connection pool
pg_pool: Optional[asyncpg.Pool] = None

async def initialize_pool():
    """Initialize the PostgreSQL connection pool"""
    global pg_pool
    
    # If pool already exists, return it
    if pg_pool is not None:
        logger.info("Using existing PostgreSQL connection pool")
        return True
    
    try:
        # Log connection details (without password)
        logger.info(f"Initializing PostgreSQL connection pool with settings:")
        logger.info(f"  Host: {settings.POSTGRES_SERVER}")
        logger.info(f"  Port: {settings.POSTGRES_PORT}")
        logger.info(f"  User: {settings.POSTGRES_USER}")
        logger.info(f"  Database: {settings.POSTGRES_DB}")
        
        # Create connection pool with retry logic
        for attempt in range(3):
            try:
                pg_pool = await asyncpg.create_pool(
                    host=settings.POSTGRES_SERVER,
                    port=settings.POSTGRES_PORT,
                    user=settings.POSTGRES_USER,
                    password=settings.POSTGRES_PASSWORD,
                    database=settings.POSTGRES_DB,
                    min_size=5,
                    max_size=20,
                    command_timeout=60,
                    timeout=10
                )
                
                # Test connection
                async with pg_pool.acquire() as conn:
                    version = await conn.fetchval("SELECT version()")
                    logger.info(f"Connected to PostgreSQL: {version}")
                    
                    # List tables to verify connection
                    tables = await conn.fetch(
                        """SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public';"""
                    )
                    table_names = [table['table_name'] for table in tables]
                    logger.info(f"Available tables: {table_names}")
                    
                return True
                
            except Exception as e:
                logger.warning(f"Connection attempt {attempt+1} failed: {str(e)}")
                if pg_pool is not None:
                    await pg_pool.close()
                    pg_pool = None
                
                if attempt == 2:  # Last attempt
                    raise
                
                import asyncio
                await asyncio.sleep(1)  # Wait before retrying
                
    except Exception as e:
        logger.error(f"Error initializing PostgreSQL connection pool: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        pg_pool = None
        return False

async def close_pool():
    """Close the PostgreSQL connection pool"""
    global pg_pool
    
    if pg_pool:
        await pg_pool.close()
        logger.info("PostgreSQL connection pool closed")

async def get_connection():
    """Get a connection from the pool"""
    global pg_pool
    
    if not pg_pool:
        success = await initialize_pool()
        if not success:
            raise Exception("PostgreSQL connection pool not available")
    
    return await pg_pool.acquire()

async def release_connection(conn):
    """Release a connection back to the pool"""
    await pg_pool.release(conn)

async def get_pool():
    """Get the connection pool, initializing it if necessary"""
    global pg_pool
    
    if pg_pool is None:
        logger.info("Connection pool not initialized, attempting to initialize")
        success = await initialize_pool()
        if not success:
            logger.error("Failed to initialize connection pool")
            return None
    
    return pg_pool
