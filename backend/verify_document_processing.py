#!/usr/bin/env python
"""
Verification script to ensure the entire document processing pipeline works
from upload to ChromaDB storage with progress updates
"""
import os
import sys
import asyncio
import json
import uuid
from datetime import datetime
import logging
import chromadb
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add local module paths
sys.path.append('.')
from app.db.init_db_simple import get_async_db, get_chroma_client
from app.models.document import Document, DocumentCreate, DocumentUpdate
from app.services.document_processor import DocumentProcessor

async def verify_document_status_in_db(document_id: str):
    """Check the status of a document in the database"""
    logger.info(f"Verifying document {document_id} status in database...")
    
    async for db in get_async_db():
        try:
            # Query the document directly
            result = await db.execute(
                text("SELECT id, title, status, progress, doc_metadata FROM documents WHERE id = :id"),
                {"id": document_id}
            )
            doc = result.fetchone()
            
            if doc:
                logger.info(f"Document found: ID={doc.id}, Title={doc.title}, Status={doc.status}, Progress={doc.progress}")
                if hasattr(doc, 'doc_metadata') and doc.doc_metadata:
                    try:
                        metadata = doc.doc_metadata
                        if isinstance(metadata, str):
                            metadata = json.loads(metadata)
                        logger.info(f"Document metadata: {json.dumps(metadata, indent=2)}")
                    except Exception as e:
                        logger.error(f"Error parsing metadata: {e}")
                return doc
            else:
                logger.error(f"Document {document_id} not found in database")
                return None
                
        except Exception as e:
            logger.error(f"Error querying database: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

def verify_document_in_chroma(document_id: str):
    """Check if a document is stored in ChromaDB"""
    logger.info(f"Verifying document {document_id} in ChromaDB...")
    
    try:
        client = get_chroma_client()
        collection = client.get_or_create_collection("documents")
        
        # Query ChromaDB for chunks with this document_id
        results = collection.get(
            where={"document_id": document_id},
            include=["metadatas", "documents"]
        )
        
        if results and len(results["ids"]) > 0:
            logger.info(f"Document found in ChromaDB with {len(results['ids'])} chunks")
            
            # Print sample data from the first chunk
            if len(results["documents"]) > 0:
                logger.info(f"First chunk text (sample): {results['documents'][0][:100]}...")
                
            # Print metadata from the first chunk
            if len(results["metadatas"]) > 0:
                logger.info(f"First chunk metadata: {json.dumps(results['metadatas'][0], indent=2)}")
                
            return results
        else:
            logger.error(f"Document {document_id} not found in ChromaDB")
            return None
            
    except Exception as e:
        logger.error(f"Error querying ChromaDB: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def verify_full_pipeline(file_path: str):
    """Test the complete document processing pipeline"""
    logger.info(f"Testing full document processing pipeline for file: {file_path}")
    
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False
        
    # Create a unique document ID
    document_id = str(uuid.uuid4())
    logger.info(f"Generated document ID: {document_id}")
    
    # Create document processor
    processor = DocumentProcessor()
    
    # Create document record in database
    async for db in get_async_db():
        try:
            # Print file info
            logger.info(f"File path: {file_path}")
            logger.info(f"File exists: {os.path.exists(file_path)}")
            logger.info(f"File size: {os.path.getsize(file_path)}")
            
            # Create document with ALL required fields
            file_basename = os.path.basename(file_path)
            logger.info("Creating document with ALL required fields including filename and file_path")
            doc_create = DocumentCreate(
                id=document_id,
                filename=file_basename,  # Add filename field
                project_id="test_project",
                file_path=file_path,
                status="pending"
            )
            
            document = await processor.create_document(db, doc_create)
            logger.info(f"Created document record: {document.id}")
            
            # Process document
            logger.info(f"Starting document processing...")
            await processor.process_document(db, document.id, file_path)
            logger.info(f"Document processing completed")
            
            # Wait briefly to ensure processing completes
            await asyncio.sleep(2)
            
            # Verify document status in database
            db_doc = await verify_document_status_in_db(document_id)
            db_success = db_doc is not None and db_doc.status == "processed" and db_doc.progress == "100"
            
            # Verify document in ChromaDB
            chroma_results = verify_document_in_chroma(document_id)
            chroma_success = chroma_results is not None and len(chroma_results["ids"]) > 0
            
            if db_success and chroma_success:
                logger.info("✓✓✓ VERIFICATION SUCCESSFUL: Document correctly processed and stored in both databases")
                return True
            else:
                logger.error(f"× VERIFICATION FAILED: DB Success={db_success}, ChromaDB Success={chroma_success}")
                return False
                
        except Exception as e:
            logger.error(f"Error in processing pipeline: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

async def main():
    """Main function"""
    # Check if file path argument is provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Use a test document if none provided
        uploads_dir = "./uploads"
        logger.info(f"Looking for test documents in {uploads_dir}")
        if os.path.exists(uploads_dir):
            test_docs = [f for f in os.listdir(uploads_dir) if f.endswith(".pdf") or f.endswith(".docx") or f.endswith(".txt")]
            if test_docs:
                file_path = os.path.join(uploads_dir, test_docs[0])
                logger.info(f"Found test document: {file_path}")
            else:
                logger.error("No test documents found in ./uploads directory")
                return
        else:
            logger.error(f"Uploads directory not found: {uploads_dir}")
            return
            
    logger.info(f"Using test document: {file_path}")
    
    # Make sure the file exists and is readable
    if not os.path.exists(file_path):
        logger.error(f"Test file does not exist: {file_path}")
        return
        
    try:
        # Verify the pipeline
        success = await verify_full_pipeline(file_path)
        print(f"\nFinal result: {'SUCCESS' if success else 'FAILURE'}")
    except Exception as e:
        logger.error(f"Unhandled error during verification: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print("\nFinal result: FAILURE - unhandled exception occurred")

if __name__ == "__main__":
    asyncio.run(main())
