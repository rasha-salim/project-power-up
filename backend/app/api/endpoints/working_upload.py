"""
Working Document Upload Endpoint
A simplified version of the standalone upload server integrated into the main application
"""
import os
import uuid
import logging
import asyncpg
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, BackgroundTasks, status

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Response models
class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    message: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# Configuration
UPLOAD_DIRECTORY = "./uploads"
PG_HOST = "localhost"
PG_PORT = "5432"
PG_USER = "postgres"
PG_PASSWORD = "adam15"  # Use your actual password
PG_DATABASE = "project_planning"

# Global connection pool
pg_pool = None

@router.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global pg_pool
    
    logger.info("Initializing services...")
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
    logger.info(f"Upload directory initialized: {UPLOAD_DIRECTORY}")
    
    # Create connection pool
    try:
        pg_pool = await asyncpg.create_pool(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            database=PG_DATABASE,
            min_size=2,
            max_size=10
        )
        
        # Test connection
        async with pg_pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            logger.info(f"Connected to PostgreSQL: {version}")
            
            # Create documents table if it doesn't exist
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS working_documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                content_type TEXT,
                status TEXT NOT NULL,
                project_id TEXT,
                description TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            """)
            logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        logger.exception(e)
        pg_pool = None

@router.on_event("shutdown")
async def shutdown_event():
    """Close services on shutdown"""
    global pg_pool
    
    logger.info("Shutting down services...")
    
    # Close connection pool
    if pg_pool:
        await pg_pool.close()
        logger.info("Database connection pool closed")

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    global pg_pool
    
    # Check database connection
    db_status = "ok" if pg_pool else "failed"
    
    # Check upload directory
    storage_status = "ok" if os.path.exists(UPLOAD_DIRECTORY) else "failed"
    
    # All services ready
    all_ready = all([
        db_status == "ok",
        storage_status == "ok"
    ])
    
    return {
        "database": db_status,
        "storage": storage_status,
        "all_ready": all_ready
    }

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """
    Upload a document
    """
    global pg_pool
    
    # Check if services are ready
    if not pg_pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available"
        )
    
    try:
        # Validate file type
        allowed_extensions = [".pdf", ".docx", ".txt"]
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Read file content
        content = await file.read()
        
        # Save file to disk
        file_path = os.path.join(UPLOAD_DIRECTORY, f"{document_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"File saved: {file_path}")
        
        # Determine content type
        content_type_map = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain"
        }
        content_type = content_type_map.get(file_ext, "application/octet-stream")
        
        # Get current time
        now = datetime.utcnow()
        
        # Save document record
        async with pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO working_documents 
                (id, filename, file_path, content_type, status, project_id, description, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                document_id,
                file.filename,
                file_path,
                content_type,
                "pending",
                project_id,
                description,
                now,
                now
            )
        
        logger.info(f"Document record saved: {document_id}")
        
        # Define background task
        async def process_document():
            try:
                logger.info(f"Processing document {document_id}")
                
                # Simulate processing delay
                await asyncio.sleep(2)
                
                # Update document status
                async with pg_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE working_documents SET status = $1, updated_at = $2 WHERE id = $3",
                        "processed", datetime.utcnow(), document_id
                    )
                
                logger.info(f"Document {document_id} processed successfully")
            except Exception as e:
                logger.error(f"Error processing document {document_id}: {str(e)}")
        
        # Add background task
        background_tasks.add_task(process_document)
        
        # Return success response
        return DocumentResponse(
            id=document_id,
            filename=file.filename,
            status="pending",
            message="Document uploaded successfully",
            created_at=now,
            updated_at=now
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        # Log and convert other exceptions to HTTP exceptions
        logger.error(f"Error uploading document: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading document: {str(e)}"
        )
