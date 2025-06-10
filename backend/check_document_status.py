#!/usr/bin/env python
"""
Check document processing status in the database and ChromaDB
"""

import asyncio
import sys
import logging
import json
import traceback
from sqlalchemy import text
from app.db.init_db_simple import AsyncSessionLocal, get_chroma_client

# Make sure we capture and display all output
import chromadb

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_document(document_id):
    """Check document status and ChromaDB embeddings"""
    if not document_id:
        print("Please provide a document ID as argument")
        return
    
    print(f"Checking status for document: {document_id}")
    
    # Create a database session
    db = AsyncSessionLocal()
    try:
        # Check document status in database
        result = await db.execute(
            text("SELECT id, filename, status, progress, doc_metadata FROM documents WHERE id = :id"),
            {"id": document_id}
        )
        document = result.fetchone()
        
        if not document:
            logger.error(f"Document with ID {document_id} not found in database")
            return
        
        # Print document info
        print("\n===== DOCUMENT DATABASE STATUS =====")
        print(f"ID: {document.id}")
        print(f"Filename: {document.filename}")
        print(f"Status: {document.status}")
        print(f"Progress: {document.progress}")
        
        # Print metadata if available
        if document.doc_metadata:
            if isinstance(document.doc_metadata, str):
                try:
                    metadata = json.loads(document.doc_metadata)
                    print("\nMetadata:")
                    for key, value in metadata.items():
                        print(f"  {key}: {value}")
                except:
                    print(f"\nMetadata (raw): {document.doc_metadata}")
            else:
                print("\nMetadata:")
                for key, value in document.doc_metadata.items():
                    print(f"  {key}: {value}")
        
        # Check document in ChromaDB
        print("\n===== DOCUMENT CHROMA STATUS =====")
        client = get_chroma_client()
        collection = client.get_or_create_collection("documents")
        
        # Query for the document ID in ChromaDB
        results = collection.get(
            where={"document_id": document_id},
            include=["metadatas", "documents"]
        )
        
        if results and len(results["ids"]) > 0:
            print(f"Document found in ChromaDB with {len(results['ids'])} chunks")
            print(f"First chunk ID: {results['ids'][0]}")
            print(f"Sample text: {results['documents'][0][:100]}..." if results['documents'] else "No text available")
            
            # Show metadata of first chunk
            if results['metadatas'] and len(results['metadatas']) > 0:
                print("\nChunk metadata sample:")
                for key, value in results['metadatas'][0].items():
                    print(f"  {key}: {value}")
        else:
            print("Document not found in ChromaDB. The embedding process may have failed.")
    
    except Exception as e:
        print(f"Error checking document: {str(e)}")
        print(traceback.format_exc())
    
    finally:
        # Close the database session
        await db.close()
        print("Database session closed")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_document_status.py <document_id>")
        sys.exit(1)
        
    document_id = sys.argv[1]
    asyncio.run(check_document(document_id))
