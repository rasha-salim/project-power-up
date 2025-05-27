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
    
    try:
        # Create connection pool
        pg_pool = await asyncpg.create_pool(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
            min_size=5,
            max_size=20
        )
        
        # Test connection
        async with pg_pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            logger.info(f"Connected to PostgreSQL: {version}")
            
        return True
    except Exception as e:
        logger.error(f"Error initializing PostgreSQL connection pool: {str(e)}")
        logger.exception(e)
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

def get_pool():
    """Get the connection pool"""
    global pg_pool
    return pg_pool
