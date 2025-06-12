#!/usr/bin/env python
"""
Simple script to check document status in the PostgreSQL database
"""

import asyncio
import json
from sqlalchemy import text
from app.db.init_db_simple import AsyncSessionLocal

async def check_document_status(document_id):
    """Check document status in the database"""
    # Create a database session
    db = AsyncSessionLocal()
    try:
        print(f"Checking document status in database for: {document_id}")
        
        # Query for the document
        result = await db.execute(
            text("SELECT id, filename, status, progress, doc_metadata FROM documents WHERE id = :id"),
            {"id": document_id}
        )
        
        document = result.fetchone()
        
        if document:
            print("\n===== DOCUMENT DATABASE RECORD =====")
            print(f"ID: {document.id}")
            print(f"Filename: {document.filename}")
            print(f"Status: {document.status}")
            print(f"Progress: {document.progress}")
            
            # Print metadata if available
            if hasattr(document, 'doc_metadata') and document.doc_metadata:
                try:
                    if isinstance(document.doc_metadata, str):
                        metadata = json.loads(document.doc_metadata)
                    else:
                        metadata = document.doc_metadata
                        
                    print("\nMetadata:")
                    for key, value in metadata.items():
                        print(f"  {key}: {value}")
                except:
                    print(f"\nRaw metadata: {document.doc_metadata}")
                    
            print("\nDocument has been successfully processed!" if document.status == "processed" else "Document processing is incomplete.")
        else:
            print(f"No document found with ID: {document_id}")
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
    
    finally:
        await db.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python check_db_document_status.py <document_id>")
    else:
        asyncio.run(check_document_status(sys.argv[1]))
