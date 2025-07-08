from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import os
import json
import logging
from datetime import datetime
from app.db.init_db_simple import get_async_db, get_chroma_client
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/chroma-status")
async def get_chroma_status(db: AsyncSession = Depends(get_async_db)):
    """
    Debug endpoint to check ChromaDB configuration and volume status
    """
    try:
        status = {
            "timestamp": datetime.now().isoformat(),
            "environment_variables": {},
            "chroma_config": {},
            "directory_info": {},
            "volume_test": {},
            "collections_info": {}
        }
        
        # 1. Check environment variables
        status["environment_variables"] = {
            "CHROMA_PERSIST_DIRECTORY": os.getenv("CHROMA_PERSIST_DIRECTORY"),
            "CHROMA_PERSIST_DIRECTORY_from_settings": settings.CHROMA_PERSIST_DIRECTORY,
            "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT"),
            "RAILWAY_PROJECT_ID": os.getenv("RAILWAY_PROJECT_ID"),
            "working_directory": os.getcwd()
        }
        
        # 2. Check ChromaDB configuration
        chroma_dir = settings.CHROMA_PERSIST_DIRECTORY
        status["chroma_config"] = {
            "configured_directory": chroma_dir,
            "directory_exists": os.path.exists(chroma_dir),
            "is_directory": os.path.isdir(chroma_dir) if os.path.exists(chroma_dir) else False,
            "directory_absolute_path": os.path.abspath(chroma_dir)
        }
        
        # 3. Check directory permissions and contents
        try:
            if os.path.exists(chroma_dir):
                dir_stat = os.stat(chroma_dir)
                dir_contents = os.listdir(chroma_dir)
                total_size = 0
                
                # Calculate total size of directory contents
                for item in dir_contents:
                    item_path = os.path.join(chroma_dir, item)
                    if os.path.isfile(item_path):
                        total_size += os.path.getsize(item_path)
                    elif os.path.isdir(item_path):
                        for root, dirs, files in os.walk(item_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                total_size += os.path.getsize(file_path)
                
                status["directory_info"] = {
                    "permissions": oct(dir_stat.st_mode)[-3:],
                    "owner_uid": dir_stat.st_uid,
                    "group_gid": dir_stat.st_gid,
                    "size_bytes": total_size,
                    "size_mb": round(total_size / (1024 * 1024), 2),
                    "contents_count": len(dir_contents),
                    "contents": dir_contents[:10],  # First 10 items
                    "readable": os.access(chroma_dir, os.R_OK),
                    "writable": os.access(chroma_dir, os.W_OK),
                    "executable": os.access(chroma_dir, os.X_OK)
                }
            else:
                status["directory_info"] = {
                    "error": "Directory does not exist",
                    "parent_exists": os.path.exists(os.path.dirname(chroma_dir)),
                    "parent_permissions": oct(os.stat(os.path.dirname(chroma_dir)).st_mode)[-3:] if os.path.exists(os.path.dirname(chroma_dir)) else None
                }
        except Exception as e:
            status["directory_info"] = {"error": str(e)}
        
        # 4. Test volume write operations
        try:
            test_file_path = os.path.join(chroma_dir, "volume_test.txt")
            test_content = f"Test write at {datetime.now().isoformat()}"
            
            # Try to create directory if it doesn't exist
            if not os.path.exists(chroma_dir):
                os.makedirs(chroma_dir, exist_ok=True)
                status["volume_test"]["directory_created"] = True
            
            # Try to write a test file
            with open(test_file_path, "w") as f:
                f.write(test_content)
            
            # Try to read it back
            with open(test_file_path, "r") as f:
                read_content = f.read()
            
            # Clean up test file
            os.remove(test_file_path)
            
            status["volume_test"] = {
                "write_success": True,
                "read_success": read_content == test_content,
                "test_file_size": len(test_content)
            }
            
        except Exception as e:
            status["volume_test"] = {
                "write_success": False,
                "error": str(e)
            }
        
        # 5. Check ChromaDB client and collections
        try:
            client = get_chroma_client()
            status["chroma_config"]["client_type"] = str(type(client))
            status["chroma_config"]["client_created"] = True
            
            # List all collections
            collections = client.list_collections()
            status["collections_info"] = {
                "total_collections": len(collections),
                "collection_names": [col.name for col in collections],
                "collections_detail": []
            }
            
            # Get details for each collection
            for collection in collections[:5]:  # Limit to first 5 collections
                try:
                    col_info = {
                        "name": collection.name,
                        "count": collection.count()
                    }
                    
                    # Try to get a sample of data
                    if collection.count() > 0:
                        sample = collection.get(limit=1)
                        col_info["has_data"] = True
                        col_info["sample_ids"] = sample["ids"][:3] if sample["ids"] else []
                    else:
                        col_info["has_data"] = False
                    
                    status["collections_info"]["collections_detail"].append(col_info)
                    
                except Exception as col_error:
                    status["collections_info"]["collections_detail"].append({
                        "name": collection.name,
                        "error": str(col_error)
                    })
        
        except Exception as e:
            status["chroma_config"]["client_error"] = str(e)
            status["collections_info"]["error"] = str(e)
        
        return status
        
    except Exception as e:
        logger.error(f"Error in chroma-status debug endpoint: {e}")
        return {"error": str(e), "timestamp": datetime.now().isoformat()}

@router.post("/test-chroma-write")
async def test_chroma_write():
    """
    Test writing data to ChromaDB to verify volume persistence
    """
    try:
        client = get_chroma_client()
        
        # Create a test collection
        test_collection = client.get_or_create_collection("debug_test")
        
        # Add some test data
        test_data = {
            "ids": ["test_1", "test_2"],
            "documents": ["This is test document 1", "This is test document 2"],
            "metadatas": [
                {"source": "debug", "timestamp": datetime.now().isoformat()},
                {"source": "debug", "timestamp": datetime.now().isoformat()}
            ]
        }
        
        test_collection.add(**test_data)
        
        # Verify the data was written
        result = test_collection.get()
        
        return {
            "write_success": True,
            "collection_name": "debug_test",
            "items_written": len(test_data["ids"]),
            "items_retrieved": len(result["ids"]) if result["ids"] else 0,
            "data_matches": len(result["ids"]) == len(test_data["ids"]) if result["ids"] else False,
            "chroma_directory": settings.CHROMA_PERSIST_DIRECTORY,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in test-chroma-write: {e}")
        return {
            "write_success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }