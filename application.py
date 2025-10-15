# application.py
from flask import Flask, request, jsonify, send_file
from models import Base, get_engine_from_env, get_session_context, Watchlist, Signal, UserSignal, User
from datetime import datetime
from flask_cors import CORS
from sqlalchemy import desc
import traceback
import os
import threading
from algo.runner import generate_pdf_report_full
import boto3
from botocore.exceptions import ClientError

application = Flask(__name__)

# Enable CORS for Amplify frontend
CORS(application, resources={
    r"/*": {
        "origins": [
            "https://main.d2lu8gx2f335fg.amplifyapp.com",
            "http://localhost:3000"
        ],
        "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"],
        "supports_credentials": True
    }
})


# Create tables at startup
engine = get_engine_from_env()
Base.metadata.create_all(engine)

# Store for tracking PDF generation status
pdf_generation_status = {}

# ======================
# HEALTH CHECK
# ======================
@application.route("/health")
def health():
    return {"status": "ok"}

# ======================
# PDF GENERATION ROUTES
# ======================
@application.route("/api/generate-pdf/<symbol>", methods=["POST"])
def generate_pdf(symbol):
    """
    Start PDF generation for a specific symbol.
    Returns a job_id to track the generation status.
    """
    try:
        symbol = symbol.upper()
        job_id = f"{symbol}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize status
        pdf_generation_status[job_id] = {
            "status": "processing",
            "symbol": symbol,
            "started_at": datetime.utcnow().isoformat(),
            "pdf_path": None,
            "error": None
        }
        
        # Start PDF generation in background thread
        thread = threading.Thread(
            target=generate_pdf_background,
            args=(job_id, symbol)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "ok": True,
            "job_id": job_id,
            "message": f"PDF generation started for {symbol}",
            "estimated_time": "5-15 minutes"
        }), 202
        
    except Exception as e:
        print(f"Error starting PDF generation: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def generate_pdf_background(job_id, symbol):
    """Background task to generate PDF"""
    try:
        print(f"Starting PDF generation for {symbol} (job: {job_id})")
        
        # Determine the timeframe based on symbol
        from algo.runner import get_timeframes_for_symbol
        ltf, main_tf, htf = get_timeframes_for_symbol(symbol)
        
        # Call the PDF generation function with interval parameter
        result = generate_pdf_report_full(symbol)
        
        if "error" in result:
            pdf_generation_status[job_id] = {
                "status": "failed",
                "symbol": symbol,
                "started_at": pdf_generation_status[job_id]["started_at"],
                "completed_at": datetime.utcnow().isoformat(),
                "pdf_path": None,
                "error": result["error"]
            }
            print(f"PDF generation failed for {symbol}: {result['error']}")
        else:
            pdf_path = result.get("pdf_path")
            pdf_generation_status[job_id] = {
                "status": "completed",
                "symbol": symbol,
                "started_at": pdf_generation_status[job_id]["started_at"],
                "completed_at": datetime.utcnow().isoformat(),
                "pdf_path": pdf_path,
                "error": None
            }
            print(f"PDF generation completed for {symbol}: {pdf_path}")
            
    except Exception as e:
        pdf_generation_status[job_id] = {
            "status": "failed",
            "symbol": symbol,
            "started_at": pdf_generation_status[job_id].get("started_at"),
            "completed_at": datetime.utcnow().isoformat(),
            "pdf_path": None,
            "error": str(e)
        }
        print(f"Exception in PDF generation for {symbol}: {e}")
        traceback.print_exc()

@application.route("/api/pdf-status/<job_id>", methods=["GET"])
def check_pdf_status(job_id):
    """Check the status of a PDF generation job"""
    try:
        if job_id not in pdf_generation_status:
            return jsonify({"error": "Job not found"}), 404
        
        status = pdf_generation_status[job_id]
        return jsonify(status), 200
        
    except Exception as e:
        print(f"Error checking PDF status: {e}")
        return jsonify({"error": str(e)}), 500

@application.route("/api/download-pdf/<job_id>", methods=["GET"])
def download_pdf(job_id):
    """Download the generated PDF"""
    try:
        if job_id not in pdf_generation_status:
            return jsonify({"error": "Job not found"}), 404
        
        status = pdf_generation_status[job_id]
        
        if status["status"] != "completed":
            return jsonify({
                "error": "PDF not ready yet",
                "status": status["status"]
            }), 400
        
        pdf_path = status["pdf_path"]
        
        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({"error": "PDF file not found"}), 404
        
        # Send file for download
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=os.path.basename(pdf_path),
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

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
@application.route("/api/user-signals/<user_sub>", methods=["GET"])
def get_user_signals_dashboard(user_sub):
    """Fetch all signals for coins in the user's watchlist with PDF status."""
    try:
        with get_session_context() as session:
            watchlist = session.query(Watchlist).filter_by(user_sub=user_sub).all()
            
            if not watchlist:
                return jsonify({
                    "signals": [],
                    "message": "No coins in watchlist"
                }), 200
            
            watched_symbols = [w.symbol for w in watchlist]
            
            # Get signals with their corresponding user_signal data
            signals = session.query(Signal).filter(
                Signal.symbol.in_(watched_symbols)
            ).order_by(
                Signal.created_at.desc()
            ).limit(20).all()
            
            result = []
            for signal in signals:
                payload = signal.payload or {}
                
                # Get the user_signal row for this user and signal
                user_signal = session.query(UserSignal).filter_by(
                    user_sub=user_sub,
                    signal_id=signal.id
                ).first()
                
                result.append({
                    "id": signal.id,
                    "symbol": signal.symbol,
                    "signal": payload.get("signal", "HOLD"),
                    "confidence": payload.get("confidence", 0),
                    "price": payload.get("price"),  
                    "timing": payload.get("timing", {}),
                    "risk": payload.get("risk", {}),
                    "sentiment": payload.get("sentiment", "Neutral"),
                    "strategies": payload.get("top_contributing_strategies", []),
                    "created_at": signal.created_at.isoformat() if signal.created_at else None,
                    "pdf_status": user_signal.pdf_status if user_signal else None,
                    "pdf_url": user_signal.pdf_url if user_signal else None
                })
            
            return jsonify({
                "signals": result,
                "count": len(result),
                "watchlist_count": len(watched_symbols)
            }), 200
            
    except Exception as e:
        print(f"Error fetching user signals: {e}")
        traceback.print_exc()
        return jsonify({"error": "Failed to fetch signals"}), 500
    
@application.route("/signals/<user_sub>", methods=["GET"])
def get_user_signals(user_sub):
    """Get live signals for user's watchlist (legacy endpoint)"""
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

def generate_presigned_url(bucket_name, object_key, expiration=3600):
    s3_client = boto3.client('s3')
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        return None

@application.route("/api/user-signals/<int:user_signal_id>/request-pdf", methods=["POST"])
def request_pdf(user_signal_id):
    """
    Mark pdf_status as 'initiated' for a specific UserSignal.
    The PDF worker running every minute will pick it up and generate the PDF.
    """
    try:
        with get_session_context() as session:
            user_signal = session.query(UserSignal).filter_by(id=user_signal_id).first()
            if not user_signal:
                return jsonify({"error": "UserSignal not found"}), 404

            # If already generated, return a fresh presigned URL
            if user_signal.pdf_status == "generated" and user_signal.pdf_url:
                # Extract S3 object key from the stored URL
                s3_url_parts = user_signal.pdf_url.split(".com/")  # "https://bucket.s3.amazonaws.com/pdfs/filename.pdf"
                if len(s3_url_parts) == 2:
                    s3_object_key = s3_url_parts[1]
                    fresh_url = generate_presigned_url('tradingsignals-pdfs', s3_object_key, expiration=3600)
                    if fresh_url:
                        return jsonify({
                            "message": "PDF already generated",
                            "pdf_url": fresh_url
                        })
                # fallback if presigned URL generation fails
                return jsonify({
                    "message": "PDF already generated",
                    "pdf_url": user_signal.pdf_url
                })

            # Initiate PDF generation for new files
            user_signal.pdf_status = "initiated"
            user_signal.pdf_url = None
            session.add(user_signal)

        return jsonify({"message": "PDF generation initiated"}), 202

    except Exception as e:
        print(f"Error initiating PDF: {e}")
        return jsonify({"error": str(e)}), 500

@application.route("/api/user-signals/<int:user_signal_id>/pdf-status", methods=["GET"])
def pdf_status(user_signal_id):
    """
    Return the current pdf_status and s3 URL (if ready) for a user signal.
    """
    try:
        with get_session_context() as session:
            user_signal = session.query(UserSignal).filter_by(id=user_signal_id).first()
            if not user_signal:
                return jsonify({"error": "UserSignal not found"}), 404

            return jsonify({
                "pdf_status": user_signal.pdf_status,
                "pdf_url": user_signal.pdf_url
            })

    except Exception as e:
        print(f"Error checking PDF status: {e}")
        return jsonify({"error": str(e)}), 500


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

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5000)

