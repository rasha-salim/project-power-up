import os
import logging
from typing import AsyncGenerator, Generator
import chromadb
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Import the Base class for SQLAlchemy models
from app.db.base.base_class import Base

# Import all models to ensure they are registered with the Base metadata
from app.models.project import Project

# Configure logging
logger = logging.getLogger(__name__)

# SQLAlchemy setup
# Get database URL from settings
db_url = str(settings.DATABASE_URI)
logger.info(f"Database URL from settings: {db_url}")

# Configure the engine based on database type
if db_url.startswith('sqlite'):
    # For SQLite, use the standard engine (not async)
    from sqlalchemy import create_engine
    sync_engine = create_engine(db_url, echo=True, connect_args={"check_same_thread": False})
    # Use standard session instead of async for SQLite
    from sqlalchemy.orm import sessionmaker as standard_sessionmaker
    SyncSessionLocal = standard_sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
    is_async = False
    logger.info("Using SQLite database with synchronous engine")
else:
    # For PostgreSQL, use async engine
    async_db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')
    logger.info(f"Using PostgreSQL with async engine: {async_db_url}")
    
    # Create the async engine with proper connection arguments
    async_engine = create_async_engine(
        async_db_url,
        echo=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800
    )
    
    # Use async session for PostgreSQL
    AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    is_async = True
    logger.info("PostgreSQL async engine and session factory created")

# ChromaDB setup
chroma_client = None

# Create two separate dependency functions for sync and async DB access
def get_sync_db():
    """Dependency for getting synchronous database session"""
    session = SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()

async def get_async_db():
    """Dependency for getting asynchronous database session"""
    logger.debug("Creating new async database session")
    try:
        async with AsyncSessionLocal() as session:
            logger.debug("Yielding async database session")
            yield session
    except Exception as e:
        logger.error(f"Error in async database session: {str(e)}")
        raise
    finally:
        logger.debug("Async database session closed")

# Main dependency function that returns the appropriate DB session based on database type
def get_db():
    """Main dependency function that returns the appropriate DB session"""
    # This function should directly yield the session, not return another function
    if is_async:
        return get_async_db()
    else:
        return get_sync_db()

# Mock ChromaDB Collection class
class MockChromaCollection:
    """Mock implementation of ChromaDB Collection to avoid errors"""
    
    def __init__(self, name):
        self.name = name
        logger.info(f"Created mock ChromaDB collection: {name}")
    
    def add(self, ids, documents, metadatas=None, **kwargs):
        """Mock add method that logs but doesn't actually store data"""
        logger.info(f"Mock add to collection {self.name}: {len(ids)} documents")
        return True
    
    def query(self, query_texts, where=None, n_results=10, **kwargs):
        """Mock query method that returns empty results"""
        logger.info(f"Mock query on collection {self.name}: {query_texts}")
        return {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }
    
    def get(self, where=None, **kwargs):
        """Mock get method that returns empty results"""
        logger.info(f"Mock get on collection {self.name}")
        return {
            "ids": [],
            "documents": [],
            "metadatas": [],
            "embeddings": []
        }

# Mock ChromaDB Client class
class MockChromaClient:
    """Mock implementation of ChromaDB Client to avoid errors"""
    
    def __init__(self):
        self.collections = {}
        logger.info("Created mock ChromaDB client")
    
    def get_or_create_collection(self, name):
        """Get or create a mock collection"""
        if name not in self.collections:
            self.collections[name] = MockChromaCollection(name)
            logger.info(f"Created new mock collection: {name}")
        return self.collections[name]
    
    def get_collection(self, name):
        """Get a mock collection, creating it if it doesn't exist"""
        return self.get_or_create_collection(name)

def get_chroma_client():
    """Get a mock ChromaDB client for vector storage"""
    global chroma_client
    try:
        logger.info("Getting ChromaDB client (mock implementation)")
        if chroma_client is None:
            logger.info("Initializing new mock ChromaDB client")
            chroma_client = MockChromaClient()
            logger.info(f"Mock ChromaDB client initialized: {type(chroma_client)}")
        else:
            logger.info(f"Using existing ChromaDB client: {type(chroma_client)}")
        return chroma_client
    except Exception as e:
        logger.error(f"Error getting ChromaDB client: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Return a new mock client as fallback
        return MockChromaClient()

async def init_db():
    """Initialize database connections and create tables"""
    try:
        # Check if tables exist before creating them
        logger.info("Checking if tables exist and creating them if needed")
        
        # Import all models to ensure they are registered with Base.metadata
        from app.models.project import Project
        
        # Log the tables that will be created
        table_names = [table.name for table in Base.metadata.sorted_tables]
        logger.info(f"Tables to be created/checked: {table_names}")
        
        # Create tables if they don't exist
        if is_async:
            logger.info("Using async engine to create tables")
            async with async_engine.begin() as conn:
                # Create tables without dropping existing ones
                await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))
        else:
            logger.info("Using sync engine to create tables")
            Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        
        logger.info("Database tables created or verified successfully")
        
        # Initialize mock ChromaDB client
        global chroma_client
        chroma_client = get_chroma_client()
        logger.info("Using mock ChromaDB implementation for vector storage")
        
        # Create mock collections
        chroma_client.get_or_create_collection("documents")
        chroma_client.get_or_create_collection("projects")
        chroma_client.get_or_create_collection("project_insights")
        logger.info("Mock ChromaDB collections initialized successfully")
        
        # Create uploads directory if it doesn't exist
        os.makedirs("./uploads", exist_ok=True)
        logger.info("Upload directory created at ./uploads")
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Don't re-raise the exception to allow the app to start even if there are issues
        logger.warning("Continuing despite database initialization errors")
