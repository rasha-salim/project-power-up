from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import uuid
import os
import logging
from datetime import datetime
from app.db.init_db import get_db, get_sync_db, get_async_db
from app.services.document_processor import DocumentProcessor
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Model for document response
class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# Model for preflight check results
class PreflightResult(BaseModel):
    db_ready: bool
    upload_dir_ready: bool
    chroma_ready: bool
    all_ready: bool
    details: Dict[str, Any] = {}

router = APIRouter()
logger = logging.getLogger(__name__)

# 1. Minimal test endpoint - just file reading
@router.post("/test-upload")
async def test_upload(file: UploadFile = File(...)):
    """
    Minimal test endpoint that only reads the file content
    """
    try:
        # Only test file reading - nothing else
        content = await file.read()
        return {"size": len(content), "filename": file.filename}
    except Exception as e:
        logger.error(f"Error in test upload: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error in test upload: {str(e)}")

# 2. Test endpoint with database session - using direct asyncpg
@router.post("/test-upload-db")
async def test_upload_db(file: UploadFile = File(...)):
    """
    Test endpoint that reads the file and interacts with the database
    Uses direct asyncpg connection to PostgreSQL
    """
    try:
        # Import asyncpg for direct PostgreSQL access
        import asyncpg
        from app.core.config import settings
        
        # Read file content
        content = await file.read()
        
        # Generate a test ID
        test_id = str(uuid.uuid4())
        
        # Connect directly to PostgreSQL
        conn = await asyncpg.connect(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB
        )
        
        # Insert test data
        await conn.execute(
            "INSERT INTO documents (id, filename, size, status, created_at) VALUES ($1, $2, $3, $4, $5)",
            test_id, file.filename, len(content), "pending", datetime.utcnow()
        )
        
        # Query to verify it worked
        row = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", test_id)
        
        # Close the connection
        await conn.close()
        
        return {
            "size": len(content),
            "filename": file.filename,
            "test_id": test_id,
            "db_test": "success",
            "db_type": "direct_asyncpg",
            "result": dict(row) if row else None
        }
    except Exception as e:
        logger.error(f"Error in test upload with DB: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error in test upload with DB: {str(e)}")

# 2.1 Super isolated test endpoint - exact copy of working isolated test
@router.post("/isolated-test")
async def isolated_test(file: UploadFile = File(...)):
    """
    Completely isolated test endpoint that's an exact copy of the working isolated test
    """
    try:
        # Read file content
        content = await file.read()
        
        # Generate a test ID
        test_id = str(uuid.uuid4())
        
        # PostgreSQL connection parameters - hardcoded to avoid any dependency issues
        PG_HOST = "localhost"
        PG_PORT = "5432"
        PG_USER = "postgres"
        PG_PASSWORD = "adam15"  # Use your actual password
        PG_DATABASE = "project_planning"
        
        # Connect to PostgreSQL
        import asyncpg
        conn = await asyncpg.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            database=PG_DATABASE
        )
        
        # Insert test data
        await conn.execute(
            "INSERT INTO test_uploads (id, filename, size, created_at) VALUES ($1, $2, $3, $4)",
            test_id, file.filename, len(content), datetime.utcnow()
        )
        
        # Query to verify it worked
        row = await conn.fetchrow("SELECT * FROM test_uploads WHERE id = $1", test_id)
        
        # Close the connection
        await conn.close()
        
        return {
            "size": len(content),
            "filename": file.filename,
            "test_id": test_id,
            "db_test": "success",
            "result": dict(row) if row else None
        }
    except Exception as e:
        logger.error(f"Error in isolated test: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error in isolated test: {str(e)}")

# 3. Test endpoint with file saving
@router.post("/test-upload-file")
async def test_upload_file(file: UploadFile = File(...)):
    """
    Test endpoint that reads the file and saves it to disk
    """
    try:
        # Generate unique ID
        document_id = str(uuid.uuid4())
        
        # Get file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        # Create upload directory
        upload_dir = "./uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Create file path
        file_path = f"{upload_dir}/test_{document_id}{file_ext}"
        
        # Read and save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        return {
            "size": len(content), 
            "filename": file.filename,
            "saved_to": file_path
        }
    except Exception as e:
        logger.error(f"Error in test upload with file saving: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error in test upload with file saving: {str(e)}")

