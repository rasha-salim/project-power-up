"""
Test script to check for CORS issues with the document upload endpoint
"""
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import logging
import os
import uuid
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a simple test app
app = FastAPI(title="CORS Test App")

# Add CORS middleware with permissive settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create upload directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/api/v1/documents/upload")
async def test_upload(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """
    Test endpoint for document upload
    """
    try:
        # Log request details
        logger.info(f"Document upload request received")
        logger.info(f"File: {file.filename}, Content-Type: {file.content_type}")
        logger.info(f"Project ID: {project_id}, Description: {description}")
        
        # Generate unique ID for the document
        document_id = str(uuid.uuid4())
        logger.info(f"Generated document ID: {document_id}")
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        logger.info(f"File size: {file_size} bytes")
        
        # Save file to disk
        file_extension = os.path.splitext(file.filename)[1].lower()
        file_path = os.path.join(UPLOAD_DIR, f"{document_id}{file_extension}")
        
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"File saved to {file_path}")
        
        # Return success response with proper datetime values
        now = datetime.utcnow().isoformat()
        return {
            "id": document_id,
            "filename": file.filename,
            "status": "pending",
            "message": "Document uploaded successfully",
            "project_id": project_id,
            "description": description,
            "created_at": now,
            "updated_at": now
        }
    except Exception as e:
        logger.error(f"Error in test_upload: {str(e)}")
        return {"detail": str(e)}

if __name__ == "__main__":
    logger.info("Starting CORS test server on port 8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
