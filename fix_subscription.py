#!/usr/bin/env python3
"""
Script to manually fix subscription status for testing
Run this script to extend your subscription expiry date
"""

import os
import sys
from datetime import datetime, timedelta

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import get_session_context, User

def fix_user_subscription(user_sub, plan='pro', extend_days=30):
    """
    Fix a user's subscription by:
    1. Setting subscription_status to 'active'
    2. Setting subscription_plan to specified plan (default: 'pro')
    3. Extending expiry_date by specified days (default: 30)
    """
    try:
        with get_session_context() as session:
            user = session.query(User).filter_by(user_sub=user_sub).first()
            
            if not user:
                print(f"❌ User not found: {user_sub}")
                return False
            
            print(f"📋 Current user status:")
            print(f"   Email: {user.email}")
            print(f"   Subscription Status: {user.subscription_status}")
            print(f"   Subscription Plan: {getattr(user, 'subscription_plan', 'None')}")
            print(f"   Expiry Date: {getattr(user, 'expiry_date', 'None')}")
            print(f"   Is Active: {user.has_active_subscription()}")
            
            # Update subscription
            user.subscription_status = 'active'
            user.subscription_plan = plan
            user.expiry_date = datetime.utcnow() + timedelta(days=extend_days)
            user.updated_at = datetime.utcnow()
            
            session.flush()
            
            print(f"\n✅ Updated user subscription:")
            print(f"   Subscription Status: {user.subscription_status}")
            print(f"   Subscription Plan: {user.subscription_plan}")
            print(f"   New Expiry Date: {user.expiry_date}")
            print(f"   Is Active: {user.has_active_subscription()}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error fixing subscription: {e}")
        return False

def list_all_users():
    """List all users and their subscription status"""
    try:
        with get_session_context() as session:
            users = session.query(User).all()
            
            print(f"\n📋 Found {len(users)} users:")
            print("-" * 80)
            
            for user in users:
                print(f"User: {user.email}")
                print(f"  Sub: {user.user_sub}")
                print(f"  Status: {user.subscription_status}")
                print(f"  Plan: {getattr(user, 'subscription_plan', 'None')}")
                print(f"  Expiry: {getattr(user, 'expiry_date', 'None')}")
                print(f"  Active: {user.has_active_subscription()}")
                print("-" * 80)
                
    except Exception as e:
        print(f"❌ Error listing users: {e}")

if __name__ == "__main__":
    print("🔧 Subscription Fix Tool")
    print("=" * 50)
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python fix_subscription.py list                    # List all users")
        print("  python fix_subscription.py fix <user_sub>          # Fix subscription for user")
        print("  python fix_subscription.py fix <user_sub> max      # Fix with Max plan")
        print("  python fix_subscription.py fix <user_sub> pro 60   # Fix with Pro plan for 60 days")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        list_all_users()
    elif command == "fix":
        if len(sys.argv) < 3:
            print("❌ Please provide user_sub")
            sys.exit(1)
        
        user_sub = sys.argv[2]
        plan = sys.argv[3] if len(sys.argv) > 3 else 'pro'
        days = int(sys.argv[4]) if len(sys.argv) > 4 else 30
        
        print(f"🔧 Fixing subscription for user: {user_sub}")
        print(f"   Plan: {plan}")
        print(f"   Extend by: {days} days")
        
        if fix_user_subscription(user_sub, plan, days):
            print("\n✅ Subscription fixed successfully!")
        else:
            print("\n❌ Failed to fix subscription")
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)