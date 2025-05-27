"""
Script to clean up test files created during debugging
This script moves test files to a backup directory instead of deleting them
"""
import os
import shutil
from datetime import datetime

# Files to move to backup
TEST_FILES = [
    # Python test files
    "test_cors.py",
    "test_direct_upload.py",
    "test_document_upload.py",
    "test_upload_direct.py",
    "simple_test_server.py",
    "verify_upload_fix.py",
    "check_db_schema.py",
    
    # HTML test files
    "test_upload.html",
    "test_upload_form.html"
]

# Keep these test files as they might be part of the original codebase
KEEP_FILES = [
    "test_db_connection.py",
    "test_db_schema.py",
    "test_sqlalchemy.py"
]

def main():
    # Create backup directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.path.dirname(__file__), f"test_files_backup_{timestamp}")
    os.makedirs(backup_dir, exist_ok=True)
    
    print(f"Moving test files to backup directory: {backup_dir}")
    
    # Move files to backup directory
    for filename in TEST_FILES:
        src_path = os.path.join(os.path.dirname(__file__), filename)
        if os.path.exists(src_path):
            dst_path = os.path.join(backup_dir, filename)
            shutil.move(src_path, dst_path)
            print(f"Moved {filename} to backup directory")
        else:
            print(f"File not found: {filename}")
    
    print("\nKeeping the following test files as they may be part of the original codebase:")
    for filename in KEEP_FILES:
        print(f"- {filename}")
    
    print("\nCleanup complete!")

if __name__ == "__main__":
    main()
