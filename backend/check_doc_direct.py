#!/usr/bin/env python
import asyncio
import sys
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Database connection details from your app config
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/powerup"

async def check_document():
    # Get document ID from command line
    if len(sys.argv) < 2:
        print("Usage: python check_doc_direct.py <document_id>")
        return
    
    document_id = sys.argv[1]
    print(f"Checking document: {document_id}")
    
    # Create engine and session
    engine = create_async_engine(DATABASE_URL)
    
    # Check database
    async with AsyncSession(engine) as session:
        # Query document status
        result = await session.execute(
            text("SELECT id, filename, status, progress FROM documents WHERE id = :id"),
            {"id": document_id}
        )
        document = result.fetchone()
        
        if document:
            print("\n=== DATABASE STATUS ===")
            print(f"ID: {document.id}")
            print(f"Filename: {document.filename}")
            print(f"Status: {document.status}")
            print(f"Progress: {document.progress}")
            
            # Check if fully processed
            if document.status == "processed" and document.progress == "100":
                print("\n✅ Document processing COMPLETED successfully")
            else:
                print(f"\n❌ Document processing INCOMPLETE: Status={document.status}, Progress={document.progress}")
        else:
            print(f"\n❌ No document found with ID: {document_id}")
    
    # Check ChromaDB folder size as a simple verification
    chroma_path = os.path.join(os.getcwd(), "chromadb")
    if os.path.exists(chroma_path):
        db_file = os.path.join(chroma_path, "chroma.sqlite3")
        if os.path.exists(db_file):
            size_mb = os.path.getsize(db_file) / (1024 * 1024)
            print(f"\n=== CHROMADB STATUS ===")
            print(f"ChromaDB exists: {os.path.exists(chroma_path)}")
            print(f"Database file size: {size_mb:.2f} MB")
            print(f"Database file modified: {os.path.getmtime(db_file)}")
            
            if size_mb > 0.1:  # If database is larger than 100KB
                print("\n✅ ChromaDB appears to contain data")
            else:
                print("\n⚠️ ChromaDB file exists but may be empty")
        else:
            print("\n❌ ChromaDB database file not found")
    else:
        print("\n❌ ChromaDB directory not found")

if __name__ == "__main__":
    asyncio.run(check_document())
