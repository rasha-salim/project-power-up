"""
Simplified database initialization module
"""
import os
import logging
from typing import AsyncGenerator, Generator
import chromadb
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.base.base_class import Base

# Configure logging
logger = logging.getLogger(__name__)

# SQLAlchemy setup
# Get database URL from settings
db_url = str(settings.DATABASE_URI)
logger.info(f"Database URL from settings: {db_url}")

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
logger.info("PostgreSQL async engine and session factory created")

# ChromaDB setup
chroma_client = None

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
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
    """Get a ChromaDB client for vector storage, preferring real client but falling back to mock if needed"""
    global chroma_client
    
    # If we already have a client, return it
    if chroma_client is not None:
        # Check if it's already a mock client
        if isinstance(chroma_client, MockChromaClient):
            logger.info("Using existing mock ChromaDB client")
        else:
            logger.info(f"Using existing real ChromaDB client: {type(chroma_client)}")
        return chroma_client
    
    # Try to create a real ChromaDB client first
    try:
        # Create ChromaDB directory if it doesn't exist
        chroma_dir = os.path.join(os.getcwd(), "chromadb")
        os.makedirs(chroma_dir, exist_ok=True)
        
        logger.info(f"Initializing new real ChromaDB client with persistent storage at {chroma_dir}")
        chroma_client = chromadb.PersistentClient(path=chroma_dir)
        logger.info(f"Real ChromaDB client initialized successfully: {type(chroma_client)}")
        return chroma_client
    except Exception as e:
        logger.error(f"Error initializing real ChromaDB client: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Fall back to mock client if real client fails
        logger.warning("Falling back to mock ChromaDB client due to initialization error")
        chroma_client = MockChromaClient()
        return chroma_client

async def init_db():
    """Initialize database connections and create tables"""
    try:
        # We're connecting to an existing database, so we don't need to create tables
        logger.info("Using existing PostgreSQL database tables")
        
        # Initialize ChromaDB client (real or mock depending on what's available)
        global chroma_client
        chroma_client = get_chroma_client()
        
        # Initialize document collections
        collection_names = ["documents", "projects", "project_insights"]
        try:
            # Get or create all necessary collections
            if isinstance(chroma_client, MockChromaClient):
                # For mock client
                for name in collection_names:
                    chroma_client.get_or_create_collection(name)
                logger.info("All mock ChromaDB collections initialized successfully")
            else:
                # For real client
                for name in collection_names:
                    chroma_client.get_or_create_collection(name=name)
                logger.info("All real ChromaDB collections initialized successfully")
        except Exception as coll_error:
            logger.error(f"Error initializing ChromaDB collections: {str(coll_error)}")
            logger.warning("Some document search features may not work properly")
        
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
