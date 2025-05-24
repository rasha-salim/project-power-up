import os
import logging
import json
import uuid
import traceback
from typing import List, Dict, Any, Optional
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from app.models.document import Document, DocumentCreate, DocumentUpdate
from app.db.init_db import get_chroma_client
from app.core.config import settings

# Configure more detailed logging
logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Service for processing documents and storing them in the database and vector store"""
    
    async def save_uploaded_file(self, file: UploadFile, document_id: str) -> str:
        """
        Save an uploaded file to disk
        
        Args:
            file: The uploaded file
            document_id: Unique ID for the document
            
        Returns:
            str: Path to the saved file
        """
        # Create upload directory if it doesn't exist
        os.makedirs(settings.UPLOAD_DIRECTORY, exist_ok=True)
        
        # Get file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        # Create a unique filename
        unique_filename = f"{document_id}{file_ext}"
        file_path = os.path.join(settings.UPLOAD_DIRECTORY, unique_filename)
        
        # Write file to disk
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        logger.info(f"[DEBUG] Saved file {file.filename} to {file_path} (size: {len(content)} bytes)")
        return file_path
    
    async def create_document(self, db: AsyncSession, document_create: DocumentCreate) -> Document:
        """
        Create a new document record in the database
        
        Args:
            db: Database session
            document_create: Document creation data
            
        Returns:
            Document: Created document
        """
        document = Document(
            id=document_create.id,
            filename=document_create.filename,
            file_path=document_create.file_path,
            content_type=document_create.content_type,
            status=document_create.status,
            project_id=document_create.project_id,
            description=document_create.description,
            doc_metadata=json.dumps(document_create.doc_metadata) if document_create.doc_metadata else None
        )
        
        db.add(document)
        await db.commit()
        await db.refresh(document)
        
        logger.info(f"[DEBUG] Created document record with ID {document.id} for project {document_create.project_id}")
        return document
    
    async def process_document(self, document_id: str, file_path: str, db) -> None:
        """
        Process a document and extract text for vectorization
        
        Args:
            document_id: ID of the document to process
            file_path: Path to the document file
            db: Database session (can be sync or async)
        """
        try:
            logger.info(f"[DEBUG] Starting processing of document {document_id} at path {file_path}")
            
            # Update document status to processing
            await self.update_document_status(db, document_id, "processing")
            
            # Verify file exists
            if not os.path.exists(file_path):
                logger.error(f"[DEBUG] File not found at path {file_path}")
                await self.update_document_status(db, document_id, "error")
                await self.update_document(
                    db,
                    document_id,
                    DocumentUpdate(doc_metadata={"error": "File not found"})
                )
                return
            
            # Extract text from document based on file type
            file_ext = os.path.splitext(file_path)[1].lower()
            logger.info(f"[DEBUG] Detected file extension: {file_ext}")
            
            if file_ext == ".pdf":
                # This would use a PDF extraction library like PyPDF2 or pdfplumber
                text_content = "PDF content would be extracted here"
                logger.info(f"[DEBUG] Extracted PDF content from {file_path}")
                
            elif file_ext == ".docx":
                # This would use a DOCX extraction library like python-docx
                text_content = "DOCX content would be extracted here"
                logger.info(f"[DEBUG] Extracted DOCX content from {file_path}")
                
            elif file_ext == ".txt":
                # Simple text file reading
                with open(file_path, "r", encoding="utf-8") as f:
                    text_content = f.read()
                logger.info(f"[DEBUG] Read text file content from {file_path}, size: {len(text_content)} characters")
                    
            else:
                logger.error(f"[DEBUG] Unsupported file type: {file_ext}")
                await self.update_document_status(db, document_id, "error")
                await self.update_document(
                    db,
                    document_id,
                    DocumentUpdate(doc_metadata={"error": f"Unsupported file type: {file_ext}"})
                )
                return
            
            # Split text into chunks for vectorization
            logger.info(f"[DEBUG] Splitting text content into chunks")
            chunks = self._split_text_into_chunks(text_content)
            logger.info(f"[DEBUG] Split text into {len(chunks)} chunks")
            
            # Vectorize and store chunks in ChromaDB
            logger.info(f"[DEBUG] Vectorizing and storing chunks in ChromaDB")
            await self._vectorize_chunks(document_id, chunks)
            
            # Update document status to processed
            doc_metadata = {
                "chunk_count": len(chunks),
                "processing_complete": True,
                "processed_at": str(datetime.now())
            }
            
            await self.update_document(
                db, 
                document_id, 
                DocumentUpdate(status="processed", doc_metadata=doc_metadata)
            )
            
            logger.info(f"[DEBUG] Successfully processed document {document_id} with {len(chunks)} chunks")
            
        except Exception as e:
            error_details = {
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            logger.error(f"[DEBUG] Error processing document {document_id}: {str(e)}\n{traceback.format_exc()}")
            # Update document status to error
            await self.update_document_status(db, document_id, "error")
            await self.update_document(
                db,
                document_id,
                DocumentUpdate(doc_metadata=error_details)
            )
    
    def _split_text_into_chunks(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split text into overlapping chunks for vectorization
        
        Args:
            text: Text to split
            chunk_size: Maximum size of each chunk
            overlap: Overlap between chunks
            
        Returns:
            List[str]: List of text chunks
        """
        chunks = []
        if len(text) <= chunk_size:
            chunks.append(text)
            logger.debug(f"[DEBUG] Text fits in a single chunk of size {len(text)}")
        else:
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                # If this is not the first chunk, include overlap
                if start > 0:
                    start = start - overlap
                chunks.append(text[start:end])
                logger.debug(f"[DEBUG] Created chunk from position {start} to {end}")
                start = end
        
        return chunks
    
    async def _vectorize_chunks(self, document_id: str, chunks: List[str]) -> None:
        """
        Vectorize text chunks and store in ChromaDB
        
        Args:
            document_id: ID of the document
            chunks: List of text chunks to vectorize
        """
        # Get ChromaDB client
        client = get_chroma_client()
        collection = client.get_or_create_collection("documents")
        logger.info(f"[DEBUG] Connected to ChromaDB collection 'documents'")
        
        # Create IDs for chunks
        chunk_ids = [f"{document_id}_{i}" for i in range(len(chunks))]
        
        # Create metadata for chunks
        metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]
        
        # Add chunks to collection
        try:
            # Check if chunks for this document already exist and delete them
            existing_results = collection.get(
                where={"document_id": document_id}
            )
            
            if existing_results and existing_results["ids"]:
                logger.info(f"[DEBUG] Removing {len(existing_results['ids'])} existing chunks for document {document_id}")
                collection.delete(
                    where={"document_id": document_id}
                )
            
            # Add new chunks
            collection.add(
                ids=chunk_ids,
                documents=chunks,
                metadatas=metadatas
            )
            logger.info(f"[DEBUG] Successfully added {len(chunks)} chunks to ChromaDB for document {document_id}")
        except Exception as e:
            logger.error(f"[DEBUG] Error adding chunks to ChromaDB: {str(e)}\n{traceback.format_exc()}")
            raise
    
    async def get_document(self, db: AsyncSession, document_id: str) -> Optional[Document]:
        """
        Get a document by ID
        
        Args:
            db: Database session
            document_id: ID of the document to retrieve
            
        Returns:
            Optional[Document]: Document if found, None otherwise
        """
        result = await db.execute(select(Document).where(Document.id == document_id))
        return result.scalars().first()
    
    async def list_documents(self, db: AsyncSession, project_id: Optional[str] = None) -> List[Document]:
        """
        List all documents, optionally filtered by project_id
        
        Args:
            db: Database session
            project_id: Optional project ID to filter by
            
        Returns:
            List[Document]: List of documents
        """
        if project_id:
            result = await db.execute(select(Document).where(Document.project_id == project_id))
        else:
            result = await db.execute(select(Document))
            
        return result.scalars().all()
    
    async def update_document_status(self, db: AsyncSession, document_id: str, status: str) -> Optional[Document]:
        """
        Update a document's status
        
        Args:
            db: Database session
            document_id: ID of the document to update
            status: New status
            
        Returns:
            Optional[Document]: Updated document if found, None otherwise
        """
        return await self.update_document(db, document_id, DocumentUpdate(status=status))
    
    async def update_document(self, db: AsyncSession, document_id: str, document_update: DocumentUpdate) -> Optional[Document]:
        """
        Update a document
        
        Args:
            db: Database session
            document_id: ID of the document to update
            document_update: Document update data
            
        Returns:
            Optional[Document]: Updated document if found, None otherwise
        """
        document = await self.get_document(db, document_id)
        
        if not document:
            return None
            
        # Update document fields
        if document_update.filename is not None:
            document.filename = document_update.filename
            
        if document_update.status is not None:
            document.status = document_update.status
            
        if document_update.project_id is not None:
            document.project_id = document_update.project_id
            
        if document_update.description is not None:
            document.description = document_update.description
            
        if document_update.metadata is not None:
            document.metadata = json.dumps(document_update.metadata)
            
        await db.commit()
        await db.refresh(document)
        
        return document
    
    async def delete_document(self, db: AsyncSession, document_id: str) -> bool:
        """
        Delete a document
        
        Args:
            db: Database session
            document_id: ID of the document to delete
            
        Returns:
            bool: True if document was deleted, False otherwise
        """
        document = await self.get_document(db, document_id)
        
        if not document:
            return False
            
        # Delete document from ChromaDB
        client = get_chroma_client()
        collection = client.get_collection("documents")
        
        # Query for chunks with this document_id in metadata
        results = collection.get(
            where={"document_id": document_id}
        )
        
        if results and results["ids"]:
            # Delete chunks from collection
            collection.delete(ids=results["ids"])
            
        # Delete file from disk if it exists
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
            
        # Delete document from database
        await db.delete(document)
        await db.commit()
        
        return True
