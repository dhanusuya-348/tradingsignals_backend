# subscription_utils.py
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from models import get_session_context, User

def calculate_expiry_date(start_date):
    """Calculate expiry date: start_date + 30 days"""
    return start_date + timedelta(days=30)

def is_subscription_active(user):
    """Check if user has active, non-expired subscription"""
    if not user:
        return False
    return user.has_active_subscription()

def require_active_subscription(f):
    """Decorator to protect routes requiring active subscription"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract user_sub from URL path or request body
        user_sub = None
        
        # Try to get from URL path (e.g., /api/user-signals/<user_sub>)
        if 'user_sub' in request.view_args:
            user_sub = request.view_args['user_sub']
        # Try to get from request body
        elif request.json and 'user_sub' in request.json:
            user_sub = request.json['user_sub']
        
        if not user_sub:
            return jsonify({"error": "User identification required"}), 400
        
        try:
            with get_session_context() as session:
                user = session.query(User).filter_by(user_sub=user_sub).first()
                if not user:
                    return jsonify({"error": "User not found"}), 404
                
                if not is_subscription_active(user):
                    return jsonify({
                        "error": "Active subscription required",
                        "subscription_status": user.subscription_status,
                        "subscription_plan": user.subscription_plan,
                        "expired": user.expiry_date and datetime.utcnow() > user.expiry_date if user.expiry_date else False
                    }), 403
                
                return f(*args, **kwargs)
        except Exception as e:
            print(f"❌ [SUBSCRIPTION_CHECK] Error: {e}")
            return jsonify({"error": "Subscription validation failed"}), 500
    
    return decorated_function

def cleanup_expired_subscriptions():
    """Background job to clean up expired subscriptions"""
    try:
        with get_session_context() as session:
            now = datetime.utcnow()
            
            # Find users with expired subscriptions that are still marked as active
            expired_users = session.query(User).filter(
                User.subscription_status == 'active',
                User.expiry_date.isnot(None),
                User.expiry_date < now
            ).all()
            
            count = 0
            for user in expired_users:
                print(f"🧹 [CLEANUP] Expiring subscription for user {user.user_sub} (expired: {user.expiry_date})")
                user.subscription_plan = 'free'
                user.subscription_status = 'expired'
                user.email_notifications = False  # Disable email notifications
                user.updated_at = now
                count += 1
            
            if count > 0:
                session.flush()
                print(f"✅ [CLEANUP] Cleaned up {count} expired subscriptions and disabled email notifications")
            else:
                print(f"ℹ️ [CLEANUP] No expired subscriptions found")
                
            return count
            
    except Exception as e:
        print(f"❌ [CLEANUP] Error cleaning up expired subscriptions: {e}")
        return 0