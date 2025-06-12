import requests
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API endpoint
BASE_URL = "http://localhost:8000"
UPLOAD_URL = f"{BASE_URL}/api/v1/documents/upload"

# Project ID - replace with a valid project ID from your database
PROJECT_ID = "replace_with_valid_project_id"  # You'll need to update this

# Test file path - create a simple test file
TEST_FILE_PATH = os.path.join(os.path.dirname(__file__), "test_document.txt")

def create_test_file():
    """Create a simple test file for upload"""
    with open(TEST_FILE_PATH, "w") as f:
        f.write("This is a test document for upload testing.")
    logger.info(f"Created test file at {TEST_FILE_PATH}")
    return TEST_FILE_PATH

def test_document_upload():
    """Test the document upload endpoint"""
    # Create test file if it doesn't exist
    if not os.path.exists(TEST_FILE_PATH):
        create_test_file()
    
    # Prepare form data
    files = {'file': open(TEST_FILE_PATH, 'rb')}
    data = {
        'project_id': PROJECT_ID,
        'description': 'Test document upload'
    }
    
    logger.info(f"Sending POST request to {UPLOAD_URL}")
    logger.info(f"Project ID: {PROJECT_ID}")
    
    # Send request
    try:
        response = requests.post(UPLOAD_URL, files=files, data=data)
        logger.info(f"Response status code: {response.status_code}")
        
        # Try to parse response as JSON
        try:
            response_json = response.json()
            logger.info(f"Response JSON: {json.dumps(response_json, indent=2)}")
        except json.JSONDecodeError:
            logger.error(f"Failed to parse response as JSON: {response.text}")
        
        # Check response status
        if response.status_code == 200:
            logger.info("Document upload successful!")
            return True
        else:
            logger.error(f"Document upload failed with status {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Exception during upload: {str(e)}")
        return False
    finally:
        # Close the file
        files['file'].close()

def test_document_upload_with_curl():
    """Test the document upload endpoint using curl command"""
    import subprocess
    
    curl_command = f'curl -v -F "file=@{TEST_FILE_PATH}" -F "project_id={PROJECT_ID}" -F "description=Test document upload" {UPLOAD_URL}'
    logger.info(f"Executing curl command: {curl_command}")
    
    try:
        result = subprocess.run(curl_command, shell=True, check=True, capture_output=True, text=True)
        logger.info(f"Curl output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Curl command failed: {e}")
        logger.error(f"Stderr: {e.stderr}")
        return False

if __name__ == "__main__":
    # Get a valid project ID from command line if provided
    import sys
    if len(sys.argv) > 1:
        PROJECT_ID = sys.argv[1]
        logger.info(f"Using project ID from command line: {PROJECT_ID}")
    
    # Test using Python requests
    logger.info("Testing document upload using Python requests...")
    result = test_document_upload()
    
    # Test using curl
    logger.info("\nTesting document upload using curl...")
    curl_result = test_document_upload_with_curl()
    
    if result and curl_result:
        logger.info("All tests passed!")
    else:
        logger.error("Some tests failed.")
