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
                await conn.execute(
                    """INSERT INTO documents 
                    (id, filename, file_path, content_type, file_size, status, project_id, description, created_at, updated_at) 
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                    document_id, file.filename, file_path, file.content_type, file_size, "pending", 
                    project_id, description, now, now
                )
        
        # Schedule background processing task
        # This will be implemented later if needed
        # background_tasks.add_task(process_document, document_id, file_path)
        
        # Return success response
        return DocumentResponse(
            id=document_id,
            filename=file.filename,
            status="pending",
            message="Document uploaded successfully and queued for processing",
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

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Get document details by ID using connection pool
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
        # Get document from database
        async with pg_pool.acquire() as conn:
            document = await conn.fetchrow(
                "SELECT * FROM documents WHERE id = $1",
                document_id
            )
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Convert to dictionary for easier access
        doc_dict = dict(document)
        
        return DocumentResponse(
            id=doc_dict["id"],
            filename=doc_dict["filename"],
            status=doc_dict["status"],
            message="Document retrieved successfully",
            project_id=doc_dict.get("project_id"),
            description=doc_dict.get("description"),
            created_at=doc_dict["created_at"],
            updated_at=doc_dict["updated_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving document: {str(e)}")

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
