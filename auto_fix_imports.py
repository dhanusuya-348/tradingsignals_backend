#!/usr/bin/env python3
"""
Automatically fix import statements in the algo folder
This will modify your files to use proper relative imports
"""

import os
import re
from pathlib import Path

def fix_imports_in_file(file_path, project_root):
    """Fix imports in a single file"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Get relative path from project root
        rel_path = file_path.relative_to(project_root)
        
        # Skip main.py and sentinel_logger.py (they're in algo root)
        if file_path.name in ['main.py', 'sentiment_logger.py']:
            # These are in algo/ root, so they use direct imports
            replacements = [
                (r'from config import', 'from .config import'),
            ]
        else:
            # These are in subfolders, so they need .. prefix
            replacements = [
                (r'from config import', 'from ..config import'),
                (r'from data\.', 'from ..data.'),
                (r'from logic\.', 'from ..logic.'),
                (r'from strategies\.', 'from ..strategies.'),
                (r'from indicators\.', 'from ..indicators.'),
                (r'from backtesting\.', 'from ..backtesting.'),
                (r'from reports\.', 'from ..reports.'),
            ]
        
        # Apply replacements
        changes_made = []
        for pattern, replacement in replacements:
            old_content = content
            content = re.sub(pattern, replacement, content)
            if content != old_content:
                changes_made.append(f"{pattern} -> {replacement}")
        
        # Write back if changes were made
        if content != original_content:
            # Create backup
            backup_path = file_path.with_suffix('.py.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            
            # Write fixed version
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True, changes_made
        else:
            return False, []
            
    except Exception as e:
        print(f"❌ Error fixing {file_path}: {e}")
        return False, []

def main():
    project_root = Path(__file__).parent
    algo_dir = project_root / "algo"
    
    if not algo_dir.exists():
        print("❌ algo directory not found")
        return
    
    print("🔧 Auto-fixing imports in algo folder...")
    print("=" * 50)
    
    # Files that need fixing based on the scan
    files_to_fix = [
        "algo/main.py",
        "algo/sentiment_logger.py", 
        "algo/backtesting/backtester.py",
        "algo/backtesting/evaluator.py",
        "algo/data/fetch_price.py",
        "algo/data/fetch_sentiment.py",
        "algo/logic/risk_manager.py",
        "algo/logic/signal_engine.py",
        "algo/reports/generate_pdf.py",
        "algo/strategies/bollinger_squeezer_strategy.py",
        "algo/strategies/composite_weighted_strategy.py",
        "algo/strategies/macd_ema_strategy.py",
        "algo/strategies/rsi_volatility_strategy.py",
        "algo/strategies/trend_sentiment_strategy.py"
    ]
    
    fixed_files = []
    skipped_files = []
    
    for file_rel_path in files_to_fix:
        file_path = project_root / file_rel_path
        
        if not file_path.exists():
            print(f"⚠️ File not found: {file_rel_path}")
            continue
        
        fixed, changes = fix_imports_in_file(file_path, project_root)
        
        if fixed:
            fixed_files.append(file_rel_path)
            print(f"✅ Fixed {file_rel_path}")
            for change in changes:
                print(f"   {change}")
        else:
            skipped_files.append(file_rel_path)
            print(f"ℹ️ No changes needed: {file_rel_path}")
    
    print("\n" + "=" * 50)
    print("📊 SUMMARY:")
    print(f"✅ Fixed: {len(fixed_files)} files")
    print(f"ℹ️ Skipped: {len(skipped_files)} files")
    
    if fixed_files:
        print(f"\n📁 Fixed files:")
        for file in fixed_files:
            print(f"   {file}")
            
        print(f"\n💾 Backups created:")
        for file in fixed_files:
            backup = f"{file}.backup"
            print(f"   {backup}")
    
    print(f"\n🚀 Next steps:")
    print("1. Run: python test_signal_worker.py")
    print("2. If tests pass, run: python signal_worker.py")
    print("3. If something breaks, restore from .backup files")

if __name__ == "__main__":
    main()