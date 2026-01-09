#!/usr/bin/env python3
"""
Database migration script to add email_notifications column to users table.
Run this once to add the new column to existing database.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Add the current directory to Python path to import load_env
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from load_env import load_env_file
    load_env_file()
    print("✅ Loaded .env file")
except ImportError:
    print("⚠️  load_env.py not found, using system environment variables")

def run_migration():
    """Add email_notifications column to users table"""
    
    # Get database URL from environment
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("❌ ERROR: DATABASE_URL not set in environment variables")
        return False
    
    print(f"🔗 Connecting to database...")
    
    try:
        # Create engine
        engine = create_engine(db_url)
        
        # Test connection
        with engine.connect() as conn:
            print("✅ Database connection successful")
            
            # Check if column already exists
            check_column_sql = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'email_notifications';
            """
            
            result = conn.execute(text(check_column_sql))
            existing_column = result.fetchone()
            
            if existing_column:
                print("✅ email_notifications column already exists, no migration needed")
                return True
            
            print("📝 Adding email_notifications column to users table...")
            
            # Add the column with default value TRUE
            add_column_sql = """
            ALTER TABLE users 
            ADD COLUMN email_notifications BOOLEAN NOT NULL DEFAULT TRUE;
            """
            
            conn.execute(text(add_column_sql))
            conn.commit()
            
            print("✅ Successfully added email_notifications column")
            
            # Verify the column was added
            verify_sql = """
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'email_notifications';
            """
            
            result = conn.execute(text(verify_sql))
            column_info = result.fetchone()
            
            if column_info:
                print(f"✅ Verification successful:")
                print(f"   Column: {column_info[0]}")
                print(f"   Type: {column_info[1]}")
                print(f"   Default: {column_info[2]}")
                
                # Count existing users
                count_sql = "SELECT COUNT(*) FROM users;"
                result = conn.execute(text(count_sql))
                user_count = result.fetchone()[0]
                
                print(f"📊 Updated {user_count} existing users with email_notifications = TRUE")
                
                return True
            else:
                print("❌ ERROR: Column verification failed")
                return False
                
    except OperationalError as e:
        print(f"❌ Database connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("EMAIL NOTIFICATIONS COLUMN MIGRATION")
    print("=" * 60)
    
    success = run_migration()
    
    print("=" * 60)
    if success:
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("🎉 Email notifications feature is now ready to use")
    else:
        print("❌ MIGRATION FAILED!")
        print("🔧 Please check the error messages above and try again")
    print("=" * 60)