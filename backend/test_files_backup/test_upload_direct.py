"""
Test the document upload endpoint directly using FastAPI's TestClient
"""
import os
import logging
from fastapi.testclient import TestClient
from app.main import app

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create test client
client = TestClient(app)

# Create a test file
TEST_FILE_PATH = os.path.join(os.path.dirname(__file__), "test_document.txt")

def create_test_file():
    """Create a simple test file for upload"""
    with open(TEST_FILE_PATH, "w") as f:
        f.write("This is a test document for upload testing.")
    logger.info(f"Created test file at {TEST_FILE_PATH}")
    return TEST_FILE_PATH

def test_document_upload(project_id="test-project-id"):
    """Test the document upload endpoint directly"""
    # Create test file if it doesn't exist
    if not os.path.exists(TEST_FILE_PATH):
        create_test_file()
    
    # Open the file for reading
    with open(TEST_FILE_PATH, "rb") as f:
        # Prepare form data
        files = {"file": ("test_document.txt", f, "text/plain")}
        data = {
            "project_id": project_id,
            "description": "Test document upload"
        }
        
        logger.info(f"Testing document upload with project_id: {project_id}")
        
        # Send request to the test client
        response = client.post("/api/v1/documents/upload", files=files, data=data)
        
        # Log response
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")
        
        try:
            logger.info(f"Response body: {response.json()}")
        except Exception as e:
            logger.error(f"Failed to parse response as JSON: {response.text}")
        
        return response

if __name__ == "__main__":
    import sys
    import traceback
    
    # Get project ID from command line if provided
    project_id = "test-project-id"
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
    
    try:
        # Run the test
        print(f"Starting document upload test with project_id: {project_id}")
        response = test_document_upload(project_id)
        
        # Print result
        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {response.headers}")
        
        try:
            print(f"Response body: {response.json()}")
        except Exception as e:
            print(f"Failed to parse response as JSON: {response.text}")
        
        if response.status_code == 200:
            print("Document upload test passed!")
        else:
            print(f"Document upload test failed with status code {response.status_code}")
    except Exception as e:
        print(f"Exception during test: {str(e)}")
        traceback.print_exc()
