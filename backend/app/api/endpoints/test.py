import logging
from fastapi import APIRouter, File, UploadFile, HTTPException
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/simple-upload")
def simple_upload(file: UploadFile = File(...)):
    """
    Absolute minimal test endpoint with no async/await
    """
    try:
        # Read file content synchronously
        content = file.file.read()
        
        # Reset file position
        file.file.seek(0)
        
        # Generate test ID
        test_id = str(uuid.uuid4())
        
        return {
            "size": len(content),
            "filename": file.filename,
            "test_id": test_id,
            "message": "Simple test successful"
        }
    except Exception as e:
        logger.error(f"Error in simple upload: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error in simple upload: {str(e)}")
