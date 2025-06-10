#!/usr/bin/env python
"""
Final ChromaDB test with file output to ensure we can see full results
"""
import os
import sys
import chromadb
import uuid
from datetime import datetime

# Create output file
output_file = "chroma_test_results.txt"
with open(output_file, "w") as f:
    f.write("Starting ChromaDB test...\n")

    # Create a unique document ID for testing
    document_id = str(uuid.uuid4())
    f.write(f"Test document ID: {document_id}\n")

    try:
        # Create ChromaDB directory if it doesn't exist
        chroma_dir = os.path.join(os.getcwd(), "chromadb")
        os.makedirs(chroma_dir, exist_ok=True)
        f.write(f"Using ChromaDB directory: {chroma_dir}\n")
        
        # Create a ChromaDB client
        client = chromadb.PersistentClient(path=chroma_dir)
        f.write("Successfully created ChromaDB client\n")
        
        # Create or get a collection
        collection = client.get_or_create_collection("test_documents")
        f.write("Successfully created/got ChromaDB collection\n")
        
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
        f.write(f"Successfully added document chunk with ID {chunk_id}\n")
        
        # Retrieve the document to verify storage
        results = collection.get(
            where={"document_id": document_id},
            include=["metadatas", "documents"]
        )
        
        if results and len(results["ids"]) > 0:
            f.write(f"Successfully retrieved document from ChromaDB\n")
            f.write(f"Found {len(results['ids'])} chunks\n")
            f.write(f"Document text: {results['documents'][0]}\n")
            f.write(f"Document metadata: {results['metadatas'][0]}\n")
            
            # Check ChromaDB file
            db_file = os.path.join(chroma_dir, "chroma.sqlite3")
            if os.path.exists(db_file):
                mod_time = datetime.fromtimestamp(os.path.getmtime(db_file))
                f.write(f"ChromaDB file exists and was last modified: {mod_time}\n")
                f.write(f"File size: {os.path.getsize(db_file)} bytes\n")
                f.write("✅ TEST PASSED: ChromaDB integration is working correctly!\n")
            else:
                f.write("❌ TEST FAILED: ChromaDB file does not exist\n")
        else:
            f.write("❌ TEST FAILED: Could not retrieve document from ChromaDB\n")

    except Exception as e:
        f.write(f"Error during ChromaDB test: {str(e)}\n")
        import traceback
        f.write(traceback.format_exc() + "\n")
        f.write("❌ TEST FAILED\n")

    f.write("ChromaDB test completed.\n")

print(f"Test completed. Results written to {output_file}")
print("Checking file size to verify ChromaDB file creation...")
db_file = os.path.join(os.getcwd(), "chromadb", "chroma.sqlite3")
if os.path.exists(db_file):
    print(f"ChromaDB file exists with size: {os.path.getsize(db_file)} bytes")
    print(f"Last modified: {datetime.fromtimestamp(os.path.getmtime(db_file))}")
    print("✅ CHROMA INTEGRATION IS WORKING!")
else:
    print("❌ ChromaDB file does not exist")