# 4. Test endpoint with ChromaDB
@router.post("/test-upload-chroma")
async def test_upload_chroma(file: UploadFile = File(...)):
    """
    Test endpoint that reads the file and interacts with ChromaDB
    """
    try:
        # Read file
        content = await file.read()
        
        # Test ChromaDB connection
        chroma_client = get_chroma_client()
        collection_name = "test_collection"
        
        # Get or create a test collection
        test_collection = chroma_client.get_or_create_collection(name=collection_name)
        
        # Add a test document
        test_id = str(uuid.uuid4())
        test_collection.add(
            ids=[test_id],
            documents=["This is a test document for ChromaDB"],
            metadatas=[{"source": "test", "filename": file.filename}]
        )
        
        # Query to verify it works
        results = test_collection.query(
            query_texts=["test document"],
            n_results=1
        )
        
        # Delete the test document
        test_collection.delete(ids=[test_id])
        
        return {
            "size": len(content), 
            "filename": file.filename,
            "chroma_test": "success",
            "results": results
        }
    except Exception as e:
        logger.error(f"Error in test upload with ChromaDB: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error in test upload with ChromaDB: {str(e)}")

# 5. Synchronous version of upload
@router.post("/upload-sync", response_model=DocumentResponse)
def upload_sync(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """
    Synchronous implementation of document upload without any await calls
    """
    try:
        # Validate file type
        allowed_extensions = [".pdf", ".docx", ".txt"]
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Generate unique ID for the document
        document_id = str(uuid.uuid4())
        
        # Create upload directory
        upload_dir = "./uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Create file path
        file_path = f"{upload_dir}/{document_id}{file_ext}"
        
        # Read and save file synchronously
        content = file.file.read()  # Synchronous read
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Reset file position for future reads
        file.file.seek(0)
        
        # Create document record (without DB - just return the response)
        return DocumentResponse(
            id=document_id,
            filename=file.filename,
            status="pending",
            message="Document uploaded successfully (sync version)"
        )
        
    except Exception as e:
        logger.error(f"Error in sync upload: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error in sync upload: {str(e)}")

# 6. Preflight check function
async def check_all_dependencies() -> PreflightResult:
    """
    Check if all required services and dependencies are available
    """
    # Import is_async to check database type
    from app.db.init_db import is_async
    
    result = PreflightResult(
        db_ready=False,
        upload_dir_ready=False,
        chroma_ready=False,
        all_ready=False
    )
    
    # Check database
    try:
        if is_async:
            # For PostgreSQL (async)
            db = next(get_async_db())
            await db.execute(text("SELECT 1"))
        else:
            # For SQLite (sync)
            db = next(get_sync_db())
            db.execute(text("SELECT 1"))
            
        result.db_ready = True
        result.details["db"] = f"Database connection successful (type: {'async' if is_async else 'sync'})"
    except Exception as e:
        result.details["db_error"] = str(e)
    
    # Check upload directory
    try:
        upload_dir = "./uploads"
        os.makedirs(upload_dir, exist_ok=True)
        test_file = f"{upload_dir}/test_write.txt"
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        result.upload_dir_ready = True
        result.details["upload_dir"] = "Upload directory is writable"
    except Exception as e:
        result.details["upload_dir_error"] = str(e)
    
    # Check ChromaDB
    try:
        chroma_client = get_chroma_client()
        collection_name = "preflight_test"
        test_collection = chroma_client.get_or_create_collection(name=collection_name)
        result.chroma_ready = True
        result.details["chroma"] = "ChromaDB connection successful"
    except Exception as e:
        result.details["chroma_error"] = str(e)
    
    # Set all_ready if everything is ready
    result.all_ready = result.db_ready and result.upload_dir_ready and result.chroma_ready
    
    return result

# 7. Upload with preflight check
@router.post("/upload-with-preflight", response_model=DocumentResponse)
async def upload_with_preflight(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload endpoint with preflight checks to verify all dependencies
    """
    try:
        # Import is_async to check database type
        from app.db.init_db import is_async
        
        # Run preflight checks
        preflight_results = await check_all_dependencies()
        if not preflight_results.all_ready:
            return {"error": "Services not ready", "details": preflight_results}
        
        # Validate file type
        allowed_extensions = [".pdf", ".docx", ".txt"]
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Generate unique ID for the document
        document_id = str(uuid.uuid4())
        
        # Create upload directory (already checked in preflight)
        upload_dir = "./uploads"
        
        # Create file path
        file_path = f"{upload_dir}/{document_id}{file_ext}"
        
        # Read and save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"File saved to {file_path}")
        
        # Determine content type based on extension
        content_type_map = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain"
        }
        content_type = content_type_map.get(file_ext, "application/octet-stream")
        
        # Get current UTC time
        now = datetime.utcnow()
        
        # Create document record with explicit fields
        document = Document(
            id=document_id,
            filename=file.filename,
            file_path=file_path,
            content_type=content_type,
            project_id=project_id,
            description=description,
            status="pending",
            doc_metadata=None,
            created_at=now,
            updated_at=now
        )
        
        # Add to database - handle both async and sync cases
        db.add(document)
        
        if is_async:
            # For PostgreSQL (async)
            await db.commit()
        else:
            # For SQLite (sync)
            db.commit()
        
        # Return response
        return DocumentResponse(
            id=document_id,
            filename=file.filename,
            status="pending",
            message="Document uploaded successfully with preflight checks"
        )
        
    except Exception as e:
        logger.error(f"Error in upload with preflight: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error in upload with preflight: {str(e)}")

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """
    Upload a document (PDF, DOCX, TXT) for processing.
    Using direct asyncpg connection to PostgreSQL (working pattern)
    """
    try:
        # Validate file type
        allowed_extensions = [".pdf", ".docx", ".txt"]
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Generate unique ID for the document
        document_id = str(uuid.uuid4())
        
        # Read file content
        content = await file.read()
        
        # Create uploads directory if it doesn't exist
        os.makedirs(settings.UPLOAD_DIRECTORY, exist_ok=True)
        
        # Save file to disk
        file_path = os.path.join(settings.UPLOAD_DIRECTORY, f"{document_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Get current UTC time
        now = datetime.utcnow()
        
        # Determine content type based on extension
        content_type_map = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".txt": "text/plain"
        }
        content_type = content_type_map.get(file_ext, "application/octet-stream")
        
        # Connect directly to PostgreSQL using asyncpg
        import asyncpg
        conn = await asyncpg.connect(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB
        )
        
        # Insert document record
        await conn.execute(
            """INSERT INTO documents 
               (id, filename, file_path, content_type, status, project_id, description, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
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
        
        # Close the connection
        await conn.close()
        
        # Define a simplified background task function
        async def process_document_task():
            try:
                logger.info(f"Starting background processing for document {document_id}")
                
                # Connect directly to PostgreSQL using asyncpg
                import asyncpg
                task_conn = await asyncpg.connect(
                    host=settings.POSTGRES_SERVER,
                    port=settings.POSTGRES_PORT,
                    user=settings.POSTGRES_USER,
                    password=settings.POSTGRES_PASSWORD,
                    database=settings.POSTGRES_DB
                )
                
                # Update the document status
                await task_conn.execute(
                    "UPDATE documents SET status = $1, updated_at = $2 WHERE id = $3",
                    "processed", datetime.utcnow(), document_id
                )
                
                # Close the connection
                await task_conn.close()
                
                logger.info(f"Completed background processing for document {document_id}")
            except Exception as e:
                logger.error(f"Background task error processing document {document_id}: {str(e)}")
                logger.exception(e)
        
        # Add the task to the background tasks
        background_tasks.add_task(process_document_task)
        
        logger.info(f"Document {document_id} queued for processing")
        
        return DocumentResponse(
            id=document_id,
            filename=file.filename,
            status="pending",
            message="Document uploaded successfully and queued for processing"
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")
        
    # Return the document response
    return DocumentResponse(
        id=document_id,
        filename=file.filename,
        status="pending",
        message="Document uploaded successfully",
        created_at=now,
        updated_at=now
    )

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get document details by ID
    """
    try:
        document_processor = DocumentProcessor()
        document = await document_processor.get_document(db, document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return DocumentResponse(
            id=document.id,
            filename=document.filename,
            status=document.status,
            message="Document retrieved successfully",
            project_id=document.project_id,
            description=document.description,
            created_at=document.created_at,
            updated_at=document.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving document: {str(e)}")

@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List all documents, optionally filtered by project_id
    """
    try:
        document_processor = DocumentProcessor()
        documents = await document_processor.list_documents(db, project_id)
        
        return [
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                status=doc.status,
                message="Document retrieved successfully",
                project_id=doc.project_id,
                description=doc.description,
                created_at=doc.created_at,
                updated_at=doc.updated_at
            ) for doc in documents
        ]
        
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

@router.delete("/{document_id}", response_model=DocumentResponse)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a document by ID
    """
    try:
        document_processor = DocumentProcessor()
        document = await document_processor.get_document(db, document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
            
        # Delete document from database and vector store
        await document_processor.delete_document(db, document_id)
        
        return DocumentResponse(
            id=document_id,
            filename=document.filename,
            status="deleted",
            message="Document deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")
