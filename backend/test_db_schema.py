"""
Test the database schema and connection
"""
import asyncio
import logging
from sqlalchemy import text
from app.db.init_db_simple import get_async_db, init_db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_database_schema():
    """Check the database schema and tables"""
    logger.info("Initializing database...")
    await init_db()
    
    logger.info("Checking database schema...")
    async for db in get_async_db():
        try:
            # Check if the documents table exists
            result = await db.execute(text(
                """SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'documents'
                )"""
            ))
            documents_table_exists = result.scalar()
            logger.info(f"Documents table exists: {documents_table_exists}")
            
            if documents_table_exists:
                # Get column names for documents table
                result = await db.execute(text(
                    """SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'documents'"""
                ))
                columns = result.fetchall()
                column_names = [col[0] for col in columns]
                logger.info(f"Documents table columns: {column_names}")
            
            # Check if the projects table exists
            result = await db.execute(text(
                """SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'projects'
                )"""
            ))
            projects_table_exists = result.scalar()
            logger.info(f"Projects table exists: {projects_table_exists}")
            
            if projects_table_exists:
                # Get column names for projects table
                result = await db.execute(text(
                    """SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'projects'"""
                ))
                columns = result.fetchall()
                column_names = [col[0] for col in columns]
                logger.info(f"Projects table columns: {column_names}")
                
                # Get a sample project ID
                result = await db.execute(text("SELECT id FROM projects LIMIT 1"))
                project_id = result.scalar()
                logger.info(f"Sample project ID: {project_id}")
                
                return project_id
        except Exception as e:
            logger.error(f"Error checking database schema: {str(e)}")
            raise

async def test_document_insert(project_id):
    """Test inserting a document record directly into the database"""
    logger.info(f"Testing document insert with project_id: {project_id}")
    
    async for db in get_async_db():
        try:
            # Insert a test document record
            await db.execute(text("""
                INSERT INTO documents (
                    id, filename, file_path, content_type, 
                    file_size, status, project_id, description, 
                    created_at, updated_at
                ) VALUES (
                    :id, :filename, :file_path, :content_type,
                    :file_size, :status, :project_id, :description,
                    NOW(), NOW()
                )
            """), {
                "id": "test-doc-id",
                "filename": "test-document.txt",
                "file_path": "/path/to/test-document.txt",
                "content_type": "text/plain",
                "file_size": 100,
                "status": "pending",
                "project_id": project_id,
                "description": "Test document"
            })
            
            await db.commit()
            logger.info("Test document inserted successfully")
            
            # Verify the document was inserted
            result = await db.execute(text(
                "SELECT * FROM documents WHERE id = :id"
            ), {"id": "test-doc-id"})
            
            document = result.fetchone()
            logger.info(f"Retrieved document: {document}")
            
            # Clean up - delete the test document
            await db.execute(text(
                "DELETE FROM documents WHERE id = :id"
            ), {"id": "test-doc-id"})
            
            await db.commit()
            logger.info("Test document deleted")
            
            return True
        except Exception as e:
            await db.rollback()
            logger.error(f"Error testing document insert: {str(e)}")
            return False

async def main():
    """Main function to run the tests"""
    try:
        # Check database schema
        project_id = await check_database_schema()
        
        if project_id:
            # Test document insert
            insert_success = await test_document_insert(project_id)
            
            if insert_success:
                logger.info("Database tests passed!")
            else:
                logger.error("Document insert test failed")
        else:
            logger.error("No projects found in the database")
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
