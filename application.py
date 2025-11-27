# application.py
from flask import Flask, request, jsonify, send_file
from models import Base, get_engine_from_env, get_session_context, Watchlist, Signal, UserSignal, User, SignalPerformance, Review
from datetime import datetime
from flask_cors import CORS
from sqlalchemy import desc
import traceback
import os
import threading
from algo.runner import generate_pdf_report_full
from subscription_routes import register_subscription_routes
import boto3
from botocore.exceptions import ClientError

application = Flask(__name__)

# Enable CORS for your domains
CORS(application, resources={
    r"/*": {
        "origins": [
            "https://dollaraptor.com",          # Also add without www if needed
            "http://localhost:3000",             # Local dev
            "https://api.dollaraptor.com",
            "https://signal.dollaraptor.com"
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
# REVIEW ROUTES
# ======================

@application.route("/api/reviews/submit", methods=["POST"])
def submit_review():
    """Submit a new review (requires authentication)"""
    try:
        data = request.json or {}
        user_sub = data.get("user_sub")
        email = data.get("email")
        name = data.get("name")
        rating = data.get("rating")
        comment = data.get("comment")
        
        # Validation
        if not all([user_sub, email, name, rating, comment]):
            return jsonify({"error": "All fields are required"}), 400
        
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({"error": "Rating must be between 1 and 5"}), 400
        
        if len(comment.strip()) < 10:
            return jsonify({"error": "Comment must be at least 10 characters"}), 400
        
        with get_session_context() as session:
            # Check if user exists
            user = session.query(User).filter_by(user_sub=user_sub).first()
            if not user:
                return jsonify({"error": "User not found. Please sign up first."}), 404
            
            # Check subscription status (optional - only allow subscribers to review)
            if user.subscription_status not in ['active', 'pro', 'max']:
                return jsonify({"error": "Only subscribers can post reviews"}), 403
            
            # Create new review
            review = Review(
                user_sub=user_sub,
                email=email,
                name=name,
                rating=rating,
                comment=comment.strip(),
                verified=False,  # Admin must verify
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(review)
            
            return jsonify({
                "ok": True,
                "message": "Review submitted successfully! It will be published after verification.",
                "review": review.to_dict()
            }), 201
            
    except Exception as e:
        print(f"Error submitting review: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@application.route("/api/reviews/verified", methods=["GET"])
def get_verified_reviews():
    """Get all verified reviews for public display"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        with get_session_context() as session:
            # Get total count
            total_count = session.query(Review).filter_by(verified=True).count()
            
            # Fetch verified reviews
            reviews = session.query(Review).filter_by(
                verified=True
            ).order_by(
                Review.created_at.desc()
            ).limit(limit).offset(offset).all()
            
            return jsonify({
                "reviews": [r.to_dict() for r in reviews],
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total_count
                }
            }), 200
            
    except Exception as e:
        print(f"Error fetching verified reviews: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@application.route("/api/reviews/pending", methods=["GET"])
def get_pending_reviews():
    """Get all pending (unverified) reviews - ADMIN ONLY"""
    try:
        # Simple admin check - you can enhance this with proper auth later
        admin_key = request.headers.get('X-Admin-Key')
        if admin_key != os.environ.get('ADMIN_SECRET_KEY', 'your-secret-admin-key'):
            return jsonify({"error": "Unauthorized"}), 403
        
        with get_session_context() as session:
            reviews = session.query(Review).filter_by(
                verified=False
            ).order_by(
                Review.created_at.desc()
            ).all()
            
            return jsonify({
                "reviews": [r.to_dict() for r in reviews],
                "count": len(reviews)
            }), 200
            
    except Exception as e:
        print(f"Error fetching pending reviews: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@application.route("/api/reviews/verify/<int:review_id>", methods=["POST"])
def verify_review(review_id):
    """Verify a review - ADMIN ONLY"""
    try:
        # Admin authentication
        admin_key = request.headers.get('X-Admin-Key')
        if admin_key != os.environ.get('ADMIN_SECRET_KEY', 'your-secret-admin-key'):
            return jsonify({"error": "Unauthorized"}), 403
        
        with get_session_context() as session:
            review = session.query(Review).filter_by(id=review_id).first()
            if not review:
                return jsonify({"error": "Review not found"}), 404
            
            review.verified = True
            review.updated_at = datetime.utcnow()
            
            return jsonify({
                "ok": True,
                "message": f"Review #{review_id} verified successfully",
                "review": review.to_dict()
            }), 200
            
    except Exception as e:
        print(f"Error verifying review: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@application.route("/api/reviews/delete/<int:review_id>", methods=["DELETE"])
def delete_review(review_id):
    """Delete a review - ADMIN ONLY"""
    try:
        # Admin authentication
        admin_key = request.headers.get('X-Admin-Key')
        if admin_key != os.environ.get('ADMIN_SECRET_KEY', 'your-secret-admin-key'):
            return jsonify({"error": "Unauthorized"}), 403
        
        with get_session_context() as session:
            review = session.query(Review).filter_by(id=review_id).first()
            if not review:
                return jsonify({"error": "Review not found"}), 404
            
            session.delete(review)
            
            return jsonify({
                "ok": True,
                "message": f"Review #{review_id} deleted successfully"
            }), 200
            
    except Exception as e:
        print(f"Error deleting review: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ======================
# CONTACT FORM ROUTES
# ======================
@application.route("/api/contact", methods=["POST"])
def send_contact_email():
    """Send contact form email via SES"""
    try:
        data = request.json or {}
        firstName = data.get("firstName", "").strip()
        lastName = data.get("lastName", "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()
        subject = data.get("subject", "").strip()
        message = data.get("message", "").strip()
        
        # Validate required fields
        if not all([firstName, email, subject, message]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Initialize SES client
        ses_client = boto3.client(
            'ses',
            region_name=os.environ.get('AWS_REGION', 'ap-southeast-2'),
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
        )
        
        # Your verified email from environment
        from_email = os.environ.get('SES_FROM_EMAIL', 'rkaydhanu@gmail.com')
        
        # HTML email body
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #0f0f0f; color: #e0e0e0;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #1a1a1a; border: 1px solid #333; border-radius: 10px; padding: 30px;">
                    <h2 style="color: #06b6d4; margin-bottom: 20px;">📬 New Contact Form Submission</h2>
                    
                    <div style="background-color: #0f0f0f; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                        <p><strong style="color: #06b6d4;">Name:</strong> {firstName} {lastName}</p>
                        <p><strong style="color: #06b6d4;">Email:</strong> <a href="mailto:{email}" style="color: #06b6d4;">{email}</a></p>
                        <p><strong style="color: #06b6d4;">Phone:</strong> {phone if phone else 'Not provided'}</p>
                        <p><strong style="color: #06b6d4;">Subject:</strong> {subject}</p>
                    </div>
                    
                    <div style="background-color: #0f0f0f; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #06b6d4;">
                        <h3 style="color: #06b6d4; margin-top: 0;">Message:</h3>
                        <p style="white-space: pre-wrap; line-height: 1.6;">{message}</p>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid #333; margin: 20px 0;">
                    
                    <p style="color: #999; font-size: 12px; margin: 0;">
                        This is an automated message from DollaRaptor contact form.<br>
                        <strong>Reply to:</strong> {email}
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Plain text fallback
        text_body = f"""
NEW CONTACT FORM SUBMISSION

Name: {firstName} {lastName}
Email: {email}
Phone: {phone if phone else 'Not provided'}
Subject: {subject}

MESSAGE:
{message}

---
This is an automated message from DollaRaptor contact form.
Reply to: {email}
        """
        
        # Send email via SES
        response = ses_client.send_email(
            Source=from_email,
            Destination={
                'ToAddresses': [from_email]
            },
            Message={
                'Subject': {
                    'Data': f'New Contact: {subject}',
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Html': {
                        'Data': html_body,
                        'Charset': 'UTF-8'
                    },
                    'Text': {
                        'Data': text_body,
                        'Charset': 'UTF-8'
                    }
                }
            },
            ReplyToAddresses=[email]
        )
        
        print(f"✓ Email sent successfully. MessageId: {response['MessageId']}")
        
        return jsonify({
            "ok": True,
            "message": "Message sent successfully! We'll get back to you soon.",
            "messageId": response['MessageId']
        }), 200
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"✗ AWS SES Error: {error_code} - {e.response['Error']['Message']}")
        
        if error_code == 'MessageRejected':
            return jsonify({"error": "Email rejected. Please check your email address."}), 400
        else:
            return jsonify({"error": f"Email service error: {error_code}"}), 500
            
    except Exception as e:
        print(f"✗ Error sending contact email: {e}")
        traceback.print_exc()
        return jsonify({"error": "Failed to send email. Please try again later."}), 500

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

@application.route("/api/signals/all", methods=["GET"])
def get_all_historical_signals():
    """Fetch all signals from the signals table that are at least 5 hours old"""
    try:
        from datetime import datetime, timedelta
        
        with get_session_context() as session:
            # Calculate 5 hours ago
            five_hours_ago = datetime.utcnow() - timedelta(hours=5)
            
            # Only fetch signals older than 5 hours
            signals = session.query(Signal).filter(
                Signal.created_at <= five_hours_ago
            ).order_by(
                Signal.created_at.desc()
            ).limit(100).all()
            
            result = []
            for signal in signals:
                payload = signal.payload or {}
                
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
                })
            
            return jsonify({
                "signals": result,
                "count": len(result)
            }), 200
            
    except Exception as e:
        print(f"Error fetching all signals: {e}")
        traceback.print_exc()
        return jsonify({"error": "Failed to fetch signals"}), 500
    
# Add this to your application.py file

@application.route("/api/signals/<int:signal_id>/performance", methods=["GET"])
def get_signal_performance(signal_id):
    """
    Fetch performance data for a specific signal.
    Returns tracked performance metrics if available.
    """
    try:
        with get_session_context() as session:
            # Get the signal first
            signal = session.query(Signal).filter_by(id=signal_id).first()
            if not signal:
                return jsonify({"error": "Signal not found"}), 404
            
            # Get all performance records for this signal
            performances = session.query(SignalPerformance).filter_by(signal_id=signal_id).all()
            
            if not performances:
                return jsonify({
                    "signal_id": signal_id,
                    "symbol": signal.symbol,
                    "status": "pending",
                    "message": "Performance data not yet calculated. Signal is being monitored.",
                    "performance": None
                }), 200
            
            # Return the most recent performance record
            latest_perf = performances[-1]  # Most recent
            
            return jsonify({
                "signal_id": signal_id,
                "symbol": signal.symbol,
                "status": "completed",
                "performance": {
                    "exit_price": float(latest_perf.exit_price) if latest_perf.exit_price else None,
                    "exit_reason": latest_perf.exit_reason,  # TP / SL / TIME
                    "result": latest_perf.result,  # SUCCESS / FAILURE
                    "return_percent": float(latest_perf.return_percent) if latest_perf.return_percent else None,
                    "profit_usd": float(latest_perf.profit_usd) if latest_perf.profit_usd else None,
                    "duration_minutes": latest_perf.duration_minutes,
                    "tracked_at": latest_perf.tracked_at.isoformat() if latest_perf.tracked_at else None
                },
                "all_performances": [
                    {
                        "exit_price": float(p.exit_price) if p.exit_price else None,
                        "exit_reason": p.exit_reason,
                        "result": p.result,
                        "return_percent": float(p.return_percent) if p.return_percent else None,
                        "profit_usd": float(p.profit_usd) if p.profit_usd else None,
                        "duration_minutes": p.duration_minutes,
                        "tracked_at": p.tracked_at.isoformat() if p.tracked_at else None
                    } for p in performances
                ]
            }), 200
            
    except Exception as e:
        print(f"Error fetching signal performance: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@application.route("/api/user-signals/<user_sub>/performance", methods=["GET"])
def get_user_signals_with_performance(user_sub):
    """
    Fetch all signals for a user's watchlist with their performance data if available.
    More efficient than calling performance endpoint for each signal individually.
    """
    try:
        with get_session_context() as session:
            # Get user's watchlist
            watchlist = session.query(Watchlist).filter_by(user_sub=user_sub).all()
            
            if not watchlist:
                return jsonify({
                    "signals": [],
                    "message": "No coins in watchlist"
                }), 200
            
            watched_symbols = [w.symbol for w in watchlist]
            
            # Get signals for watched symbols
            signals = session.query(Signal).filter(
                Signal.symbol.in_(watched_symbols)
            ).order_by(
                Signal.created_at.desc()
            ).limit(50).all()
            
            result = []
            for signal in signals:
                payload = signal.payload or {}
                
                # Get user_signal data
                user_signal = session.query(UserSignal).filter_by(
                    user_sub=user_sub,
                    signal_id=signal.id
                ).first()
                
                # Get performance data
                performance_records = session.query(SignalPerformance).filter_by(
                    signal_id=signal.id
                ).all()
                
                performance_data = None
                perf_status = "pending"
                
                if performance_records:
                    latest_perf = performance_records[-1]
                    performance_data = {
                        "exit_price": float(latest_perf.exit_price) if latest_perf.exit_price else None,
                        "exit_reason": latest_perf.exit_reason,
                        "result": latest_perf.result,
                        "return_percent": float(latest_perf.return_percent) if latest_perf.return_percent else None,
                        "profit_usd": float(latest_perf.profit_usd) if latest_perf.profit_usd else None,
                        "duration_minutes": latest_perf.duration_minutes,
                        "tracked_at": latest_perf.tracked_at.isoformat() if latest_perf.tracked_at else None
                    }
                    perf_status = "completed"
                
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
                    "pdf_url": user_signal.pdf_url if user_signal else None,
                    "performance_status": perf_status,
                    "performance": performance_data
                })
            
            return jsonify({
                "signals": result,
                "count": len(result),
                "watchlist_count": len(watched_symbols)
            }), 200
            
    except Exception as e:
        print(f"Error fetching user signals with performance: {e}")
        traceback.print_exc()
        return jsonify({"error": "Failed to fetch signals"}), 500

# Add these routes to your application.py file

@application.route("/api/signals/performance/all", methods=["GET"])
def get_all_signal_performance():
    """
    Fetch ALL performance data from signal_performance table.
    Returns all completed signals regardless of watchlist.
    """
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        with get_session_context() as session:
            # Get total count
            total_count = session.query(SignalPerformance).count()
            
            # Fetch performance records with limit/offset
            performances = session.query(SignalPerformance).order_by(
                SignalPerformance.tracked_at.desc()
            ).limit(limit).offset(offset).all()
            
            if not performances:
                return jsonify({
                    "message": "No performance data found",
                    "data": [],
                    "pagination": {
                        "total": total_count,
                        "limit": limit,
                        "offset": offset,
                        "has_more": False
                    }
                }), 200

            result = []
            for perf in performances:
                # Join with Signal table to get symbol
                signal = session.query(Signal).filter_by(id=perf.signal_id).first()
                
                # Get entry price from signal payload
                entry_price = None
                created_at = None
                
                if signal:
                    if signal.payload and 'price' in signal.payload:
                        entry_price = float(signal.payload['price'])
                    elif signal.payload and 'risk' in signal.payload and 'entry_price' in signal.payload['risk']:
                        entry_price = float(signal.payload['risk']['entry_price'])
                    
                    # Get signal creation time
                    created_at = signal.created_at.isoformat() if signal.created_at else None
                
                result.append({
                    "performance_id": perf.id,
                    "signal_id": perf.signal_id,
                    "symbol": signal.symbol if signal else "UNKNOWN",
                    "entry_price": entry_price,  # FIX: Now properly extracted
                    "exit_price": float(perf.exit_price) if perf.exit_price else None,
                    "exit_reason": perf.exit_reason,  # TP / SL / TIME
                    "result": perf.result,  # SUCCESS / FAILURE
                    "return_percent": float(perf.return_percent) if perf.return_percent else None,
                    "profit_usd": float(perf.profit_usd) if perf.profit_usd else None,
                    "duration_minutes": perf.duration_minutes,
                    "tracked_at": perf.tracked_at.isoformat() if perf.tracked_at else None,
                    "created_at": created_at  # FIX: Added this field
                })

            return jsonify({
                "data": result,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total_count
                }
            }), 200

    except Exception as e:
        print(f"Error fetching all signal performance: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Add these UPDATED routes to your application.py file (replace the existing ones)

@application.route("/api/signals/performance/user/<user_sub>", methods=["GET"])
def get_user_signal_performance_direct(user_sub):
    """
    Fetch performance data for a specific user's signals.
    Includes timing data from the signals table.
    Does NOT depend on watchlist.
    """
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        with get_session_context() as session:
            # Get all signals created by/for this user
            user_signals = session.query(UserSignal).filter_by(
                user_sub=user_sub
            ).all()
            
            if not user_signals:
                return jsonify({
                    "message": "No signals found for this user",
                    "data": [],
                    "pagination": {
                        "total": 0,
                        "limit": limit,
                        "offset": offset,
                        "has_more": False
                    }
                }), 200
            
            signal_ids = [us.signal_id for us in user_signals]
            
            # Get performance records for these signals
            total_count = session.query(SignalPerformance).filter(
                SignalPerformance.signal_id.in_(signal_ids)
            ).count()
            
            performances = session.query(SignalPerformance).filter(
                SignalPerformance.signal_id.in_(signal_ids)
            ).order_by(
                SignalPerformance.tracked_at.desc()
            ).limit(limit).offset(offset).all()

            result = []
            for perf in performances:
                signal = session.query(Signal).filter_by(id=perf.signal_id).first()
                
                # Extract timing data from signal payload
                start_time = None
                end_time = None
                created_at = None  # ADD THIS LINE
                
                if signal and signal.payload:
                    timing = signal.payload.get('timing', {})
                    start_time = timing.get('start')
                    end_time = timing.get('end')
                
                # ADD THIS: Get created_at from Signal table
                if signal:
                    created_at = signal.created_at.isoformat() if signal.created_at else None
                
                result.append({
                    "performance_id": perf.id,
                    "signal_id": perf.signal_id,
                    "symbol": signal.symbol if signal else "UNKNOWN",
                    "entry_price": float(signal.payload.get("price")) if signal and signal.payload else None,
                    "exit_price": float(perf.exit_price) if perf.exit_price else None,
                    "exit_reason": perf.exit_reason,
                    "result": perf.result,
                    "return_percent": float(perf.return_percent) if perf.return_percent else None,
                    "profit_usd": float(perf.profit_usd) if perf.profit_usd else None,
                    "duration_minutes": perf.duration_minutes,
                    "tracked_at": perf.tracked_at.isoformat() if perf.tracked_at else None,
                    "start_time": start_time,
                    "end_time": end_time,
                    "created_at": created_at  # ADD THIS LINE
                })

            return jsonify({
                "data": result,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total_count
                }
            }), 200

    except Exception as e:
        print(f"Error fetching user signal performance: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@application.route("/api/signals/performance/stats/<user_sub>", methods=["GET"])
def get_user_performance_stats(user_sub):
    """
    Get aggregated performance statistics for a user.
    Calculate win rate, avg return, total P&L, etc.
    """
    try:
        with get_session_context() as session:
            # Get user's signals
            user_signals = session.query(UserSignal).filter_by(
                user_sub=user_sub
            ).all()
            
            if not user_signals:
                return jsonify({
                    "stats": {
                        "total_signals": 0,
                        "success_count": 0,
                        "failure_count": 0,
                        "pending_count": 0,
                        "win_rate": 0,
                        "avg_return": 0,
                        "total_profit": 0,
                        "total_loss": 0,
                        "net_pnl": 0,
                        "best_trade": 0,
                        "worst_trade": 0,
                        "avg_duration_minutes": 0
                    }
                }), 200
            
            signal_ids = [us.signal_id for us in user_signals]
            
            # Get all performances
            performances = session.query(SignalPerformance).filter(
                SignalPerformance.signal_id.in_(signal_ids)
            ).all()
            
            if not performances:
                return jsonify({
                    "stats": {
                        "total_signals": len(user_signals),
                        "success_count": 0,
                        "failure_count": 0,
                        "pending_count": len(user_signals),
                        "win_rate": 0,
                        "avg_return": 0,
                        "total_profit": 0,
                        "total_loss": 0,
                        "net_pnl": 0,
                        "best_trade": 0,
                        "worst_trade": 0,
                        "avg_duration_minutes": 0
                    }
                }), 200
            
            # Calculate statistics
            success_count = sum(1 for p in performances if p.result == "SUCCESS")
            failure_count = sum(1 for p in performances if p.result == "FAILURE")
            pending_count = len(user_signals) - len(performances)
            
            returns = [float(p.return_percent) if p.return_percent else 0 for p in performances]
            profits = [float(p.profit_usd) if p.profit_usd else 0 for p in performances]
            durations = [p.duration_minutes for p in performances if p.duration_minutes]
            
            win_rate = (success_count / len(performances) * 100) if performances else 0
            avg_return = sum(returns) / len(returns) if returns else 0
            total_profit = sum(p for p in profits if p > 0)
            total_loss = sum(abs(p) for p in profits if p < 0)
            net_pnl = total_profit - total_loss
            best_trade = max(returns) if returns else 0
            worst_trade = min(returns) if returns else 0
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            return jsonify({
                "stats": {
                    "total_signals": len(user_signals),
                    "completed_signals": len(performances),
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "pending_count": pending_count,
                    "win_rate": round(win_rate, 2),
                    "avg_return": round(avg_return, 2),
                    "total_profit": round(total_profit, 2),
                    "total_loss": round(total_loss, 2),
                    "net_pnl": round(net_pnl, 2),
                    "best_trade": round(best_trade, 2),
                    "worst_trade": round(worst_trade, 2),
                    "avg_duration_minutes": round(avg_duration, 2)
                }
            }), 200

    except Exception as e:
        print(f"Error fetching performance stats: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

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
    If PDF already exists, generate and return a fresh presigned URL.
    """
    try:
        with get_session_context() as session:
            user_signal = session.query(UserSignal).filter_by(id=user_signal_id).first()
            if not user_signal:
                return jsonify({"error": "UserSignal not found"}), 404

            # If already generated, return a fresh presigned URL
            if user_signal.pdf_status == "generated" and user_signal.pdf_url:
                # Extract S3 object key from the stored URL
                # Expected format: "https://bucket-name.s3.region.amazonaws.com/path/to/file.pdf"
                # or: "https://s3.region.amazonaws.com/bucket-name/path/to/file.pdf"
                
                s3_object_key = None
                
                # Try parsing format: https://bucket.s3.region.amazonaws.com/key
                if ".s3." in user_signal.pdf_url and ".amazonaws.com/" in user_signal.pdf_url:
                    s3_object_key = user_signal.pdf_url.split(".amazonaws.com/", 1)[1]
                # Try parsing format: https://s3.region.amazonaws.com/bucket/key
                elif "s3." in user_signal.pdf_url and ".amazonaws.com/" in user_signal.pdf_url:
                    parts = user_signal.pdf_url.split(".amazonaws.com/", 1)
                    if len(parts) == 2:
                        # Skip bucket name, get key
                        key_parts = parts[1].split("/", 1)
                        if len(key_parts) == 2:
                            s3_object_key = key_parts[1]
                
                if s3_object_key:
                    print(f"Generating fresh presigned URL for: {s3_object_key}")
                    fresh_url = generate_presigned_url(
                        'tradingsignals-pdfs', 
                        s3_object_key, 
                        expiration=3600  # 1 hour validity
                    )
                    
                    if fresh_url:
                        return jsonify({
                            "status": "generated",
                            "message": "PDF already exists, fresh URL generated",
                            "pdf_url": fresh_url
                        }), 200
                    else:
                        print(f"Failed to generate presigned URL for {s3_object_key}")
                        # Fall through to re-initiate generation
                else:
                    print(f"Could not parse S3 key from URL: {user_signal.pdf_url}")
                    # Fall through to re-initiate generation

            # If we reach here, either:
            # 1. PDF was never generated, OR
            # 2. PDF status is not "generated", OR
            # 3. Failed to generate fresh presigned URL
            # Solution: Initiate (or re-initiate) PDF generation
            
            user_signal.pdf_status = "initiated"
            user_signal.pdf_url = None
            session.add(user_signal)

        return jsonify({
            "status": "initiated",
            "message": "PDF generation initiated"
        }), 202

    except Exception as e:
        print(f"Error in request_pdf: {e}")
        traceback.print_exc()
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
    
# After this line:
register_subscription_routes(application)

# Add this debug code:
print("\n=== REGISTERED ROUTES ===")
for rule in application.url_map.iter_rules():
    print(f"{rule.endpoint}: {rule.rule} -> {list(rule.methods)}")
print("========================\n")

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5000)
