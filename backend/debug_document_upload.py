"""
Debug script for document upload issues
"""
import os
import sys
import asyncio
import logging
from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.init_db_simple import get_async_db, init_db
from app.core.config import settings
import uuid
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def debug_document_upload(project_id: str):
    """Debug the document upload process step by step"""
    logger.info("=== Starting Document Upload Debug ===")
    
    # Step 1: Check if project exists
    logger.info("Step 1: Checking if project exists")
    project_exists = False
    
    async for db in get_async_db():
        try:
            result = await db.execute(
                text("SELECT COUNT(*) FROM projects WHERE id = :project_id"),
                {"project_id": project_id}
            )
            count = result.scalar()
            project_exists = count > 0
            logger.info(f"Project exists: {project_exists}")
            
            if not project_exists:
                logger.error(f"Project with ID {project_id} does not exist")
                return False
            
            # Step 2: Create test file
            logger.info("Step 2: Creating test file")
            test_file_path = os.path.join(os.path.dirname(__file__), "debug_test_doc.txt")
            with open(test_file_path, "w") as f:
                f.write("This is a test document for debugging the upload process.")
            logger.info(f"Test file created at: {test_file_path}")
            
            # Step 3: Simulate file upload process
            logger.info("Step 3: Simulating file upload process")
            document_id = str(uuid.uuid4())
            logger.info(f"Generated document ID: {document_id}")
            
            # Create upload directory
            upload_dir = settings.UPLOAD_DIRECTORY
            os.makedirs(upload_dir, exist_ok=True)
            logger.info(f"Upload directory: {upload_dir}")
            
            # Read file content
            with open(test_file_path, "rb") as f:
                content = f.read()
            file_size = len(content)
            logger.info(f"File size: {file_size} bytes")
            
            # Prepare file path
            file_extension = ".txt"
            file_path = os.path.join(upload_dir, f"{document_id}{file_extension}")
            logger.info(f"Target file path: {file_path}")
            
            # Save file to disk
            try:
                with open(file_path, "wb") as f:
                    f.write(content)
                logger.info("File saved successfully to disk")
            except Exception as e:
                logger.error(f"Error saving file to disk: {str(e)}")
                return False
            
            # Step 4: Insert document record into database
            logger.info("Step 4: Inserting document record into database")
            
            # Check if documents table exists
            result = await db.execute(text(
                """SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'documents'
                )"""
            ))
            table_exists = result.scalar()
            logger.info(f"Documents table exists: {table_exists}")
            
            if not table_exists:
                logger.error("Documents table does not exist")
                return False
            
            # Get column names
            result = await db.execute(text(
                """SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'documents'"""
            ))
            columns = result.fetchall()
            column_names = [col[0] for col in columns]
            logger.info(f"Documents table columns: {column_names}")
            
            # Check if required columns exist
            required_columns = ["id", "filename", "file_path", "content_type", "status", "project_id"]
            missing_columns = [col for col in required_columns if col not in column_names]
            
            if missing_columns:
                logger.error(f"Missing required columns: {missing_columns}")
                return False
            
            # Check if 'file_size' or 'size' column exists
            size_column = 'file_size' if 'file_size' in column_names else 'size'
            if size_column not in column_names:
                logger.error(f"Neither 'file_size' nor 'size' column exists")
                return False
            
            logger.info(f"Using size column: {size_column}")
            
            # Insert document using dynamic SQL based on existing columns
            now = datetime.utcnow()
            logger.info(f"Current timestamp: {now}")
            
            # Prepare SQL query based on existing columns
            columns_str = "id, filename, file_path, content_type, "
            values_str = ":id, :filename, :file_path, :content_type, "
            params = {
                "id": document_id,
                "filename": "debug_test_doc.txt",
                "file_path": file_path,
                "content_type": "text/plain"
            }
            
            # Add size parameter with appropriate column name
            columns_str += f"{size_column}, "
            values_str += f":{size_column}, "
            params[size_column] = file_size
            
            # Add remaining columns
            columns_str += "status, project_id, description, created_at, updated_at"
            values_str += ":status, :project_id, :description, :created_at, :updated_at"
            params.update({
                "status": "pending",
                "project_id": project_id,
                "description": "Debug test document",
                "created_at": now,
                "updated_at": now
            })
            
            # Log the SQL query and parameters
            logger.info(f"SQL Insert Query: INSERT INTO documents ({columns_str}) VALUES ({values_str})")
            logger.info(f"Parameters: {params}")
            
            # Execute insert query
            try:
                await db.execute(
                    text(f"INSERT INTO documents ({columns_str}) VALUES ({values_str})"),
                    params
                )
                logger.info("Document record inserted successfully")
                
                await db.commit()
                logger.info("Database transaction committed successfully")
                
                # Step 5: Verify document was inserted
                logger.info("Step 5: Verifying document was inserted")
                result = await db.execute(
                    text("SELECT * FROM documents WHERE id = :id"),
                    {"id": document_id}
                )
                document = result.fetchone()
                
                if document:
                    logger.info(f"Document retrieved successfully: {document}")
                    logger.info("=== Document Upload Debug Successful ===")
                    return True
                else:
                    logger.error("Document not found in database after insert")
                    return False
                
            except Exception as e:
                logger.error(f"Error executing SQL insert: {str(e)}")
                logger.error(f"Error type: {type(e)}")
                await db.rollback()
                logger.info("Database transaction rolled back due to error")
                return False
                
        except Exception as e:
            logger.error(f"Error in debug_document_upload: {str(e)}")
            return False

async def main():
    """Main function"""
    if len(sys.argv) < 2:
        logger.error("Please provide a project ID as a command line argument")
        print("Usage: python debug_document_upload.py <project_id>")
        return
    
    project_id = sys.argv[1]
    logger.info(f"Using project ID: {project_id}")
    
    # Initialize database
    await init_db()
    
    # Run debug process
    success = await debug_document_upload(project_id)
    
    if success:
        print("Document upload debug process completed successfully!")
    else:
        print("Document upload debug process failed. Check the logs for details.")

if __name__ == "__main__":
    asyncio.run(main())
