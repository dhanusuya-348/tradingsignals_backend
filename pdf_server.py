#pdf-server.py - updated
import os
import time
import threading
import traceback
import sys
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

# ============================================================
# ✅ ENV LOADER
# ============================================================
def load_env_file() -> bool:
    """Load environment variables from .env file"""
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print(f"[WARN] .env file not found at {env_file}", flush=True)
        return False
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key, value = key.strip(), value.strip()
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    if key not in os.environ:
                        os.environ[key] = value
        print(f"[INFO] Loaded environment variables from {env_file}", flush=True)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to load .env file: {e}", flush=True)
        return False


load_env_file()

from typing import Dict
import matplotlib
matplotlib.use('Agg')  # Avoid GUI issues

from flask import Flask, jsonify, request
from sqlalchemy import text

# Your algorithm imports
from algo.runner import generate_pdf_for_signal

# ✅ Use SQLAlchemy session instead of raw MySQL
from models import get_session

# ============================================================
# ✅ FLASK APP WITH MANUAL CORS
# ============================================================
app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    """Add CORS headers to all responses"""
    origin = request.headers.get('Origin')
    
    allowed_origins = [
        'https://dollaraptor.com',
        'http://localhost:3000',
        'https://signal.dollaraptor.com'
    ]
    
    if origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Max-Age'] = '3600'
    
    return response

