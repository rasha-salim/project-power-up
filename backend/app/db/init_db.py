import logging
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import chromadb
from app.core.config import settings
from app.db.base.base_class import Base

# Configure logging
logger = logging.getLogger(__name__)

# SQLAlchemy setup
# Get database URL from settings
db_url = str(settings.DATABASE_URI)

# Configure the engine based on database type
if db_url.startswith('sqlite'):
    # For SQLite, use the standard engine (not async)
    from sqlalchemy import create_engine
    sync_engine = create_engine(db_url, echo=True, connect_args={"check_same_thread": False})
    # Use standard session instead of async for SQLite
    from sqlalchemy.orm import sessionmaker as standard_sessionmaker
    SyncSessionLocal = standard_sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
    is_async = False
else:
    # For PostgreSQL, use async engine
    async_db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')
    async_engine = create_async_engine(async_db_url, echo=True)
    # Use async session for PostgreSQL
    AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    is_async = True

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
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Main dependency function that returns the appropriate DB session based on database type
def get_db():
    """Main dependency function that returns the appropriate DB session"""
    if is_async:
        return get_async_db
    else:
        return get_sync_db

def get_chroma_client():
    """Get ChromaDB client for vector storage"""
    global chroma_client
    if chroma_client is None:
        # Ensure the persist directory exists
        os.makedirs(settings.CHROMA_PERSIST_DIRECTORY, exist_ok=True)
        chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIRECTORY)
    return chroma_client

async def init_db():
    """Initialize database connections and create tables"""
    try:
        # Create tables if they don't exist
        if is_async:
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        else:
            Base.metadata.create_all(bind=sync_engine)
        
        logger.info("Database tables created successfully")
        
        # Initialize ChromaDB
        global chroma_client
        chroma_client = get_chroma_client()
        
        # Create collections if they don't exist
        chroma_client.get_or_create_collection("documents")
        chroma_client.get_or_create_collection("projects")
        logger.info("ChromaDB collections initialized successfully")
        
        # Create uploads directory if it doesn't exist
        os.makedirs("./uploads", exist_ok=True)
        logger.info("Upload directory created at ./uploads")
        
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise
