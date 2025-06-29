from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
import sys
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
    
    # Validate configuration
    if not validation_success:
        logger.error("Configuration validation failed")
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
