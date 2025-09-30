#application.py
from flask import Flask, request, jsonify
from models import Base, get_engine_from_env, get_session_context, Watchlist, Signal, UserSignal, User
from datetime import datetime
from flask_cors import CORS
from sqlalchemy import desc
import traceback

application = Flask(__name__)

# Enable CORS for Amplify frontend
CORS(
    application,
    resources={r"/*": {"origins": [
        "https://main.d2lu8gx2f335fg.amplifyapp.com",
        "http://localhost:3000"
    ]}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"]
)

# Create tables at startup (for dev only; in prod use migrations)
engine = get_engine_from_env()
Base.metadata.create_all(engine)

# ======================
# HEALTH CHECK
# ======================
@application.route("/health")
def health():
    return {"status": "ok"}

# Removed /worker/run route – not needed anymore.

# ======================
# PROFILE ROUTES
# ======================
@application.route("/profile", methods=["POST"])
def create_or_update_profile():
    data = request.json or {}
    user_sub = data.get("user_sub")
    email = data.get("email")
    name = data.get("name")
    phone = data.get("phone")
    subscription_status = data.get("subscription_status", "free")

    if not user_sub or not email:
        return {"error": "user_sub and email are required"}, 400

    try:
        with get_session_context() as session:
            user = session.query(User).filter_by(user_sub=user_sub).first()
            if user:
                user.email = email
                user.name = name or user.name
                user.phone = phone or user.phone
                user.subscription_status = subscription_status
                user.updated_at = datetime.utcnow()
                action = "updated"
            else:
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
        return {"error": str(e)}, 500

@application.route("/profile/<user_sub>", methods=["GET"])
def get_profile(user_sub):
    try:
        with get_session_context() as session:
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
    except Exception as e:
        return {"error": str(e)}, 500

@application.route("/profile/<user_sub>/subscription", methods=["PUT"])
def update_subscription(user_sub):
    data = request.json or {}
    subscription_status = data.get("subscription_status")
    if not subscription_status:
        return {"error": "subscription_status is required"}, 400
    try:
        with get_session_context() as session:
            user = session.query(User).filter_by(user_sub=user_sub).first()
            if not user:
                return {"error": "User not found"}, 404
            user.subscription_status = subscription_status
            user.updated_at = datetime.utcnow()
            return jsonify({"ok": True, "subscription_status": subscription_status})
    except Exception as e:
        return {"error": str(e)}, 500

# ======================
# WATCHLIST ROUTES
# ======================
@application.route("/watchlist", methods=["POST"])
def add_watchlist():
    data = request.json or {}
    user_sub = data.get("user_sub")
    symbol = data.get("symbol")
    email = data.get("email")
    phone = data.get("phone")
    if not user_sub or not symbol or not email:
        return {"error": "missing fields (user_sub, symbol, email required)"}, 400

    try:
        with get_session_context() as session:
            existing = session.query(Watchlist).filter_by(user_sub=user_sub, symbol=symbol.upper()).first()
            if existing:
                return {"error": "Symbol already in watchlist"}, 400
            w = Watchlist(user_sub=user_sub, email=email, symbol=symbol.upper(), created_at=datetime.utcnow())
            if hasattr(w, "phone") and phone:
                setattr(w, "phone", phone)
            session.add(w)
            return jsonify({"ok": True, "message": f"Added {symbol.upper()} to watchlist"})
    except Exception as e:
        return {"error": str(e)}, 500

@application.route("/watchlist/<user_sub>", methods=["GET"])
def get_watchlist(user_sub):
    try:
        with get_session_context() as session:
            rows = session.query(Watchlist).filter_by(user_sub=user_sub).all()
            return jsonify([{
                "id": r.id,
                "symbol": r.symbol,
                "email": getattr(r, "email", None),
                "phone": getattr(r, "phone", None),
                "created_at": r.created_at.isoformat() if r.created_at else None
            } for r in rows])
    except Exception as e:
        return {"error": str(e)}, 500

@application.route("/watchlist/<user_sub>/<symbol>", methods=["DELETE"])
def remove_from_watchlist(user_sub, symbol):
    try:
        with get_session_context() as session:
            watchlist_item = session.query(Watchlist).filter_by(user_sub=user_sub, symbol=symbol.upper()).first()
            if not watchlist_item:
                return {"error": "Watchlist item not found"}, 404
            session.delete(watchlist_item)
            return jsonify({"ok": True, "message": f"Removed {symbol.upper()} from watchlist"})
    except Exception as e:
        return {"error": str(e)}, 500

# ======================
# DASHBOARD/SIGNALS ROUTES
# ======================
@application.route("/signals/<user_sub>", methods=["GET"])
def get_user_signals(user_sub):
    """Get live signals for user's watchlist"""
    try:
        with get_session_context() as session:
            watchlist = session.query(Watchlist).filter_by(user_sub=user_sub).all()
            if not watchlist:
                return jsonify([])
            symbols = [w.symbol for w in watchlist]

            signals = session.query(Signal).filter(Signal.symbol.in_(symbols)).order_by(desc(Signal.created_at)).limit(50).all()
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
    except Exception as e:
        return {"error": str(e)}, 500

@application.route("/signals/<user_sub>/history", methods=["GET"])
def get_signal_history(user_sub):
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    offset = (page - 1) * limit

    try:
        with get_session_context() as session:
            user_signals = session.query(UserSignal).filter_by(user_sub=user_sub).order_by(desc(UserSignal.id)).offset(offset).limit(limit).all()
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
    except Exception as e:
        return {"error": str(e)}, 500

@application.route("/returns/<user_sub>", methods=["GET"])
def get_user_returns(user_sub):
    try:
        with get_session_context() as session:
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

            total_signals = len(user_signals)
            buy_signals = sum(1 for us in user_signals if us.signal and us.signal.payload and us.signal.payload.get("signal") == "BUY")
            sell_signals = sum(1 for us in user_signals if us.signal and us.signal.payload and us.signal.payload.get("signal") == "SELL")

            total_return = total_signals * 2.5
            win_rate = 65.0
            avg_return = total_return / total_signals if total_signals > 0 else 0

            return jsonify({
                "total_signals": total_signals,
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "total_return": round(total_return, 2),
                "win_rate": round(win_rate, 1),
                "avg_return": round(avg_return, 2),
                "monthly_returns": []
            })
    except Exception as e:
        return {"error": str(e)}, 500

# ======================
# SUBSCRIPTION ROUTES
# ======================
@application.route("/subscription/plans", methods=["GET"])
def get_subscription_plans():
    plans = [
        {"id": "basic", "name": "Basic Plan", "price": 29.99, "currency": "USD", "interval": "month",
         "features": ["Real-time trading signals", "Email notifications", "Up to 5 coins in watchlist", "Basic analytics"]},
        {"id": "pro", "name": "Pro Plan", "price": 79.99, "currency": "USD", "interval": "month",
         "features": ["Everything in Basic", "SMS notifications", "Unlimited watchlist", "Advanced analytics", "PDF reports", "Priority support"]}
    ]
    return jsonify(plans)

@application.route("/subscription/checkout", methods=["POST"])
def create_checkout_session():
    data = request.json or {}
    user_sub = data.get("user_sub")
    plan_id = data.get("plan_id")
    if not user_sub or not plan_id:
        return {"error": "user_sub and plan_id are required"}, 400
    return jsonify({"checkout_url": "https://checkout.stripe.com/session_placeholder", "session_id": "cs_test_placeholder"})

@application.route("/subscription/cancel", methods=["POST"])
def cancel_subscription():
    data = request.json or {}
    user_sub = data.get("user_sub")
    if not user_sub:
        return {"error": "user_sub is required"}, 400
    try:
        with get_session_context() as session:
            user = session.query(User).filter_by(user_sub=user_sub).first()
            if user:
                user.subscription_status = "cancelled"
                user.updated_at = datetime.utcnow()
            return jsonify({"ok": True, "message": "Subscription cancelled"})
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "_main_":
    application.run(host="0.0.0.0", port=5000)