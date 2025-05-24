from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import os
import uuid
import logging
from app.db.init_db import get_db
from app.services.document_processor import DocumentProcessor
from app.models.document import Document, DocumentCreate, DocumentResponse

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document (PDF, DOCX, TXT) for processing.
    The document will be processed in the background and vectorized.
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
        
        # Create document processor
        document_processor = DocumentProcessor()
        
        # Save file with unique name
        file_path = await document_processor.save_uploaded_file(file, document_id)
        
        # Create document record
        document = await document_processor.create_document(
            db=db,
            document_create=DocumentCreate(
                id=document_id,
                filename=file.filename,
                file_path=file_path,
                project_id=project_id,
                description=description,
                status="pending"  # Change initial status to pending
            )
        )
        
        # Process document in background
        # We need to create a new database session for the background task
        # since the current session will be closed after the request completes
        from app.db.init_db import is_async, SessionLocal
        
        # Create a function that will run in the background
        async def process_document_task():
            try:
                # Create a new database session for this background task
                if is_async:
                    # For PostgreSQL (async)
                    async with SessionLocal() as task_db:
                        await document_processor.process_document(
                            document_id=document_id,
                            file_path=file_path,
                            db=task_db
                        )
                else:
                    # For SQLite (sync)
                    task_db = SessionLocal()
                    try:
                        await document_processor.process_document(
                            document_id=document_id,
                            file_path=file_path,
                            db=task_db
                        )
                    finally:
                        task_db.close()
            except Exception as e:
                logger.error(f"Background task error processing document {document_id}: {str(e)}")
                logger.exception(e)
        
        # Add the task to the background tasks
        background_tasks.add_task(process_document_task)
        
        logger.info(f"Document {document_id} queued for processing")
        
        return DocumentResponse(
            id=document.id,
            filename=document.filename,
            status="pending",  # Changed from "processing" to "pending"
            message="Document uploaded successfully and queued for processing"
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

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
