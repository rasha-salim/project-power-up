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
    logger.info(f"Using PostgreSQL with async engine: {async_db_url[:50]}...")
    
    # Check if we're in Railway environment for specific connection settings
    railway_env = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID") or os.getenv("RAILWAY_SERVICE_ID")
    
    # Railway-specific connection arguments
    connect_args = {}
    if railway_env:
        logger.info("🚂 Railway environment detected - configuring SSL and connection settings")
        connect_args = {
            "server_settings": {
                "jit": "off",  # Disable JIT for Railway compatibility
            },
            "ssl": "require",  # Railway requires SSL
            "command_timeout": 60,
        }
    else:
        logger.info("Local environment detected - using standard connection settings")
        connect_args = {
            "server_settings": {
                "jit": "off"
            }
        }
    
    # Create the async engine with proper connection arguments
    async_engine = create_async_engine(
        async_db_url,
        echo=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
        connect_args=connect_args
    )
    
    logger.info(f"Async engine created with connect_args: {connect_args}")
    
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

class AsyncDatabaseContextManager:
    """Simple async context manager that uses the existing get_async_db generator"""
    def __init__(self):
        self.db_generator = None
        self.session = None
    
    async def __aenter__(self):
        """Get database session from generator"""
        self.db_generator = get_async_db()
        self.session = await self.db_generator.__anext__()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Let the generator handle cleanup"""
        if self.db_generator:
            try:
                await self.db_generator.__anext__()
            except StopAsyncIteration:
                # This is expected when the generator is exhausted
                pass
            except Exception as cleanup_error:
                logger.error(f"Error during database session cleanup: {cleanup_error}")
        
        self.session = None
        self.db_generator = None

def get_db_context():
    """Get database session as async context manager"""
    return AsyncDatabaseContextManager()

def get_chroma_client():
    """Get a ChromaDB client for vector storage"""
    global chroma_client
    
    # If we already have a client, return it
    if chroma_client is not None:
        logger.info(f"Using existing ChromaDB client: {type(chroma_client)}")
        return chroma_client
    
    # Use the configured ChromaDB directory from settings
    chroma_dir = settings.CHROMA_PERSIST_DIRECTORY
    logger.info(f"🗂️  ChromaDB Configuration:")
    logger.info(f"   - Settings directory: {chroma_dir}")
    logger.info(f"   - Environment variable: {os.getenv('CHROMA_PERSIST_DIRECTORY')}")
    logger.info(f"   - Current working directory: {os.getcwd()}")
    logger.info(f"   - Absolute path: {os.path.abspath(chroma_dir)}")
    
    # Create ChromaDB directory if it doesn't exist
    try:
        logger.info(f"📁 Creating/verifying ChromaDB directory: {chroma_dir}")
        os.makedirs(chroma_dir, exist_ok=True)
        
        # Check directory properties
        if os.path.exists(chroma_dir):
            stat_info = os.stat(chroma_dir)
            logger.info(f"✅ ChromaDB directory verified:")
            logger.info(f"   - Exists: ✓")
            logger.info(f"   - Is directory: {os.path.isdir(chroma_dir)}")
            logger.info(f"   - Permissions: {oct(stat_info.st_mode)[-3:]}")
            logger.info(f"   - Readable: {os.access(chroma_dir, os.R_OK)}")
            logger.info(f"   - Writable: {os.access(chroma_dir, os.W_OK)}")
            
            # List existing contents
            contents = os.listdir(chroma_dir)
            logger.info(f"   - Contents: {len(contents)} items")
            if contents:
                logger.info(f"   - Files: {contents[:5]}")  # First 5 items
        
        # Test write permissions
        test_file = os.path.join(chroma_dir, ".write_test")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            logger.info(f"✅ Write test successful")
        except Exception as write_error:
            logger.error(f"❌ Write test failed: {write_error}")
            
    except Exception as e:
        logger.error(f"❌ Failed to create ChromaDB directory {chroma_dir}: {e}")
        # Fallback to a local directory if volume mount fails
        chroma_dir = os.path.join(os.getcwd(), "chromadb_fallback")
        os.makedirs(chroma_dir, exist_ok=True)
        logger.warning(f"⚠️  Using fallback ChromaDB directory: {chroma_dir}")
    
    logger.info(f"🚀 Initializing ChromaDB client with persistent storage at {chroma_dir}")
    chroma_client = chromadb.PersistentClient(path=chroma_dir)
    logger.info(f"✅ ChromaDB client initialized successfully: {type(chroma_client)}")
    
    # Log the actual storage location
    logger.info(f"📊 ChromaDB will persist data to: {os.path.abspath(chroma_dir)}")
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
            logger.info("🔧 Attempting to connect to PostgreSQL database...")
            logger.info(f"Database URL being used: {settings.async_database_uri[:50]}...")
            
            # Check Railway environment variables for debugging
            railway_env = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID") or os.getenv("RAILWAY_SERVICE_ID")
            database_url = os.getenv("DATABASE_URL")
            
            if railway_env:
                logger.info(f"🚂 Railway Environment: {railway_env}")
                logger.info(f"🚂 DATABASE_URL available: {'✓' if database_url else '✗'}")
                if database_url:
                    logger.info(f"🚂 DATABASE_URL starts with: {database_url[:30]}...")
            
            try:
                # Test basic connection first
                logger.info("Testing basic database connection...")
                async with async_engine.connect() as conn:
                    result = await conn.execute(text("SELECT 1"))
                    test_result = result.scalar()
                    logger.info(f"✅ Basic connection test successful: {test_result}")
                
                # Now create tables
                logger.info("Creating/verifying database tables...")
                async with async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                    logger.info("✅ Database tables created/verified successfully")
                    
            except Exception as db_error:
                logger.error(f"❌ PostgreSQL connection failed: {db_error}")
                logger.error(f"Error type: {type(db_error).__name__}")
                
                # Provide specific debugging for Railway
                if railway_env:
                    logger.error("🚂 Railway PostgreSQL Connection Troubleshooting:")
                    logger.error("1. Ensure PostgreSQL service is added to Railway project")
                    logger.error("2. Verify database service is connected to web service")
                    logger.error("3. Check Railway dashboard for database status")
                    logger.error("4. Verify DATABASE_URL environment variable is set")
                    
                    # Try to parse the DATABASE_URL for debugging
                    if database_url:
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(database_url)
                            logger.error(f"🔍 Database host: {parsed.hostname}")
                            logger.error(f"🔍 Database port: {parsed.port}")
                            logger.error(f"🔍 Database name: {parsed.path[1:] if parsed.path else 'N/A'}")
                            logger.error(f"🔍 Database user: {parsed.username}")
                        except Exception as parse_error:
                            logger.error(f"Could not parse DATABASE_URL: {parse_error}")
                
                raise
        else:
            # For SQLite, use regular engine
            logger.info("Creating SQLite database tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables created/verified successfully")
            
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error during database initialization: {str(e)}")
        raise
