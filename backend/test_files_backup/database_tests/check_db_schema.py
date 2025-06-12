"""
Check the database schema to identify column names in the documents table
"""
import asyncio
import logging
from sqlalchemy import text
from app.db.init_db_simple import get_async_db, init_db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_db_schema():
    """Check the database schema and print column names"""
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
                
                # Check for size-related columns
                size_columns = [col for col in column_names if 'size' in col.lower()]
                logger.info(f"Size-related columns: {size_columns}")
                
                # Get a sample document if any exist
                result = await db.execute(text("SELECT * FROM documents LIMIT 1"))
                document = result.fetchone()
                if document:
                    document_dict = dict(zip(result.keys(), document))
                    logger.info(f"Sample document: {document_dict}")
            
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
                
                # Get a sample project if any exist
                result = await db.execute(text("SELECT * FROM projects LIMIT 1"))
                project = result.fetchone()
                if project:
                    project_dict = dict(zip(result.keys(), project))
                    logger.info(f"Sample project: {project_dict}")
            
            return True
        except Exception as e:
            logger.error(f"Error checking database schema: {str(e)}")
            return False

async def main():
    """Main function"""
    # Initialize database
    await init_db()
    
    # Check database schema
    success = await check_db_schema()
    
    if success:
        print("Database schema check completed successfully!")
    else:
        print("Database schema check failed. Check the logs for details.")

if __name__ == "__main__":
    asyncio.run(main())