# #application.py
# from flask import Flask, request, jsonify
# from models import Base, get_engine_from_env, get_session_context, Watchlist, Signal, UserSignal, User
# from datetime import datetime
# from flask_cors import CORS
# from sqlalchemy import desc
# import traceback

# application = Flask(__name__)

# # Enable CORS for Amplify frontend
# CORS(
#     application,
#     resources={r"/*": {"origins": [
#         "https://main.d2lu8gx2f335fg.amplifyapp.com",
#         "http://localhost:3000"
#     ]}},
#     supports_credentials=True,
#     allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"]
# )

# # Create tables at startup (for dev only; in prod use migrations)
# engine = get_engine_from_env()
# Base.metadata.create_all(engine)

# # ======================
# # HEALTH CHECK
# # ======================
# @application.route("/health")
# def health():
#     return {"status": "ok"}

# # ======================
# # PROFILE ROUTES
# # ======================
# @application.route("/profile", methods=["POST"])
# def create_or_update_profile():
#     data = request.json or {}
#     user_sub = data.get("user_sub")
#     email = data.get("email")
#     name = data.get("name")
#     phone = data.get("phone")
#     subscription_status = data.get("subscription_status", "free")

#     if not user_sub or not email:
#         return {"error": "user_sub and email are required"}, 400

