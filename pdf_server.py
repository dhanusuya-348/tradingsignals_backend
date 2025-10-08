# pdf_server.py
import os
import time
import threading
import traceback
from pathlib import Path
from typing import Dict
import matplotlib
matplotlib.use('Agg')  # Avoid GUI issues
from flask import Flask, jsonify, request
from flask_cors import CORS
from algo.runner import generate_pdf_report_full, generate_pdf_for_signal

# ✅ DB utils (import your existing DB connection helper)
from db import get_db_connection  # make sure this exists in your project


# -----------------------------
# ✅ ENV LOADER
# -----------------------------
def load_env_file() -> bool:
    """Load environment variables from .env file"""
    env_file = Path(__file__).parent / '.env'
    if not env_file.exists():
        print(f"[WARN] .env file not found at {env_file}")
        return False
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    if key not in os.environ:
                        os.environ[key] = value
        print(f"[INFO] Loaded environment variables from {env_file}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to load .env file: {e}")
        return False

load_env_file()


# -----------------------------
# ✅ FLASK APP
# -----------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


# -----------------------------
# ✅ PDF BACKGROUND WORKER (runs every 1 minute)
# -----------------------------
def pdf_worker_loop():
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Fetch all signals that need PDF generation
            cursor.execute("SELECT signal_id FROM user_signals WHERE pdf_status = 'initiated'")
            rows = cursor.fetchall()

            if rows:
                print(f"[INFO] Found {len(rows)} pending PDFs to generate")

            for row in rows:
                signal_id = str(row["signal_id"])
                print(f"[INFO] Generating PDF for signal_id: {signal_id}")

                try:
                    result = generate_pdf_for_signal(signal_id)

                    if result.get("s3_url"):
                        pdf_url = result["s3_url"]
                        # Update DB with generated PDF URL
                        cursor.execute("""
                            UPDATE user_signals
                            SET pdf_status = 'generated', pdf_url = %s
                            WHERE signal_id = %s
                        """, (pdf_url, signal_id))
                        conn.commit()
                        print(f"[SUCCESS] PDF generated and uploaded for signal_id {signal_id}")
                    else:
                        print(f"[ERROR] PDF generation failed for signal_id {signal_id}: {result.get('error')}")

                except Exception as e:
                    print(f"[ERROR] Exception during PDF generation for signal_id {signal_id}: {e}")
                    traceback.print_exc()

            cursor.close()
            conn.close()

        except Exception as e:
            print(f"[ERROR] PDF worker loop failed: {e}")
            traceback.print_exc()

        # Sleep for 1 minute before next check
        time.sleep(60)


# -----------------------------
# ✅ ENDPOINT: Generate PDF for specific signal (manual trigger)
# -----------------------------
@app.route("/generate-pdf", methods=["POST"])
def generate_pdf() -> Dict:
    try:
        signal_id = request.args.get("signal_id")
        if not signal_id:
            return jsonify({"error": "signal_id parameter is required"}), 400

        print(f"[INFO] Starting manual PDF generation for signal_id: {signal_id}")
        result = generate_pdf_for_signal(signal_id)

        if "error" in result:
            print(f"[ERROR] PDF generation failed: {result['error']}")
            return jsonify({"error": result["error"]}), 500

        s3_url = result.get("s3_url")
        if not s3_url:
            print(f"[WARN] PDF generated but failed to upload to S3")
            return jsonify({"error": "PDF generated but S3 upload failed"}), 500

        print(f"[SUCCESS] PDF successfully generated and uploaded to S3: {s3_url}")
        return jsonify({
            "signal_id": signal_id,
            "s3_url": s3_url,
            "signal_info": result.get("signal")
        })

    except Exception as e:
        print(f"[ERROR] Exception in /generate-pdf: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# ✅ LEGACY ENDPOINT: Generate PDF for symbol (for live signal)
# -----------------------------
@app.route("/download-pdf/<symbol>")
def download_pdf(symbol: str) -> Dict:
    try:
        print(f"[INFO] Legacy endpoint called for symbol: {symbol}")
        result = generate_pdf_report_full(symbol)

        if "error" in result:
            print(f"[ERROR] PDF generation failed for symbol {symbol}: {result['error']}")
            return jsonify({"error": result["error"]}), 500

        s3_url = result.get("s3_url")
        if not s3_url:
            print(f"[WARN] PDF generated but failed to upload to S3")
            return jsonify({"error": "PDF generated but S3 upload failed"}), 500

        print(f"[SUCCESS] PDF successfully generated and uploaded to S3: {s3_url}")
        return jsonify({
            "symbol": symbol,
            "s3_url": s3_url,
            "signal_info": result.get("signal")
        })

    except Exception as e:
        print(f"[ERROR] Exception in /download-pdf: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# ✅ MAIN ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    print("[INFO] Starting PDF server...")

    # Start background PDF worker thread
    threading.Thread(target=pdf_worker_loop, daemon=True).start()

    app.run(host="0.0.0.0", port=8001)


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

