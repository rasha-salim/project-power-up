from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
import sys
import os
from app.core.config import settings, validation_success
from app.api.routes import api_router
from app.db.init_db_simple import init_db
from app.db.connection_pool import initialize_pool, close_pool  # TODO: Remove after migration to SQLAlchemy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Intelligent Project Planning System API",
    version="0.1.0",
)

# Add CORS middleware with explicit WebSocket support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Add HTTPS redirect middleware only in production (Railway)
if settings.ENVIRONMENT == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
    logger.info("HTTPS redirect middleware enabled for production environment")
else:
    logger.info(f"HTTPS redirect middleware disabled for {settings.ENVIRONMENT} environment")

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Debug: List all registered routes
logger.info("=== Registered Routes ===")
for route in app.routes:
    if hasattr(route, 'path'):
        logger.info(f"Route: {route.path} - Type: {type(route).__name__}")
logger.info("=== End Routes ===")

@app.on_event("startup")
async def startup_event():
    """Initialize database connections and other startup tasks"""
    logger.info("Starting up application...")
    
    # Check if we're in Railway environment
    railway_env = os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID") or os.getenv("RAILWAY_SERVICE_ID")
    database_url = os.getenv("DATABASE_URL")
    
    if railway_env:
        logger.info(f"🚂 Railway environment detected: {railway_env}")
        logger.info(f"Railway DATABASE_URL present: {'✓' if database_url else '✗'}")
    
    # Validate configuration with Railway-specific handling
    if not validation_success:
        logger.error("Configuration validation failed")
        
        # Get detailed validation info for debugging
        validation_result = settings.validate_required_settings()
        logger.error("Validation errors:")
        for error in validation_result.get("errors", []):
            logger.error(f"  - {error}")
        
        # In Railway environment, be more permissive if we have DATABASE_URL
        if railway_env and database_url:
            logger.warning("⚠️ Railway environment with DATABASE_URL detected - proceeding despite validation warnings")
            logger.info("🚂 Railway database configuration will override local settings")
            
            # Test if we can actually connect to the database
            try:
                # Quick connection test using DATABASE_URL
                logger.info("Testing Railway database connection...")
                import asyncpg
                # Parse DATABASE_URL for connection test
                parsed_url = database_url
                if parsed_url.startswith("postgres://"):
                    parsed_url = parsed_url.replace("postgres://", "postgresql://")
                
                # Try a quick connection
                import asyncio
                conn = await asyncpg.connect(parsed_url)
                await conn.close()
                logger.info("✅ Railway database connection successful!")
                
            except Exception as db_error:
                logger.error(f"❌ Railway database connection failed: {db_error}")
                logger.error("This likely means the PostgreSQL service is not properly attached to Railway")
                logger.error("Please check Railway dashboard and ensure PostgreSQL is connected")
                sys.exit(1)
        else:
            logger.error("❌ Not a Railway environment or missing DATABASE_URL - configuration validation failed")
            if not railway_env:
                logger.error("💡 For local development, ensure all required environment variables are set")
            else:
                logger.error("💡 For Railway deployment, ensure PostgreSQL service is added and connected")
            sys.exit(1)
    
    # Initialize database tables and schema
    await init_db()
    
    # Initialize PostgreSQL connection pool
    # TODO: MIGRATION PRIORITY 3 - Remove connection pool after migration to SQLAlchemy
    # See docs/database-migration-plan.md for details
    pool_initialized = await initialize_pool()
    if pool_initialized:
        logger.info("PostgreSQL connection pool initialized")
        
        # Run migrations
        try:
            from app.db.migrations.add_progress_column import run_migration
            migration_success = await run_migration()
            if migration_success:
                logger.info("Database migrations completed successfully")
            else:
                logger.warning("Database migrations failed")
        except Exception as e:
            logger.error(f"Error running migrations: {str(e)}")
    else:
        logger.warning("Failed to initialize PostgreSQL connection pool")

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections and perform cleanup"""
    logger.info("Shutting down application...")
    
    # Close PostgreSQL connection pool
    await close_pool()
    logger.info("Application shutdown complete")

@app.get("/")
async def root():
    """Root endpoint for health check"""
    return {"message": "Intelligent Project Planning System API is running"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