#     try:
#         with get_session_context() as session:
#             user = session.query(User).filter_by(user_sub=user_sub).first()
#             if user:
#                 user.email = email
#                 user.name = name or user.name
#                 user.phone = phone or user.phone
#                 user.subscription_status = subscription_status
#                 user.updated_at = datetime.utcnow()
#                 action = "updated"
#             else:
#                 user = User(
#                     user_sub=user_sub,
#                     email=email,
#                     name=name or email.split('@')[0],
#                     phone=phone,
#                     subscription_status=subscription_status,
#                     created_at=datetime.utcnow(),
#                     updated_at=datetime.utcnow()
#                 )
#                 session.add(user)
#                 action = "created"

#             return jsonify({
#                 "ok": True,
#                 "action": action,
#                 "user": {
#                     "user_sub": user.user_sub,
#                     "email": user.email,
#                     "name": user.name,
#                     "phone": user.phone,
#                     "subscription_status": user.subscription_status
#                 }
#             })
#     except Exception as e:
#         return {"error": str(e)}, 500

# @application.route("/profile/<user_sub>", methods=["GET"])
# def get_profile(user_sub):
#     try:
#         with get_session_context() as session:
#             user = session.query(User).filter_by(user_sub=user_sub).first()
#             if not user:
#                 return {"error": "User not found"}, 404
#             return jsonify({
#                 "user_sub": user.user_sub,
#                 "email": user.email,
#                 "name": user.name,
#                 "phone": user.phone,
#                 "subscription_status": user.subscription_status,
#                 "created_at": user.created_at.isoformat() if user.created_at else None,
#                 "updated_at": user.updated_at.isoformat() if user.updated_at else None
#             })
#     except Exception as e:
#         return {"error": str(e)}, 500

# @application.route("/profile/<user_sub>/subscription", methods=["PUT"])
# def update_subscription(user_sub):
#     data = request.json or {}
#     subscription_status = data.get("subscription_status")
#     if not subscription_status:
#         return {"error": "subscription_status is required"}, 400
#     try:
#         with get_session_context() as session:
#             user = session.query(User).filter_by(user_sub=user_sub).first()
#             if not user:
#                 return {"error": "User not found"}, 404
#             user.subscription_status = subscription_status
#             user.updated_at = datetime.utcnow()
#             return jsonify({"ok": True, "subscription_status": subscription_status})
#     except Exception as e:
#         return {"error": str(e)}, 500

# # ======================
# # WATCHLIST ROUTES
# # ======================
# @application.route("/watchlist", methods=["POST"])
# def add_watchlist():
#     data = request.json or {}
#     user_sub = data.get("user_sub")
#     symbol = data.get("symbol")
#     email = data.get("email")
#     phone = data.get("phone")
#     if not user_sub or not symbol or not email:
#         return {"error": "missing fields (user_sub, symbol, email required)"}, 400

#     try:
#         with get_session_context() as session:
#             existing = session.query(Watchlist).filter_by(user_sub=user_sub, symbol=symbol.upper()).first()
#             if existing:
#                 return {"error": "Symbol already in watchlist"}, 400
#             w = Watchlist(user_sub=user_sub, email=email, symbol=symbol.upper(), created_at=datetime.utcnow())
#             if hasattr(w, "phone") and phone:
#                 setattr(w, "phone", phone)
#             session.add(w)
#             return jsonify({"ok": True, "message": f"Added {symbol.upper()} to watchlist"})
#     except Exception as e:
#         return {"error": str(e)}, 500

