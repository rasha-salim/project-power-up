"""
Script to test PostgreSQL connection
"""
import os
import logging
import psycopg2
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Database connection settings from .env file
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "adam15")
POSTGRES_SERVER = os.getenv("POSTGRES_SERVER", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "project_planning")

# Construct the database URL
DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"

def test_connection():
    """Test the PostgreSQL connection"""
    try:
        logger.info(f"Testing connection to: {DATABASE_URL}")
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=POSTGRES_SERVER,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            dbname=POSTGRES_DB
        )
        
        # Create a cursor
        cursor = conn.cursor()
        
        # Execute a simple query
        cursor.execute("SELECT version();")
        
        # Fetch the result
        version = cursor.fetchone()
        logger.info(f"PostgreSQL version: {version[0]}")
        
        # List all tables
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = cursor.fetchall()
        logger.info("Tables in database:")
        for table in tables:
            logger.info(f"  - {table[0]}")
            
            # Count rows in the table
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]};")
            count = cursor.fetchone()[0]
            logger.info(f"    Rows: {count}")
        
        # Close the cursor and connection
        cursor.close()
        conn.close()
        
        logger.info("Connection test successful!")
        return True
        
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    test_connection()
