#!/usr/bin/env python3
"""
Code Cleanup Script for Project Power-Up
This script helps identify and clean up redundant code
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
import json
import traceback

class CodeCleanupAnalyzer:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "duplicates": [],
            "unused_files": [],
            "large_files": [],
            "recommendations": []
        }
    
    def find_duplicate_services(self):
        """Find duplicate service implementations"""
        print("  - Checking for duplicate services...")
        services_dir = self.project_root / "backend" / "app" / "services"
        
        if not services_dir.exists():
            print(f"    Warning: Services directory not found: {services_dir}")
            return
            
        # Check for v2 versions
        for file in services_dir.glob("*.py"):
            if file.stem.endswith("_v2"):
                original = services_dir / f"{file.stem[:-3]}.py"
                if original.exists():
                    self.report["duplicates"].append({
                        "type": "service",
                        "original": str(original),
                        "duplicate": str(file),
                        "recommendation": f"Merge {file.name} into {original.name} and delete duplicate"
                    })
                    print(f"    Found duplicate: {file.name} (original: {original.name})")
    
    def find_backup_files(self):
        """Find backup files that should be removed"""
        print("  - Checking for backup files...")
        count = 0
        for pattern in ["*.bak", "*.new", "*.old", "*_backup*"]:
            for file in self.project_root.rglob(pattern):
                if ".git" not in str(file):  # Skip git directory
                    self.report["unused_files"].append({
                        "file": str(file),
                        "type": "backup",
                        "recommendation": "Delete or move to version control"
                    })
                    count += 1
        print(f"    Found {count} backup files")
    
    def analyze_test_structure(self):
        """Analyze test file organization"""
        print("  - Analyzing test structure...")
        test_backup = self.project_root / "backend" / "test_files_backup"
        if test_backup.exists():
            test_count = sum(1 for _ in test_backup.rglob("*.py"))
            self.report["recommendations"].append({
                "issue": "Disorganized test files",
                "location": str(test_backup),
                "details": f"Found {test_count} test files in backup directory",
                "action": "Create proper test structure and migrate valuable tests"
            })
            print(f"    Found {test_count} test files in backup directory")
    
    def find_duplicate_endpoints(self):
        """Find duplicate API endpoints"""
        print("  - Checking for duplicate endpoints...")
        endpoints_dir = self.project_root / "backend" / "app" / "api" / "endpoints"
        
        if not endpoints_dir.exists():
            print(f"    Warning: Endpoints directory not found: {endpoints_dir}")
            return
            
        # Check for similar endpoint files
        endpoint_files = list(endpoints_dir.glob("*.py"))
        duplicates_found = 0
        for i, file1 in enumerate(endpoint_files):
            for file2 in endpoint_files[i+1:]:
                if self._similar_names(file1.stem, file2.stem):
                    self.report["duplicates"].append({
                        "type": "endpoint",
                        "file1": str(file1),
                        "file2": str(file2),
                        "recommendation": "Review and consolidate similar endpoints"
                    })
                    duplicates_found += 1
        print(f"    Found {duplicates_found} potential duplicate endpoints")
    
    def _similar_names(self, name1, name2):
        """Check if two names are similar"""
        # Simple similarity check
        return (name1 in name2 or name2 in name1) and name1 != name2
    
    def find_large_files(self):
        """Find unusually large files that might need refactoring"""
        print("  - Checking for large files...")
        count = 0
        for file in self.project_root.rglob("*.py"):
            if ".git" not in str(file) and file.exists():  # Skip git directory
                try:
                    size = file.stat().st_size
                    if size > 20000:  # Files larger than 20KB
                        lines = len(file.read_text(encoding='utf-8', errors='ignore').splitlines())
                        self.report["large_files"].append({
                            "file": str(file),
                            "size_kb": size / 1024,
                            "lines": lines,
                            "recommendation": "Consider breaking into smaller modules" if lines > 500 else "Review for cleanup"
                        })
                        count += 1
                except Exception as e:
                    print(f"    Error reading file {file}: {e}")
        print(f"    Found {count} large files")
    
    def generate_cleanup_commands(self):
        """Generate shell commands for cleanup"""
        commands = []
        
        # Commands to remove backup files
        for item in self.report["unused_files"]:
            if item["type"] == "backup":
                commands.append(f"# Remove backup file\n# rm '{item['file']}'")
        
        # Commands to create test structure
        commands.append("\n# Create proper test structure")
        commands.append("mkdir -p backend/tests/unit/services")
        commands.append("mkdir -p backend/tests/unit/models")
        commands.append("mkdir -p backend/tests/unit/api")
        commands.append("mkdir -p backend/tests/integration")
        commands.append("mkdir -p backend/tests/fixtures")
        
        return commands
    
    def run_analysis(self):
        """Run the complete analysis"""
        print("🔍 Starting code cleanup analysis...")
        
        try:
            self.find_duplicate_services()
            self.find_backup_files()
            self.analyze_test_structure()
            self.find_duplicate_endpoints()
            self.find_large_files()
            
            # Save report
            report_path = self.project_root / "cleanup_report.json"
            print(f"\n💾 Saving report to: {report_path}")
            with open(report_path, "w", encoding='utf-8') as f:
                json.dump(self.report, f, indent=2)
            
            print(f"✅ Analysis complete! Report saved to: {report_path}")
            
            # Print summary
            print("\n📊 Summary:")
            print(f"  - Found {len(self.report['duplicates'])} duplicate files/services")
            print(f"  - Found {len(self.report['unused_files'])} backup/unused files")
            print(f"  - Found {len(self.report['large_files'])} large files")
            print(f"  - Generated {len(self.report['recommendations'])} recommendations")
            
            # Generate cleanup commands
            commands = self.generate_cleanup_commands()
            commands_path = self.project_root / "cleanup_commands.sh"
            print(f"\n💾 Saving cleanup commands to: {commands_path}")
            with open(commands_path, "w", encoding='utf-8') as f:
                f.write("#!/bin/bash\n")
                f.write("# Auto-generated cleanup commands\n")
                f.write("# Review each command before executing!\n\n")
                f.write("\n".join(commands))
            
            print(f"📝 Cleanup commands saved to: {commands_path}")
            print("   Review and uncomment commands before executing!")
            
        except Exception as e:
            print(f"\n❌ Error during analysis: {e}")
            traceback.print_exc()
            
        return self.report


def main():
    # Get the project root (current directory)
    project_root = Path.cwd()
    print(f"📁 Project root: {project_root}")
    
    # Create analyzer
    analyzer = CodeCleanupAnalyzer(project_root)
    
    # Run analysis
    report = analyzer.run_analysis()
    
    # Print detailed findings
    print("\n🔍 Detailed Findings:")
    
    if report["duplicates"]:
        print("\n📑 Duplicate Files/Services:")
        for dup in report["duplicates"]:
            print(f"  - {dup['type']}: {Path(dup.get('original', dup.get('file1'))).name}")
            print(f"    {dup['recommendation']}")
    
    if report["large_files"]:
        print("\n📏 Large Files:")
        for file in report["large_files"]:
            print(f"  - {Path(file['file']).name}: {file['lines']} lines ({file['size_kb']:.1f} KB)")
            print(f"    {file['recommendation']}")
    
    print("\n✨ Next steps:")
    print("1. Review the cleanup_report.json for detailed findings")
    print("2. Check cleanup_commands.sh for suggested commands")
    print("3. Create a backup before making changes")
    print("4. Execute cleanup in phases")
    print("5. Run tests after each phase")


if __name__ == "__main__":
    main()
