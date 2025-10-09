#pdf-server.py
import os
import time
import threading
import traceback
import sys
from pathlib import Path

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
        'https://main.d2lu8gx2f335fg.amplifyapp.com',
        'http://localhost:3000'
    ]
    
    if origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Max-Age'] = '3600'
    
    return response


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
                "message": "PDF generation initiated",
                "signal_id": signal_id,
                "estimated_time_minutes": 15
            }), 202
        
        user_signal_id, pdf_status, pdf_url = user_signal[0], user_signal[1], user_signal[2]
        
        # If already generated, return URL
        if pdf_status == 'generated' and pdf_url:
            print(f"[INFO] PDF already exists: {pdf_url}", flush=True)
            session.close()
            return jsonify({
                "message": "PDF already generated",
                "pdf_url": pdf_url
            }), 200
        
        # Set to 'initiated'
        session.execute(text("""
            UPDATE user_signals
            SET pdf_status = 'initiated'
            WHERE id = :user_signal_id
        """), {"user_signal_id": user_signal_id})
        session.commit()
        
        print(f"[INFO] ✅ Set pdf_status='initiated' for UserSignal ID {user_signal_id}", flush=True)
        
        session.close()
        
        return jsonify({
            "message": "PDF generation initiated",
            "signal_id": signal_id,
            "estimated_time_minutes": 15
        }), 202
        
    except Exception as e:
        print(f"[ERROR] Failed to initiate PDF: {e}", flush=True)
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
    print("\n" + "="*60, flush=True)
    print("[INFO] 🔥 PDF SERVER STARTING", flush=True)
    print("="*60, flush=True)
    print(f"[INFO] Python: {sys.version}", flush=True)
    print(f"[INFO] Working Dir: {os.getcwd()}", flush=True)
    print(f"[INFO] Port: 8001", flush=True)
    print("="*60 + "\n", flush=True)

    # Start background worker
    worker = threading.Thread(target=pdf_worker_loop, daemon=True)
    worker.start()
    print(f"[INFO] ✅ Worker thread alive: {worker.is_alive()}\n", flush=True)

    # Start Flask
    app.run(host="0.0.0.0", port=8001, debug=False)

# # pdf_server.py
# import os
# from pathlib import Path

# # -----------------------------
# # ✅ ENV LOADER
# # -----------------------------
# def load_env_file() -> bool:
#     """Load environment variables from .env file"""
#     env_file = Path(__file__).parent / '.env'
#     if not env_file.exists():
#         print(f"[WARN] .env file not found at {env_file}")
#         return False
#     try:
#         with open(env_file, 'r', encoding='utf-8') as f:
#             for line in f:
#                 line = line.strip()
#                 if not line or line.startswith('#'):
#                     continue
#                 if '=' in line:
#                     key, value = line.split('=', 1)
#                     key = key.strip()
#                     value = value.strip()
#                     if value.startswith('"') and value.endswith('"'):
#                         value = value[1:-1]
#                     elif value.startswith("'") and value.endswith("'"):
#                         value = value[1:-1]
#                     if key not in os.environ:
#                         os.environ[key] = value
#         print(f"[INFO] Loaded environment variables from {env_file}")
#         return True
#     except Exception as e:
#         print(f"[ERROR] Failed to load .env file: {e}")
#         return False

# load_env_file()


# import traceback
# from typing import Dict
# from flask import Flask, jsonify, request
# from flask_cors import CORS
# from algo.runner import generate_pdf_report_full, generate_pdf_for_signal


# # -----------------------------
# # ✅ MATPLOTLIB CONFIG
# # -----------------------------
# import matplotlib
# matplotlib.use('Agg')  # Avoid GUI issues

# # -----------------------------
# # ✅ FLASK APP
# # -----------------------------
# app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "*"}})

# # -----------------------------
# # ✅ ENDPOINT: Generate PDF for specific signal
# # -----------------------------
# @app.route("/generate-pdf", methods=["POST"])
# def generate_pdf() -> Dict:
#     try:
#         signal_id = request.args.get("signal_id")
#         if not signal_id:
#             return jsonify({"error": "signal_id parameter is required"}), 400

#         print(f"[INFO] Starting PDF generation for signal_id: {signal_id}")
#         result = generate_pdf_for_signal(signal_id)

#         if "error" in result:
#             print(f"[ERROR] PDF generation failed: {result['error']}")
#             return jsonify({"error": result["error"]}), 500

#         s3_url = result.get("s3_url")
#         if not s3_url:
#             print(f"[WARN] PDF generated but failed to upload to S3")
#             return jsonify({"error": "PDF generated but S3 upload failed"}), 500

#         print(f"[SUCCESS] PDF successfully generated and uploaded to S3: {s3_url}")
#         return jsonify({
#             "signal_id": signal_id,
#             "s3_url": s3_url,
#             "signal_info": result.get("signal")
#         })

#     except Exception as e:
#         print(f"[ERROR] Exception in generate_pdf endpoint: {e}")
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

# # -----------------------------
# # ✅ LEGACY ENDPOINT: Generate PDF for a symbol (live signal)
# # -----------------------------
# @app.route("/download-pdf/<symbol>")
# def download_pdf(symbol: str) -> Dict:
#     try:
#         print(f"[INFO] Legacy endpoint called for symbol: {symbol}")
#         result = generate_pdf_report_full(symbol)

#         if "error" in result:
#             print(f"[ERROR] PDF generation failed for symbol {symbol}: {result['error']}")
#             return jsonify({"error": result["error"]}), 500

#         s3_url = result.get("s3_url")
#         if not s3_url:
#             print(f"[WARN] PDF generated but failed to upload to S3")
#             return jsonify({"error": "PDF generated but S3 upload failed"}), 500

#         print(f"[SUCCESS] PDF successfully generated and uploaded to S3: {s3_url}")
#         return jsonify({
#             "symbol": symbol,
#             "s3_url": s3_url,
#             "signal_info": result.get("signal")
#         })

#     except Exception as e:
#         print(f"[ERROR] Exception in download_pdf endpoint: {e}")
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500

# # -----------------------------
# # ✅ MAIN
# # -----------------------------
# if __name__ == "__main__":
#     print("[INFO] Starting PDF server...")

#     # ---------- TEMP TEST: PDF generation ----------
#     test_signal_id = "701"  # Replace with a valid signal ID
#     try:
#         print(f"[INFO] Testing PDF generation for signal_id: {test_signal_id}")
#         result = generate_pdf_for_signal(test_signal_id)
#         if "s3_url" in result and result["s3_url"]:
#             print(f"[SUCCESS] PDF successfully uploaded to S3: {result['s3_url']}")
#         else:
#             print(f"[FAIL] PDF generation/upload failed: {result.get('error', 'Unknown error')}")
#     except Exception as e:
#         print(f"[ERROR] Exception during test PDF generation: {e}")
#         traceback.print_exc()
#     # ---------- END TEMP TEST ----------

#     app.run(host="0.0.0.0", port=8001)