# @application.route("/watchlist/<user_sub>", methods=["GET"])
# def get_watchlist(user_sub):
#     try:
#         with get_session_context() as session:
#             rows = session.query(Watchlist).filter_by(user_sub=user_sub).all()
#             return jsonify([{
#                 "id": r.id,
#                 "symbol": r.symbol,
#                 "email": getattr(r, "email", None),
#                 "phone": getattr(r, "phone", None),
#                 "created_at": r.created_at.isoformat() if r.created_at else None
#             } for r in rows])
#     except Exception as e:
#         return {"error": str(e)}, 500

# @application.route("/watchlist/<user_sub>/<symbol>", methods=["DELETE"])
# def remove_from_watchlist(user_sub, symbol):
#     try:
#         with get_session_context() as session:
#             watchlist_item = session.query(Watchlist).filter_by(user_sub=user_sub, symbol=symbol.upper()).first()
#             if not watchlist_item:
#                 return {"error": "Watchlist item not found"}, 404
#             session.delete(watchlist_item)
#             return jsonify({"ok": True, "message": f"Removed {symbol.upper()} from watchlist"})
#     except Exception as e:
#         return {"error": str(e)}, 500

# # ======================
# # DASHBOARD/SIGNALS ROUTES
# # ======================
# @application.route("/api/user-signals/<user_sub>", methods=["GET"])
# def get_user_signals_dashboard(user_sub):
#     """
#     NEW ENDPOINT: Fetch all signals for coins in the user's watchlist.
#     Returns the last 20 signals ordered by created_at desc with full payload.
#     This is specifically for the dashboard page.
#     """
#     try:
#         with get_session_context() as session:
#             # Get user's watchlist symbols
#             watchlist = session.query(Watchlist).filter_by(user_sub=user_sub).all()
            
#             if not watchlist:
#                 return jsonify({
#                     "signals": [],
#                     "message": "No coins in watchlist"
#                 }), 200
            
#             # Extract symbols from watchlist
#             watched_symbols = [w.symbol for w in watchlist]
            
#             # Get signals for those symbols (last 20)
#             signals = session.query(Signal).filter(
#                 Signal.symbol.in_(watched_symbols)
#             ).order_by(
#                 Signal.created_at.desc()
#             ).limit(20).all()
            
#             # Format response
#             result = []
#             for signal in signals:
#                 payload = signal.payload or {}
#                 result.append({
#                     "id": signal.id,
#                     "symbol": signal.symbol,
#                     "signal": payload.get("signal", "HOLD"),
#                     "confidence": payload.get("confidence", 0),
#                     "price": payload.get("price"),  
#                     "timing": payload.get("timing", {}),
#                     "risk": payload.get("risk", {}),
#                     "sentiment": payload.get("sentiment", "Neutral"),
#                     "strategies": payload.get("top_contributing_strategies", []),
#                     "created_at": signal.created_at.isoformat() if signal.created_at else None
#                 })
            
#             return jsonify({
#                 "signals": result,
#                 "count": len(result),
#                 "watchlist_count": len(watched_symbols)
#             }), 200
            
#     except Exception as e:
#         print(f"Error fetching user signals: {e}")
#         traceback.print_exc()
#         return jsonify({"error": "Failed to fetch signals"}), 500

# @application.route("/signals/<user_sub>", methods=["GET"])
# def get_user_signals(user_sub):
#     """Get live signals for user's watchlist (legacy endpoint)"""
#     try:
#         with get_session_context() as session:
#             watchlist = session.query(Watchlist).filter_by(user_sub=user_sub).all()
#             if not watchlist:
#                 return jsonify([])
#             symbols = [w.symbol for w in watchlist]

#             signals = session.query(Signal).filter(Signal.symbol.in_(symbols)).order_by(desc(Signal.created_at)).limit(50).all()
#             signal_list = []
#             for signal in signals:
#                 signal_list.append({
#                     "id": signal.id,
#                     "symbol": signal.symbol,
#                     "timeframe": signal.timeframe,
#                     "signal": signal.payload.get("signal") if signal.payload else None,
#                     "confidence": signal.payload.get("confidence") if signal.payload else None,
#                     "price": signal.payload.get("price") if signal.payload else None,
#                     "created_at": signal.created_at.isoformat() if signal.created_at else None,
#                     "pdf_url": signal.pdf_url
#                 })
#             return jsonify(signal_list)
#     except Exception as e:
#         return {"error": str(e)}, 500

