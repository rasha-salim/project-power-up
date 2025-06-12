"""
Simple test server to debug document upload issues
"""
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
app = FastAPI(title="Simple Test Server")

# Add CORS middleware with permissive settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create upload directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "test_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload")
async def simple_upload(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None)
):
    """
    Simple upload endpoint for testing
    """
    try:
        # Log request details
        logger.info(f"Upload request received")
        logger.info(f"File: {file.filename}, Content-Type: {file.content_type}")
        logger.info(f"Project ID: {project_id}")
        
        # Generate unique ID
        doc_id = str(uuid.uuid4())
        
        # Save file to disk
        file_extension = os.path.splitext(file.filename)[1].lower()
        file_path = os.path.join(UPLOAD_DIR, f"{doc_id}{file_extension}")
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"File saved to {file_path}")
        
        # Return success response
        return {
            "id": doc_id,
            "filename": file.filename,
            "status": "success",
            "project_id": project_id
        }
    except Exception as e:
        logger.error(f"Error in upload: {str(e)}")
        return {"error": str(e)}

@app.get("/")
async def root():
    return {"message": "Simple test server is running"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting simple test server on port 8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)
