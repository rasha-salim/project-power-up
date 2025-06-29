"""
Document Upload Service
Handles document uploads using the PostgreSQL connection pool

TODO: MIGRATION PRIORITY 1 - Migrate to SQLAlchemy AsyncSession for consistency
Currently uses asyncpg connection pool - target for Phase 2 migration
See docs/database-migration-plan.md for details
"""
import os
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from fastapi import UploadFile, HTTPException, status
import asyncpg

from app.core.config import settings
from app.db.connection_pool import get_pool  # TODO: Replace with SQLAlchemy AsyncSession

# Configure logging
logger = logging.getLogger(__name__)

class DocumentUploadService:
    """Service for handling document uploads"""
    
    def __init__(self):
        """Initialize the document upload service"""
        self.upload_dir = settings.UPLOAD_DIRECTORY
        
        # Ensure upload directory exists
        os.makedirs(self.upload_dir, exist_ok=True)
    
    async def upload_document(self, 
                             file: UploadFile, 
                             project_id: Optional[str] = None,
                             description: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Upload a document and save it to disk and database
        
        Returns:
            Tuple[str, Dict[str, Any]]: Document ID and document details
        """
        # Get connection pool
        pool = get_pool()
        if not pool:
            logger.error("PostgreSQL connection pool not available")
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
            file_path = os.path.join(self.upload_dir, f"{document_id}_{file.filename}")
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
            
            # Save document record using connection from pool
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO documents 
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
            
            # Return document details
            return document_id, {
                "id": document_id,
                "filename": file.filename,
                "file_path": file_path,
                "content_type": content_type,
                "status": "processing",
                "progress": "10",
                "project_id": project_id,
                "description": description,
                "created_at": now,
                "updated_at": now
            }
        
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
    
    async def process_document(self, document_id: str) -> bool:
        """
        Process a document (background task)
        
        Returns:
            bool: True if processing was successful, False otherwise
        """
        # Get connection pool
        pool = get_pool()
        if not pool:
            logger.error("PostgreSQL connection pool not available")
            return False
        
        try:
            logger.info(f"Starting background processing for document {document_id}")
            
            # Update document status
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE documents SET status = $1, updated_at = $2 WHERE id = $3",
                    "processed", datetime.utcnow(), document_id
                )
            
            logger.info(f"Completed background processing for document {document_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {str(e)}")
            logger.exception(e)
            return False
