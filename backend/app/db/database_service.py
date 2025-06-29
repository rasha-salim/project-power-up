"""
Unified Database Service
Provides compatibility layer for migration from asyncpg connection pool to SQLAlchemy AsyncSession

This service allows both patterns to coexist during the migration process.
See docs/database-migration-plan.md for migration details.
"""
import logging
from typing import AsyncGenerator, Optional, Dict, Any, List
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.init_db_simple import AsyncSessionLocal, get_async_db
from app.db.connection_pool import get_pool

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Unified database access service providing compatibility between
    asyncpg connection pool and SQLAlchemy AsyncSession patterns
    """
    
    @staticmethod
    async def get_session() -> AsyncGenerator[AsyncSession, None]:
        """
        Get SQLAlchemy AsyncSession - PREFERRED METHOD for new code
        
        Usage:
            async with DatabaseService.get_session() as session:
                result = await session.execute(text("SELECT * FROM projects"))
        """
        async for session in get_async_db():
            yield session
    
    @staticmethod
    async def get_raw_connection():
        """
        Get raw asyncpg connection for legacy code during migration
        
        Usage:
            conn = await DatabaseService.get_raw_connection()
            try:
                result = await conn.fetch("SELECT * FROM projects")
            finally:
                await DatabaseService.release_raw_connection(conn)
        """
        pool = await get_pool()
        if not pool:
            raise Exception("Database connection pool not available")
        return await pool.acquire()
    
    @staticmethod
    async def release_raw_connection(conn):
        """Release raw connection back to pool"""
        pool = await get_pool()
        if pool:
            await pool.release(conn)
    
    @staticmethod
    @asynccontextmanager
    async def raw_connection():
        """
        Context manager for raw connections
        
        Usage:
            async with DatabaseService.raw_connection() as conn:
                result = await conn.fetch("SELECT * FROM projects")
        """
        conn = await DatabaseService.get_raw_connection()
        try:
            yield conn
        finally:
            await DatabaseService.release_raw_connection(conn)
    
    @staticmethod
    async def execute_raw_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute raw SQL query using SQLAlchemy (migration helper)
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of dictionaries representing rows
            
        Usage:
            result = await DatabaseService.execute_raw_query(
                "SELECT * FROM projects WHERE status = :status",
                {"status": "active"}
            )
        """
        async with DatabaseService.get_session() as session:
            result = await session.execute(text(query), params or {})
            rows = result.fetchall()
            # Convert to list of dictionaries for compatibility
            return [dict(row._mapping) for row in rows]
    
    @staticmethod
    async def execute_raw_query_one(query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Execute raw SQL query and return first result using SQLAlchemy
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Dictionary representing first row or None
        """
        async with DatabaseService.get_session() as session:
            result = await session.execute(text(query), params or {})
            row = result.fetchone()
            return dict(row._mapping) if row else None
    
    @staticmethod
    async def execute_raw_insert(query: str, params: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Execute raw INSERT query and return ID if available
        
        Args:
            query: INSERT SQL query string
            params: Query parameters
            
        Returns:
            ID of inserted record if available
        """
        async with DatabaseService.get_session() as session:
            try:
                result = await session.execute(text(query), params or {})
                await session.commit()
                
                # Try to get the ID if it's a returning query
                if result.returns_rows:
                    row = result.fetchone()
                    if row and hasattr(row, '_mapping'):
                        row_dict = dict(row._mapping)
                        # Look for common ID field names
                        for id_field in ['id', 'uuid', 'document_id', 'project_id']:
                            if id_field in row_dict:
                                return str(row_dict[id_field])
                
                return None
            except Exception as e:
                await session.rollback()
                logger.error(f"Error executing insert query: {e}")
                raise
    
    @staticmethod
    async def migrate_asyncpg_query(
        asyncpg_query: str, 
        params: Optional[List] = None,
        return_one: bool = False
    ) -> Any:
        """
        Helper function to migrate asyncpg queries to SQLAlchemy
        
        Args:
            asyncpg_query: Original asyncpg query string
            params: Positional parameters (converted to named parameters)
            return_one: Whether to return first row only
            
        Returns:
            Query results in compatible format
        """
        # Convert positional parameters to named parameters
        named_params = {}
        converted_query = asyncpg_query
        
        if params:
            for i, param in enumerate(params):
                param_name = f"param_{i}"
                named_params[param_name] = param
                # Replace $1, $2, etc. with :param_0, :param_1, etc.
                converted_query = converted_query.replace(f"${i+1}", f":{param_name}")
        
        if return_one:
            return await DatabaseService.execute_raw_query_one(converted_query, named_params)
        else:
            return await DatabaseService.execute_raw_query(converted_query, named_params)


class MigrationHelper:
    """
    Helper class for common migration patterns
    """
    
    @staticmethod
    def convert_asyncpg_to_sqlalchemy(asyncpg_code: str) -> str:
        """
        Provide guidance for converting asyncpg code to SQLAlchemy
        (This is a documentation helper, not actual code conversion)
        """
        return f"""
        # Original asyncpg pattern:
        {asyncpg_code}
        
        # Converted SQLAlchemy pattern:
        async with DatabaseService.get_session() as session:
            # Replace conn.fetch() with session.execute()
            # Replace $1, $2 with :param_name
            # Use text() for raw SQL
            result = await session.execute(text("your_query"), params)
            rows = result.fetchall()
        """
    
    @staticmethod
    def log_migration_status(file_path: str, status: str):
        """Log migration status for tracking"""
        logger.info(f"Migration status for {file_path}: {status}")


# Convenience exports for backward compatibility
get_database_session = DatabaseService.get_session
execute_query = DatabaseService.execute_raw_query
execute_query_one = DatabaseService.execute_raw_query_one