#!/usr/bin/env python
"""
Simple standalone ChromaDB test that doesn't rely on the full document processing pipeline
"""
import os
import sys
import chromadb
import uuid
from datetime import datetime

print("Starting ChromaDB test...")

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
    collection = client.get_or_create_collection("test_documents")
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
        
        # Check ChromaDB file
        db_file = os.path.join(chroma_dir, "chroma.sqlite3")
        if os.path.exists(db_file):
            mod_time = datetime.fromtimestamp(os.path.getmtime(db_file))
            print(f"ChromaDB file exists and was last modified: {mod_time}")
            print(f"File size: {os.path.getsize(db_file)} bytes")
            print("✅ TEST PASSED: ChromaDB integration is working correctly!")
        else:
            print("❌ TEST FAILED: ChromaDB file does not exist")
    else:
        print("❌ TEST FAILED: Could not retrieve document from ChromaDB")

except Exception as e:
    print(f"Error during ChromaDB test: {str(e)}")
    import traceback
    print(traceback.format_exc())
    print("❌ TEST FAILED")

print("ChromaDB test completed.")
