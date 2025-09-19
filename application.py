from flask import Flask, request, jsonify
from models import Base, get_engine_from_env, get_session, Watchlist, Signal, UserSignal, User
from datetime import datetime
from flask_cors import CORS
from sqlalchemy import desc, func

application = Flask(__name__)

# Enable CORS for your Amplify frontend
CORS(
    application,
    resources={r"/*": {"origins": ["https://main.d2lu8gx2f335fg.amplifyapp.com", "http://localhost:3000" ]}},  # removed trailing slash
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"]
)

# Create tables at startup (for dev; in prod you'd use migrations)
engine = get_engine_from_env()
Base.metadata.create_all(engine)

@application.route("/health")
def health():
    return {"status": "ok"}

# ==============================================
# PROFILE ROUTES
# ==============================================
@application.route("/profile", methods=["POST"])
def create_or_update_profile():
    """
    Create or update user profile on login
    Expected JSON:
    {
      "user_sub": "<cognito-sub>",
      "email": "user@example.com", 
      "name": "John Doe",
      "phone": "+911234567890",
      "subscription_status": "free"
    }
    """
    data = request.json or {}
    user_sub = data.get("user_sub")
    email = data.get("email")
    name = data.get("name")
    phone = data.get("phone")
    subscription_status = data.get("subscription_status", "free")

    if not user_sub or not email:
        return {"error": "user_sub and email are required"}, 400

    session = get_session()
    try:
        # Check if user already exists
        user = session.query(User).filter_by(user_sub=user_sub).first()
        
        if user:
            # Update existing user
            user.email = email
            user.name = name or user.name
            user.phone = phone or user.phone
            user.subscription_status = subscription_status
            user.updated_at = datetime.utcnow()
            action = "updated"
        else:
            # Create new user
            user = User(
                user_sub=user_sub,
                email=email,
                name=name or email.split('@')[0],
                phone=phone,
                subscription_status=subscription_status,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(user)
            action = "created"
        
        session.commit()
        
        return jsonify({
            "ok": True, 
            "action": action,
            "user": {
                "user_sub": user.user_sub,
                "email": user.email,
                "name": user.name,
                "phone": user.phone,
                "subscription_status": user.subscription_status
            }
        })
    except Exception as e:
        session.rollback()
        return {"error": str(e)}, 500
    finally:
        session.close()

@application.route("/profile/<user_sub>", methods=["GET"])
def get_profile(user_sub):
    """Get user profile"""
    session = get_session()
    try:
        user = session.query(User).filter_by(user_sub=user_sub).first()
        if not user:
            return {"error": "User not found"}, 404
            
        return jsonify({
            "user_sub": user.user_sub,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "subscription_status": user.subscription_status,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        })
    finally:
        session.close()

@application.route("/profile/<user_sub>/subscription", methods=["PUT"])
def update_subscription(user_sub):
    """Update user subscription status"""
    data = request.json or {}
    subscription_status = data.get("subscription_status")
    
    if not subscription_status:
        return {"error": "subscription_status is required"}, 400
    
    session = get_session()
    try:
        user = session.query(User).filter_by(user_sub=user_sub).first()
        if not user:
            return {"error": "User not found"}, 404
            
        user.subscription_status = subscription_status
        user.updated_at = datetime.utcnow()
        session.commit()
        
        return jsonify({"ok": True, "subscription_status": subscription_status})
    except Exception as e:
        session.rollback()
        return {"error": str(e)}, 500
    finally:
        session.close()

# ==============================================
# WATCHLIST ROUTES
# ==============================================
@application.route("/watchlist", methods=["POST"])
def add_watchlist():
    """
    Expected JSON:
    {
      "user_sub": "<cognito-sub>",
      "symbol": "BTCUSDT",
      "email": "user@example.com",
      "phone": "+911234567890"   # optional
    }
    """
    data = request.json or {}
    user_sub = data.get("user_sub")   # Cognito user id
    symbol = data.get("symbol")
    email = data.get("email")
    phone = data.get("phone")

    if not user_sub or not symbol or not email:
        return {"error": "missing fields (user_sub, symbol, email required)"}, 400

    session = get_session()
    try:
        # Check if already exists
        existing = session.query(Watchlist).filter_by(
            user_sub=user_sub, 
            symbol=symbol.upper()
        ).first()
        
        if existing:
            return {"error": "Symbol already in watchlist"}, 400

        w = Watchlist(
            user_sub=user_sub,
            email=email,
            symbol=symbol.upper(),
            created_at=datetime.utcnow()
        )
        # optional phone column
        if hasattr(w, "phone") and phone:
            setattr(w, "phone", phone)

        session.add(w)
        session.commit()
        return jsonify({"ok": True, "message": f"Added {symbol.upper()} to watchlist"})
    except Exception as e:
        session.rollback()
        return {"error": str(e)}, 500
    finally:
        session.close()

@application.route("/watchlist/<user_sub>", methods=["GET"])
def get_watchlist(user_sub):
    """Get user's watchlist"""
    session = get_session()
    try:
        rows = session.query(Watchlist).filter_by(user_sub=user_sub).all()
        out = [
            {
                "id": r.id,
                "symbol": r.symbol,
                "email": getattr(r, "email", None),
                "phone": getattr(r, "phone", None),
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in rows
        ]
        return jsonify(out)
    finally:
        session.close()

@application.route("/watchlist/<user_sub>/<symbol>", methods=["DELETE"])
def remove_from_watchlist(user_sub, symbol):
    """Remove a coin from user's watchlist"""
    session = get_session()
    try:
        watchlist_item = session.query(Watchlist).filter_by(
            user_sub=user_sub, 
            symbol=symbol.upper()
        ).first()
        
        if not watchlist_item:
            return {"error": "Watchlist item not found"}, 404
            
        session.delete(watchlist_item)
        session.commit()
        
        return jsonify({"ok": True, "message": f"Removed {symbol.upper()} from watchlist"})
    except Exception as e:
        session.rollback()
        return {"error": str(e)}, 500
    finally:
        session.close()

# ==============================================
# DASHBOARD/SIGNALS ROUTES
# ==============================================
@application.route("/signals/<user_sub>", methods=["GET"])
def get_user_signals(user_sub):
    """Get live signals for user's watchlist"""
    session = get_session()
    try:
        # Get user's watchlist symbols
        watchlist = session.query(Watchlist).filter_by(user_sub=user_sub).all()
        if not watchlist:
            return jsonify([])
            
        symbols = [w.symbol for w in watchlist]
        
        # Get latest signals for these symbols
        signals = session.query(Signal).filter(
            Signal.symbol.in_(symbols)
        ).order_by(desc(Signal.created_at)).limit(50).all()
        
        signal_list = []
        for signal in signals:
            signal_list.append({
                "id": signal.id,
                "symbol": signal.symbol,
                "timeframe": signal.timeframe,
                "signal": signal.payload.get("signal") if signal.payload else None,
                "confidence": signal.payload.get("confidence") if signal.payload else None,
                "price": signal.payload.get("price") if signal.payload else None,
                "created_at": signal.created_at.isoformat() if signal.created_at else None,
                "pdf_url": signal.pdf_url
            })
            
        return jsonify(signal_list)
    finally:
        session.close()

@application.route("/signals/<user_sub>/history", methods=["GET"])
def get_signal_history(user_sub):
    """Get paginated signal history for user"""
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    offset = (page - 1) * limit
    
    session = get_session()
    try:
        # Get user signals with pagination
        user_signals = session.query(UserSignal).filter_by(
            user_sub=user_sub
        ).order_by(desc(UserSignal.id)).offset(offset).limit(limit).all()
        
        history = []
        for us in user_signals:
            signal = us.signal
            if signal:
                history.append({
                    "id": us.id,
                    "signal_id": signal.id,
                    "symbol": signal.symbol,
                    "signal": signal.payload.get("signal") if signal.payload else None,
                    "confidence": signal.payload.get("confidence") if signal.payload else None,
                    "price": signal.payload.get("price") if signal.payload else None,
                    "created_at": signal.created_at.isoformat() if signal.created_at else None,
                    "delivery_status": us.delivery_status,
                    "pdf_url": signal.pdf_url
                })
            
        # Get total count for pagination
        total_count = session.query(UserSignal).filter_by(user_sub=user_sub).count()
        
        return jsonify({
            "signals": history,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "has_more": offset + limit < total_count
            }
        })
    finally:
        session.close()

@application.route("/returns/<user_sub>", methods=["GET"])
def get_user_returns(user_sub):
    """Get trading returns/performance for user"""
    session = get_session()
    try:
        # Get all user signals
        user_signals = session.query(UserSignal).filter_by(user_sub=user_sub).all()
        
        if not user_signals:
            return jsonify({
                "total_signals": 0,
                "buy_signals": 0,
                "sell_signals": 0,
                "total_return": 0,
                "win_rate": 0,
                "avg_return": 0,
                "monthly_returns": []
            })
        
        # Calculate basic stats
        total_signals = len(user_signals)
        buy_signals = sum(1 for us in user_signals 
                         if us.signal and us.signal.payload and 
                         us.signal.payload.get("signal") == "BUY")
        sell_signals = sum(1 for us in user_signals 
                          if us.signal and us.signal.payload and 
                          us.signal.payload.get("signal") == "SELL")
        
        # Mock returns calculation (replace with your actual logic)
        # You can enhance this based on your algorithm's performance tracking
        total_return = total_signals * 2.5  # Mock: 2.5% per signal
        win_rate = 65.0  # Mock: 65% win rate
        avg_return = total_return / total_signals if total_signals > 0 else 0
        
        return jsonify({
            "total_signals": total_signals,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "total_return": round(total_return, 2),
            "win_rate": round(win_rate, 1),
            "avg_return": round(avg_return, 2),
            "monthly_returns": []  # You can calculate this based on created_at dates
        })
    finally:
        session.close()

# ==============================================
# SUBSCRIPTION ROUTES (for future Stripe integration)
# ==============================================
@application.route("/subscription/plans", methods=["GET"])
def get_subscription_plans():
    """Get available subscription plans"""
    plans = [
        {
            "id": "basic",
            "name": "Basic Plan",
            "price": 29.99,
            "currency": "USD",
            "interval": "month",
            "features": [
                "Real-time trading signals",
                "Email notifications", 
                "Up to 5 coins in watchlist",
                "Basic analytics"
            ]
        },
        {
            "id": "pro",
            "name": "Pro Plan", 
            "price": 79.99,
            "currency": "USD",
            "interval": "month",
            "features": [
                "Everything in Basic",
                "SMS notifications",
                "Unlimited watchlist",
                "Advanced analytics",
                "PDF reports",
                "Priority support"
            ]
        }
    ]
    return jsonify(plans)

@application.route("/subscription/checkout", methods=["POST"])
def create_checkout_session():
    """Create Stripe checkout session (implement next week)"""
    data = request.json or {}
    user_sub = data.get("user_sub")
    plan_id = data.get("plan_id")
    
    if not user_sub or not plan_id:
        return {"error": "user_sub and plan_id are required"}, 400
    
    # TODO: Implement Stripe checkout session creation
    return jsonify({
        "checkout_url": "https://checkout.stripe.com/session_placeholder",
        "session_id": "cs_test_placeholder"
    })

@application.route("/subscription/cancel", methods=["POST"])  
def cancel_subscription():
    """Cancel user subscription (implement next week)"""
    data = request.json or {}
    user_sub = data.get("user_sub")
    
    if not user_sub:
        return {"error": "user_sub is required"}, 400
    
    # TODO: Implement Stripe subscription cancellation
    # For now, just update user status to cancelled
    session = get_session()
    try:
        user = session.query(User).filter_by(user_sub=user_sub).first()
        if user:
            user.subscription_status = "cancelled"
            user.updated_at = datetime.utcnow()
            session.commit()
            
        return jsonify({"ok": True, "message": "Subscription cancelled"})
    except Exception as e:
        session.rollback()
        return {"error": str(e)}, 500
    finally:
        session.close()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5000)