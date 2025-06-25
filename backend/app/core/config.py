import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, validator

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    PROJECT_NAME: str = "Intelligent Project Planning System"
    API_V1_STR: str = "/api/v1"
    
    # CORS settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Database settings - Unified configuration
    DATABASE_TYPE: str = os.getenv("DATABASE_TYPE", "postgresql")  # postgresql or sqlite
    
    # PostgreSQL settings (used when DATABASE_TYPE=postgresql)
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "project_planning")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    
    # SQLite settings (used when DATABASE_TYPE=sqlite)
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "./project_powerup.db")
    
    # Unified database URI
    DATABASE_URI: Optional[str] = None
    
    @validator("DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: dict) -> str:
        """Assemble database connection string based on DATABASE_TYPE"""
        if isinstance(v, str) and v:
            # If DATABASE_URI is explicitly provided, use it
            return v
        
        database_type = values.get("DATABASE_TYPE", "postgresql").lower()
        
        if database_type == "sqlite":
            sqlite_path = values.get("SQLITE_PATH", "./project_powerup.db")
            return f"sqlite:///{sqlite_path}"
        
        elif database_type == "postgresql":
            postgres_user = values.get("POSTGRES_USER")
            postgres_password = values.get("POSTGRES_PASSWORD")
            postgres_server = values.get("POSTGRES_SERVER")
            postgres_port = values.get("POSTGRES_PORT")
            postgres_db = values.get("POSTGRES_DB", "")
            
            # Validate required PostgreSQL settings
            if not all([postgres_user, postgres_password, postgres_server, postgres_db]):
                raise ValueError(
                    "PostgreSQL configuration incomplete. Required: "
                    "POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_SERVER, POSTGRES_DB"
                )
            
            return f"postgresql://{postgres_user}:{postgres_password}@{postgres_server}:{postgres_port}/{postgres_db}"
        
        else:
            raise ValueError(f"Unsupported DATABASE_TYPE: {database_type}. Use 'postgresql' or 'sqlite'")
    
    @property
    def async_database_uri(self) -> str:
        """Get async version of database URI for PostgreSQL"""
        if self.DATABASE_URI.startswith("postgresql://"):
            return self.DATABASE_URI.replace("postgresql://", "postgresql+asyncpg://")
        return self.DATABASE_URI
    
    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database"""
        return self.DATABASE_TYPE.lower() == "sqlite"
    
    @property
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL database"""
        return self.DATABASE_TYPE.lower() == "postgresql"
    
    # Vector DB settings
    CHROMA_PERSIST_DIRECTORY: str = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
    
    # Anthropic API settings
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
    
    # File upload settings
    UPLOAD_DIRECTORY: str = os.getenv("UPLOAD_DIRECTORY", "./uploads")
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB
    
    def validate_required_settings(self) -> Dict[str, Any]:
        """
        Comprehensive validation of all required settings
        Returns validation results with errors, warnings, and status
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks_performed": []
        }
        
        # 1. Validate Anthropic API key
        validation_result["checks_performed"].append("Anthropic API Configuration")
        if not self.ANTHROPIC_API_KEY:
            validation_result["errors"].append("ANTHROPIC_API_KEY is required for AI functionality")
            validation_result["valid"] = False
        elif self.ANTHROPIC_API_KEY == "your_anthropic_api_key_here":
            validation_result["warnings"].append("ANTHROPIC_API_KEY appears to be a placeholder value")
        
        # 2. Validate database configuration
        validation_result["checks_performed"].append("Database Configuration")
        if self.is_postgresql:
            required_postgres_vars = [
                ("POSTGRES_USER", self.POSTGRES_USER),
                ("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD), 
                ("POSTGRES_SERVER", self.POSTGRES_SERVER),
                ("POSTGRES_DB", self.POSTGRES_DB)
            ]
            for var_name, var_value in required_postgres_vars:
                if not var_value:
                    validation_result["errors"].append(f"{var_name} is required for PostgreSQL")
                    validation_result["valid"] = False
        elif self.is_sqlite:
            if not self.SQLITE_PATH:
                validation_result["errors"].append("SQLITE_PATH is required for SQLite")
                validation_result["valid"] = False
        else:
            validation_result["errors"].append(f"Invalid DATABASE_TYPE: {self.DATABASE_TYPE}. Must be 'postgresql' or 'sqlite'")
            validation_result["valid"] = False
        
        # 3. Validate directories and paths
        validation_result["checks_performed"].append("Directory Validation")
        directories_to_check = [
            ("UPLOAD_DIRECTORY", self.UPLOAD_DIRECTORY),
            ("CHROMA_PERSIST_DIRECTORY", self.CHROMA_PERSIST_DIRECTORY)
        ]
        
        for dir_name, dir_path in directories_to_check:
            try:
                path_obj = Path(dir_path)
                if not path_obj.exists():
                    # Try to create the directory
                    path_obj.mkdir(parents=True, exist_ok=True)
                    validation_result["warnings"].append(f"Created missing directory: {dir_path}")
                elif not path_obj.is_dir():
                    validation_result["errors"].append(f"{dir_name} path exists but is not a directory: {dir_path}")
                    validation_result["valid"] = False
            except Exception as e:
                validation_result["errors"].append(f"Cannot access/create {dir_name} directory {dir_path}: {e}")
                validation_result["valid"] = False
        
        # 4. Validate SQLite file path (if using SQLite)
        if self.is_sqlite:
            validation_result["checks_performed"].append("SQLite File Validation")
            try:
                sqlite_path = Path(self.SQLITE_PATH)
                sqlite_dir = sqlite_path.parent
                if not sqlite_dir.exists():
                    sqlite_dir.mkdir(parents=True, exist_ok=True)
                    validation_result["warnings"].append(f"Created SQLite directory: {sqlite_dir}")
                # Check if we can write to the directory
                if not os.access(sqlite_dir, os.W_OK):
                    validation_result["errors"].append(f"Cannot write to SQLite directory: {sqlite_dir}")
                    validation_result["valid"] = False
            except Exception as e:
                validation_result["errors"].append(f"SQLite path validation failed: {e}")
                validation_result["valid"] = False
        
        return validation_result
    
    def validate_database_connectivity(self) -> Dict[str, Any]:
        """
        Validate database connectivity
        Returns connection test results
        """
        connectivity_result = {
            "connected": False,
            "database_type": self.DATABASE_TYPE,
            "error": None,
            "details": {}
        }
        
        try:
            if self.is_postgresql:
                # Test PostgreSQL connection
                import psycopg2
                conn = psycopg2.connect(
                    host=self.POSTGRES_SERVER,
                    port=self.POSTGRES_PORT,
                    user=self.POSTGRES_USER,
                    password=self.POSTGRES_PASSWORD,
                    database='postgres',  # Connect to default database first
                    connect_timeout=5
                )
                
                # Check if our database exists
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
                    (self.POSTGRES_DB,)
                )
                db_exists = cursor.fetchone() is not None
                
                connectivity_result["details"]["server_accessible"] = True
                connectivity_result["details"]["database_exists"] = db_exists
                
                if not db_exists:
                    connectivity_result["error"] = f"Database '{self.POSTGRES_DB}' does not exist"
                else:
                    # Test connection to actual database
                    cursor.close()
                    conn.close()
                    
                    conn = psycopg2.connect(
                        host=self.POSTGRES_SERVER,
                        port=self.POSTGRES_PORT,
                        user=self.POSTGRES_USER,
                        password=self.POSTGRES_PASSWORD,
                        database=self.POSTGRES_DB,
                        connect_timeout=5
                    )
                    connectivity_result["connected"] = True
                
                cursor.close()
                conn.close()
                
            elif self.is_sqlite:
                # Test SQLite connection
                import sqlite3
                sqlite_path = Path(self.SQLITE_PATH)
                
                # Check if file exists or can be created
                if not sqlite_path.exists():
                    # Try to create the file
                    conn = sqlite3.connect(str(sqlite_path))
                    conn.close()
                    connectivity_result["details"]["file_created"] = True
                else:
                    connectivity_result["details"]["file_exists"] = True
                
                # Test actual connection
                conn = sqlite3.connect(str(sqlite_path))
                cursor = conn.cursor()
                cursor.execute("SELECT sqlite_version()")
                version = cursor.fetchone()[0]
                connectivity_result["details"]["sqlite_version"] = version
                connectivity_result["connected"] = True
                cursor.close()
                conn.close()
                
        except ImportError as e:
            if "psycopg2" in str(e):
                connectivity_result["error"] = "PostgreSQL driver (psycopg2) not installed. Run: pip install psycopg2-binary"
            else:
                connectivity_result["error"] = f"Database driver not available: {e}"
        except Exception as e:
            connectivity_result["error"] = f"Database connection failed: {e}"
        
        return connectivity_result
    
    def get_validation_summary(self) -> str:
        """Get a formatted validation summary for logging"""
        validation = self.validate_required_settings()
        connectivity = self.validate_database_connectivity()
        
        summary = []
        summary.append("🔍 Configuration Validation Summary")
        summary.append("=" * 50)
        
        # Configuration validation
        if validation["valid"]:
            summary.append("✅ Configuration: Valid")
        else:
            summary.append("❌ Configuration: Invalid")
            for error in validation["errors"]:
                summary.append(f"   • {error}")
        
        if validation["warnings"]:
            summary.append("⚠️  Configuration Warnings:")
            for warning in validation["warnings"]:
                summary.append(f"   • {warning}")
        
        # Database connectivity
        if connectivity["connected"]:
            summary.append(f"✅ Database ({connectivity['database_type']}): Connected")
            if connectivity["details"]:
                for key, value in connectivity["details"].items():
                    summary.append(f"   • {key}: {value}")
        else:
            summary.append(f"❌ Database ({connectivity['database_type']}): Connection Failed")
            if connectivity["error"]:
                summary.append(f"   • Error: {connectivity['error']}")
        
        summary.append("=" * 50)
        return "\n".join(summary)

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"  # Allow extra env vars for backward compatibility


settings = Settings()

# Enhanced validation on import with better error handling
def validate_configuration_on_startup():
    """Perform comprehensive configuration validation at startup"""
    try:
        validation_result = settings.validate_required_settings()
        
        if not validation_result["valid"]:
            logger.error("❌ Configuration validation failed:")
            for error in validation_result["errors"]:
                logger.error(f"   • {error}")
            
            print("🚨 CONFIGURATION ERROR")
            print("=" * 50)
            print("The application cannot start due to configuration errors:")
            for error in validation_result["errors"]:
                print(f"❌ {error}")
            print("\n💡 Please check your .env file and ensure all required variables are set.")
            print("📖 See .env.example for reference configuration.")
            return False
        
        # Show warnings if any
        if validation_result["warnings"]:
            logger.warning("⚠️  Configuration warnings:")
            for warning in validation_result["warnings"]:
                logger.warning(f"   • {warning}")
        
        # Test database connectivity (non-blocking)
        try:
            connectivity = settings.validate_database_connectivity()
            if not connectivity["connected"]:
                logger.warning(f"⚠️  Database connection issue: {connectivity.get('error', 'Unknown error')}")
                logger.warning("💡 The application will start but database operations may fail")
        except Exception as e:
            logger.warning(f"⚠️  Could not test database connectivity: {e}")
        
        logger.info("✅ Configuration validation completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration validation failed with unexpected error: {e}")
        print(f"🚨 CONFIGURATION ERROR: {e}")
        return False

# Perform validation on import
validation_success = validate_configuration_on_startup()