# @application.route("/signals/<user_sub>/history", methods=["GET"])
# def get_signal_history(user_sub):
#     page = int(request.args.get('page', 1))
#     limit = int(request.args.get('limit', 10))
#     offset = (page - 1) * limit

#     try:
#         with get_session_context() as session:
#             user_signals = session.query(UserSignal).filter_by(user_sub=user_sub).order_by(desc(UserSignal.id)).offset(offset).limit(limit).all()
#             history = []
#             for us in user_signals:
#                 signal = us.signal
#                 if signal:
#                     history.append({
#                         "id": us.id,
#                         "signal_id": signal.id,
#                         "symbol": signal.symbol,
#                         "signal": signal.payload.get("signal") if signal.payload else None,
#                         "confidence": signal.payload.get("confidence") if signal.payload else None,
#                         "price": signal.payload.get("price") if signal.payload else None,
#                         "created_at": signal.created_at.isoformat() if signal.created_at else None,
#                         "delivery_status": us.delivery_status,
#                         "pdf_url": signal.pdf_url
#                     })
#             total_count = session.query(UserSignal).filter_by(user_sub=user_sub).count()
#             return jsonify({
#                 "signals": history,
#                 "pagination": {
#                     "page": page,
#                     "limit": limit,
#                     "total": total_count,
#                     "has_more": offset + limit < total_count
#                 }
#             })
#     except Exception as e:
#         return {"error": str(e)}, 500

# @application.route("/returns/<user_sub>", methods=["GET"])
# def get_user_returns(user_sub):
#     try:
#         with get_session_context() as session:
#             user_signals = session.query(UserSignal).filter_by(user_sub=user_sub).all()
#             if not user_signals:
#                 return jsonify({
#                     "total_signals": 0,
#                     "buy_signals": 0,
#                     "sell_signals": 0,
#                     "total_return": 0,
#                     "win_rate": 0,
#                     "avg_return": 0,
#                     "monthly_returns": []
#                 })

#             total_signals = len(user_signals)
#             buy_signals = sum(1 for us in user_signals if us.signal and us.signal.payload and us.signal.payload.get("signal") == "BUY")
#             sell_signals = sum(1 for us in user_signals if us.signal and us.signal.payload and us.signal.payload.get("signal") == "SELL")

#             total_return = total_signals * 2.5
#             win_rate = 65.0
#             avg_return = total_return / total_signals if total_signals > 0 else 0

#             return jsonify({
#                 "total_signals": total_signals,
#                 "buy_signals": buy_signals,
#                 "sell_signals": sell_signals,
#                 "total_return": round(total_return, 2),
#                 "win_rate": round(win_rate, 1),
#                 "avg_return": round(avg_return, 2),
#                 "monthly_returns": []
#             })
#     except Exception as e:
#         return {"error": str(e)}, 500

# # ======================
# # SUBSCRIPTION ROUTES
# # ======================
# @application.route("/subscription/plans", methods=["GET"])
# def get_subscription_plans():
#     plans = [
#         {"id": "basic", "name": "Basic Plan", "price": 29.99, "currency": "USD", "interval": "month",
#          "features": ["Real-time trading signals", "Email notifications", "Up to 5 coins in watchlist", "Basic analytics"]},
#         {"id": "pro", "name": "Pro Plan", "price": 79.99, "currency": "USD", "interval": "month",
#          "features": ["Everything in Basic", "SMS notifications", "Unlimited watchlist", "Advanced analytics", "PDF reports", "Priority support"]}
#     ]
#     return jsonify(plans)

# @application.route("/subscription/checkout", methods=["POST"])
# def create_checkout_session():
#     data = request.json or {}
#     user_sub = data.get("user_sub")
#     plan_id = data.get("plan_id")
#     if not user_sub or not plan_id:
#         return {"error": "user_sub and plan_id are required"}, 400
#     return jsonify({"checkout_url": "https://checkout.stripe.com/session_placeholder", "session_id": "cs_test_placeholder"})

# @application.route("/subscription/cancel", methods=["POST"])
# def cancel_subscription():
#     data = request.json or {}
#     user_sub = data.get("user_sub")
#     if not user_sub:
#         return {"error": "user_sub is required"}, 400
#     try:
#         with get_session_context() as session:
#             user = session.query(User).filter_by(user_sub=user_sub).first()
#             if user:
#                 user.subscription_status = "cancelled"
#                 user.updated_at = datetime.utcnow()
#             return jsonify({"ok": True, "message": "Subscription cancelled"})
#     except Exception as e:
#         return {"error": str(e)}, 500

# if __name__ == "__main__":
#     application.run(host="0.0.0.0", port=5000)
