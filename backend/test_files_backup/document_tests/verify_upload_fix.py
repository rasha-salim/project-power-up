"""
Verify that the document upload fix works correctly
"""
import os
import asyncio
import logging
import requests
import json
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def get_project_id():
    """Get a project ID from the database"""
    try:
        response = requests.get("http://localhost:8000/api/v1/projects")
        if response.status_code == 200:
            projects = response.json()
            if projects and len(projects) > 0:
                project_id = projects[0]["id"]
                logger.info(f"Using project ID: {project_id}")
                return project_id
        
        logger.warning("No projects found, will create a test project")
        
        # Create a test project
        project_data = {
            "name": "Test Project",
            "description": "Project for testing document uploads"
        }
        
        response = requests.post(
            "http://localhost:8000/api/v1/projects",
            json=project_data
        )
        
        if response.status_code == 200:
            project = response.json()
            project_id = project["id"]
            logger.info(f"Created test project with ID: {project_id}")
            return project_id
        else:
            logger.error(f"Failed to create test project: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error getting project ID: {str(e)}")
        return None

async def test_document_upload(project_id):
    """Test document upload with the fixed endpoint"""
    try:
        # Create a test file
        test_file_path = os.path.join(os.path.dirname(__file__), "test_upload_file.txt")
        with open(test_file_path, "w") as f:
            f.write("This is a test file for verifying the document upload fix.")
        
        logger.info(f"Created test file at {test_file_path}")
        
        # Prepare form data for upload
        files = {
            "file": ("test_upload_file.txt", open(test_file_path, "rb"), "text/plain")
        }
        
        data = {
            "project_id": project_id,
            "description": "Test file for verifying upload fix"
        }
        
        # Upload the file
        logger.info("Uploading test file...")
        response = requests.post(
            "http://localhost:8000/api/v1/documents/upload",
            files=files,
            data=data
        )
        
        # Check response
        logger.info(f"Upload response status: {response.status_code}")
        
        try:
            response_data = response.json()
            logger.info(f"Response data: {json.dumps(response_data, indent=2)}")
        except Exception as e:
            logger.error(f"Failed to parse response as JSON: {str(e)}")
            logger.error(f"Response text: {response.text}")
        
        # Clean up
        files["file"][1].close()
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
        
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error testing document upload: {str(e)}")
        return False

async def main():
    """Main function"""
    # Get a project ID
    project_id = await get_project_id()
    
    if not project_id:
        logger.error("Could not get a project ID, aborting test")
        return
    
    # Test document upload
    success = await test_document_upload(project_id)
    
    if success:
        print("✅ Document upload test passed! The fix works correctly.")
    else:
        print("❌ Document upload test failed. The fix did not resolve the issue.")

if __name__ == "__main__":
    asyncio.run(main())
