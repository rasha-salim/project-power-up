import asyncio
import os
import sys
import logging
from app.db.init_db_simple import get_async_db, get_chroma_client
from app.services.document_processor import DocumentProcessor
from app.models.document import DocumentCreate, Document

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_processing():
    """Simple test for document processing and ChromaDB storage"""
    # Find a test document
    uploads_dir = "./uploads"
    test_files = [f for f in os.listdir(uploads_dir) 
                 if f.endswith(".pdf") or f.endswith(".docx") or f.endswith(".txt")]
    
    if not test_files:
        logger.error("No test files found in uploads directory")
        return False
    
    test_file = os.path.join(uploads_dir, test_files[0])
    logger.info(f"Testing with file: {test_file}")
    
    # Create document processor
    processor = DocumentProcessor()
    document_id = None
    
    # Create and process document
    async for db in get_async_db():
        try:
            # Create document
            doc = DocumentCreate(
                filename=os.path.basename(test_file),
                file_path=test_file,
                project_id="test_project"
            )
            
            created_doc = await processor.create_document(db, doc)
            document_id = created_doc.id
            logger.info(f"Created document with ID: {document_id}")
            
            # Process the document
            await processor.process_document(db, document_id, test_file)
            
            # Check status
            result = await db.execute(f"SELECT status, progress FROM documents WHERE id = '{document_id}'")
            doc_status = result.fetchone()
            logger.info(f"Document status: {doc_status}")
            
            # Check ChromaDB
            client = get_chroma_client()
            collection = client.get_or_create_collection("documents")
            results = collection.get(
                where={"document_id": document_id},
                include=["metadatas", "documents"]
            )
            
            if results and len(results["ids"]) > 0:
                logger.info(f"Found {len(results['ids'])} chunks in ChromaDB")
                logger.info(f"First chunk: {results['documents'][0][:50]}...")
                logger.info("SUCCESS: Document processed and stored in ChromaDB")
                return True
            else:
                logger.error("No chunks found in ChromaDB")
                return False
                
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False

if __name__ == "__main__":
    asyncio.run(test_processing())
