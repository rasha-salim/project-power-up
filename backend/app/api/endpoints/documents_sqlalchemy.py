"""
Document endpoints using SQLAlchemy instead of direct connection pool
This provides an alternative implementation that's more consistent with the rest of the application
"""
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import uuid
import os
import logging
import json
from datetime import datetime
from app.core.config import settings
from app.db.init_db_simple import get_async_db
from app.services.document_processor import DocumentProcessor

router = APIRouter()
logger = logging.getLogger(__name__)

# Model for document response
class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    progress: Optional[str] = None  # Added progress field
    message: Optional[str] = None
    project_id: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Upload a document (PDF, DOCX, TXT) for processing.
    Uses SQLAlchemy for database access.
    """
    try:
        # Log request details
        logger.info(f"Document upload request received")
        logger.info(f"File: {file.filename}, Content-Type: {file.content_type}")
        logger.info(f"Project ID: {project_id}, Description: {description}")
        
        # Generate unique ID for the document
        document_id = str(uuid.uuid4())
        logger.info(f"Generated document ID: {document_id}")
        
        # Create upload directory if it doesn't exist
        upload_dir = settings.UPLOAD_DIRECTORY
        os.makedirs(upload_dir, exist_ok=True)
        logger.info(f"Upload directory: {upload_dir}")
        
        # Get file content and save to disk
        content = await file.read()
        file_size = len(content)
        logger.info(f"File size: {file_size} bytes")
        
        # Prepare file path
        file_extension = os.path.splitext(file.filename)[1].lower()
        file_path = os.path.join(upload_dir, f"{document_id}{file_extension}")
        logger.info(f"File will be saved to: {file_path}")
        
        # Save file to disk
        try:
            with open(file_path, "wb") as f:
                f.write(content)
            logger.info(f"File saved successfully to disk")
        except Exception as e:
            logger.error(f"Error saving file to disk: {str(e)}")
            raise
        
        # Reset file position for potential future reads
        await file.seek(0)
        logger.info("File position reset for future reads")
        
        # Store document metadata in database using SQLAlchemy
        logger.info("Starting database operations for document storage")
        
        # First check if the documents table exists
        logger.info("Checking if documents table exists")
        result = await db.execute(text(
            """SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'documents'
            )"""
        ))
        table_exists = result.scalar()
        logger.info(f"Documents table exists: {table_exists}")
        
        if table_exists:
            # Get column names
            logger.info("Getting column names from documents table")
            result = await db.execute(text(
                """SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'documents'"""
            ))
            columns = result.fetchall()
            column_names = [col[0] for col in columns]
            logger.info(f"Existing columns in documents table: {column_names}")
            
            # Insert document using dynamic SQL based on existing columns
            now = datetime.utcnow()
            logger.info(f"Current timestamp: {now}")
            
            # Build column list and values dynamically based on actual schema
            available_columns = [
                "id", "filename", "file_path", "content_type", "status", 
                "project_id", "description", "created_at", "updated_at"
            ]
            
            # Check for doc_metadata column
            has_metadata = "doc_metadata" in column_names
            if has_metadata:
                available_columns.append("doc_metadata")
            
            # Check for size-related columns
            size_columns = [col for col in column_names if "size" in col.lower()]
            if size_columns:
                available_columns.extend(size_columns)
            
            # Filter to only include columns that exist in the database
            columns_to_use = [col for col in available_columns if col in column_names]
            logger.info(f"Using columns: {columns_to_use}")
            
            # Build the SQL query
            columns_str = ", ".join(columns_to_use)
            placeholders = [f":{col}" for col in columns_to_use]
            values_str = ", ".join(placeholders)
            logger.info(f"SQL columns: {columns_str}")
            logger.info(f"SQL values placeholders: {values_str}")
            
            # Prepare parameters
            params = {
                "id": document_id,
                "filename": file.filename,
                "file_path": file_path,
                "content_type": file.content_type,
                "status": "processing",
                "progress": "10",
                "project_id": project_id,
                "description": description,
                "created_at": now,
                "updated_at": now
            }
            
            # Add size parameter if needed
            for size_col in size_columns:
                params[size_col] = file_size
                
            # Add metadata if needed
            if has_metadata:
                params["doc_metadata"] = json.dumps({
                    "upload_time": now.isoformat(),
                    "original_filename": file.filename,
                    "content_type": file.content_type,
                    "file_size": file_size
                })
            
            # Log the SQL query and parameters
            logger.info(f"SQL Insert Query: INSERT INTO documents ({columns_str}) VALUES ({values_str})")
            logger.info(f"Parameters: {params}")
            
            # Execute insert query
            try:
                await db.execute(
                    text(f"INSERT INTO documents ({columns_str}) VALUES ({values_str})"),
                    params
                )
                logger.info("Document record inserted successfully")
                
                await db.commit()
                logger.info("Database transaction committed successfully")
            except Exception as e:
                logger.error(f"Error executing SQL insert: {str(e)}")
                logger.error(f"Error type: {type(e)}")
                await db.rollback()
                logger.info("Database transaction rolled back due to error")
                raise
        
        else:
            # Create documents table if it doesn't exist
            await db.execute(text("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                status TEXT NOT NULL,
                progress TEXT DEFAULT '0',
                project_id TEXT,
                description TEXT,
                doc_metadata JSONB,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            """))
            
            # Insert document record
            now = datetime.utcnow()
            await db.execute(
                text("""INSERT INTO documents 
                (id, filename, file_path, content_type, file_size, status, progress, project_id, description, created_at, updated_at) 
                VALUES (:id, :filename, :file_path, :content_type, :file_size, :status, :progress, :project_id, :description, :created_at, :updated_at)"""),
                {
                    "id": document_id,
                    "filename": file.filename,
                    "file_path": file_path,
                    "content_type": file.content_type,
                    "file_size": file_size,
                    "status": "processing",
                    "progress": "10",
                    "project_id": project_id,
                    "description": description,
                    "created_at": now,
                    "updated_at": now
                }
            )
            await db.commit()
        
        # Initialize document processor and schedule background task
        doc_processor = DocumentProcessor()
        
        # Log detailed information for debugging
        logger.info(f"Document at upload time: ID={document_id}, filename={file.filename}, path={file_path}")
        logger.info(f"File exists check: {os.path.exists(file_path)}")
        logger.info(f"File size: {os.path.getsize(file_path) if os.path.exists(file_path) else 'file not found'}")
        logger.info(f"Absolute file path: {os.path.abspath(file_path)}")
        
        # We should NOT pass the existing db session to a background task
        # Instead, let the processor create its own session when needed
        try:
            background_tasks.add_task(
                doc_processor.process_document,
                None,  # Pass None instead of db session
                document_id,
                file_path
            )
            logger.info(f"Background document processing task scheduled for document {document_id}")
        except Exception as bg_error:
            logger.error(f"Error scheduling background task: {str(bg_error)}")
            logger.error(traceback.format_exc())
        
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
        logger.error(f"Error type: {type(e)}")
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Traceback: {trace}")
        
        # Create a more user-friendly error message
        error_message = "Error uploading document"
        
        # Check for specific error types
        if "column" in str(e) and "does not exist" in str(e):
            error_message = "Database schema mismatch: Column does not exist"
        elif "violates foreign key constraint" in str(e):
            error_message = "Invalid project ID: The specified project does not exist"
        elif "duplicate key value" in str(e):
            error_message = "Duplicate document ID: A document with this ID already exists"
        elif "value too long" in str(e):
            error_message = "Value too long for database column"
        
        # Return a structured error response
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": error_message,
                "error": str(e),
                "error_type": str(type(e).__name__)
            }
        )

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get document details by ID using SQLAlchemy
    """
    try:
        # Get document from database
        try:
            logger.info(f"[DEBUG] Fetching document with ID: {document_id} using SQLAlchemy")
            result = await db.execute(
                text("SELECT * FROM documents WHERE id = :id"),
                {"id": document_id}
            )
            document = result.fetchone()
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
            doc_dict = dict(zip(result.keys(), document))
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
        logger.error(f"Error getting document: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting document: {str(e)}"
        )

@router.get("/status/{document_id}", response_model=DocumentResponse)
async def get_document_status(
    document_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get document status by ID using SQLAlchemy
    """
    try:
        logger.info(f"[DEBUG] Fetching status for document with ID: {document_id}")
        
        # Get document status from database
        try:
            result = await db.execute(
                text("SELECT id, filename, status, progress, created_at, updated_at FROM documents WHERE id = :id"),
                {"id": document_id}
            )
            document = result.fetchone()
            logger.info(f"[DEBUG] Document status fetch result: {document is not None}")
            
        except Exception as db_error:
            logger.error(f"[DEBUG] Database error fetching document status {document_id}: {str(db_error)}")
            import traceback
            logger.error(traceback.format_exc())
            # Return a default response instead of raising an exception
            return DocumentResponse(
                id=document_id,
                filename="unknown",
                status="processing",
                message="Error fetching document status, using default",
                progress="10"
            )
        
        if not document:
            logger.warning(f"[DEBUG] Document not found for status check: {document_id}")
            # Return a default response instead of raising a 404
            return DocumentResponse(
                id=document_id,
                filename="unknown",
                status="processing",
                message="Document not found, using default status",
                progress="10"
            )
        
        # Convert to dictionary for easier access
        doc_dict = dict(zip(result.keys(), document))
        logger.info(f"[DEBUG] Document status keys: {list(doc_dict.keys())}")
        
        # Return document status
        return DocumentResponse(
            id=doc_dict["id"],
            filename=doc_dict["filename"],
            status=doc_dict.get("status", "processing"),
            message="Document status retrieved successfully",
            progress=doc_dict.get("progress", "10")
        )
            
    except Exception as e:
        logger.error(f"Unexpected error getting document status: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Return a default response instead of raising an exception
        return DocumentResponse(
            id=document_id,
            filename="unknown",
            status="processing",
            message=f"Error: {str(e)}",
            progress="10"
        )

@router.get("/project/{project_id}", response_model=List[DocumentResponse])
async def get_project_documents(
    project_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get all documents for a project using SQLAlchemy
    """
    try:
        # Get documents from database
        result = await db.execute(
            text("SELECT * FROM documents WHERE project_id = :project_id"),
            {"project_id": project_id}
        )
        documents = result.fetchall()
        
        # Convert to list of DocumentResponse objects
        document_list = []
        for doc in documents:
            doc_dict = dict(zip(result.keys(), doc))
            document_list.append(
                DocumentResponse(
                    id=doc_dict["id"],
                    filename=doc_dict["filename"],
                    status=doc_dict["status"],
                    message="Document retrieved successfully",
                    project_id=doc_dict.get("project_id"),
                    description=doc_dict.get("description"),
                    created_at=doc_dict.get("created_at"),
                    updated_at=doc_dict.get("updated_at")
                )
            )
        
        return document_list
        
    except Exception as e:
        logger.error(f"Error getting project documents: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting project documents: {str(e)}"
        )
