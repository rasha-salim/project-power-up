#!/usr/bin/env python
"""
Test script to verify ChromaDB storage works independently
"""
import os
import sys
import chromadb
import uuid
from datetime import datetime

def test_chromadb_storage():
    """Test storing and retrieving documents from ChromaDB"""
    print("Testing ChromaDB storage...")
    
    # Create a unique document ID for testing
    document_id = str(uuid.uuid4())
    print(f"Test document ID: {document_id}")
    
    try:
        # Create ChromaDB directory if it doesn't exist
        chroma_dir = os.path.join(os.getcwd(), "chromadb")
        os.makedirs(chroma_dir, exist_ok=True)
        print(f"Using ChromaDB directory: {chroma_dir}")
        
        # Create a ChromaDB client
        client = chromadb.PersistentClient(path=chroma_dir)
        print("Successfully created ChromaDB client")
        
        # Create or get a collection
        collection = client.get_or_create_collection("documents")
        print("Successfully created/got ChromaDB collection")
        
        # Test data
        chunk_text = f"This is a test document with ID {document_id} created at {datetime.now()}"
        chunk_id = f"{document_id}_chunk_0"
        
        # Store a test document
        collection.add(
            ids=[chunk_id],
            documents=[chunk_text],
            metadatas=[{
                "document_id": document_id,
                "chunk_number": 0,
                "total_chunks": 1,
                "filename": "test_document.txt",
                "file_extension": ".txt",
                "processing_date": str(datetime.now())
            }]
        )
        print(f"Successfully added document chunk with ID {chunk_id}")
        
        # Retrieve the document to verify storage
        results = collection.get(
            where={"document_id": document_id},
            include=["metadatas", "documents"]
        )
        
        if results and len(results["ids"]) > 0:
            print(f"Successfully retrieved document from ChromaDB")
            print(f"Found {len(results['ids'])} chunks")
            print(f"Document text: {results['documents'][0]}")
            print(f"Document metadata: {results['metadatas'][0]}")
            
            # Check ChromaDB file timestamp
            db_file = os.path.join(chroma_dir, "chroma.sqlite3")
            if os.path.exists(db_file):
                mod_time = datetime.fromtimestamp(os.path.getmtime(db_file))
                print(f"ChromaDB file last modified: {mod_time}")
            
            return True
        else:
            print("Failed to retrieve the document from ChromaDB")
            return False
    
    except Exception as e:
        print(f"Error testing ChromaDB: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_chromadb_storage()
    print(f"ChromaDB test {'succeeded' if success else 'failed'}")
    sys.exit(0 if success else 1)
