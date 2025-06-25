#!/usr/bin/env python3
"""
Startup Configuration Validation Script

This script performs comprehensive validation of the application configuration
including environment variables, database connectivity, and required dependencies.

Can be run independently or as part of application startup.
"""

import os
import sys
import logging
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_required_dependencies():
    """Check if all required Python packages are installed"""
    dependency_result = {
        "all_available": True,
        "missing": [],
        "available": []
    }
    
    required_packages = [
        ("fastapi", "FastAPI web framework"),
        ("uvicorn", "ASGI server"),
        ("sqlalchemy", "Database ORM"),
        ("pydantic", "Data validation"),
        ("anthropic", "Anthropic AI client"),
        ("chromadb", "Vector database"),
        ("websockets", "WebSocket support")
    ]
    
    # Add database-specific packages
    if settings.is_postgresql:
        required_packages.append(("psycopg2", "PostgreSQL driver"))
    
    for package_name, description in required_packages:
        try:
            __import__(package_name)
            dependency_result["available"].append((package_name, description))
        except ImportError:
            dependency_result["missing"].append((package_name, description))
            dependency_result["all_available"] = False
    
    return dependency_result

def validate_api_keys():
    """Validate API keys and external service configurations"""
    api_validation = {
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Check Anthropic API key
    if not settings.ANTHROPIC_API_KEY:
        api_validation["errors"].append("ANTHROPIC_API_KEY is not set")
        api_validation["valid"] = False
    elif settings.ANTHROPIC_API_KEY == "your_anthropic_api_key_here":
        api_validation["warnings"].append("ANTHROPIC_API_KEY appears to be a placeholder")
    elif len(settings.ANTHROPIC_API_KEY) < 20:
        api_validation["warnings"].append("ANTHROPIC_API_KEY appears to be too short")
    
    # Check model configuration
    if not settings.ANTHROPIC_MODEL:
        api_validation["warnings"].append("ANTHROPIC_MODEL is not set, using default")
    
    return api_validation

def validate_file_permissions():
    """Validate file and directory permissions"""
    permission_result = {
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Check upload directory
    try:
        upload_path = Path(settings.UPLOAD_DIRECTORY)
        if not upload_path.exists():
            upload_path.mkdir(parents=True, exist_ok=True)
            permission_result["warnings"].append(f"Created upload directory: {upload_path}")
        
        # Test write permission
        test_file = upload_path / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        
    except Exception as e:
        permission_result["errors"].append(f"Cannot write to upload directory {settings.UPLOAD_DIRECTORY}: {e}")
        permission_result["valid"] = False
    
    # Check ChromaDB directory
    try:
        chroma_path = Path(settings.CHROMA_PERSIST_DIRECTORY)
        if not chroma_path.exists():
            chroma_path.mkdir(parents=True, exist_ok=True)
            permission_result["warnings"].append(f"Created ChromaDB directory: {chroma_path}")
        
        # Test write permission
        test_file = chroma_path / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        
    except Exception as e:
        permission_result["errors"].append(f"Cannot write to ChromaDB directory {settings.CHROMA_PERSIST_DIRECTORY}: {e}")
        permission_result["valid"] = False
    
    return permission_result

def run_comprehensive_validation():
    """Run all validation checks and return comprehensive results"""
    logger.info("🚀 Starting comprehensive configuration validation...")
    
    results = {
        "overall_valid": True,
        "configuration": None,
        "database": None,
        "dependencies": None,
        "api_keys": None,
        "permissions": None
    }
    
    # 1. Configuration validation
    logger.info("🔍 Validating configuration settings...")
    results["configuration"] = settings.validate_required_settings()
    if not results["configuration"]["valid"]:
        results["overall_valid"] = False
    
    # 2. Database connectivity
    logger.info("🔍 Testing database connectivity...")
    results["database"] = settings.validate_database_connectivity()
    if not results["database"]["connected"]:
        # Database connectivity is a warning, not a hard failure
        logger.warning("Database connectivity issues detected")
    
    # 3. Dependencies
    logger.info("🔍 Checking required dependencies...")
    results["dependencies"] = check_required_dependencies()
    if not results["dependencies"]["all_available"]:
        results["overall_valid"] = False
    
    # 4. API keys
    logger.info("🔍 Validating API keys...")
    results["api_keys"] = validate_api_keys()
    if not results["api_keys"]["valid"]:
        results["overall_valid"] = False
    
    # 5. File permissions
    logger.info("🔍 Checking file permissions...")
    results["permissions"] = validate_file_permissions()
    if not results["permissions"]["valid"]:
        results["overall_valid"] = False
    
    return results

def print_validation_report(results):
    """Print a comprehensive validation report"""
    print("\n" + "=" * 60)
    print("🔍 PROJECT POWER-UP CONFIGURATION VALIDATION REPORT")
    print("=" * 60)
    
    # Overall status
    if results["overall_valid"]:
        print("✅ OVERALL STATUS: READY TO START")
    else:
        print("❌ OVERALL STATUS: CONFIGURATION ISSUES DETECTED")
    
    print()
    
    # Configuration
    config = results["configuration"]
    print("📋 CONFIGURATION SETTINGS:")
    if config["valid"]:
        print("   ✅ All required settings present")
    else:
        print("   ❌ Configuration errors:")
        for error in config["errors"]:
            print(f"      • {error}")
    
    if config["warnings"]:
        print("   ⚠️  Warnings:")
        for warning in config["warnings"]:
            print(f"      • {warning}")
    print()
    
    # Database
    db = results["database"]
    print(f"🗄️  DATABASE ({db['database_type'].upper()}):")
    if db["connected"]:
        print("   ✅ Connection successful")
        for key, value in db["details"].items():
            print(f"      • {key}: {value}")
    else:
        print("   ❌ Connection failed")
        if db["error"]:
            print(f"      • Error: {db['error']}")
    print()
    
    # Dependencies
    deps = results["dependencies"]
    print("📦 DEPENDENCIES:")
    if deps["all_available"]:
        print("   ✅ All required packages available")
    else:
        print("   ❌ Missing packages:")
        for package, desc in deps["missing"]:
            print(f"      • {package}: {desc}")
        print("   💡 Run: pip install -r requirements.txt")
    print()
    
    # API Keys
    api = results["api_keys"]
    print("🔑 API CONFIGURATION:")
    if api["valid"]:
        print("   ✅ API keys configured")
    else:
        print("   ❌ API key issues:")
        for error in api["errors"]:
            print(f"      • {error}")
    
    if api["warnings"]:
        print("   ⚠️  Warnings:")
        for warning in api["warnings"]:
            print(f"      • {warning}")
    print()
    
    # Permissions
    perms = results["permissions"]
    print("📁 FILE PERMISSIONS:")
    if perms["valid"]:
        print("   ✅ All directories accessible")
    else:
        print("   ❌ Permission issues:")
        for error in perms["errors"]:
            print(f"      • {error}")
    
    if perms["warnings"]:
        print("   ⚠️  Directory changes:")
        for warning in perms["warnings"]:
            print(f"      • {warning}")
    
    print("\n" + "=" * 60)
    
    if results["overall_valid"]:
        print("🎉 Configuration validation passed! The application is ready to start.")
    else:
        print("🚨 Please fix the configuration issues above before starting the application.")
        print("📖 See .env.example for reference configuration.")
    
    print("=" * 60)

def main():
    """Main validation function"""
    try:
        results = run_comprehensive_validation()
        print_validation_report(results)
        
        # Return appropriate exit code
        return 0 if results["overall_valid"] else 1
        
    except Exception as e:
        logger.error(f"❌ Validation failed with unexpected error: {e}")
        print(f"\n🚨 VALIDATION ERROR: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