# Add OPTIONS handler
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Handle CORS preflight"""
    return '', 204


# ============================================================
# ✅ PDF BACKGROUND WORKER - Processes ONE UserSignal at a time
# ============================================================
def pdf_worker_loop():
    """Continuously checks DB for initiated PDFs and generates them ONE AT A TIME"""
    print("[INFO] 🚀 PDF Worker thread started!", flush=True)
    
    while True:
        try:
            session = get_session()

            # ✅ Fetch ONE pending UserSignal row
            row = session.execute(
                text("""
                    SELECT id, signal_id, user_sub 
                    FROM user_signals 
                    WHERE pdf_status = 'initiated' 
                    LIMIT 1
                """)
            ).fetchone()

            if row:
                user_signal_id, signal_id, user_sub = row[0], row[1], row[2]
                print(f"\n[INFO] ⏳ Processing UserSignal ID: {user_signal_id}", flush=True)
                print(f"[INFO] Signal ID: {signal_id}, User: {user_sub}", flush=True)

                try:
                    # Generate PDF for this signal
                    result = generate_pdf_for_signal(str(signal_id))

                    if result.get("s3_url"):
                        pdf_url = result["s3_url"]

                        # ✅ Update ONLY this UserSignal row
                        session.execute(text("""
                            UPDATE user_signals
                            SET pdf_status = 'generated', pdf_url = :pdf_url
                            WHERE id = :user_signal_id
                        """), {"pdf_url": pdf_url, "user_signal_id": user_signal_id})
                        session.commit()

                        print(f"[SUCCESS] ✅ PDF generated for UserSignal ID {user_signal_id}", flush=True)
                        print(f"[SUCCESS] PDF URL: {pdf_url}", flush=True)

                    else:
                        error_msg = result.get('error', 'Unknown error')
                        print(f"[ERROR] ❌ PDF generation failed: {error_msg}", flush=True)
                        
                        session.execute(text("""
                            UPDATE user_signals
                            SET pdf_status = 'failed'
                            WHERE id = :user_signal_id
                        """), {"user_signal_id": user_signal_id})
                        session.commit()

                except Exception as e:
                    print(f"[ERROR] 💥 Exception during PDF generation: {e}", flush=True)
                    traceback.print_exc()
                    
                    try:
                        session.execute(text("""
                            UPDATE user_signals
                            SET pdf_status = 'failed'
                            WHERE id = :user_signal_id
                        """), {"user_signal_id": user_signal_id})
                        session.commit()
                    except Exception as db_err:
                        print(f"[ERROR] Failed to update DB: {db_err}", flush=True)
            else:
                print("[INFO] 😴 No pending PDFs, sleeping 60s...", flush=True)

            session.close()

        except Exception as e:
            print(f"[ERROR] Worker loop error: {e}", flush=True)
            traceback.print_exc()

        time.sleep(60)


# ============================================================
# ✅ API: Request PDF for specific user's signal
# ============================================================
def generate_presigned_url(bucket_name, object_key, expiration=3600):
    """Generate a fresh presigned URL for S3 object"""
    s3_client = boto3.client('s3')
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        print(f"[ERROR] Failed to generate presigned URL: {e}", flush=True)
        return None

# ============================================================
# ✅ API: Request PDF for specific user's signal (FIXED VERSION)
# ============================================================
@app.route("/api/user-signals/<user_sub>/<int:signal_id>/request-pdf", methods=["POST", "OPTIONS"])
def request_pdf_for_user_signal(user_sub, signal_id):
    """Initiate PDF generation for a specific user's signal"""
    
    if request.method == "OPTIONS":
        return "", 200
        
    try:
        session = get_session()
        
        print(f"\n[INFO] 📄 PDF Request received", flush=True)
        print(f"[INFO] user_sub: {user_sub}", flush=True)
        print(f"[INFO] signal_id: {signal_id}", flush=True)
        
        # ✅ Find UserSignal row for this user + signal
        user_signal = session.execute(text("""
            SELECT id, pdf_status, pdf_url FROM user_signals 
            WHERE user_sub = :user_sub AND signal_id = :signal_id
            LIMIT 1
        """), {"user_sub": user_sub, "signal_id": signal_id}).fetchone()
        
        if not user_signal:
            # Create new UserSignal if doesn't exist
            session.execute(text("""
                INSERT INTO user_signals (user_sub, signal_id, pdf_status, delivery_status, created_at)
                VALUES (:user_sub, :signal_id, 'initiated', 'sent', NOW())
            """), {"user_sub": user_sub, "signal_id": signal_id})
            session.commit()
            print(f"[INFO] ✨ Created new UserSignal row", flush=True)
            
            session.close()
            return jsonify({
                "status": "initiated",
                "message": "PDF generation initiated",
                "signal_id": signal_id,
                "estimated_time_minutes": 15
            }), 202
        
        user_signal_id, pdf_status, pdf_url = user_signal[0], user_signal[1], user_signal[2]
        
        # ✅ If already generated, return FRESH presigned URL
        if pdf_status == 'generated' and pdf_url:
            print(f"[INFO] PDF already exists in DB: {pdf_url}", flush=True)
            
            # Extract S3 object key from stored URL
            s3_object_key = None
            
            # Try parsing format: https://bucket.s3.region.amazonaws.com/key
            if ".s3." in pdf_url and ".amazonaws.com/" in pdf_url:
                s3_object_key = pdf_url.split(".amazonaws.com/", 1)[1]
                # Remove query parameters if present
                if "?" in s3_object_key:
                    s3_object_key = s3_object_key.split("?")[0]
            
            if s3_object_key:
                print(f"[INFO] 🔄 Generating fresh presigned URL for: {s3_object_key}", flush=True)
                fresh_url = generate_presigned_url(
                    'tradingsignals-pdfs', 
                    s3_object_key, 
                    expiration=3600  # 1 hour validity
                )
                
                if fresh_url:
                    print(f"[SUCCESS] ✅ Fresh presigned URL generated", flush=True)
                    session.close()
                    return jsonify({
                        "status": "generated",
                        "message": "PDF already exists, fresh URL generated",
                        "pdf_url": fresh_url
                    }), 200
                else:
                    print(f"[WARN] Failed to generate presigned URL, will re-initiate", flush=True)
            else:
                print(f"[WARN] Could not parse S3 key from URL: {pdf_url}", flush=True)
        
        # If we reach here: PDF not generated OR failed to get fresh URL
        # Set to 'initiated' to trigger regeneration
        session.execute(text("""
            UPDATE user_signals
            SET pdf_status = 'initiated', pdf_url = NULL
            WHERE id = :user_signal_id
        """), {"user_signal_id": user_signal_id})
        session.commit()
        
        print(f"[INFO] ✅ Set pdf_status='initiated' for UserSignal ID {user_signal_id}", flush=True)
        
        session.close()
        
        return jsonify({
            "status": "initiated",
            "message": "PDF generation initiated",
            "signal_id": signal_id,
            "estimated_time_minutes": 15
        }), 202
        
    except Exception as e:
        print(f"[ERROR] Failed to process PDF request: {e}", flush=True)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ============================================================
# ✅ HEALTH CHECK
# ============================================================
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy", 
        "service": "pdf-server",
        "port": 8001
    }), 200


# ============================================================
# ✅ MAIN ENTRY POINT
# ============================================================
if __name__ == "__main__":
    import threading
    import sys
    import traceback

    print(f"[INFO] 🔥 Starting PDF Server (Python {sys.version})", flush=True)

    try:
        # Start the background worker thread
        worker = threading.Thread(target=pdf_worker_loop, daemon=True)
        worker.start()
        print(f"[INFO] ✅ PDF Worker thread started (daemon mode)", flush=True)

        # Start the Flask API server
        app.run(host="0.0.0.0", port=8001)

    except Exception as e:
        print(f"[ERROR] PDF server failed to start: {e}", flush=True)
        traceback.print_exc()

