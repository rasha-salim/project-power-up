"""
Script to test SQLAlchemy connection to PostgreSQL
"""
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
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

def test_sqlalchemy_connection():
    """Test the SQLAlchemy connection to PostgreSQL"""
    try:
        logger.info(f"Testing SQLAlchemy connection to: {DATABASE_URL}")
        
        # Create engine
        engine = create_engine(DATABASE_URL, echo=True)
        
        # Create session
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Test connection with a simple query
        result = session.execute(text("SELECT version();"))
        version = result.scalar()
        logger.info(f"PostgreSQL version: {version}")
        
        # List all tables
        result = session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"))
        tables = result.fetchall()
        logger.info("Tables in database:")
        for table in tables:
            logger.info(f"  - {table[0]}")
            
            # Count rows in the table
            count_result = session.execute(text(f"SELECT COUNT(*) FROM {table[0]};"))
            count = count_result.scalar()
            logger.info(f"    Rows: {count}")
        
        # Close the session
        session.close()
        
        logger.info("SQLAlchemy connection test successful!")
        return True
        
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL with SQLAlchemy: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    test_sqlalchemy_connection()
