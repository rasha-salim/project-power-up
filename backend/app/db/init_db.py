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
    engine = create_engine(db_url, echo=True, connect_args={"check_same_thread": False})
    # Use standard session instead of async for SQLite
    from sqlalchemy.orm import sessionmaker as standard_sessionmaker
    SessionLocal = standard_sessionmaker(autocommit=False, autoflush=False, bind=engine)
    is_async = False
else:
    # For PostgreSQL, use async engine
    async_db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')
    engine = create_async_engine(async_db_url, echo=True)
    # Use async session for PostgreSQL
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    is_async = True

# ChromaDB setup
chroma_client = None

async def get_db():
    """Dependency for getting database session (works with both sync and async)"""
    if is_async:
        # For PostgreSQL (async)
        async with SessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()
    else:
        # For SQLite (sync)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

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
        # Create all tables
        if is_async:
            # For PostgreSQL (async)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        else:
            # For SQLite (sync)
            Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Initialize ChromaDB collections
        client = get_chroma_client()
        # Create collections if they don't exist
        try:
            client.get_or_create_collection("documents")
            client.get_or_create_collection("project_insights")
            logger.info("ChromaDB collections initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing ChromaDB collections: {e}")
            
        # Create upload directory if it doesn't exist
        os.makedirs(settings.UPLOAD_DIRECTORY, exist_ok=True)
        logger.info(f"Upload directory created at {settings.UPLOAD_DIRECTORY}")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
