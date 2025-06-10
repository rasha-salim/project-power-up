from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, BackgroundTasks, status
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import uuid
import os
import logging
from datetime import datetime
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Model for document response
class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    message: Optional[str] = None
    progress: Optional[str] = "0"
    project_id: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# Main document endpoints using connection pool approach

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """
    Upload a document (PDF, DOCX, TXT) for processing.
    Uses connection pool for reliable PostgreSQL access.
    """
    # Import connection pool
    from app.db.connection_pool import get_pool
    
    # Get connection pool
    pg_pool = get_pool()
    if not pg_pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection pool not available"
        )
    
    try:
        # Generate unique ID for the document
        document_id = str(uuid.uuid4())
        
        # Create upload directory if it doesn't exist
        upload_dir = settings.UPLOAD_DIRECTORY
        os.makedirs(upload_dir, exist_ok=True)
        
        # Get file content and save to disk
        content = await file.read()
        file_size = len(content)
        
        # Prepare file path
        file_extension = os.path.splitext(file.filename)[1].lower()
        file_path = os.path.join(upload_dir, f"{document_id}{file_extension}")
        
        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Reset file position for potential future reads
        await file.seek(0)
        
        # Store document metadata in database
        async with pg_pool.acquire() as conn:
            # Check if the documents table exists and get its columns
            table_exists = await conn.fetchval(
                """SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'documents'
                )"""
            )
            
            if table_exists:
                # Get column names
                columns = await conn.fetch(
                    """SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'documents'"""
                )
                column_names = [col['column_name'] for col in columns]
                logger.info(f"Existing columns in documents table: {column_names}")
                
                # Check if 'file_size' or 'size' column exists
                size_column = 'file_size' if 'file_size' in column_names else 'size'
                
                # Prepare SQL query based on existing columns
                columns_str = "id, filename, file_path, content_type, "
                values_str = "$1, $2, $3, $4, "
                params = [document_id, file.filename, file_path, file.content_type]
                
                # Add size parameter with appropriate column name
                if size_column in column_names:
                    columns_str += f"{size_column}, "
                    values_str += "$5, "
                    params.append(file_size)
                
                # Add remaining columns
                columns_str += "status, project_id, description, created_at, updated_at"
                values_count = len(params) + 1
                values_str += f"${values_count}, ${values_count+1}, ${values_count+2}, ${values_count+3}, ${values_count+4}"
                params.extend(["pending", project_id, description, datetime.utcnow(), datetime.utcnow()])
                
                # Execute insert query
                await conn.execute(
                    f"""INSERT INTO documents 
                    ({columns_str}) 
                    VALUES ({values_str})""",
                    *params
                )
            else:
                # Create documents table if it doesn't exist
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    project_id TEXT,
                    description TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """)
                
                # Insert document record
                now = datetime.utcnow()
                logger.info(f"Inserting document with ID: {document_id}, status: processing, progress: 10")
                
                # Check if the progress column exists
                column_exists = await conn.fetchval(
                    """SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'documents' AND column_name = 'progress'
                    )"""
                )
                logger.info(f"Progress column exists in documents table: {column_exists}")
                
                # If progress column doesn't exist, add it
                if not column_exists:
                    logger.info("Adding progress column to documents table")
                    await conn.execute(
                        """ALTER TABLE documents 
                        ADD COLUMN IF NOT EXISTS progress TEXT DEFAULT '0'"""
                    )
                
                await conn.execute(
                    """INSERT INTO documents 
                    (id, filename, file_path, content_type, file_size, status, progress, project_id, description, created_at, updated_at) 
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
                    document_id, file.filename, file_path, file.content_type, file_size, "processing", "10", 
                    project_id, description, now, now
                )
                logger.info("Document record inserted successfully")
        
        # Schedule background processing task
        from app.services.document_processor import DocumentProcessor
        document_processor = DocumentProcessor()
        logger.info(f"Adding background task to process document {document_id}")
        
        # Define a wrapper function to ensure the task completes and logs properly
        async def process_document_task(doc_id, path, pool):
            try:
                logger.info(f"Starting background processing task for document {doc_id}")
                await document_processor.process_document(doc_id, path, pool)
                logger.info(f"Background processing task completed successfully for document {doc_id}")
                
                # Double-check the document status after processing
                async with pool.acquire() as conn:
                    doc_result = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", doc_id)
                    if doc_result:
                        logger.info(f"Final document state after background task: id={doc_result['id']}, status={doc_result['status']}, progress={doc_result.get('progress', 'N/A')}")
                    else:
                        logger.warning(f"Document {doc_id} not found after background task completion")
                        
            except Exception as e:
                logger.error(f"Error in background processing task for document {doc_id}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        
        # Add the task to the background tasks
        background_tasks.add_task(process_document_task, document_id, file_path, pg_pool)
        
        # Return success response
        return DocumentResponse(
            id=document_id,
            filename=file.filename,
            status="processing",
            progress="10",
            message="Document uploaded successfully and processing has started",
            project_id=project_id,
            description=description
        )
    
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading document: {str(e)}"
        )

