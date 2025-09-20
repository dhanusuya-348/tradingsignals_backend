#!/usr/bin/env python3
"""
Script to find and list all import issues in the algo folder
Run this to see which files need import fixes
"""

import os
import re
from pathlib import Path

def find_import_issues():
    """Find all files with potential import issues"""
    
    project_root = Path(__file__).parent
    algo_dir = project_root / "algo"
    
    if not algo_dir.exists():
        print("❌ algo directory not found")
        return
    
    print(f"🔍 Scanning {algo_dir} for import issues...")
    
    issues = []
    
    # Patterns to look for
    patterns = [
        r'from config import',
        r'from data\.',
        r'from logic\.',
        r'from strategies\.',
        r'from indicators\.',
        r'from backtesting\.',
        r'from reports\.'
    ]
    
    for py_file in algo_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            file_issues = []
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                for pattern in patterns:
                    if re.search(pattern, line):
                        file_issues.append((line_num, line.strip()))
            
            if file_issues:
                issues.append((py_file, file_issues))
                
        except Exception as e:
            print(f"⚠️ Error reading {py_file}: {e}")
    
    # Report issues
    if issues:
        print(f"\n📋 Found import issues in {len(issues)} files:")
        for file_path, file_issues in issues:
            rel_path = file_path.relative_to(project_root)
            print(f"\n📁 {rel_path}:")
            for line_num, line in file_issues:
                print(f"   Line {line_num}: {line}")
        
        print(f"\n🔧 FIXES NEEDED:")
        print("1. Replace 'from config import' with 'from ..config import' (if in subfolder)")
        print("2. Replace 'from data.' with 'from ..data.' (if in algo subfolder)")
        print("3. Replace 'from logic.' with 'from ..logic.' (if in algo subfolder)")
        print("4. Similar fixes for strategies, indicators, backtesting, reports")
        
    else:
        print("✅ No obvious import issues found!")
    
    # Check for missing __init__.py files
    print(f"\n🔍 Checking for missing __init__.py files...")
    
    required_inits = [
        "algo/__init__.py",
        "algo/data/__init__.py", 
        "algo/logic/__init__.py",
        "algo/strategies/__init__.py",
        "algo/indicators/__init__.py",
        "algo/backtesting/__init__.py",
        "algo/reports/__init__.py"
    ]
    
    missing_inits = []
    for init_file in required_inits:
        init_path = project_root / init_file
        if not init_path.exists():
            missing_inits.append(init_file)
    
    if missing_inits:
        print(f"❌ Missing __init__.py files:")
        for missing in missing_inits:
            print(f"   {missing}")
        print(f"\n🔧 To fix, run:")
        for missing in missing_inits:
            print(f"   touch {missing}")
    else:
        print("✅ All required __init__.py files found!")

def create_missing_inits():
    """Create missing __init__.py files"""
    
    project_root = Path(__file__).parent
    
    required_inits = [
        "algo/__init__.py",
        "algo/data/__init__.py", 
        "algo/logic/__init__.py",
        "algo/strategies/__init__.py",
        "algo/indicators/__init__.py", 
        "algo/backtesting/__init__.py",
        "algo/reports/__init__.py"
    ]
    
    created = []
    
    for init_file in required_inits:
        init_path = project_root / init_file
        if not init_path.exists():
            try:
                init_path.parent.mkdir(parents=True, exist_ok=True)
                init_path.touch()
                created.append(init_file)
            except Exception as e:
                print(f"❌ Error creating {init_file}: {e}")
    
    if created:
        print(f"✅ Created {len(created)} missing __init__.py files:")
        for created_file in created:
            print(f"   {created_file}")
    else:
        print("ℹ️ All __init__.py files already exist")

if __name__ == "__main__":
    print("🔧 Import Issue Finder and Fixer")
    print("=" * 50)
    
    find_import_issues()
    
    print("\n" + "=" * 50)
    create_missing_inits()
    
    print(f"\n💡 Next steps:")
    print("1. Fix the import issues listed above")
    print("2. Replace your files with the fixed versions I provided")
    print("3. Run: python test_signal_worker.py")