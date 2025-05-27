"""
Direct test script for document upload endpoint
"""
import os
import asyncio
import logging
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.init_db_simple import get_async_db, init_db
from app.core.config import settings
import uuid
from datetime import datetime
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def test_direct_upload(project_id: str):
    """Test the document upload process directly"""
    logger.info(f"Testing direct upload with project_id: {project_id}")
    
    # Create a test file
    test_file_path = os.path.join(os.path.dirname(__file__), "test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("This is a test file for document upload testing.")
    
    logger.info(f"Created test file at {test_file_path}")
    
    # Create a mock UploadFile object
    class MockUploadFile:
        def __init__(self, filename, content_type):
            self.filename = filename
            self.content_type = content_type
            self._file = open(test_file_path, "rb")
        
        async def read(self):
            return self._file.read()
        
        async def seek(self, offset):
            self._file.seek(offset)
        
        def close(self):
            self._file.close()
    
    mock_file = MockUploadFile("test_file.txt", "text/plain")
    
    try:
        # Generate a unique document ID
        document_id = str(uuid.uuid4())
        logger.info(f"Generated document ID: {document_id}")
        
        # Create upload directory if it doesn't exist
        upload_dir = settings.UPLOAD_DIRECTORY
        os.makedirs(upload_dir, exist_ok=True)
        logger.info(f"Upload directory: {upload_dir}")
        
        # Get file content and save to disk
        content = await mock_file.read()
        file_size = len(content)
        logger.info(f"File size: {file_size} bytes")
        
        # Prepare file path
        file_extension = os.path.splitext(mock_file.filename)[1].lower()
        file_path = os.path.join(upload_dir, f"{document_id}{file_extension}")
        logger.info(f"File will be saved to: {file_path}")
        
        # Save file to disk
        try:
            with open(file_path, "wb") as f:
                f.write(content)
            logger.info(f"File saved successfully to disk")
        except Exception as e:
            logger.error(f"Error saving file to disk: {str(e)}")
            return False
        
        # Reset file position for potential future reads
        await mock_file.seek(0)
        logger.info("File position reset for future reads")
        
        # Get a database session
        async for db in get_async_db():
            try:
                # Check if the documents table exists
                logger.info("Checking if documents table exists")
                result = await db.execute(text(
                    """SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'documents'
                    )"""
                ))
                table_exists = result.scalar()
                logger.info(f"Documents table exists: {table_exists}")
                
                if not table_exists:
                    logger.info("Creating documents table")
                    await db.execute(text("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        content_type TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        project_id TEXT,
                        description TEXT,
                        created_at TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP NOT NULL
                    )
                    """))
                    await db.commit()
                    logger.info("Documents table created successfully")
                
                # Get column names
                logger.info("Getting column names from documents table")
                result = await db.execute(text(
                    """SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'documents'"""
                ))
                columns = result.fetchall()
                column_names = [col[0] for col in columns]
                logger.info(f"Existing columns in documents table: {column_names}")
                
                # Check if project exists
                if project_id:
                    logger.info(f"Checking if project {project_id} exists")
                    result = await db.execute(text(
                        """SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'projects'
                        )"""
                    ))
                    projects_table_exists = result.scalar()
                    
                    if projects_table_exists:
                        result = await db.execute(text(
                            "SELECT COUNT(*) FROM projects WHERE id = :project_id"
                        ), {"project_id": project_id})
                        project_count = result.scalar()
                        logger.info(f"Project exists: {project_count > 0}")
                        
                        if project_count == 0:
                            logger.warning(f"Project {project_id} does not exist in the database")
                
                # Insert document record
                now = datetime.utcnow()
                
                # Prepare SQL query
                columns_str = "id, filename, file_path, content_type, file_size, "
                values_str = ":id, :filename, :file_path, :content_type, :file_size, "
                params = {
                    "id": document_id,
                    "filename": mock_file.filename,
                    "file_path": file_path,
                    "content_type": mock_file.content_type,
                    "file_size": file_size
                }
                
                # Add remaining columns
                columns_str += "status, project_id, description, created_at, updated_at"
                values_str += ":status, :project_id, :description, :created_at, :updated_at"
                params.update({
                    "status": "pending",
                    "project_id": project_id,
                    "description": "Test document upload",
                    "created_at": now,
                    "updated_at": now
                })
                
                # Log the SQL query and parameters
                logger.info(f"SQL Insert Query: INSERT INTO documents ({columns_str}) VALUES ({values_str})")
                
                # Execute insert query
                try:
                    await db.execute(
                        text(f"INSERT INTO documents ({columns_str}) VALUES ({values_str})"),
                        params
                    )
                    logger.info("Document record inserted successfully")
                    
                    await db.commit()
                    logger.info("Database transaction committed successfully")
                    
                    # Verify document was inserted
                    result = await db.execute(text(
                        "SELECT * FROM documents WHERE id = :id"
                    ), {"id": document_id})
                    document = result.fetchone()
                    
                    if document:
                        logger.info(f"Document retrieved successfully: {document}")
                        return True
                    else:
                        logger.error("Document not found in database after insert")
                        return False
                    
                except Exception as e:
                    logger.error(f"Error executing SQL insert: {str(e)}")
                    logger.error(f"Error type: {type(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    await db.rollback()
                    return False
            
            except Exception as e:
                logger.error(f"Database error: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return False
    
    except Exception as e:
        logger.error(f"Error in test_direct_upload: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False
    finally:
        # Clean up
        mock_file.close()
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

async def main():
    """Main function"""
    # Initialize database
    await init_db()
    
    # Get a project ID from the database
    project_id = None
    async for db in get_async_db():
        try:
            result = await db.execute(text("SELECT id FROM projects LIMIT 1"))
            project_id = result.scalar()
            if project_id:
                logger.info(f"Using project ID from database: {project_id}")
            else:
                logger.warning("No projects found in the database")
                # Create a test project
                project_id = str(uuid.uuid4())
                logger.info(f"Created test project ID: {project_id}")
                
                # Check if projects table exists
                result = await db.execute(text(
                    """SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'projects'
                    )"""
                ))
                table_exists = result.scalar()
                
                if not table_exists:
                    logger.info("Creating projects table")
                    await db.execute(text("""
                    CREATE TABLE IF NOT EXISTS projects (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        status TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP NOT NULL
                    )
                    """))
                
                # Insert test project
                now = datetime.utcnow()
                await db.execute(
                    text("""
                    INSERT INTO projects (id, name, description, status, created_at, updated_at)
                    VALUES (:id, :name, :description, :status, :created_at, :updated_at)
                    """),
                    {
                        "id": project_id,
                        "name": "Test Project",
                        "description": "Project for testing document uploads",
                        "status": "active",
                        "created_at": now,
                        "updated_at": now
                    }
                )
                await db.commit()
                logger.info(f"Test project created with ID: {project_id}")
        except Exception as e:
            logger.error(f"Error getting/creating project: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return
    
    if not project_id:
        logger.error("Could not get or create a project ID")
        return
    
    # Test direct upload
    success = await test_direct_upload(project_id)
    
    if success:
        print("✅ Document upload test completed successfully!")
    else:
        print("❌ Document upload test failed. Check the logs for details.")

if __name__ == "__main__":
    asyncio.run(main())
