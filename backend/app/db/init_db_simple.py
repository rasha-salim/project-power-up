"""
Simplified database initialization module
"""
import os
import logging
from typing import AsyncGenerator, Generator
import chromadb
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.db.base.base_class import Base

# Configure logging
logger = logging.getLogger(__name__)

# SQLAlchemy setup using unified configuration
db_url = settings.DATABASE_URI
logger.info(f"Database URL from settings: {db_url}")

# Setup based on database type
if settings.is_postgresql:
    # For PostgreSQL, use async engine
    async_db_url = settings.async_database_uri
    logger.info(f"Using PostgreSQL with async engine: {async_db_url}")
    
    # Create the async engine with proper connection arguments
    async_engine = create_async_engine(
        async_db_url,
        echo=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
    )
    
    # Create async session factory
    AsyncSessionLocal = sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
elif settings.is_sqlite:
    # For SQLite, use regular engine (async not needed for development)
    logger.info(f"Using SQLite: {db_url}")
    
    # Create regular engine for SQLite
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=True
    )
    
    # For SQLite, we'll use regular sessions (can be adapted for async if needed)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create a simple async wrapper for SQLite if needed
    async def get_async_db_sqlite() -> AsyncGenerator[Session, None]:
        """Simple async wrapper for SQLite sessions"""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    AsyncSessionLocal = get_async_db_sqlite

else:
    raise ValueError(f"Unsupported database type: {settings.DATABASE_TYPE}")

# Global ChromaDB client
chroma_client = None

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting asynchronous database session"""
    if settings.is_postgresql:
        async with AsyncSessionLocal() as session:
            try:
                logger.debug("Created async database session")
                yield session
            except Exception as e:
                logger.error(f"Database session error: {e}")
                await session.rollback()
                raise
            finally:
                await session.close()
    else:
        # For SQLite, use the wrapper
        async for session in AsyncSessionLocal():
            yield session

def get_chroma_client():
    """Get a ChromaDB client for vector storage"""
    global chroma_client
    
    # If we already have a client, return it
    if chroma_client is not None:
        logger.info(f"Using existing ChromaDB client: {type(chroma_client)}")
        return chroma_client
    
    # Create ChromaDB directory if it doesn't exist
    chroma_dir = os.path.join(os.getcwd(), "chromadb")
    os.makedirs(chroma_dir, exist_ok=True)
    
    logger.info(f"Initializing ChromaDB client with persistent storage at {chroma_dir}")
    chroma_client = chromadb.PersistentClient(path=chroma_dir)
    logger.info(f"ChromaDB client initialized successfully: {type(chroma_client)}")
    return chroma_client

async def init_db():
    """Initialize database connections and create tables"""
    try:
        logger.info("Initializing database connections...")
        
        # Initialize ChromaDB client
        chroma_client = get_chroma_client()
        
        # Initialize collections for different document types
        try:
            # Create or get collections for different document types
            collections = [
                "project_documents",
                "technical_specs", 
                "requirements",
                "meeting_notes"
            ]
            
            for collection_name in collections:
                collection = chroma_client.get_or_create_collection(name=collection_name)
                logger.info(f"ChromaDB collection '{collection_name}' ready")
                
            logger.info("All ChromaDB collections initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing ChromaDB collections: {str(e)}")
            raise
            
        # Create database tables using async engine
        if settings.is_postgresql:
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database tables created/verified successfully")
        else:
            # For SQLite, use regular engine
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created/verified successfully")
            
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error during database initialization: {str(e)}")
        raise
