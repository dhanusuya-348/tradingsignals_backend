# add_expiry_date_migration.py
"""
SQL Migration: Add expiry_date column to users table
Run this script once to add the new column to existing database
"""

import os
from sqlalchemy import create_engine, text
import sys
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from load_env import load_env_file
    load_env_file()
    print("✅ Loaded .env file")
except ImportError:
    print("⚠️  load_env.py not found, using system environment variables")

def run_migration():
    """Add expiry_date column and populate existing active subscriptions"""
    
    # Get database URL from environment
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("❌ ERROR: DATABASE_URL not set in environment variables")
        return False
    
    print(f"🔗 Connecting to database...")
    
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                print("🔧 [MIGRATION] Adding expiry_date column to users table...")
                
                # Add the new column (nullable initially)
                conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN expiry_date TIMESTAMP NULL
                """))
                
                print("✅ [MIGRATION] Column added successfully")
                
                # Update existing active subscriptions with expiry dates
                print("🔧 [MIGRATION] Updating existing active subscriptions...")
                
                # Set expiry_date = subscription_date + 30 days for active subscriptions
                result = conn.execute(text("""
                    UPDATE users 
                    SET expiry_date = subscription_date + INTERVAL '30 days'
                    WHERE subscription_status = 'active' 
                    AND subscription_date IS NOT NULL
                    AND subscription_plan IN ('pro', 'max')
                """))
                
                updated_count = result.rowcount
                print(f"✅ [MIGRATION] Updated {updated_count} existing active subscriptions")
                
                # Commit transaction
                trans.commit()
                print("✅ [MIGRATION] Migration completed successfully!")
                
            except Exception as e:
                # Rollback on error
                trans.rollback()
                print(f"❌ [MIGRATION] Error during migration: {e}")
                raise
                
    except Exception as e:
        print(f"❌ [MIGRATION] Failed to connect to database: {e}")
        raise

if __name__ == "__main__":
    print("🚀 [MIGRATION] Starting expiry_date migration...")
    run_migration()
    print("🎉 [MIGRATION] Migration script completed!")