@router.get("/status/{document_id}", response_model=DocumentResponse)
async def get_document_status_alt(document_id: str):
    """
    Get document processing status by ID - endpoint for frontend polling
    """
    # Import connection pool
    from app.db.connection_pool import get_pool
    import traceback
    
    # Get connection pool
    pg_pool = get_pool()
    if not pg_pool:
        logger.error(f"[DEBUG] Database connection pool not available for status check of {document_id}")
        # Return a default response instead of error to keep polling working
        return DocumentResponse(
            id=document_id,
            filename="Unknown",
            status="processing",
            progress="10",
            message="Database connection unavailable, using default status"
        )
    
    try:
        # Get document status from database - simplified query
        async with pg_pool.acquire() as conn:
            try:
                logger.info(f"[DEBUG] Fetching status for document: {document_id}")
                document = await conn.fetchrow(
                    "SELECT id, filename, status, progress, created_at, updated_at FROM documents WHERE id = $1",
                    document_id
                )
                
                if not document:
                    logger.warning(f"[DEBUG] Document not found: {document_id}")
                    raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
                
                doc_dict = dict(document)
                logger.info(f"[DEBUG] Document status response: id={doc_dict['id']}, status={doc_dict['status']}, progress={doc_dict.get('progress', 'N/A')}")
                
                return DocumentResponse(
                    id=doc_dict["id"],
                    filename=doc_dict["filename"],
                    status=doc_dict.get("status", "processing"),
                    progress=doc_dict.get("progress", "10"),
                    created_at=doc_dict.get("created_at"),
                    updated_at=doc_dict.get("updated_at"),
                    message="Document status retrieved successfully"
                )
            
            except Exception as db_error:
                logger.error(f"[DEBUG] Database error in document status: {str(db_error)}")
                logger.error(traceback.format_exc())
                # Return a default response to keep polling working
                return DocumentResponse(
                    id=document_id,
                    filename="Unknown",
                    status="processing",
                    progress="10",
                    message=f"Error retrieving document status: {str(db_error)}"
                )
    
    except Exception as e:
        logger.error(f"[DEBUG] Error in document status endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        # Return a default response to keep polling working even during errors
        return DocumentResponse(
            id=document_id,
            filename="Unknown",
            status="processing",
            progress="10",
            message=f"Unexpected error: {str(e)}"
        )

@router.get("/{document_id}/status", response_model=DocumentResponse)
async def get_document_status(document_id: str):
    """
    Get document processing status by ID - simplified endpoint for polling
    """
    # Import connection pool
    from app.db.connection_pool import get_pool
    import traceback
    
    # Get connection pool
    pg_pool = get_pool()
    if not pg_pool:
        logger.error(f"[DEBUG] Database connection pool not available for status check of {document_id}")
        # Return a default response instead of error to keep polling working
        return DocumentResponse(
            id=document_id,
            filename="Unknown",
            status="processing",
            progress="10",
            message="Database connection unavailable, using default status"
        )
    
    try:
        # Get document status from database - simplified query
        async with pg_pool.acquire() as conn:
            try:
                logger.info(f"[DEBUG] Fetching status for document: {document_id}")
                document = await conn.fetchrow(
                    "SELECT id, filename, status, progress, created_at, updated_at FROM documents WHERE id = $1",
                    document_id
                )
                logger.info(f"[DEBUG] Document status fetch result: {document is not None}")
            except Exception as db_error:
                logger.error(f"[DEBUG] Database error fetching status for {document_id}: {str(db_error)}")
                # Return a default response instead of error to keep polling working
                return DocumentResponse(
                    id=document_id,
                    filename="Unknown",
                    status="processing",
                    progress="10",
                    message=f"Database error: {str(db_error)}"
                )
        
        if not document:
            logger.warning(f"[DEBUG] Document not found for status check: {document_id}")
            # Return a default response instead of error to keep polling working
            return DocumentResponse(
                id=document_id,
                filename="Unknown",
                status="processing",
                progress="10",
                message="Document not found, using default status"
            )
        
        # Convert to dictionary for easier access
        doc_dict = dict(document)
        logger.info(f"[DEBUG] Document status: {doc_dict.get('status')}, progress: {doc_dict.get('progress')}")
        
        # Return simplified response
        return DocumentResponse(
            id=doc_dict["id"],
            filename=doc_dict.get("filename", "Unknown"),
            status=doc_dict.get("status", "processing"),
            progress=doc_dict.get("progress", "10"),
            message="Document status retrieved successfully",
            created_at=doc_dict.get("created_at", datetime.now()),
            updated_at=doc_dict.get("updated_at", datetime.now())
        )
    except Exception as e:
        logger.error(f"[DEBUG] Unexpected error in get_document_status for {document_id}: {str(e)}")
        # Return a default response instead of error to keep polling working
        return DocumentResponse(
            id=document_id,
            filename="Unknown",
            status="processing",
            progress="10",
            message=f"Error retrieving status: {str(e)}"
        )

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Get document details by ID using connection pool
    """
    # Import connection pool
    from app.db.connection_pool import get_pool
    import traceback
    
    # Get connection pool
    pg_pool = get_pool()
    if not pg_pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection pool not available"
        )
    
    try:
        # Get document from database
        async with pg_pool.acquire() as conn:
            try:
                logger.info(f"[DEBUG] Fetching document with ID: {document_id}")
                document = await conn.fetchrow(
                    "SELECT * FROM documents WHERE id = $1",
                    document_id
                )
                logger.info(f"[DEBUG] Document fetch result: {document is not None}")
            except Exception as db_error:
                logger.error(f"[DEBUG] Database error fetching document {document_id}: {str(db_error)}")
                logger.error(traceback.format_exc())
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {str(db_error)}"
                )
        
        if not document:
            logger.warning(f"[DEBUG] Document not found: {document_id}")
            raise HTTPException(status_code=404, detail="Document not found")
        
        try:
            # Convert to dictionary for easier access
            doc_dict = dict(document)
            logger.info(f"[DEBUG] Document keys: {list(doc_dict.keys())}")
            
            # Ensure all required fields exist with fallbacks
            response = DocumentResponse(
                id=doc_dict["id"],
                filename=doc_dict["filename"],
                status=doc_dict.get("status", "processing"),  # Default to processing if missing
                progress=doc_dict.get("progress", "10"),  # Default to 10% if missing
                message="Document retrieved successfully",
                project_id=doc_dict.get("project_id"),
                description=doc_dict.get("description"),
                created_at=doc_dict.get("created_at", datetime.now()),
                updated_at=doc_dict.get("updated_at", datetime.now())
            )
            logger.info(f"[DEBUG] Document response created successfully for {document_id}")
            return response
        except Exception as format_error:
            logger.error(f"[DEBUG] Error formatting document response for {document_id}: {str(format_error)}")
            logger.error(f"[DEBUG] Document data: {doc_dict}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error formatting document: {str(format_error)}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DEBUG] Unexpected error in get_document for {document_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )



@router.get("/", response_model=List[DocumentResponse])
async def list_documents(project_id: Optional[str] = None):
    """
    List all documents, optionally filtered by project_id using connection pool
    """
    # Import connection pool
    from app.db.connection_pool import get_pool
    
    # Get connection pool
    pg_pool = get_pool()
    if not pg_pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection pool not available"
        )
    
    try:
        # Get documents from database using connection pool
        async with pg_pool.acquire() as conn:
            if project_id:
                # Filter by project_id if provided
                rows = await conn.fetch(
                    "SELECT * FROM documents WHERE project_id = $1 ORDER BY created_at DESC",
                    project_id
                )
            else:
                # Get all documents
                rows = await conn.fetch(
                    "SELECT * FROM documents ORDER BY created_at DESC"
                )
        
        # Convert rows to response objects
        return [
            DocumentResponse(
                id=dict(row)["id"],
                filename=dict(row)["filename"],
                status=dict(row)["status"],
                message="Document retrieved successfully",
                project_id=dict(row).get("project_id"),
                description=dict(row).get("description"),
                created_at=dict(row)["created_at"],
                updated_at=dict(row)["updated_at"]
            ) for row in rows
        ]
    
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing documents: {str(e)}"
        )

@router.delete("/{document_id}", response_model=DocumentResponse)
async def delete_document(document_id: str):
    """
    Delete a document by ID using connection pool
    """
    # Import connection pool
    from app.db.connection_pool import get_pool
    
    # Get connection pool
    pg_pool = get_pool()
    if not pg_pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection pool not available"
        )
    
    try:
        # Get document details before deleting
        async with pg_pool.acquire() as conn:
            document = await conn.fetchrow(
                "SELECT * FROM documents WHERE id = $1",
                document_id
            )
            
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Get document details for response
            doc_dict = dict(document)
            filename = doc_dict["filename"]
            file_path = doc_dict["file_path"]
            
            # Delete document from database
            await conn.execute(
                "DELETE FROM documents WHERE id = $1",
                document_id
            )
            
            logger.info(f"Document {document_id} deleted from database")
        
        # Try to delete the file from disk
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
        except Exception as file_e:
            logger.warning(f"Could not delete file {file_path}: {str(file_e)}")
        
        return DocumentResponse(
            id=document_id,
            filename=filename,
            status="deleted",
            message="Document deleted successfully",
            project_id=doc_dict.get("project_id"),
            description=doc_dict.get("description"),
            created_at=None,
            updated_at=None
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting document: {str(e)}"
        )
